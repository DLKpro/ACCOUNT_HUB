//! `SQLCipher`-backed local vault.
//!
//! Stub. Real impl lands with `docs/design/03-vault.md` (pending).
//!
//! Will contain:
//! - `Vault` handle (wraps a `SQLCipher` connection).
//! - Schema migrations via `refinery` (files under `crates/core/migrations/`).
//! - Multi-process safety via `fs2` advisory file lock + WAL mode.
//! - Models: `LinkedEmail`, `OAuthState`, `ScanSession`, `DiscoveredAccount`, `ClosureRequest`.
//!
//! Retired tables (vs. current Python schema): `user`, `email_verification_token`,
//! `password_reset_token` — replaced by master-password unlock.
