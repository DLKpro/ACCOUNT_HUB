# Design 03 — Vault

> Ground-up design #3, the centerpiece. Depends on: design 01 (workspace + `core::vault`
> module home), design 02 (`SecretStore` supplies the KEK). Feeds: design 04 (OAuth tokens
> land in the vault), design 05 (IPC commands read/write vault rows). Threat model: assets
> A1 (KEK), A2 (OAuth tokens), A5 (discovered-account catalog).

## Purpose

Give the Rust core a single, local, encrypted store for every piece of per-user persistent
state: linked email accounts, in-flight OAuth state, scan sessions, discovered accounts,
closure requests. Encryption must be strong enough to justify the "1Password-class" posture
the threat model commits to, and the vault must be safe to open from two processes
simultaneously (GUI + CLI).

Non-goals:

- Sync across devices. Explicitly out of scope (refined plan, remaining open question).
- Storing the master password or an auth tag on disk. Only a SQLCipher-encrypted DB + the
  OS-keychain-held KEK (design 02).
- Per-column encryption on top of SQLCipher. The whole-file AES-256 is the answer; layering
  more crypto adds complexity without a corresponding threat.

## Architecture at a glance

```
     crates/core/src/session.rs                  crates/core/src/keychain/
     ┌─────────────────────┐                     ┌──────────────────────┐
     │ LockedSession       │                     │ SecretStore          │
     │  - master password  │─────argon2id──────▶ │   VAULT_KEK  ◀──────┐│
     │                     │                     │                      ││
     │ unlock() ──────────────┐                  └──────────────────────┘│
     └─────────────────────┘  │                                          │
                              │ on success: kek: SecretValue             │
                              ▼                                          │
     crates/core/src/vault/                                               │
     ┌───────────────────────────────────────────────┐                   │
     │ Vault                                         │                   │
     │   conn: Arc<Mutex<rusqlite::Connection>>     │                   │
     │   lock_file: fs2::FileExt                    │                   │
     │                                               │                   │
     │ PRAGMA key = x'<kek>';  ─────────────────────────────────────────┘
     │ PRAGMA journal_mode = WAL;                    │
     │ PRAGMA cipher_memory_security = ON;           │
     │                                               │
     │ refinery migrations (V0001__initial.sql, ...) │
     │                                               │
     │   async fn add_linked_email(...)              │
     │   async fn consume_oauth_state(...)           │  ← all ops go via
     │   async fn list_discoveries(...)              │    tokio::task::spawn_blocking
     │   async fn rekey(new_kek)                     │
     │   async fn close(self)                        │
     └───────────────────────────────────────────────┘
                              │
                              ▼
     Platform data dir:
       macOS:   ~/Library/Application Support/AccountHub/vault.db
       Windows: %APPDATA%\AccountHub\vault.db
       Linux:   $XDG_DATA_HOME/AccountHub/vault.db  (or ~/.local/share/AccountHub/vault.db)
```

## Schema

Initial migration (`crates/core/migrations/V0001__initial.sql`). Five tables survive from
the Python schema; three auth-only tables (`user`, `email_verification_token`,
`password_reset_token`) are dropped entirely because master-password unlock replaces their
reason for existing.

