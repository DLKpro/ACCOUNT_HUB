//! Session lifecycle: locked → unlocked.
//!
//! A [`LockedSession`] is the handle returned by `crate::init` (Phase 2). Calling its future
//! `unlock` method with the master password produces an [`UnlockedSession`] that carries the
//! derived KEK and an open vault handle. Dropping the [`UnlockedSession`] zeroizes the
//! in-memory KEK.
//!
//! This module currently only declares the two state types as empty placeholders. The `unlock`
//! method and the internal fields land with the vault design (`docs/design/03-vault.md`,
//! pending) — deliberately no stub implementation, to avoid dead code that pretends to work.

/// Pre-unlock state. Holds only non-secret handles (config, DB path, etc.).
#[derive(Debug)]
pub struct LockedSession {
    // Fields materialize in Phase 2 when the vault lands.
    _private: (),
}

/// Post-unlock state. Holds the in-memory KEK and an open `SQLCipher` connection (Phase 2+).
/// Dropping this type zeroizes the KEK via the `zeroize` crate (Phase 2 impl).
#[derive(Debug)]
pub struct UnlockedSession {
    _private: (),
}
