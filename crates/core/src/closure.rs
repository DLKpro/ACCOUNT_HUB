//! Account closure registry.
//!
//! Stub. **No dedicated design doc** — direct Phase 3 port from `account_hub/data/`,
//! with behaviour specified by the existing Python tests under `tests/test_services/`
//! (port forward to `crates/core/tests/` before deletion; see
//! `docs/quality-gates.md §3`).
//!
//! Tiered deletion system: `api` (direct HTTP call) / `web_link` (user navigates) /
//! `email_request` (user sends a message) / `manual` (documentation only). The per-service
//! registry (20+ services) is a static table; vault (design 03) persists the user's
//! closure requests and their status transitions.