```sql
-- V0001__initial.sql
-- Initial vault schema.
--
-- Conventions:
--   - Primary keys are INTEGER AUTOINCREMENT (SQLite rowid-based; stable across rewrites).
--   - Timestamps are INTEGER unix seconds. No TEXT dates. Makes arithmetic trivial.
--   - Single-user vault: no user_id columns. The vault IS the user scope.
--   - All on-disk token fields are TEXT (plaintext inside the SQLCipher envelope).
--   - Booleans are INTEGER 0/1 (SQLite convention; rusqlite serde handles it).

PRAGMA foreign_keys = ON;

CREATE TABLE linked_email (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    email             TEXT NOT NULL UNIQUE,
    provider          TEXT NOT NULL CHECK (provider IN ('google', 'microsoft', 'apple', 'meta')),
    provider_user_id  TEXT,
    access_token      TEXT,
    refresh_token     TEXT,
    token_expires_at  INTEGER,              -- unix seconds; NULL = no expiry known
    scopes            TEXT,                 -- JSON array of granted scope strings
    is_verified       INTEGER NOT NULL DEFAULT 0 CHECK (is_verified IN (0, 1)),
    created_at        INTEGER NOT NULL,
    updated_at        INTEGER NOT NULL
);

CREATE TABLE oauth_state (
    state             TEXT PRIMARY KEY,     -- opaque random bytes, b64url-encoded
    provider          TEXT NOT NULL,
    code_verifier     TEXT NOT NULL,        -- PKCE (RFC 7636)
    nonce             TEXT,                 -- OIDC nonce (NULL for non-OIDC providers)
    loopback_port     INTEGER,              -- port the loopback server bound to (Apple state routing)
    created_at        INTEGER NOT NULL,
    expires_at        INTEGER NOT NULL      -- ~10 min after created_at
);

CREATE TABLE scan_session (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    status            TEXT NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    emails_scanned    INTEGER NOT NULL DEFAULT 0,
    accounts_found    INTEGER NOT NULL DEFAULT 0,
    error_message     TEXT,                 -- populated on 'failed'
    started_at        INTEGER NOT NULL,
    completed_at      INTEGER                -- NULL while running
);

CREATE TABLE discovered_account (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_session_id   INTEGER NOT NULL REFERENCES scan_session(id) ON DELETE CASCADE,
    linked_email_id   INTEGER REFERENCES linked_email(id) ON DELETE SET NULL,
    email             TEXT NOT NULL,
    service_name      TEXT NOT NULL,
    source            TEXT NOT NULL CHECK (source IN ('oauth_profile', 'hibp', 'scanner')),
    confidence        REAL CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
    breach_date       INTEGER,              -- unix seconds; only populated for hibp-sourced rows
    created_at        INTEGER NOT NULL
);

CREATE TABLE closure_request (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    discovered_account_id INTEGER REFERENCES discovered_account(id) ON DELETE SET NULL,
    service_name      TEXT NOT NULL,
    method            TEXT NOT NULL CHECK (method IN ('api', 'web_link', 'email_request', 'manual')),
    status            TEXT NOT NULL CHECK (status IN ('pending', 'in_progress', 'completed', 'failed')),
    deletion_url      TEXT,
    notes             TEXT,                 -- user-entered; freeform
    created_at        INTEGER NOT NULL,
    completed_at      INTEGER
);

-- Indexes
CREATE INDEX idx_oauth_state_expires     ON oauth_state(expires_at);     -- scheduled pruning
CREATE INDEX idx_discovered_account_scan ON discovered_account(scan_session_id);
CREATE INDEX idx_discovered_account_linked_email ON discovered_account(linked_email_id);
CREATE INDEX idx_closure_request_status  ON closure_request(status);
CREATE INDEX idx_linked_email_provider   ON linked_email(provider);
```

### Column choices worth flagging

- **`access_token` and `refresh_token` as plaintext TEXT** — no per-column encryption.
  SQLCipher encrypts the whole file; adding a second layer would complicate the schema with
  no meaningful threat increment (if the attacker has the KEK and the file, they have everything).
- **`provider` has a CHECK constraint** listing the four known providers. Adding a fifth
  requires a migration, which is exactly the review friction we want for a security-adjacent
  change.
- **`loopback_port` in `oauth_state`** is new (not in the current Python schema). The Apple
  Worker relay encodes the port in OAuth `state` ([account_hub/services/oauth_service.py:79-80](../../account_hub/services/oauth_service.py)),
  but the state field itself is opaque random — storing the port as a separate column means
  we can surface it in diagnostics without parsing the encoded state.
- **`discovered_account.linked_email_id`** is `ON DELETE SET NULL`, not cascade. Unlinking
  an email shouldn't silently discard past discoveries; the history survives with a null pointer.
- **`closure_request.discovered_account_id`** same logic: a closure completed successfully
  shouldn't disappear if its source row later gets scrubbed.

### Why no users table, no sessions table, no audit log

- **No users:** the vault IS one user. A second user gets their own vault file and keychain
  entry (separate OS account). No session concept at rest.
- **No sessions table:** session state (unlocked vs. locked, idle timer) is in-memory only.
  Killing the app re-locks. Intentional.
- **No audit log:** personal tool; user == sole actor. Adding an append-only audit log is
  future work if compliance ever demands it, but YAGNI for v1.

## KEK lifecycle

Callers: `session.rs` orchestrates; the vault receives a KEK and doesn't know where it came from.

