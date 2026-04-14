//! `SQLCipher`-backed local vault.
//!
//! Stub. Full spec: `docs/design/03-vault.md` (accepted, ADR 0003).
//!
//! Planned shape:
//!
//! - `Vault` handle: single connection per instance, serialized by a
//!   `parking_lot::Mutex`; all public methods are `async fn` and dispatch through
//!   `tokio::task::spawn_blocking`.
//! - Encryption: `SQLCipher` whole-file AES-256 via `rusqlite` with the
//!   `bundled-sqlcipher` feature. KEK is a 32-byte `SecretValue` supplied by the
//!   session layer; the vault never derives or stores it.
//! - Migrations: `refinery`, loading `.sql` files from `crates/core/migrations/`.
//!   Initial migration `V0001__initial.sql` ships the five surviving tables —
//!   `linked_email`, `oauth_state`, `scan_session`, `discovered_account`,
//!   `closure_request`. Auth-only tables (`user`, `email_verification_token`,
//!   `password_reset_token`) are retired, not ported.
//! - Multi-process safety: `WAL` mode for concurrent readers + `fs2` advisory
//!   exclusive lock for schema migration, rekey, and `VACUUM INTO`.
//! - Data types: timestamps are `INTEGER` unix seconds; booleans are `INTEGER 0/1`;
//!   tokens are plaintext `TEXT` inside the `SQLCipher` envelope (no per-column
//!   encryption — rationale in ADR 0003).
//!
//! Dependencies (`rusqlite` + `bundled-sqlcipher`, `refinery`, `parking_lot`, `fs2`,
//! `dirs`) land with the implementation in Phase 2; per `docs/quality-gates.md §2`
//! they are not pinned ahead of consuming code.
