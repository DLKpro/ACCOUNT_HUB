//! Mail provider integrations: Gmail API, Microsoft Graph, IMAP.
//!
//! Stub. **No dedicated design doc** — direct Phase 3 port from
//! `account_hub/services/mail_service.py`, with behaviour specified by the existing Python
//! tests under `tests/test_services/`. Those tests port forward to `crates/core/tests/`
//! before the Python module is deleted (see `docs/quality-gates.md §3`).
//!
//! Consumes OAuth tokens from the vault (design 03) via the `Provider` trait (design 04).
//! Does not own any unique architectural decisions; the interesting surface is the existing
//! pluggable scanner registry plus per-provider HTTP clients.
//!
//! Explicitly **not** ported: Resend-backed email verification and password reset. Those
//! flows retire entirely when master-password unlock replaces the server-user model.