```
                                       ┌──────────────────────────────┐
                                       │ SecretStore::exists(         │
                                       │   SecretKey::VAULT_KEK)?     │
                                       └──────────────┬───────────────┘
                         false (first launch)         │  true (cached)
                 ┌───────────────────────────────┐    │
                 │ prompt("Create master pw")    │    │ biometric?
                 │   → argon2id → kek            │    │   (optional, v1.1)
                 │ SecretStore::set(VAULT_KEK,   │    │
                 │   kek)                        │    ▼
                 └──────────────┬────────────────┘    kek = SecretStore::get(...)
                                │                     │
                                ▼                     ▼
                     Vault::create(path, kek)   Vault::open(path, kek)
                                │                     │
                                ▼                     ▼
                     run migrations V0001..N   run pending migrations (if any)
                                │                     │
                                └──────────┬──────────┘
                                           ▼
                                  wrap in UnlockedSession
                                       (kek drops when
                                        session drops)
```

### Rekey (change master password)

```rust
impl Vault {
    /// Rotate the SQLCipher key. Callers pass the new KEK derived from the new master password.
    /// The caller is responsible for updating the keychain entry AFTER this returns Ok —
    /// not before, so a failure leaves the vault unlockable with the old key.
    pub async fn rekey(&self, new_kek: SecretValue) -> Result<()> {
        // Acquires the exclusive fs2 lock for the duration.
        // Issues `PRAGMA rekey = "x'<hex>'"`.
        // On error, returns without touching the keychain.
    }
}
```

Sequence for a successful master-password change:
1. Prompt user for old password.
2. Derive `kek_old` via Argon2id; verify by opening the vault with it.
3. Prompt user for new password (twice, for confirmation).
4. Derive `kek_new` via Argon2id.
5. `vault.rekey(kek_new).await?` — atomic rewrite via SQLCipher.
6. `secret_store.set(VAULT_KEK, kek_new).await?` — update keychain LAST.
7. Zeroize both KEKs.

If step 5 fails, the vault is still encrypted with `kek_old`; the keychain still holds `kek_old`;
the user experiences an error, nothing is lost. If step 6 fails, the vault is encrypted with
`kek_new` but the keychain holds `kek_old` — a stuck state. Mitigation: write step 6 as a
retry loop with a user-visible error instructing to retry or re-derive.

### Wipe

`Vault::wipe(path)` is a static fn: close any open connections, unlink the file, unlink WAL
and SHM sidecars (`vault.db-wal`, `vault.db-shm`). Separately, `SecretStore::delete(VAULT_KEK)`.
Wipe is irreversible and the UI makes that clear.

## SQLCipher configuration

On open, after setting the key:

```
PRAGMA key = "x'<hex-encoded 32-byte KEK>'";
PRAGMA cipher_memory_security = ON;    -- zero memory on page discard; required for our posture
PRAGMA journal_mode = WAL;             -- concurrent readers, crash-safety
PRAGMA synchronous = NORMAL;           -- WAL-friendly fsync level
PRAGMA foreign_keys = ON;              -- CHECK constraints + FK enforcement on every connection
PRAGMA cipher_page_size = 4096;        -- SQLCipher 4 default; stated for future-proofing
PRAGMA kdf_iter = 256000;              -- SQLCipher 4 default; uses PBKDF2 internally to derive
                                       -- the actual DB key from our KEK. Redundant-ish given we
                                       -- already Argon2id the password, but cheap and layered.
```

**Caveat on `kdf_iter`:** SQLCipher runs PBKDF2-HMAC-SHA512 on top of the key we supply, to
produce the actual page cipher key. If we pass a raw 32-byte KEK via `x'...'` hex syntax, the
KDF is bypassed and the key is used directly. This is the intended behavior for a KEK that's
already the output of a strong KDF (our Argon2id). Confirmed in SQLCipher docs; documented
here so no reviewer "fixes" the kdf_iter line on the assumption it does something.

## Multi-process safety

GUI and CLI may open the vault simultaneously. SQLite's own locking + WAL makes this safe for
ordinary reads and writes. We add two things on top:

### 1. `fs2` advisory file lock on write-critical operations

```rust
use fs2::FileExt;

impl Vault {
    async fn with_exclusive_lock<F, R>(&self, f: F) -> Result<R>
    where
        F: FnOnce(&Connection) -> Result<R> + Send + 'static,
        R: Send + 'static,
    {
        let lock_file = self.lock_file.clone();
        tokio::task::spawn_blocking(move || {
            lock_file.lock_exclusive()?;  // blocks other writers
            // run f...
            lock_file.unlock()?;
        }).await?
    }
}
```

Scope: schema migration, rekey, `VACUUM`. Normal queries use SQLite's built-in locking (WAL
shared-lock model).

### 2. Migration fence

