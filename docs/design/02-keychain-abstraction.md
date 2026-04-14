# Design 02 — Keychain Abstraction

> Ground-up design #2. Depends on: `docs/design/01-workspace-architecture.md` (defines the
> `core::keychain` module and the `test-utils` feature). Feeds: design 03 (vault needs a
> `SecretStore` to wrap the KEK), design 04 (OAuth needs a place for the Apple private key).
> Threat model: see `docs/desktop-threat-model.md` assets A1, A4.

## Purpose

Provide a single `SecretStore` trait that the Rust core uses to read, write, and delete small
pieces of secret material (≤ 512 bytes each) on behalf of the logged-in OS user. The trait
must work identically — from the caller's perspective — across:

- macOS (user's login keychain via Security.framework)
- Windows (Credential Manager via wincred)
- Linux desktop (libsecret via D-Bus; Secret Service API)
- Linux headless / CI (age-encrypted file, gated by an explicit opt-in)
- Tests (in-memory `FakeKeychain` behind the `test-utils` feature)

The abstraction exists so the vault doesn't care where the KEK lives, the OAuth module doesn't
care where the Apple private key lives, and tests don't have to touch real OS credential stores.

## What does — and does not — live here

**Lives in `SecretStore`:**

| Secret | Size | Persistence | Why |
|---|---|---|---|
| Vault KEK (wrapped) | 32 B + AEAD overhead | Until user logs out / wipe | Avoids re-running Argon2id on every unlock. Primary asset. |
| Apple OAuth private key (PEM, encrypted form) | ~1–2 KB | Until `account-hub` uninstalls | Current codebase reads it from file/env ([account_hub/services/oauth_service.py](../../account_hub/services/oauth_service.py)); OS keychain is the right home in the desktop build (Phase 3). |
| Per-provider refresh-token-MAC salt | 16–32 B | Until wipe | Phase 3 nicety; lets us MAC refresh tokens at rest with a key distinct from the vault KEK. Optional; gate behind the vault design. |

**Does not live in `SecretStore`:**

- OAuth access tokens and refresh tokens themselves. These live in the encrypted vault DB; the
  vault is the right place because they're tabular and each is ≤ provider-max size but the
  aggregate grows unbounded (more linked accounts = more tokens). `SecretStore` is for a small,
  fixed set of named secrets.
- The master password. It is derived-from and immediately zeroized; never persisted anywhere.
- Ephemeral OAuth `state` / PKCE verifier. Lives in memory for the ~60s of an in-flight OAuth
  dance. Vault's `oauth_state` table already persists it for the ≤ 10-minute window.

Keeping the abstraction narrow is deliberate: the larger the `SecretStore` surface, the more
we leak across platforms. OS credential stores have very different semantics on volume
limits, concurrent-access behavior, and what "delete" means.

## Trait shape

```rust
// crates/core/src/keychain/mod.rs (sketch)

use zeroize::Zeroizing;

/// A named secret slot. Callers construct these via the typed constructors so they can't
/// accidentally collide service/account pairs or typo the identifier.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct SecretKey {
    pub(crate) service: &'static str,
    pub(crate) account: &'static str,
}

impl SecretKey {
    /// Wrapped vault KEK — the most security-critical slot.
    pub const VAULT_KEK: Self = Self { service: "AccountHub", account: "vault-kek" };
    /// Apple OAuth client-secret signing key (Phase 3).
    pub const APPLE_CLIENT_SECRET_KEY: Self = Self { service: "AccountHub", account: "apple-oauth-priv" };
    // Add new slots as they emerge; constants force a reviewer to see the change.
}

/// Opaque byte buffer that zeroizes on drop. `SecretStore` always takes and returns this —
/// never a plain `Vec<u8>` — so callers can't accidentally forget to zeroize.
#[derive(Clone)]
pub struct SecretValue(Zeroizing<Vec<u8>>);

impl SecretValue {
    pub fn new(bytes: Vec<u8>) -> Self { Self(Zeroizing::new(bytes)) }
    pub fn as_bytes(&self) -> &[u8] { &self.0 }
    pub fn len(&self) -> usize { self.0.len() }
    pub fn is_empty(&self) -> bool { self.0.is_empty() }
}

impl std::fmt::Debug for SecretValue {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        // Never print bytes — even their hex — in Debug output.
        write!(f, "SecretValue({} bytes)", self.0.len())
    }
}

#[derive(Debug, thiserror::Error)]
pub enum KeychainError {
    /// The slot is not yet populated. First-launch path; callers should not treat as fatal.
    #[error("no such secret")]
    NotFound,

    /// The OS refused access (user dismissed a biometric prompt, keychain locked, etc.).
    /// Caller may retry after user interaction.
    #[error("access denied by OS credential store")]
    AccessDenied,

    /// The backend itself is unavailable (libsecret / D-Bus not running on Linux, corrupt
    /// Credential Manager on Windows, etc.). Distinguishing this from AccessDenied lets the
    /// CLI fall back to the age-keyfile path cleanly instead of bugging the user for a retry
    /// that will never succeed.
    #[error("credential store unavailable: {0}")]
    Unavailable(String),

    /// Anything else. Wrapped as a string rather than a dyn Error chain because different
    /// backends surface wildly-shaped errors we don't want to leak into the public API.
    #[error("backend error: {0}")]
    Backend(String),
}

/// Public trait. Async so GUI callers don't block the tokio runtime; impls may internally
/// `spawn_blocking` if the underlying API is synchronous. All methods are cancel-safe:
/// on cancellation, the store state is consistent.
#[async_trait::async_trait]
pub trait SecretStore: Send + Sync + std::fmt::Debug {
    async fn set(&self, key: SecretKey, value: SecretValue) -> Result<(), KeychainError>;
    async fn get(&self, key: SecretKey) -> Result<SecretValue, KeychainError>;
    async fn delete(&self, key: SecretKey) -> Result<(), KeychainError>;
    async fn exists(&self, key: SecretKey) -> Result<bool, KeychainError> {
        match self.get(key).await {
            Ok(_) => Ok(true),
            Err(KeychainError::NotFound) => Ok(false),
            Err(e) => Err(e),
        }
    }
}
```

### Design choices, justified

- **Async trait.** Keyring operations themselves are fast (< 10 ms typical), but biometric
  prompts can block for seconds. An async API keeps the GUI's tokio runtime responsive; the
  CLI just `.await`s. Using `async_trait` is acceptable here — the call frequency is low
  (once per unlock, not per row read).
- **Typed `SecretKey` constants rather than `&str` identifiers.** Eliminates a whole class
  of bugs: key typos, service/account swap, accidental collision with another app's
  `service="AccountHub"` entry if we forgot to namespace. Every new secret slot forces a
  commit that touches this file, which the 2-reviewer rule catches.
- **`SecretValue` wraps `Zeroizing<Vec<u8>>` and redacts in `Debug`.** The type, not the
  caller, owns the zeroization discipline.
- **Three distinct error variants for the failure modes callers genuinely need to
  discriminate** (NotFound, AccessDenied, Unavailable). Collapsing these into a single
  opaque error would force the CLI to string-match to decide whether to fall back.

## Implementations

### `MacosKeychain` (macOS)

- Wraps the [`keyring`](https://crates.io/crates/keyring) crate (version-pinned in Phase 2
  when we add it).
- Uses the **login keychain** — automatically unlocks when the user logs in, re-locks on
  screen lock per the user's keychain settings.
- Access control: set `kSecAttrAccessibleWhenUnlocked` so the KEK is accessible only while
  the login keychain is unlocked. Do **not** use `AlwaysThisDeviceOnly` — that would permit
  access even when the device is locked, which is strictly weaker.
- Biometric gating (Touch ID): optional; off by default in v1, adds `kSecAccessControlBiometryCurrentSet`
  and a `LAContext` prompt. Open question below.

### `WindowsCredentialManager` (Windows)

- Same `keyring` crate; uses CredWrite / CredRead under the hood.
- Credentials stored as `CRED_TYPE_GENERIC` in the user's credential set (not the system one).
- Access control: CRED_PERSIST_LOCAL_MACHINE — stored only on this machine, not roamed to
  domain profiles. Avoids surprising propagation on corporate Windows.
- Windows Hello integration: possible via `WinRT Windows.Security.Credentials.UI.UserConsentVerifier`,
  but not through the `keyring` crate directly. Defer to v1.1; open question below.

### `LinuxSecretService` (Linux desktop)

- `keyring` crate's Secret Service backend (D-Bus, libsecret).
- Requires a running Secret Service daemon (gnome-keyring-daemon, KWallet Secret Service, etc.).
  On a sensible Linux desktop install this is present; on headless server, it's usually not.
- Access control: relies on the daemon's own locking (typically auto-unlock on login).
- Detection: on construction, probe D-Bus for the Secret Service interface. If absent, return
  `KeychainError::Unavailable` rather than panicking; the caller decides whether to
  surface the error or fall back to `AgeKeyfile`.

### `AgeKeyfile` (Linux headless / CI / opt-in)

- File-backed; the encrypted bytes of each slot stored in `$XDG_DATA_HOME/AccountHub/secrets/<account>.age`.
- Encryption: [age](https://age-encryption.org) with an identity the user controls.
- **Identity options** — pick one per `AgeKeyfile` instance at construction:
  - **Passphrase (scrypt-based age).** Simplest; interactive headless-human use. The user
    types a passphrase on every unlock. Acceptable when OS keychain is simply absent but a
    human is present.
  - **X25519 identity file.** Private key in `~/.config/account-hub/identity.age`, typically
    passphrase-protected at file level. Suits an automation account that has its own age
    identity pre-provisioned.
  - **SSH key via `age-ssh`.** Reuses a pre-existing `ssh-ed25519` key the user already
    has. Pragmatic for hosts where `~/.ssh/id_ed25519` is already present.
  - **YubiKey / age plugin.** Hardware-backed. The keyfile is a wrapped key the plugin can
    decrypt only when the token is present. Best option for long-lived CI workers.
- The impl does not choose — it's parameterized by an `AgeIdentity` enum. CLI flag / env var
  decides at runtime.
- **Threat-model note.** A plain-passphrase `AgeKeyfile` protected only by file permissions
  is strictly weaker than an OS keychain entry. Document this clearly in the CLI help. An
  X25519 identity on removable media, or a YubiKey-backed identity, is arguably stronger
  than libsecret since it survives a compromised D-Bus.

### `FakeKeychain` (tests, `test-utils` feature)

- Trivial `tokio::sync::RwLock<HashMap<SecretKey, SecretValue>>`.
- Gated behind `#[cfg(any(test, feature = "test-utils"))]`.
- Supports deterministic-error injection (`set_failure_mode(Option<KeychainError>)`) so unit
  tests can simulate `AccessDenied`, `Unavailable`, etc. without real OS calls.

## Selection / initialization

```rust
// crates/core/src/keychain/mod.rs (selection sketch)

pub enum KeychainBackend {
    Os,                  // auto-select per OS
    AgeKeyfile(AgeKeyfileConfig),
    #[cfg(any(test, feature = "test-utils"))]
    Fake,
}

pub async fn new(backend: KeychainBackend) -> Result<Box<dyn SecretStore>, KeychainError> {
    match backend {
        KeychainBackend::Os => os_default().await,
        KeychainBackend::AgeKeyfile(cfg) => Ok(Box::new(AgeKeyfile::new(cfg).await?)),
        #[cfg(any(test, feature = "test-utils"))]
        KeychainBackend::Fake => Ok(Box::new(FakeKeychain::new())),
    }
}

async fn os_default() -> Result<Box<dyn SecretStore>, KeychainError> {
    #[cfg(target_os = "macos")]
    { return Ok(Box::new(MacosKeychain::new().await?)); }
    #[cfg(target_os = "windows")]
    { return Ok(Box::new(WindowsCredentialManager::new().await?)); }
    #[cfg(target_os = "linux")]
    {
        match LinuxSecretService::new().await {
            Ok(s) => Ok(Box::new(s)),
            Err(KeychainError::Unavailable(_)) => {
                Err(KeychainError::Unavailable(
                    "libsecret not available; pass --keyfile to use file-backed fallback".into()
                ))
            }
            Err(e) => Err(e),
        }
    }
}
```

- **GUI** (`crates/gui`) always calls `new(KeychainBackend::Os)`. If it returns `Unavailable`
  on Linux, the GUI surfaces a modal error: "Install gnome-keyring or similar to proceed."
  Falling back to age keyfile inside the GUI is **not supported** in v1 — a desktop user
  without libsecret is a configuration we decline to paper over.
- **CLI** (`crates/cli`) defaults to `Os`; `--keyfile <path>` or `ACCOUNTHUB_KEYFILE=<path>`
  switches to `AgeKeyfile`. If `Os` returns `Unavailable` on Linux and no keyfile flag is
  set, the CLI prints an actionable error (not a stack trace) pointing at the `--keyfile`
  option.
- **Tests** use `Fake`.

## Security properties

With the design above, the following hold:

1. **Vault KEK never touches disk unencrypted** in the default (OS-keychain) case. On macOS
   it's protected by the file-vault-derived login-keychain key; on Windows by DPAPI; on
   Linux by the Secret Service daemon's key derivation.
2. **`AgeKeyfile` with passphrase is strictly file-permission + passphrase security.** Loss of
   either breaks the barrier. Documented in-app and in CLI help.
3. **`SecretValue` memory is zeroized on drop.** Even if the caller stores a value in a
   local variable and panics, `Drop` runs (given `panic = "abort"` from design 01 —
   wait, abort skips destructors). → See [Open question §1](#1-panic-abort-and-zeroize).
4. **`Debug` on `SecretValue` shows `SecretValue(<N> bytes)`, never the bytes.** No
   accidental leakage into `tracing` logs or `panic!` output.
5. **`SecretKey` is a struct with private fields and typed constants** — no `new(&str, &str)`
   constructor in the public API. Collision with another app's keychain entries would
   require a deliberate commit that adds a new constant, which code review catches.

What the design does **not** protect against:

- Local malware running as the logged-in user with PTRACE on the unlocked `account-hub`
  process (acknowledged residual risk in the threat model).
- An attacker who has the user's OS login credentials — they own the keychain too. This is
  accepted; the defense against this threat is the OS, not our app.

## Testing strategy

Per `docs/quality-gates.md §3`:

- **Unit tests in `crates/core/src/keychain/`:** pure logic — `SecretKey` hashing, `SecretValue`
  zeroization behavior (verified by checking `as_bytes()` returns zeros after a deliberate
  wipe in test), error conversions. No OS calls.
- **`FakeKeychain` round-trips** in every consumer of the trait: vault, OAuth, session.
  These tests drive the trait's ergonomics — if the trait is awkward for a fake caller, it
  will be awkward for real ones.
- **Real-backend integration tests** live under `crates/core/tests/keychain_<os>.rs`, gated
  behind `#[cfg(target_os = "…")]`. Not run in CI (CI doesn't have a login keychain). Run
  manually during development and during release verification.
- **Property test** via `proptest`: arbitrary `SecretValue`s round-trip through `FakeKeychain`
  without mutation. Guards against future Zeroizing-related churn.

## Open questions

### 1. `panic = "abort"` and `zeroize`

The workspace's `[profile.release] panic = "abort"` (design 01) skips unwinding, which means
`Drop` implementations **do not run** on panic. That includes `Zeroizing`. Consequences:

- In-process secrets held during a panic are not wiped before the process exits.
- Process exit itself zeroes pages lazily via the OS, but until the OS reclaims them, a
  cold-boot attacker with RAM access could read them.

The existing 1Password / Bitwarden posture is to accept this: the cold-boot attacker is out
of scope for a user-space app. We adopt the same position. But it's worth noting that
`zeroize` is defence-in-depth for the normal (drop) path, not the panic path.

**Decision:** keep `panic = "abort"`. Document this in the threat model as a known limitation
and an accepted residual risk. No code change.

### 2. Biometric gating (Touch ID / Windows Hello)

The MVP does not require biometric verification to unlock a cached KEK — the keychain entry's
OS-level access controls are sufficient. Adding biometric gating is a usability improvement
(prompts the user even when the keychain is already unlocked) and a small security win (an
attacker who got inside the locked session still has to beat biometrics).

**Decision:** optional, off by default in v1. A setting toggle lands in v1.1 with full design.
Add the trait methods (`fn set_biometric_required(...)`) now so the interface is stable.

Actually — **revised decision after reflection:** do not add biometric methods to the trait
until we have a concrete design. The trait should reflect what the impls can reliably do
*today*, not a speculative future. When biometric gating lands, a new trait method or a
`SecretStoreBiometric: SecretStore` sub-trait is the right shape. YAGNI applies.

### 3. Auto-lock on idle

Separate from the trait: the `UnlockedSession` should auto-lock after N minutes of idle.
That's a `session.rs` concern (design 03), not a keychain concern. Mentioning here so it
doesn't get lost.

### 4. Multi-user on a shared Linux host

The current design assumes one OS user per vault. libsecret entries are per-user by default,
so this is fine. If two humans share a login, they share a vault — that's a configuration
outside the threat model. No design change; documented.

### 5. Which age-backed identity to implement first in the `AgeKeyfile` impl

All four (passphrase, X25519 file, age-ssh, YubiKey plugin) are viable. The MVP should
support at least one. Likely pick: **X25519 identity file, passphrase-protected**. Reuses
mature age crates, no plugin dependency, no hardware requirement. The other three can land
incrementally without trait changes.

**Decision to confirm in Phase 3:** v1 `AgeKeyfile` ships with X25519 identity file support;
age-ssh and YubiKey plugin land as follow-ons.

## Consequences

**Easier:**
- Vault (design 03) depends only on the `SecretStore` trait, not on any specific OS API.
- Testing secret-dependent logic is trivial with `FakeKeychain`.
- Adding a new backend is a matter of implementing one trait; no caller changes.
- Switching a user between backends (e.g. migrating from OS keychain to YubiKey-age) is a
  matter of calling `new(... different backend)` and copying all `SecretKey` slots.

**Harder:**
- Three real OS backends means three places to test. Integration tests can't run in CI for
  any of the three (no login context in GitHub runners). Mitigated by `FakeKeychain` unit
  coverage + manual release verification; acknowledged gap.
- `AgeKeyfile` introduces a second dimension of complexity (which age identity type).

**New risks:**
- An OS-level `keyring` crate CVE would affect all three OS backends simultaneously. Mitigation:
  version-pin, watch the advisory DB via `cargo-audit`, be ready to patch quickly.
- A bug in `AgeKeyfile` that corrupts the on-disk ciphertext would lock the user out. Mitigation:
  first write + verify round-trip before reporting `set` success; never truncate in place.

## Dependencies to add (Phase 2)

```toml
# crates/core/Cargo.toml (to add when this module gains code)
[dependencies]
keyring = "4"                 # macOS + Windows + Linux Secret Service
async-trait = "0.1"           # for the SecretStore trait
age = "0.11"                  # for AgeKeyfile; figure out exact version at impl time
secrecy = "0.10"              # optional — stronger redaction primitives on top of zeroize
```

Add only when the impls land. Per `docs/quality-gates.md §2`, deps aren't pinned until their
consuming code lands.

## ADR

This design has enough distinct decisions (async trait, typed SecretKey constants, age-keyfile
fallback opt-in, no biometric methods in v1) that an ADR is warranted once accepted.

File: `docs/adr/0002-keychain-abstraction.md`.

## References

- `docs/design/01-workspace-architecture.md` — where the `core::keychain` module lives.
- `docs/desktop-threat-model.md` — assets A1 (vault KEK) and A4 (Apple private key).
- `docs/quality-gates.md` §3 (test coverage), §7 (supply chain — keyring version pinning).
- Refined plan: `~/.claude/plans/woolly-coalescing-dragon.md` — "age-encrypted keyfile fallback
  for headless Linux" commitment.
