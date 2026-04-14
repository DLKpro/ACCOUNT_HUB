//! Account discovery scanners.
//!
//! Stub. **No dedicated design doc** — direct Phase 3 port from `account_hub/discovery/`,
//! with behaviour specified by the existing Python tests under `tests/test_services/`
//! (port forward to `crates/core/tests/` before deletion; see
//! `docs/quality-gates.md §3`).
//!
//! Preserves the pluggable scanner architecture: OAuth profile detection, Have I Been
//! Pwned breach lookup via k-anonymity range query, etc. Each scanner returns
//! `Vec<NewDiscoveredAccount>` which the vault persists (design 03).