On startup, each process runs `refinery` migrations. `refinery` uses its own metadata table
(`refinery_schema_history`) under an exclusive DB lock, so two processes can't both migrate
simultaneously. But two processes CAN race on the file-system open — we mitigate by:

1. Opening the DB file with `OpenFlags::SQLITE_OPEN_CREATE | SQLITE_OPEN_READ_WRITE`.
2. Acquiring the `fs2` exclusive lock.
3. Running migrations under the lock.
4. Releasing the lock; switching to shared-mode access thereafter.

A process that comes up while another is migrating waits on the lock (up to a timeout), then
checks if migrations already ran and no-ops.

## Async integration

`rusqlite` is sync; our public vault API is async. Bridge with `tokio::task::spawn_blocking`:

```rust
pub struct Vault {
    inner: Arc<VaultInner>,
}

struct VaultInner {
    conn: Mutex<rusqlite::Connection>,   // parking_lot::Mutex, not tokio
    lock_file: File,
    config: VaultConfig,
}

impl Vault {
    pub async fn list_linked_emails(&self) -> Result<Vec<LinkedEmail>> {
        let inner = Arc::clone(&self.inner);
        tokio::task::spawn_blocking(move || {
            let conn = inner.conn.lock();
            let mut stmt = conn.prepare_cached("SELECT ... FROM linked_email ORDER BY created_at")?;
            // ...
        })
        .await
        .map_err(|e| Error::from(e))?
    }
}
```

Design choices:

- **`parking_lot::Mutex` (not `tokio::sync::Mutex`).** Within a `spawn_blocking` closure, we're
  on a blocking thread; an async mutex would be wrong. Parking-lot is faster and doesn't
  require `.await`.
- **Single connection per `Vault` instance.** SQLite is serializable anyway; a connection pool
  would add overhead without throughput gains for our QPS (low, single-user).
- **`prepare_cached` for every statement.** rusqlite caches prepared statements per connection;
  no parser overhead after the first call.

## Public API shape

```rust
// crates/core/src/vault/mod.rs (sketch — full shape comes with implementation)

pub struct Vault { /* ... */ }

pub struct VaultConfig {
    pub db_path: PathBuf,
    pub lock_path: PathBuf,       // typically db_path with ".lock" suffix
    pub migration_timeout: Duration,
}

impl Default for VaultConfig {
    fn default() -> Self {
        let data_dir = platform_data_dir();  // dirs::data_dir() + "AccountHub"
        Self {
            db_path: data_dir.join("vault.db"),
            lock_path: data_dir.join("vault.db.lock"),
            migration_timeout: Duration::from_secs(30),
        }
    }
}

impl Vault {
    /// Open existing or create new. Runs pending migrations under the exclusive lock.
    pub async fn open(config: VaultConfig, kek: SecretValue) -> Result<Self>;

    /// Rotate the SQLCipher key. See KEK lifecycle.
    pub async fn rekey(&self, new_kek: SecretValue) -> Result<()>;

    /// Close gracefully. Flushes WAL, releases locks, zeroizes the cached KEK.
    pub async fn close(self) -> Result<()>;

    /// Static wipe. Removes vault.db, vault.db-wal, vault.db-shm. Does NOT touch the keychain.
    pub fn wipe(config: &VaultConfig) -> Result<()>;

    // --- linked_email ---
    pub async fn add_linked_email(&self, req: NewLinkedEmail) -> Result<LinkedEmail>;
    pub async fn list_linked_emails(&self) -> Result<Vec<LinkedEmail>>;
    pub async fn get_linked_email(&self, id: i64) -> Result<Option<LinkedEmail>>;
    pub async fn update_tokens(&self, id: i64, tokens: TokenSet) -> Result<()>;
    pub async fn remove_linked_email(&self, id: i64) -> Result<()>;

    // --- oauth_state ---
    pub async fn insert_oauth_state(&self, state: NewOAuthState) -> Result<()>;
    pub async fn consume_oauth_state(&self, state: &str) -> Result<OAuthState>;  // removes on success
    pub async fn prune_expired_oauth_states(&self) -> Result<usize>;

    // --- scan_session ---
    pub async fn start_scan_session(&self) -> Result<ScanSession>;
    pub async fn update_scan_session(&self, id: i64, update: ScanSessionUpdate) -> Result<()>;
    pub async fn list_scan_sessions(&self, limit: usize) -> Result<Vec<ScanSession>>;

    // --- discovered_account ---
    pub async fn record_discovery(&self, req: NewDiscoveredAccount) -> Result<DiscoveredAccount>;
    pub async fn list_discoveries(&self, scan_id: i64) -> Result<Vec<DiscoveredAccount>>;

    // --- closure_request ---
    pub async fn submit_closure_request(&self, req: NewClosureRequest) -> Result<ClosureRequest>;
    pub async fn list_closure_requests(&self, status: Option<ClosureStatus>) -> Result<Vec<ClosureRequest>>;
    pub async fn update_closure_status(&self, id: i64, status: ClosureStatus) -> Result<()>;
}
```

