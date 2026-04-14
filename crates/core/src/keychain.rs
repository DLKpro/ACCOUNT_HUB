//! OS keychain abstraction.
//!
//! Stub. Real impl lands with `docs/design/02-keychain-abstraction.md` (pending).
//!
//! The forthcoming `SecretStore` trait will cover macOS Keychain, Windows Credential Manager,
//! and Linux libsecret. An age-encrypted keyfile fallback for headless CLI use will live here
//! too (gated by the `cli` crate's `keyfile-fallback` feature, but the impl is in `core`).
