# 0003. Vault: SQLCipher + rusqlite + refinery + WAL + fs2 lock

**Status:** Accepted
**Date:** 2026-04-13
**Supersedes:** —
**Superseded by:** —

## Context

Design doc `docs/design/03-vault.md` defines the local encrypted store that holds every
piece of per-user persistent state: linked email accounts, in-flight OAuth state, scan
sessions, discovered accounts, closure requests. The design makes load-bearing technology
choices that are difficult to undo later; those choices are captured here.

The vault is the single most security-critical component of the desktop app. Any ADR about
it therefore documents both the choice and the threat-model rationale, so a future
maintainer doesn't "simplify" a deliberately-paranoid design.

## Decisions

### D1 — Encryption: SQLCipher 4.x, via `rusqlite` with `bundled-sqlcipher`

Whole-file AES-256 encryption. No per-column layering. KEK supplied as a raw 32-byte hex
literal (bypassing SQLCipher's own PBKDF2) because our Argon2id derivation is already
strong.

### D2 — Single connection per vault, serialized by `parking_lot::Mutex`

No pool. All queries serialize on a single `rusqlite::Connection` held behind a sync mutex
(not `tokio::sync::Mutex` — the mutex is acquired inside `spawn_blocking`, where async
mutexes would be wrong).

### D3 — Async bridge via `tokio::task::spawn_blocking`

Public `Vault` API is `async fn`; every method dispatches its SQLite work through
`spawn_blocking`. Rationale: rusqlite is sync; the GUI runs on a tokio runtime and must
not block; per-statement async wrappers (as in `sqlx`) add heft without a throughput win
at our QPS.

### D4 — Multi-process safety: WAL + `fs2` advisory exclusive lock on rekey / migration

Normal reads and writes rely on SQLite's WAL-mode locking. Rekey, schema migration, and
`VACUUM INTO` take an exclusive `fs2` file lock for the whole operation; a competing
process blocks on the lock.

### D5 — Migrations via `refinery`, not `sqlx::migrate!` or hand-rolled

Embedded SQL files under `crates/core/migrations/V*.sql`. `refinery` tracks applied
migrations in its own metadata table and supports atomic transaction wrapping per migration.

### D6 — No per-column encryption

Tokens stored as plaintext TEXT columns inside the SQLCipher envelope. An attacker who
already has the KEK and the DB has everything; adding a second layer buys no threat
reduction.

### D7 — Schema is fresh-start, not migrated from Postgres

No ETL from the existing Python Postgres DB. Hosted-alpha users re-link providers in the
desktop app (already captured in the refined plan). Initial migration (`V0001__initial.sql`)
ships the five surviving tables only; the three auth-only tables are retired entirely.

### D8 — Timestamps are `INTEGER` unix seconds

Not `TEXT ISO-8601`, not `REAL` Julian-day. Arithmetic is trivial; SQLite has native date
functions that accept integers; serialization with `serde` is a single `i64`.

### D9 — `PRAGMA cipher_memory_security = ON` and `foreign_keys = ON` on every open

Memory security zeros decrypted pages when they're discarded. Foreign-key enforcement is
off by default in SQLite (!!) — it must be set per-connection.

## Consequences

**Easier:**
- One local file contains all state. Backup = file copy. Wipe = unlink.
- Testing with `:memory:` + a random KEK is trivial; every consumer gets isolation.
- Schema changes are visible in version-controlled SQL files; `refinery` guarantees
  apply-once semantics.
- The `SecretStore` trait (design 02) is the only external dependency of the vault;
  everything else is rusqlite + SQLCipher + std.

**Harder:**
- `bundled-sqlcipher` inflates compile time (~30s cold). Workspace target caching softens
  the repeat hit.
- Two-process safety is non-trivial: WAL + migration-race + `fs2` lock semantics differ
  subtly between macOS/Linux and Windows. Mitigated by an integration test that spawns a
  second process and verifies concurrent reads work, writes serialize, and lock contention
  resolves without deadlock.
- Rekey failure states need explicit UI handling (vault now uses new key but keychain
  still holds old one — a stuck state). Captured as an ordered retry flow in the design
  doc.

**New risks:**
- SQLCipher version bump ≈ schema migration. Pin `rusqlite` by exact version; treat
  SQLCipher-upgrading PRs as schema-upgrading PRs, with the same 2-reviewer rule.
- `panic = "abort"` during rekey would interrupt SQLCipher mid-operation. Mitigated by
  SQLite's own file-level atomicity + WAL rollback, but worth a release-verification test
  that kills a process mid-rekey and verifies the vault is still readable with the old key.

## Alternatives considered

### (A) `sqlx` instead of `rusqlite`
- **Pros:** native async (no `spawn_blocking` wrapper); compile-time-checked SQL;
  ecosystem leader.
- **Cons:** SQLCipher support via `sqlx` is fiddly (custom `ConnectOptions`, no `bundled`
  flag); heavier compile; overkill for a low-QPS single-user store; async-SQL-per-query
  introduces task-switching overhead that actually hurts at low QPS.
- **Verdict:** rejected. `rusqlite + spawn_blocking` is the narrower, cheaper fit.

### (B) SQLite + application-level AEAD per column
- **Pros:** no SQLCipher dep.
- **Cons:** every query site re-derives crypto; no query-planner visibility into indices on
  encrypted columns; massively larger attack surface for bugs; performance dramatically
  worse on token-heavy queries.
- **Verdict:** rejected. SQLCipher is the right tool.

### (C) PostgreSQL in-app (postgres bundled as a sidecar)
- **Pros:** direct port from the current Python schema; familiar.
- **Cons:** ~150 MB binary; multi-process model doesn't buy anything for a single user;
  no SQLCipher-equivalent whole-file encryption.
- **Verdict:** rejected. The migration plan specifically moves off Postgres for these reasons.

### (D) sled / redb / other embedded KV store
- **Pros:** no SQL; simpler locking model.
- **Cons:** no relational queries means the scan / discovery / closure joins reinvent
  query logic by hand; no mature encryption story; ecosystem far smaller than SQLite.
- **Verdict:** rejected. SQL's schema-as-contract is exactly what we want.

### (E) Per-column AEAD on top of SQLCipher
- **Pros:** defense-in-depth. Attacker with the SQLCipher key still faces per-column
  encryption.
- **Cons:** the only realistic attacker path to the SQLCipher key *is* the in-process
  memory where the column keys also live. Adds complexity with no threat model it actually
  defeats.
- **Verdict:** rejected. Threat-modelled explicitly; per-column encryption doesn't help.

## References

- Design spec: `docs/design/03-vault.md`
- Threat model: `docs/desktop-threat-model.md` (assets A1, A2, A5)
- Keychain: `docs/design/02-keychain-abstraction.md` + ADR 0002
- Workspace: `docs/design/01-workspace-architecture.md` + ADR 0001
- Refined plan: `~/.claude/plans/woolly-coalescing-dragon.md` (Phase 2 scope)
- SQLCipher API docs: https://www.zetetic.net/sqlcipher/sqlcipher-api/
- Python schema being ported from: `account_hub/db/models.py`
