# Design 04 — OAuth Providers

> Ground-up design #4. Depends on: design 02 (keychain holds the Apple private key), design 03
> (vault persists in-flight `oauth_state` and the resulting `linked_email` rows). Feeds:
> design 05 (IPC commands drive the OAuth dance from the frontend). Threat model: assets
> A2 (OAuth tokens), A4 (Apple private key), A6 (Worker compromise), A7 (provider APIs);
> adversaries T1, T6, T7 especially.

## Purpose

Port the four OAuth provider integrations from the current Python codebase into Rust under a
**single `Provider` trait** that hides each vendor's quirks, while a non-trait orchestrator
drives the common machinery (loopback HTTP, PKCE generation, state/nonce handling, vault
persistence). Convert Microsoft from device-code flow to loopback+PKCE for consistency with
the other three. Preserve the Cloudflare Worker relay for Apple (it's architecturally
required by Apple's callback policy).

Non-goals:

- Supporting a fifth provider. Enum-closed on Google/Microsoft/Apple/Meta; adding a fifth
  requires a deliberate schema migration (vault's `CHECK` constraint enforces this).
- Running the Apple Worker's code. That lives in the separate `accounthub-oauth-relay` repo
  (see pre-Phase-0 workstream in the migration plan).
- Full MFA / step-up UX. Providers handle that themselves in-browser; our flow just hands
  off control and resumes on callback.

## Four providers, at a glance

| Provider | Flow (current) | Flow (target) | Callback | Needs special infra | OIDC? |
|---|---|---|---|---|---|
| **Google** | loopback + PKCE | loopback + PKCE | `http://127.0.0.1:<port>/callback` | — | ✅ `id_token` with JWKS |
| **Microsoft** | **device code** (legacy) | **loopback + PKCE** (switch) | `http://127.0.0.1:<port>/callback` | Entra portal must allow `http://localhost` for public clients | ✅ `id_token` with JWKS |
| **Apple** | loopback + PKCE via Worker relay | loopback + PKCE via Worker relay | `https://dlopro.com/callback` → relay → `http://127.0.0.1:<port>/callback` | Worker relay; ES256-signed client secret JWT; private key in OS keychain | ✅ `id_token` (with nuance — narrow scope) |
| **Meta** | loopback + PKCE | loopback + PKCE | `http://127.0.0.1:<port>/callback` | — | ❌ (Meta's `id_token` flavor is non-standard; we use userinfo API instead) |

The switch for Microsoft is an ADR-worthy change (ADR 0004 §D3). The three other rows hold
identical shape to the current Python implementation; the interesting work is centralising
the scaffolding.

## Trait shape

```rust
// crates/core/src/oauth/mod.rs (sketch)

#[async_trait]
pub trait Provider: Send + Sync + std::fmt::Debug {
    /// Enum tag. Used for logging, vault persistence, CHECK constraints.
    fn id(&self) -> ProviderId;

    /// Build the browser-visible authorization URL. Pure function of the parameters;
    /// no network IO. Keeps the per-provider URL quirks (scope names, response_mode,
    /// prompt, extra query params) contained.
    fn authorization_url(&self, params: &AuthRequestParams) -> Url;

    /// Exchange an authorization code for an initial TokenSet.
    /// Runs one HTTPS POST to the provider's token endpoint.
    async fn exchange_code(
        &self,
        params: CodeExchangeParams<'_>,
    ) -> Result<TokenSet, ProviderError>;

    /// Rotate a refresh token for a fresh access token.
    async fn refresh(
        &self,
        refresh_token: &SecretString,
    ) -> Result<TokenSet, ProviderError>;

    /// Fetch minimal userinfo (email, provider_user_id, display_name).
    /// Separate from `exchange_code` because Meta doesn't ship a proper `id_token` and
    /// needs an extra `/me` call; the other three include claims in the `id_token` already,
    /// but we normalise through this method for the caller.
    async fn userinfo(
        &self,
        access_token: &SecretString,
    ) -> Result<UserInfo, ProviderError>;

    /// Best-effort revocation. Not all providers expose this; default impl returns
    /// `Err(ProviderError::Unsupported)` and callers treat as non-fatal.
    async fn revoke(
        &self,
        _token: &SecretString,
        _kind: TokenKind,
    ) -> Result<(), ProviderError> {
        Err(ProviderError::Unsupported("token revocation not implemented for this provider"))
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ProviderId { Google, Microsoft, Apple, Meta }

pub struct AuthRequestParams<'a> {
    pub client_id: &'a str,
    pub redirect_uri: &'a str,
    pub scopes: &'a [&'a str],
    pub state: &'a str,                  // opaque; includes port for Apple
    pub code_challenge: &'a str,         // b64url(sha256(verifier))
    pub nonce: Option<&'a str>,          // OIDC
    pub extra: &'a [(&'a str, &'a str)], // provider-specific overrides
}

pub struct CodeExchangeParams<'a> {
    pub code: &'a str,
    pub redirect_uri: &'a str,
    pub code_verifier: &'a str,          // PKCE
    pub expected_nonce: Option<&'a str>, // validated against id_token.nonce if OIDC
}

pub struct TokenSet {
    pub access_token: SecretString,
    pub refresh_token: Option<SecretString>,   // Meta long-lived tokens don't refresh the same way
    pub id_token: Option<SecretString>,        // OIDC only
    pub expires_at: Option<i64>,               // unix seconds; None = not provided
    pub granted_scopes: Vec<String>,
}

#[derive(Debug)]
pub struct UserInfo {
    pub provider_user_id: String,
    pub email: String,
    pub email_verified: bool,
    pub display_name: Option<String>,
}

#[derive(Debug, thiserror::Error)]
pub enum ProviderError {
    #[error("user aborted the authorization flow")]
    UserAborted,
    #[error("state mismatch — possible CSRF")]
    StateMismatch,
    #[error("id_token signature or claims invalid: {0}")]
    IdTokenInvalid(String),
    #[error("provider returned HTTP {status}: {body}")]
    Http { status: u16, body: String },
    #[error("network error: {0}")]
    Network(String),
    #[error("rate limited; retry after {retry_after_secs:?} s")]
    RateLimited { retry_after_secs: Option<u64> },
    #[error("refresh token revoked by provider; user must re-link")]
    RefreshRevoked,
    #[error("unsupported operation: {0}")]
    Unsupported(&'static str),
    #[error("internal: {0}")]
    Internal(String),
}
```

### Trait design choices, justified

- **Provider is small.** Four `async` methods that each wrap one HTTPS call, plus a pure URL
  builder. All the heavy lifting — PKCE generation, loopback server, vault persistence —
  lives in the non-trait `OAuthFlow` orchestrator below, so adding a future fifth provider
  means implementing four methods, not reimplementing the whole dance.
- **`TokenSet` uses `SecretString` for tokens.** Same discipline as design 03: zeroize on drop,
  redact in `Debug`. Never let a token land in a plain `String` outside the vault.
- **`ProviderError::RefreshRevoked` is distinct from `Http`.** Callers need to special-case it
  (prompt user to re-link); a generic 400 from `Http` wouldn't be actionable.
- **`revoke` has a default impl returning `Unsupported`.** Matches reality: Meta's graph token
  revocation differs from Google's `/revoke`; Apple has no public revocation endpoint in most
  flows. Callers treat `Unsupported` from `revoke` as non-fatal.

## Flow orchestrator (non-trait, in `core::oauth::flow`)

The orchestrator owns the ceremony. Providers don't know about the vault, the keychain, or
the loopback server; the orchestrator knows about all three.

```rust
pub struct OAuthFlow<'a> {
    provider: &'a dyn Provider,
    vault: &'a Vault,
    keychain: &'a dyn SecretStore,
    http: &'a reqwest::Client,       // pre-configured with rustls + cert pins
    server_config: LoopbackConfig,
}

impl<'a> OAuthFlow<'a> {
    pub async fn run(
        self,
        open_browser: impl FnOnce(&Url) -> Result<()>,
    ) -> Result<LinkedEmail, OAuthFlowError> {
        // 1. Start loopback server on 127.0.0.1:0 (kernel assigns port).
        let server = LoopbackServer::start(&self.server_config).await?;

        // 2. Generate PKCE verifier + state + optional nonce.
        let verifier = PkceVerifier::generate();
        let challenge = verifier.s256_challenge();
        let state = OAuthState::new_with_port(server.port());
        let nonce = if self.provider.requires_oidc() { Some(Nonce::generate()) } else { None };

        // 3. Persist OAuth state row in vault (so a crash doesn't orphan an in-flight flow).
        self.vault.insert_oauth_state(NewOAuthState {
            state: state.to_string(),
            provider: self.provider.id(),
            code_verifier: verifier.as_str().into(),
            nonce: nonce.as_ref().map(Nonce::to_string),
            loopback_port: server.port(),
            expires_at: now() + 600,  // 10 min
        }).await?;

        // 4. Build authorization URL and hand to the caller to open.
        let url = self.provider.authorization_url(&AuthRequestParams {
            client_id: self.provider.client_id(),
            redirect_uri: self.provider.redirect_uri_for(server.port()),
            scopes: self.provider.default_scopes(),
            state: state.as_str(),
            code_challenge: challenge.as_str(),
            nonce: nonce.as_ref().map(|n| n.as_str()),
            extra: &[],
        });
        open_browser(&url)?;

        // 5. Await the loopback callback (timeout = 10 min).
        let callback = server.wait_for_callback(state.as_str(), Duration::from_secs(600)).await?;

        // 6. Consume the vault row atomically (protects against replay).
        let persisted = self.vault.consume_oauth_state(state.as_str()).await?;

        // 7. Exchange code for tokens.
        let tokens = self.provider.exchange_code(CodeExchangeParams {
            code: &callback.code,
            redirect_uri: self.provider.redirect_uri_for(server.port()),
            code_verifier: persisted.code_verifier.as_str(),
            expected_nonce: persisted.nonce.as_deref(),
        }).await?;

        // 8. Pull userinfo and persist LinkedEmail.
        let info = self.provider.userinfo(&tokens.access_token).await?;
        let linked = self.vault.add_linked_email(NewLinkedEmail {
            email: info.email,
            provider: self.provider.id(),
            provider_user_id: Some(info.provider_user_id),
            access_token: Some(tokens.access_token.clone()),
            refresh_token: tokens.refresh_token.clone(),
            token_expires_at: tokens.expires_at,
            scopes: tokens.granted_scopes.into(),
            is_verified: info.email_verified,
        }).await?;

        Ok(linked)
    }
}
```

### Loopback server

`crates/core/src/oauth/loopback.rs`. Tiny embedded HTTP on `127.0.0.1:0`. Two implementation
choices:

- **axum** — well-known, ergonomic, but pulls in hyper + tower.
- **hyper directly** — smaller dep; we only need one GET handler.

**Decision:** `hyper` directly. The full server is ~100 lines; axum would be the tail wagging
the dog. We don't get features we need from axum (no routing complexity, no extractors). If
future flows need more, revisit.

Properties:

- Binds `SocketAddr::from(([127, 0, 0, 1], 0))` — kernel-assigned port, loopback-only.
- **Never** binds `0.0.0.0`. Enforced in the server code with a compile-time-comment + a
  runtime `assert!` on `listener.local_addr()?.ip().is_loopback()`.
- Single-shot: accepts one request, validates the `state` parameter exactly, and shuts down.
  No `/callback` handler lingers after the flow completes.
- Response to the browser: a small HTML page saying "You can close this window." Renders
  offline; no external assets.
- Timeout: caller supplies (10 min for interactive flows).

### PKCE + state + nonce generation

```rust
pub struct PkceVerifier(SecretString);  // 43–128 random b64url chars per RFC 7636

impl PkceVerifier {
    pub fn generate() -> Self {
        let mut bytes = [0u8; 32];
        OsRng.fill_bytes(&mut bytes);
        Self(SecretString::from(b64url_encode(&bytes)))
    }
    pub fn s256_challenge(&self) -> PkceChallenge {
        PkceChallenge(b64url_encode(&sha256(self.0.expose_secret().as_bytes())))
    }
}

pub struct OAuthState(String);  // b64url(16 random bytes) + ":" + port.to_string() for Apple routing

impl OAuthState {
    pub fn new_with_port(port: u16) -> Self {
        let mut bytes = [0u8; 16];
        OsRng.fill_bytes(&mut bytes);
        Self(format!("{}:{port}", b64url_encode(&bytes)))
    }
}

pub struct Nonce(String);

impl Nonce {
    pub fn generate() -> Self {
        let mut bytes = [0u8; 16];
        OsRng.fill_bytes(&mut bytes);
        Self(b64url_encode(&bytes))
    }
}
```

- `OsRng` everywhere (`rand_core::OsRng`), never `thread_rng()`.
- b64url encoding without padding per RFC 7636 §4.1 and §4.2.
- **State format is provider-agnostic.** The `:port` suffix matters for Apple (the Worker
  parses it) but also serves as a free diagnostic for the other three.

## Per-provider implementations

### Google

- Endpoints: `https://accounts.google.com/o/oauth2/v2/auth` (authz), `https://oauth2.googleapis.com/token`
  (token), `https://openidconnect.googleapis.com/v1/userinfo`.
- Scopes (default set): `openid`, `email`, `profile`, `https://www.googleapis.com/auth/userinfo.email`.
  Gmail API scopes (`https://mail.google.com/` or narrower) are appended per-flow when the scan
  feature needs them; not granted at link time.
- OIDC: yes. `id_token` is a JWT signed by Google; validate against JWKS at
  `https://www.googleapis.com/oauth2/v3/certs`. Cache JWKS with respect to the HTTP response's
  `max-age`; re-fetch on signature-verify failure only.
- **Refresh token semantics:** Google only returns a refresh token when `access_type=offline`
  AND `prompt=consent` on first authorization. Subsequent logins without `prompt=consent` will
  return `access_token` only. Ensure default params include both.
- Revocation: `POST https://oauth2.googleapis.com/revoke` with the access or refresh token.

### Microsoft (post-flow-switch)

- Endpoints: `https://login.microsoftonline.com/common/oauth2/v2.0/authorize` (authz),
  `https://login.microsoftonline.com/common/oauth2/v2.0/token` (token),
  `https://graph.microsoft.com/v1.0/me` (userinfo — Graph, not OIDC userinfo).
- Scopes (default): `openid`, `email`, `profile`, `offline_access`, plus Graph scopes needed for
  the scan feature (`User.Read` at a minimum; `Mail.Read` when linking for scanning).
- OIDC: yes. `id_token` signed by the tenant; validate against JWKS at
  `https://login.microsoftonline.com/common/discovery/v2.0/keys`.
- **Flow switch:** previously used device-code flow because it avoids having to register
  a redirect URI with Entra. For loopback+PKCE to work, the Entra app registration must
  declare `http://localhost` and `http://127.0.0.1` as Reply URLs for public clients. This is
  a portal setting, not code. Verified via the Phase 0 spike list in
  `docs/quality-gates.md §1`.
- **Fallback:** if a corporate tenant restricts loopback, device-code remains wired as a
  backup Provider impl (gated behind a config flag, off by default). Documented in-app: "If
  you see an AADSTS700016 / reply-URL-mismatch error, your organization may require device-code
  mode; contact your IT."
- Revocation: `POST https://login.microsoftonline.com/common/oauth2/v2.0/logout?post_logout_redirect_uri=…`
  is session-level. Per-token revocation requires Graph subscription deletion; not portable.
  Our `revoke` returns `Unsupported`; we delete the vault row and call it a day.

### Apple (via `dlopro.com` Worker relay)

The most complex of the four. Two specific reasons it diverges from the template:

#### Apple-issued client secret is a signed JWT, not a string

- **Signing key**: an ECDSA P-256 private key (`.p8` file) Apple issues at app-registration time.
  Current codebase reads it from `APPLE_PRIVATE_KEY_PATH` or `APPLE_PRIVATE_KEY` env var
  ([account_hub/config.py](../../account_hub/config.py)).
- **Desktop migration**: at first Apple-flow run, the user imports the `.p8` file; core reads
  the bytes, persists them in the OS keychain under `SecretKey::APPLE_CLIENT_SECRET_KEY`, and
  offers to shred the source file. Subsequent runs load from the keychain. File/env fallback is
  supported for dev builds only, disabled at release.
- **JWT shape** (built fresh per token request; short expiry):
  ```
  header  = { alg: "ES256", kid: "<apple-issued-key-id>" }
  payload = {
    iss: "<apple-team-id>",
    iat: <now>,
    exp: <now + 180>,        // Apple permits up to 6 months; we use 3 min
    aud: "https://appleid.apple.com",
    sub: "<apple-client-id>",
  }
  ```
  Sign with ECDSA P-256, DER encoding per RFC 7515. The signed JWT is submitted as
  `client_secret` in the token-exchange request.
- **Why short expiry:** if the signed JWT ever leaks (logs, stack traces), the window of abuse
  is bounded. Apple accepts anything up to 6 months; we pay the micro-cost of generating fresh
  JWTs per request for that reduction in blast radius.

#### Apple requires a public HTTPS callback; we route through the Worker

- Apple's web-auth services do not accept `http://127.0.0.1` as a redirect URI — it must be
  publicly reachable HTTPS. The Worker at `https://dlopro.com/callback` is our relay:
  1. Client generates `state = b64url(random) || ":" || port`.
  2. Client opens browser to Apple with `redirect_uri=https://dlopro.com/callback`.
  3. User authorizes.
  4. Apple redirects to `https://dlopro.com/callback?code=…&state=…`.
  5. Worker parses `state`, extracts `port`.
  6. Worker issues `302` to `http://127.0.0.1:<port>/callback?code=…&state=…`.
  7. Client's loopback server captures the callback.
- **Cert pinning on `dlopro.com`.** The `reqwest` client used for Apple traffic has the Worker's
  cert pinned at compile time. An attacker who somehow MITMs `dlopro.com` with a different cert
  does not get accepted. The cert chain lives in a constant array inside `core::oauth::apple`.
- **State is validated twice:** by the Worker (it needs the port to route) and by the loopback
  server (it matches against the vault-persisted state). Tampering at either step fails.
- **Threat: compromised Worker deploy key.** An attacker with the Worker's Cloudflare token
  could redirect the Apple callback somewhere else. Mitigation: Worker deploys are gated on a
  required-reviewer GitHub Environment in the `accounthub-oauth-relay` repo (tracked in its
  own quality gates, not here).

Endpoints:

- Authorization: `https://appleid.apple.com/auth/authorize` (query params: `response_type=code`,
  `response_mode=query`, `scope=name%20email`, `state`, `nonce`, `client_id`, `redirect_uri`).
- Token: `https://appleid.apple.com/auth/token`.
- JWKS: `https://appleid.apple.com/auth/keys`.
- Userinfo: **there is none.** Apple returns an `id_token` with `email` + `email_verified`
  claims; our `userinfo()` for this provider decodes the `id_token` rather than hitting an endpoint.
  Apple only includes name/email claims on the *first* authorization (Apple's "hide my email"
  feature means subsequent logins have fewer claims) — we persist whatever we get the first time.

Revocation: `POST https://appleid.apple.com/auth/revoke`. Implemented; called on unlink.

### Meta (Facebook)

- Endpoints: `https://www.facebook.com/v18.0/dialog/oauth` (authz),
  `https://graph.facebook.com/v18.0/oauth/access_token` (token),
  `https://graph.facebook.com/v18.0/me?fields=id,name,email` (userinfo).
- OIDC: no. Meta has an OIDC mode (`scope=openid`) but delivers non-standard `id_token` claims
  we'd have to special-case; cleaner to skip OIDC and hit `/me` instead.
- Scopes (default): `email`, `public_profile`. Scan-specific scopes added per-flow.
- Refresh tokens: Meta does not use the standard refresh-token dance. Instead, it exchanges
  short-lived (~2h) access tokens for long-lived (~60d) access tokens via the same token
  endpoint with `grant_type=fb_exchange_token`. Our `refresh()` impl for Meta does this
  long-lived-token exchange and treats the result as the new access token.
- Revocation: `DELETE https://graph.facebook.com/<user-id>/permissions` (requires a valid
  access token). Called on unlink.

## Token lifecycle

### Refresh scheduling

A background task running inside the GUI process (and the CLI when it's a long-running command)
refreshes tokens before they expire. Algorithm:

```
for each LinkedEmail where token_expires_at is not null:
    if token_expires_at - now < 300 seconds (5 min early):
        try provider.refresh(refresh_token)
        on success: vault.update_tokens(id, new_tokens)
        on RefreshRevoked: mark linked_email as needing re-link; notify user
        on network / rate-limit: back off, retry later
    sleep until next wake-up (min 60s, max 10 min)
```

Notes:

- Refresh scheduling is orthogonal to the OAuth flow orchestrator. It lives in `core::oauth::refresh`
  and runs as a `tokio::spawn` task owned by `UnlockedSession`.
- On master-password re-lock or app close, the scheduler is cancelled cleanly.
- Meta uses its own long-lived-token exchange path via the same `refresh()` trait method;
  the scheduler treats it uniformly.
- HIBP integration and mail scans use `access_token` as-is; if it's expired, they trigger an
  on-demand refresh before retrying the underlying call. Belt-and-braces vs. the scheduler.

### Refresh-token rotation

Google and Microsoft may rotate refresh tokens (return a new one on refresh). We unconditionally
overwrite the stored refresh token with whatever comes back, even if unchanged. Apple doesn't
rotate refresh tokens in the same way; we preserve the existing value if the response omits it.
Meta has no refresh token concept.

### Token revocation on unlink

On `vault.remove_linked_email(id)`:

1. `provider.revoke(access_token, Access)` — best effort; ignore `Unsupported`.
2. `provider.revoke(refresh_token, Refresh)` — same.
3. `vault.remove_linked_email(id)` — delete vault row; cascade drops discovered_accounts
   (via `ON DELETE SET NULL` on linked_email_id), preserving history.

Revocation failures are logged at `warn` but don't block deletion — we've already lost the
ability to do anything useful with the tokens once the user said "unlink."

## HTTP client configuration

All provider traffic runs through one shared `reqwest::Client` configured as:

- **`rustls` backend** (not `native-tls`). Avoids pulling in OS cert-store surprises;
  deterministic across the three target OSes.
- **Root store:** `webpki-roots` (Mozilla's CA bundle). Updated with dep bumps.
- **Cert pinning for `dlopro.com`**: implemented via a custom `rustls::client::ServerCertVerifier`
  that checks a SHA-256 pin of the leaf cert's SPKI in addition to the webpki path. The pin
  array is a compile-time constant. Updated when the Worker's cert rotates; ADR entry each time.
- **Timeout:** 30s per request; 5 min overall per flow (token exchange can be slow on first
  provider contact).
- **User-Agent:** `AccountHub/<version> (rustls; <os>)`.

## Testing strategy

Per `docs/quality-gates.md §3`:

### Unit tests (in-crate)

- **PKCE verifier / challenge:** fixed-input round-trip (RFC 7636 examples).
- **State construction / parsing:** `OAuthState::new_with_port(p).port() == p`.
- **URL builders:** parametrised tests per provider, asserting exact query-param set.
- **JWT verification helpers:** Google/Microsoft/Apple `id_token` decoding against fixtures.

### Integration tests (`crates/core/tests/oauth_integration.rs`)

- **Fake provider server** via `axum` or `wiremock`. Serves fixed responses; runs on
  127.0.0.1 with a self-signed cert we accept only in tests.
- Full flow per provider: start_authorization → fake browser hits callback → exchange → userinfo
  → vault row present.
- **Negative cases:**
  - State mismatch → `StateMismatch` error, no vault row.
  - Expired `oauth_state` vault row (set `expires_at` in the past) → consume_oauth_state fails.
  - Malformed `id_token` → `IdTokenInvalid`.
  - Refresh-token 400 Bad Request from fake server with `error=invalid_grant` → `RefreshRevoked`.
- **Apple-specific:** JWT client secret signing against a fixture ECDSA P-256 key; verify the
  JWT using the same key's public half; check `iss`/`aud`/`iat`/`exp` claims.

### Fuzz (`cargo-fuzz`)

- `oauth::flow::parse_callback_params` — arbitrary bytes as the callback query string. Must
  never panic.
- `oauth::state::parse(&str)` — arbitrary state strings. Must never panic; must reject
  non-UTF-8 or missing port.
- JWT claims parser — the same way.

### Manual verification (per release)

Real provider round-trip, each of Google, Microsoft, Apple, Meta, on each of macOS, Windows,
Linux. Documented in `docs/release-checklist.md` (to be written before Phase 4).

### What CI cannot test

- Real provider responses (no credentials in CI).
- Real Apple Worker traffic (requires the live Worker; relay testing done in the
  `accounthub-oauth-relay` repo's own CI).
- Biometric-gated keychain access for Apple private key loading.

All three are acknowledged gaps, mitigated by manual release verification.

## Security properties

With the design above, the following hold:

1. **Authorization code can only be used once.** `consume_oauth_state` deletes the vault row
   as part of the SELECT+DELETE; a replay with the same code+state finds no row.
2. **PKCE prevents code-interception attacks.** An attacker who captures the auth code (e.g.
   local malware sniffing loopback) still can't redeem it without the verifier, which never
   leaves the local process.
3. **State binds the browser-side flow to this process.** Includes the loopback port,
   validated both by the Worker (Apple) and locally.
4. **OIDC `nonce` prevents id_token replay.** Generated per flow, validated against the
   `id_token.nonce` claim. Missing or mismatched → `IdTokenInvalid`.
5. **Apple private key stays in the OS keychain.** Only in-memory when signing a JWT (~10ms
   window). Zeroized after.
6. **Apple Worker leg is cert-pinned.** A compromised CA does not compromise the relay.
7. **Access tokens never touch disk unencrypted.** Stored in the SQLCipher vault; passed
   through `SecretString` everywhere; redacted in `Debug`.
8. **Refresh scheduling runs under the unlocked-session guard.** App locks → scheduler stops;
   app closes → tokens stay encrypted at rest.
9. **Revocation is best-effort but not silent.** Failures logged at `warn` so the user can
   spot e.g. "Google revocation 400" and know to clean up manually on account.google.com/security.

What the design does **not** protect against:

- A malicious extension in the user's browser that captures the redirect response. Out of
  scope; addressable only by not delegating to the browser, which would break every flow.
- A compromised provider (e.g. Google-issued malicious `id_token`). We trust the providers;
  signature and JWKS verification is the strongest defence available without on-device MFA.
- Phishing the user. The browser's address bar is the only signal; UI does not try to prevent
  the user from authorizing a fake provider page.

## Open questions

### 1. Microsoft device-code fallback: toggle name + where to surface

The design wires device-code as a config-gated fallback, but doesn't specify whether the toggle
is per-user, per-install, or per-link. Lean: per-link (user linking a work account picks
device-code for that email only). Resolve in Phase 3 when the flow actually lights up.

### 2. Apple `.p8` import UX

First-Apple-flow onboarding needs a file-picker + a "shred after import" checkbox. The copy
and the shred mechanism (secure overwrite? unlink?) are non-trivial UX questions — revisit
with whoever's designing the onboarding flow.

### 3. `hyper` vs. `axum` for loopback

Picked `hyper` above; if future flows grow (e.g. a "re-auth" flow that needs multiple endpoints),
revisit. Mark as a deliberate trade-off, not a permanent refusal.

### 4. Concurrent flows

Can two OAuth flows run simultaneously (e.g. user is linking Google and Meta in two browser
tabs)? Today: yes, each gets its own loopback port and its own vault state row. The loopback
server is per-flow, not global. Document this; no code constraint needed.

### 5. JWKS caching strategy

The design says "cache JWKS per HTTP response max-age, refetch on signature-verify failure
only." But in practice, providers rotate keys rarely and poll-on-failure is adequate. Explicit
policy: cache JWKS in-memory for the process lifetime; on `IdTokenInvalid` caused by an
unknown `kid`, refetch exactly once before failing the flow.

## Consequences

**Easier:**
- Adding a fifth provider (when the schema `CHECK` lets us) is four trait methods plus a module.
- Provider traffic is all through one `reqwest` client → one place to add telemetry, metrics,
  or request tracing.
- Fake-provider integration tests cover the full orchestration without network.

**Harder:**
- Four providers means four sets of quirks. The trait hides them, but the per-provider modules
  are non-trivial (Apple especially). Accepted.
- Apple Worker coupling is a permanent cross-repo concern. Any change to the Worker's response
  shape (e.g. adding a CSP header) must keep the redirect contract intact. Handled via the
  Worker's own integration tests; documented cross-reference in `accounthub-oauth-relay`'s
  README.

**New risks:**
- `webpki-roots` lag behind real CA changes. Mitigation: dep bumps at a regular cadence, watched
  via `cargo-audit`.
- Apple cert-pin rotation: when the Worker's cert renews (annual at most), we ship an app
  update with the new pin. A pin change without a corresponding app release locks out Apple
  flows. Mitigation: rollout process documented in the Worker repo; app ships *both* old and
  new pin during rotation windows.

## Dependencies to add (Phase 3)

```toml
# crates/core/Cargo.toml additions when the OAuth module lands
[dependencies]
reqwest = { version = "0.12", default-features = false, features = ["rustls-tls", "json"] }
rustls = "0.23"
webpki-roots = "0.26"
url = "2"
serde_urlencoded = "0.7"
jsonwebtoken = "9"           # for OIDC id_token verification + Apple JWT signing
p256 = { version = "0.13", features = ["ecdsa", "pkcs8"] }   # ECDSA P-256 for Apple
rand_core = { version = "0.6", features = ["getrandom"] }
sha2 = "0.10"
base64 = "0.22"
hyper = { version = "1", features = ["http1", "server"] }
http-body-util = "0.1"
bytes = "1"
```

Exact versions pinned in `Cargo.lock` on first add, per quality-gates §7.

## Review gates

Any PR touching `crates/core/src/oauth/` — especially `apple.rs` and the cert-pin constants —
requires two reviewers. Non-negotiable given the blast radius of a broken Apple flow or a
stale pin.

## ADR

`docs/adr/0004-oauth-providers.md` captures the five load-bearing decisions:

1. Unified `Provider` trait; orchestration outside the trait.
2. Microsoft switched from device-code to loopback+PKCE (with device-code as a documented
   fallback).
3. Apple client secret signed as a fresh short-lived JWT per request; private key in OS keychain.
4. Apple Worker relay cert-pinned; state carries the loopback port explicitly.
5. `hyper` directly, not `axum`, for the loopback server.

## References

- Design 01: `docs/design/01-workspace-architecture.md` — where `core::oauth` lives.
- Design 02: `docs/design/02-keychain-abstraction.md` — Apple private key storage.
- Design 03: `docs/design/03-vault.md` — `oauth_state` + `linked_email` persistence.
- Threat model: `docs/desktop-threat-model.md` — assets A2/A4/A6; adversaries T1/T6/T7.
- Refined plan: `~/.claude/plans/woolly-coalescing-dragon.md` — Phase 3 scope + MS flow switch.
- Current Python impl: [account_hub/services/oauth_service.py](../../account_hub/services/oauth_service.py),
  [account_hub/oauth/](../../account_hub/oauth/).
- Apple Worker: separate repo `accounthub-oauth-relay` (post-Pre-Phase-0 extraction).
- RFC 7636 (PKCE), RFC 7515/7517/7518/7519 (JOSE / JWT), RFC 6749 (OAuth 2.0).