### Sensitive data in memory

`TokenSet`, `LinkedEmail.access_token`, and similar carriers of secret material use a
`SecretString` wrapper (backed by `zeroize::Zeroizing<String>`) rather than plain `String`.
The `Debug` impl redacts. The vault internally unwraps these right before `rusqlite::params!`
— the window of raw-string exposure is measured in microseconds.

```rust
#[derive(Clone)]
pub struct SecretString(Zeroizing<String>);

impl std::fmt::Debug for SecretString {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "SecretString(<redacted, {} chars>)", self.0.len())
    }
}
```

This mirrors the `SecretValue` pattern from design 02. Same discipline, different domain:
`SecretValue` is for keychain byte buffers, `SecretString` is for token strings pulled from
the vault.

## Auto-lock on idle

Owned by `session.rs`, not by the vault. Sketch of the interaction:

```rust
impl UnlockedSession {
    pub fn touch(&self) { /* reset idle timer */ }

    async fn idle_task(self: Arc<Self>) {
        loop {
            tokio::time::sleep(IDLE_CHECK_INTERVAL).await;
            if self.is_idle_beyond_limit() {
                self.lock().await;   // drops the Vault, which zeroizes its cached kek
                break;
            }
        }
    }
}
```

The vault exposes `close()` but no timer-of-its-own. Separation of concerns: the vault is
storage; the session is policy.

## Testing strategy

Per `docs/quality-gates.md §3`:

- **Unit tests** inside each query function: round-trip an insert/select, verify `expires_at`
  filters, CHECK constraints rejected bad inputs, ON DELETE SET NULL/CASCADE semantics.
