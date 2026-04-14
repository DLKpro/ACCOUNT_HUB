//! Cryptographic primitives: Argon2id KDF, zeroize wrappers.
//!
//! Stub. Real impl lands with the vault design (`docs/design/03-vault.md`, pending).
//! All functions in this module handle secret material and must:
//!
//! - Wrap sensitive buffers in [`zeroize::Zeroizing`] or derive [`zeroize::Zeroize`].
//! - Never log or `Debug`-print secret contents (redact in `Debug` impls).
//! - Run on `tokio::task::spawn_blocking` when called from async code (Argon2id is CPU-bound).

// No public items yet — modules are a placeholder.
