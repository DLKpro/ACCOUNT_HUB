//! OAuth provider architecture.
//!
//! Stub. Real impl lands with `docs/design/04-oauth-providers.md` (pending).
//!
//! Providers: Google, Microsoft (switched from device-code to loopback+PKCE per refined plan),
//! Apple (via the `dlopro.com` Cloudflare Worker relay — port encoded in OAuth `state`),
//! and Meta.
//!
//! The Apple private key moves from the current file/env location
//! (see `account_hub/services/oauth_service.py`) into the OS keychain during Phase 3.
