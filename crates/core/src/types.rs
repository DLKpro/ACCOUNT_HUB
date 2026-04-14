//! Shared DTOs — single source of truth for types crossing the Rust/TypeScript boundary.
//!
//! Stub. Types here derive `serde::{Serialize, Deserialize}` and (when the Tauri IPC design
//! lands in Phase 3) `specta::Type` or `ts_rs::TS` for TypeScript codegen.
//!
//! Cross-cutting DTOs live here, not per-module, so the TS codegen has a single sweep.