- **Integration tests** under `crates/core/tests/vault_integration.rs`:
  - Create vault → insert linked email → reopen → read back. Verifies persistence survives
    close/reopen.
  - Wrong KEK → `Vault::open` returns `Error::InvalidKek` (mapping SQLCipher's "file is not
    a database"). Critical negative test.
  - Rekey happy path + rekey failure (simulated I/O error) leaves vault readable with old key.
  - Two processes: spawn a second process via `std::process::Command` that also opens the
    vault; verify concurrent reads work, writes serialize. (Skipped in CI if `fs2`-level lock
    behavior diverges on Windows runners; mark `#[ignore]` with a note.)
- **Property tests** (`proptest`):
  - Arbitrary `NewLinkedEmail` → round-trip through vault, compare fields. Catches
    serialization regressions.
  - Arbitrary byte sequences → `SecretString` round-trip → zeroized on drop.
- **Fuzz** (`cargo-fuzz`) on `consume_oauth_state`: arbitrary byte input as the `state` param,
  must never panic, must never succeed with a non-matching state. The production attack surface.

Test fixtures: `crates/core/src/vault/test_utils.rs` (behind `test-utils` feature) exposes
`InMemoryVault::new()` that opens SQLCipher with `:memory:` and a random KEK. Used by the
OAuth module's tests without needing a real disk file.

## What to delete when this module lands (Phase 2)

- `account_hub/db/` — retired (Python SQLAlchemy models + Alembic migrations).
- `account_hub/security/encryption.py` — Fernet-on-tokens replaced by SQLCipher-on-file.
- The Postgres sidecar in `docker-compose.yml` — irrelevant once the vault is the DB.

(Actual deletions happen in Phase 3 when the Python sidecar retires entirely. Phase 2 only
introduces the Rust vault alongside.)

## Open questions

### 1. Argon2id parameters

Starting point from design 02 / OWASP baseline: `m = 65536 KiB (64 MiB), t = 3, p = 4`,
output length 32 bytes. **Must benchmark on the three target OSes** before shipping — OWASP
recommends tuning to ≥ 0.5s on the user's hardware, and mobile / older laptops diverge
wildly. Action: spike in Phase 2 start, before any user-facing flow.

### 2. SQLCipher version pinning

`rusqlite` with `bundled-sqlcipher` is a single version at build time. SQLCipher 4.x is the
current major. Bumping requires a full DB migration (page format may change). Pin to a
specific minor version in `Cargo.toml`; treat bumps as schema migrations (they kind of are).

### 3. `VACUUM` policy

Deleted rows leave slack space. SQLite's `VACUUM` compacts. Decision: run `VACUUM INTO`
(a copy-based vacuum) during rekey so we never write to a live DB. Opportunistic vacuum on
idle doesn't add enough to justify the complexity. Revisit if profile/telemetry shows
growth issues.

### 4. Durability of `fs2` lock on Windows

`fs2::FileExt::lock_exclusive` maps to `LockFileEx` on Windows, which is advisory and held
by the file handle. Dropping the handle releases the lock. Should be fine; but I want a CI
or manual test that kills a process mid-lock and verifies a subsequent process can reacquire.
Added to the Phase 2 verification list.

### 5. WAL checkpoint on close

`PRAGMA wal_checkpoint(TRUNCATE)` on graceful close consolidates the WAL back into the main
file, so a restart doesn't find stale WAL bytes. Issue: checkpoint takes a full lock and may
stall other processes. Probably acceptable at app shutdown; monitor.

### 6. Should `Vault::open` auto-migrate, or require explicit call?

Auto-migrate is friendlier (no forgotten calls); explicit is safer (a dev can reason about
when schema changes). Leaning auto-migrate, with a `VaultConfig::skip_migrations: bool` escape
hatch for tests that want to verify a specific pre-migration state. Decide when implementing.

## Consequences

**Easier:**
- A single local DB file contains every secret bit of user state. Backup = copy this file;
  restore = paste back. No cloud dependencies.
- Testing with `InMemoryVault::new()` gives every consumer a cheap, isolated DB.
- The vault API is the sole persistence contract: any feature that wants to persist calls
  these methods. No "temp table" or "shadow cache" paths.

**Harder:**
- SQLCipher + rusqlite + bundled build inflates compile time. Acceptable cost; documented.
- Two-process safety is fiddly (fs2 + refinery race + WAL). Mitigated by integration tests
  that exercise the concurrent path explicitly.
- Rekey failure states have user-visible complexity; the UI needs to surface them well.

**New risks:**
- SQLCipher version upgrade ≈ schema migration in blast radius. Must be planned, not ambient.
- `panic = "abort"` at a bad time during rekey could leave the DB half-rewritten — except
  SQLCipher's rekey is atomic at the page level, and SQLite itself guarantees file-level
  atomicity via the journal. Confirmed in SQLCipher / SQLite docs; documented here for the
  reviewer who wonders.

## Dependencies to add (Phase 2)

```toml
# crates/core/Cargo.toml additions
[dependencies]
rusqlite = { version = "0.37", features = ["bundled-sqlcipher", "backup"] }
refinery = { version = "0.8", features = ["rusqlite"] }
parking_lot = "0.12"
fs2 = "0.4"
dirs = "6"           # platform data-dir resolution
# keyring + age added in their own module when they land (design 02)

[dev-dependencies]
tempfile = "3"
```

Exact versions locked at implementation time; above are indicative. Per `docs/quality-gates.md §7`,
hash-pinning happens in `Cargo.lock` on first add.

## Review gates

Any PR touching `crates/core/src/vault/` — and specifically `migrations/V*.sql` — is on the
2-reviewer list per `docs/quality-gates.md §7`. Schema is security-adjacent; add a reviewer
with Postgres / SQLite experience for migrations if one is available.

## ADR

`docs/adr/0003-vault-design.md` captures the five load-bearing decisions:

1. SQLCipher via rusqlite (not sqlx, not a custom crypto stack).
2. Single connection per vault, serialized by parking_lot::Mutex, async bridge via spawn_blocking.
3. WAL + fs2 advisory lock for multi-process safety.
4. refinery for migrations; V0001 ships the five surviving tables.
5. No per-column encryption; SQLCipher whole-file is the answer.

## References

- `docs/design/01-workspace-architecture.md` — where `core::vault` lives.
- `docs/design/02-keychain-abstraction.md` — how the KEK gets in and out of the keychain.
- `docs/desktop-threat-model.md` — assets A1, A2, A5; residual risks 1–4.
- Refined plan: `~/.claude/plans/woolly-coalescing-dragon.md` — Phase 2 scope.
- SQLCipher docs: https://www.zetetic.net/sqlcipher/sqlcipher-api/
- `account_hub/db/models.py` — the Python schema we're porting from.
