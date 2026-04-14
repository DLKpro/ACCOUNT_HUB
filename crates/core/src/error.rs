//! Unified error type for `account-hub-core`.
//!
//! Library callers match on [`Error`](enum@Error). Per-module errors (`VaultError`,
//! `OAuthError`, …) live inside their modules and are wrapped here via `#[from]`.
//!
//! **Rule:** Error `Display` impls must never include secret material (tokens, keys,
//! master-password bytes). This is enforced by code review, not by a lint.

use thiserror::Error;

/// Result alias used across the `account-hub-core` public API.
pub type Result<T> = std::result::Result<T, Error>;

/// Top-level error type for `account-hub-core`.
///
/// Library callers match on this enum. Per-module errors (e.g. `VaultError`, `OAuthError`)
/// live inside their respective modules and are wrapped here via `#[from]` as those
/// subsystems land.
///
/// # Secret-material rule
///
/// `Display` impls on every variant must elide secret bytes (master passwords, tokens, keys).
/// Reviewers enforce this; there is no reliable lint for it.
#[derive(Debug, Error)]
pub enum Error {
    /// Wrap an I/O error without leaking path details beyond what the OS already surfaces.
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),

    /// A caller-supplied value failed validation. The message is safe to display to users.
    #[error("invalid input: {0}")]
    InvalidInput(String),

    /// Placeholder until real sub-errors land. Carries a static label for grep-ability.
    #[error("not yet implemented: {0}")]
    NotImplemented(&'static str),
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn error_display_does_not_leak_debug_format() {
        let e = Error::InvalidInput("bad token".to_string());
        // Display must be human-readable; Debug may include type name.
        assert_eq!(format!("{e}"), "invalid input: bad token");
    }
}
