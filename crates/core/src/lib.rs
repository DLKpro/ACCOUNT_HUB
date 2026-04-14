//! # Account Hub core
//!
//! Shared business logic, consumed by both the Tauri GUI (`crates/gui`) and the CLI
//! (`crates/cli`). This crate is deliberately Tauri-agnostic and clap-agnostic — it
//! must not grow a dependency on either.
//!
//! See `docs/design/01-workspace-architecture.md` for the architecture spec and
//! the quality-gates checklist at `docs/quality-gates.md`.
//!
//! ## Module layout (stubs; each fills in as its design is accepted)
//!
//! | Module | Status | Design doc |
//! |---|---|---|
//! | [`error`] | Stub | — |
//! | [`session`] | Stub | — |
//! | [`crypto`] | Stub | (future, pending crypto review) |
//! | [`keychain`] | Stub | `docs/design/02-keychain-abstraction.md` (pending) |
//! | [`vault`] | Stub | `docs/design/03-vault.md` (pending) |
//! | [`oauth`] | Stub | `docs/design/04-oauth-providers.md` (pending) |
//! | [`mail`] | Stub | (pending, Phase 3) |
//! | [`discovery`] | Stub | (pending, Phase 3) |
//! | [`closure`] | Stub | (pending, Phase 3) |
//! | [`types`] | Stub | — |

#![forbid(unsafe_code)]

pub mod error;
pub mod session;

pub mod closure;
pub mod crypto;
pub mod discovery;
pub mod keychain;
pub mod mail;
pub mod oauth;
pub mod types;
pub mod vault;

pub use error::{Error, Result};
pub use session::{LockedSession, UnlockedSession};
