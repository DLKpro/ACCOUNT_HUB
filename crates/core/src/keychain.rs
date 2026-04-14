//! OS keychain abstraction.
//!
//! Stub. Full spec: `docs/design/02-keychain-abstraction.md` (accepted).
//!
//! Planned shape:
//!
//! - `SecretStore` trait: `async` `get` / `set` / `delete` / `exists` on typed `SecretKey`
//!   constants, returning a zeroizing `SecretValue`.
//! - Four production impls: `MacosKeychain`, `WindowsCredentialManager`, `LinuxSecretService`,
//!   `AgeKeyfile` (headless / CI / opt-in).
//! - One test impl behind the `test-utils` feature: `FakeKeychain`.
//!
//! Callers in `vault` (design 03) and `oauth` (design 04) consume the trait; they never see
//! the concrete backend. Selection happens at session init via a `KeychainBackend` enum —
//! GUI hardcodes `Os`, CLI defaults to `Os` with `--keyfile` overriding to `AgeKeyfile`.
//!
//! Dependencies (`keyring`, `age`, `async-trait`) land when this module gains code in
//! Phase 2; per `docs/quality-gates.md §2`, deps aren't pinned ahead of consuming code.
