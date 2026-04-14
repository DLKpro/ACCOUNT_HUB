//! Shared DTOs — single source of truth for types crossing the Rust/TypeScript boundary.
//!
//! Stub. **No dedicated design doc** — types here are the cross-cutting surface defined
//! across designs 02-05. The canonical contract for Rust↔TS type flow lives in
//! `docs/design/05-tauri-ipc.md` (+ ADR 0005); this module is where those types concretely
//! land.
//!
//! Types here derive `serde::{Serialize, Deserialize}` and `specta::Type` (for tauri-specta
//! TS codegen, per design 05). Cross-cutting DTOs live in this module rather than each
//! subsystem so the codegen has a single sweep and the frontend imports everything from
//! one place.
