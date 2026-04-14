# 0004. OAuth providers: unified trait + MS flow switch + Apple JWT client secret + relay pinning

**Status:** Accepted
**Date:** 2026-04-13
**Supersedes:** —
**Superseded by:** —

## Context

Design doc `docs/design/04-oauth-providers.md` ports the four OAuth integrations (Google,
Microsoft, Apple, Meta) from the current Python codebase into Rust and makes several
decisions that are easy to regret later. Those decisions are captured here.

## Decisions

### D1 — Unified `Provider` trait; orchestration lives outside the trait

Four `async` methods (`authorization_url`, `exchange_code`, `refresh`, `userinfo`) plus an
optional `revoke`. All the common ceremony — PKCE/state/nonce generation, loopback server,
vault persistence, refresh scheduling — lives in a non-trait `OAuthFlow` orchestrator and in
sibling modules under `core::oauth::`. Providers are narrow; the trait is stable.

### D2 — Microsoft switched from device-code to loopback+PKCE

The existing Python codebase uses device-code for Microsoft; the desktop port uses
loopback+PKCE for uniformity with Google/Apple/Meta. Consequence: Entra app registration must
whitelist `http://localhost` and `http://127.0.0.1` as Reply URLs for public clients — a
portal setting, verified during Phase 0 per `docs/quality-gates.md §1`.

Device-code remains implemented as a dead-but-documented fallback (config flag off by
default). It re-engages when corp tenants restrict loopback URIs.

### D3 — Apple client secret is a fresh short-lived ES256-signed JWT per request

The Apple `.p8` private key is loaded from the OS keychain (Phase 3 migration from
file/env), held in memory only while signing, and zeroized after. JWT `exp` is set to now + 3
minutes (Apple allows up to 6 months; we pay no meaningful cost for the stricter bound and
bound any leak's blast radius).

### D4 — Apple Worker relay is cert-pinned; state carries the loopback port

The Worker at `https://dlopro.com/callback` is the sole reason Apple OAuth works in a desktop
app (Apple rejects `http://127.0.0.1` as a redirect URI). The `reqwest` client used for Apple
traffic verifies the Worker's SHA-256 SPKI pin in addition to the webpki path. The OAuth
`state` includes `:<port>` so the Worker can route the callback back to the exact loopback
listener that initiated the flow.

### D5 — `hyper` directly for the loopback server, not `axum`

The single-endpoint, single-shot server is ~100 lines of `hyper` + `http-body-util`. `axum`
would add routing / extractor machinery we don't need. Revisit if future flows grow.

## Consequences

**Easier:**
- Adding a future fifth provider is four trait methods + a module (plus a vault migration
  because the `provider` CHECK constraint is closed).
- Fake-provider tests cover the whole flow without hitting real endpoints.
- One `reqwest::Client` shared across providers = one place to wire telemetry, tracing, or
  per-host timeouts.

**Harder:**
- Microsoft's device-code path stays in the codebase as a fallback, which adds a second
  state machine under the same `Provider` impl. Accepted: corp-tenant reality makes the cost
  worth it.
- Apple's cert-pin rotation (annual at most) requires app-release coordination; during
  rotation windows we ship both old and new pin simultaneously. Documented in the Worker
  repo's release process.
- `hyper` at the server layer is lower-level than `axum`; the loopback server is ~100 lines
  of explicit state machine vs. a handful of axum handler fns. Accepted for the dep savings.

**New risks:**
- Apple private key stored in OS keychain = same single-point-of-failure as the vault KEK
  (design 02). Both fall if the user's OS session falls. Accepted as the realistic security
  posture.
- Apple Worker is a remote dependency; our Apple flow is down if the Worker is. Mitigation:
  `accounthub-oauth-relay` repo owns its own uptime; app surfaces a specific "Apple temporarily
  unavailable" error and lets the other three providers work unaffected.
- If a future Microsoft tenant silently disables loopback Reply URLs after we've linked, the
  refresh flow continues working (the refresh token endpoint is the same) but re-linking
  requires falling back to device-code. Code path exists; surface the fallback prompt clearly.

## Alternatives considered

### (A) Provider trait covers the entire flow, including loopback server
- **Pros:** trait is the only abstraction; no separate orchestrator.
- **Cons:** every Provider impl re-implements identical scaffolding; can't factor out cert
  pinning or vault persistence cleanly; the trait becomes huge (10+ methods).
- **Verdict:** rejected. Narrow trait + external orchestrator is the cleaner split.

### (B) Keep Microsoft on device-code
- **Pros:** matches current Python; no Entra portal change.
- **Cons:** inconsistent UX (user types a code for MS only); inconsistent code path (separate
  state machine, separate error handling, separate polling loop); prevents a uniform
  auto-refresh scheduler.
- **Verdict:** rejected. Loopback+PKCE is the default; device-code is a documented backup for
  corp tenants that restrict it.

### (C) Long-lived Apple JWT client secret (e.g. 6 months)
- **Pros:** fewer signing ops.
- **Cons:** JWT stored anywhere for 6 months is a 6-month window for abuse on leak; we sign
  on-demand anyway because the private key is in the keychain; per-request signing is
  nanoseconds on modern hardware.
- **Verdict:** rejected. 3-minute JWTs are the sensible default for a local-host client.

### (D) No cert pinning for the Apple Worker; trust webpki roots only
- **Pros:** no pin-rotation process; simpler HTTP client.
- **Cons:** a compromised CA can MITM the Worker response and redirect the Apple callback
  anywhere; the Worker is a trust anchor we control and the pin is a cheap additional
  verification.
- **Verdict:** rejected. Cert pinning is one `rustls::ServerCertVerifier` and buys meaningful
  defence-in-depth for a credential-adjacent flow.

### (E) `axum` for the loopback server
- **Pros:** ergonomic; nicer routing, extractors, error handling.
- **Cons:** big dep tree for a single GET handler that runs once and shuts down. We don't
  want the routing; we don't want the tower middleware stack.
- **Verdict:** rejected for v1. Revisit if we ever need multi-endpoint flows from the
  loopback server.

## References

- Design spec: `docs/design/04-oauth-providers.md`
- Keychain: `docs/design/02-keychain-abstraction.md` + ADR 0002 (Apple private key storage)
- Vault: `docs/design/03-vault.md` + ADR 0003 (oauth_state + linked_email persistence)
- Threat model: `docs/desktop-threat-model.md` (A2, A4, A6, A7; T1, T6, T7)
- Refined plan: `~/.claude/plans/woolly-coalescing-dragon.md` (Phase 3 scope)
- Current Python impls: `account_hub/services/oauth_service.py`, `account_hub/oauth/`
- Worker repo (post-extraction): `accounthub-oauth-relay`
- RFCs: 7636 (PKCE), 7515/7517/7518/7519 (JOSE/JWT), 6749 (OAuth 2.0)
