//! OAuth provider architecture.
//!
//! Stub. Full spec: `docs/design/04-oauth-providers.md` (accepted, ADR 0004).
//!
//! Planned shape:
//!
//! - **`Provider` trait** (narrow): `authorization_url`, `exchange_code`, `refresh`,
//!   `userinfo`, optional `revoke`. Four impls: `Google`, `Microsoft`, `Apple`, `Meta`.
//! - **`OAuthFlow` orchestrator** (non-trait): owns the PKCE/state/nonce generation,
//!   vault persistence (`oauth_state` row), loopback server lifecycle, code-exchange, and
//!   final `linked_email` insert. Providers never see the vault or the keychain directly.
//! - **Loopback server** (`oauth::loopback`): `hyper` directly, binds `127.0.0.1:0`,
//!   single-shot per flow. Never binds non-loopback — enforced by runtime assert.
//! - **Microsoft flow switch:** loopback+PKCE in v1, consistent with Google/Apple/Meta.
//!   Device-code remains wired as a corp-tenant fallback behind a config flag.
//! - **Apple specifics:** client secret is a fresh ES256-signed JWT per token request
//!   (3-minute `exp`), signed using the Apple-issued private key loaded from the OS
//!   keychain via `SecretKey::APPLE_CLIENT_SECRET_KEY`. Callbacks route through the
//!   Cloudflare Worker relay at `dlopro.com/callback`; the OAuth `state` encodes the
//!   loopback port so the Worker can redirect back to the right listener. The relay's
//!   TLS cert is SHA-256 SPKI-pinned inside the `reqwest` client used for Apple traffic.
//! - **Refresh scheduler** (`oauth::refresh`): background task under `UnlockedSession`;
//!   refreshes tokens 5 min before expiry; distinguishes `RefreshRevoked` (user must
//!   re-link) from transient `Network` / `RateLimited`.
//! - **HTTP client:** one shared `reqwest::Client` with `rustls-tls` + `webpki-roots`;
//!   custom `ServerCertVerifier` adds the Apple Worker pin.
//!
//! All tokens carried as `SecretString` (`zeroize::Zeroizing<String>` with redacting
//! `Debug`). Never leaked to logs or panic output.
//!
//! Dependencies (`reqwest`, `rustls`, `webpki-roots`, `jsonwebtoken`, `p256`, `hyper`,
//! `url`, `sha2`, `base64`, `rand_core`) land with the implementation in Phase 3.
