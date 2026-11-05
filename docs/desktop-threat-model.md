# ACCOUNT_HUB Desktop — Threat Model

> Phase 0 deliverable. Reviewed at Phase 0 close; revised at each phase boundary.
> Companion to the quality gates (`docs/quality-gates.md`) and design docs 01–05
> (`docs/design/`). The original migration plan lived outside the repo and no longer
> exists; the phase ledger in quality-gates §9 is the plan of record.
>
> **Audience (decided 2026-11-05):** ACCOUNT_HUB is a personal tool for its author and
> for self-hosters. Each person runs their own build with their own provider credentials.
> It is not distributed to end users with shared credentials; if that changes, A4, A6 and
> T7 must be re-modelled before any release.

## Scope

This document covers the **end-state** desktop architecture: Tauri 2 shell, Rust core, SQLCipher
vault, OS-keychain-wrapped KEK, Cloudflare Worker relay for Apple OAuth, custom URI scheme for
deep links. Transitional Phase 1–2 states (Python sidecar, hosted Railway service) have a subset
of the same threats plus migration-specific ones called out inline.

## Assets — what we're protecting (ranked by severity of loss)

| # | Asset | Why it matters |
|---|---|---|
| A1 | **Vault encryption key (KEK)** | Unlocks everything. Compromise = full OAuth token exposure → attacker can read user's mail, modify Meta account, etc. |
| A2 | **OAuth access + refresh tokens** | Per-provider blast radius; refresh tokens allow persistent access even after password changes. |
| A3 | **Master password (in memory, pre-zeroize)** | Derives KEK. Brief exposure window during unlock. |
| A4 | **Apple private key** (OAuth client secret signer) | Each self-hoster's **own** `.p8`, issued by their own Apple developer account and imported into their OS keychain (design 04). It never ships with the app and is never shared between users. Compromise allows impersonation of that person's Apple client ID; blast radius = their own Apple OAuth registration. |
| A5 | **Discovered-account catalog** (vault contents) | Reveals user's online footprint; sensitive even without live tokens. |
| A6 | **Cloudflare Worker deploy key** | Compromise allows attacker to redirect Apple OAuth callbacks to their own listener → phishing + token theft. |
| A7 | **App signing keys** (Apple Developer ID, Windows EV, GPG) | Compromise allows attacker to ship malicious updates that the updater will trust. |
| A8 | **Ed25519 auto-updater key** | Same blast radius as A7 but specific to the Tauri updater channel. |
| A9 | **`dlopro.com` domain registration** | The Apple OAuth relay lives at `dlopro.com/callback` and Apple redirects the browser there. The domain is owned by the author (confirmed 2026-11-05; distinct from the DLO Pro site at `dlopro.ca`). If the registration lapses, a new owner receives Apple callbacks: Apple sign-in breaks, and the callback URL can serve a phishing page. PKCE and the SPKI pin stop a new owner from redeeming codes or impersonating the relay to the app. Keep on auto-renew with registrar lock. |

## Adversaries — who might want these

| # | Adversary | Capabilities | Plausible motivations |
|---|---|---|---|
| T1 | **Remote network attacker** | MITM on Wi-Fi, DNS poisoning, compromised routes | Steal tokens in transit; phish OAuth flow |
| T2 | **Malicious website the user visits** | Execute JS in the user's browser, trigger OS URL handlers | Hijack `accounthub://` deep links; CSRF the Tauri IPC |
| T3 | **Local malware (non-privileged)** | Read user-level files, snoop processes, read pasteboard | Steal vault file, read master password from pasteboard, dump tokens from live process memory |
| T4 | **Physical access (device unattended)** | Boot from external media; access disk | Read vault file at rest; install keylogger |
| T5 | **Supply-chain attacker** | Compromise a dependency (npm, Cargo) that we consume | Insert backdoor into signed release |
| T6 | **Compromised OAuth provider** | Malicious response from Google/MS/Apple/Meta API | Deliver malformed tokens that trigger parsing bugs; malicious `id_token` claims |
| T7 | **Compromised Cloudflare Worker** | Control over the `dlopro.com/callback` endpoint | Redirect Apple OAuth callbacks to attacker-controlled loopback |
| T8 | **Rogue app also installed** | Register a competing `accounthub://` URI handler | Intercept deep links intended for ACCOUNT_HUB |
| T9 | **Malicious user** (of the user's own machine — shared family device, etc.) | Same as T3 but non-covert | Unlock vault by shoulder-surfing master password |

## Trust boundaries

```
┌───────────────────────────────────────────────────────────────────┐
│ TRUSTED: Rust core process                                        │
│   crates/core: vault, keychain, oauth, mail, hibp                 │
│   --  (A1 KEK held in memory only while unlocked)                 │
│   --  (A3 master password zeroized after KEK derivation)          │
└───────────────────────────────────────────────────────────────────┘
         ▲                                    ▲
         │ IPC (validated)                    │ fs read/write
         │                                    │
┌────────┴──────────┐                  ┌──────┴─────────────────┐
│ SEMI-TRUSTED:     │                  │ DATA AT REST:          │
│ WebView (React)   │                  │ SQLCipher vault.db     │
│ — untrusted input │                  │ (A1 KEK derived from   │
│   at boundary     │                  │  OS keychain entry)    │
└───────────────────┘                  └────────────────────────┘
         ▲                                    ▲
         │ HTTPS (rustls + pinned cert for    │ OS keychain
         │ dlopro.com; webpki roots elsewhere)│ (A1 KEK wrap)
         ▼                                    ▼
┌───────────────────┐                  ┌────────────────────────┐
│ UNTRUSTED:        │                  │ OS-MEDIATED:           │
│ Provider APIs,    │                  │ macOS Keychain /       │
│ CF Worker,        │                  │ Windows Cred Mgr /     │
│ user's network    │                  │ libsecret (Linux)      │
└───────────────────┘                  └────────────────────────┘
```

**Key property:** the WebView is treated as untrusted even though it ships with the app. Every
IPC handler validates its inputs; the Rust core never assumes webview-supplied data is well-formed.

## STRIDE — threats and mitigations

### Spoofing

| Threat | Mitigation |
|---|---|
| T2 spoofs `accounthub://` deep links from a malicious webpage | Deep-link handler verifies a signed nonce for sensitive operations; read-only navigation (e.g. "open settings") is allowed without a nonce. |
| T7 spoofs Apple OAuth callback via compromised Worker | Certificate-pin `dlopro.com` in rustls client config; the Worker is a trusted relay, but its TLS cert is one we control and verify. The OAuth `state` carries both a random nonce AND a port binding the relay must echo. |
| T8 registers a rival `accounthub://` handler | OS-specific mitigation: prefer `LSHandlers` (macOS) / registered AppUserModelID (Windows) / explicit `.desktop` file with app ID (Linux). Document for users that handler collision is detectable. |
| T2 / T3 hits the OAuth loopback callback (`http://127.0.0.1:<port>/callback`, used by Google, Microsoft, Meta and the Apple relay hand-off): a webpage sends a forged request to it, or a local process guesses or races for the port | The listener binds `127.0.0.1:0` only (kernel-assigned port, never `0.0.0.0`), lives for one flow, and accepts one request. A callback is honoured only if `state` matches the value generated for that flow; the code is useless without the PKCE verifier, which never leaves the core process. A forged or replayed callback fails the `state` check and ends the flow with an error, so the worst case is a failed link attempt (DoS), not token theft. Residual: a local process that wins the port *before* the app binds cannot receive the redirect, because the port is chosen at bind time and only then placed in the redirect URI. |

### Tampering

| Threat | Mitigation |
|---|---|
| T3 modifies vault.db on disk | SQLCipher HMAC detects tampering; open fails with "file is not a database". |
| T3 modifies app binary to leak KEK | App binary signed; macOS Gatekeeper + Windows SmartScreen + Linux GPG verification detects tampering at launch. |
| T5 ships backdoored dependency | **In place (CI):** `cargo-audit`, `cargo-deny`, `cargo-vet --locked` and `osv-scanner` for Rust; `npm audit --audit-level=high` and a licence allowlist for `web/` and the root npm lockfile. `Cargo.lock` and the `package-lock.json` files are committed and carry integrity hashes. **Limits:** cargo-vet started from a baseline of exemptions (367 crates trusted as-is on 2026-11-05), so it gates *new and changed* crates, not the existing tree; advisories appear without a code change, so a quiet repo drifts until the next push or a manual run. **Not yet in place:** SBOM per release (lands with the first release build, Phase 1). |
| T5 or a stolen GitHub session pushes an unsigned commit to `main` | `main` requires signed commits, enforced for admins; force-pushes and branch deletion are blocked (branch protection, 2026-11-05). CI is not a required check (Rust CI is path-filtered), so a signed commit can still land red. |
| T5 backdoors auto-updater delivery | Tauri updater verifies Ed25519 signature (A8) before applying; public key pinned at compile time. |

### Repudiation

| Threat | Mitigation |
|---|---|
| User claims they didn't close an account | ClosureRequest records include timestamp + method + user-confirmed flag; stored in vault. Not forensic-grade (user could edit the DB with their own KEK), but matches the threat model — this is a personal tool, not a compliance product. |

### Information disclosure

| Threat | Mitigation |
|---|---|
| T3 reads master password from clipboard | App never copies master password to clipboard; OS secure input field where available. |
| T3 dumps live process memory while unlocked | `zeroize` crate on all secret buffers (master password, KEK, token plaintexts); unused tokens dropped from memory; no swap-to-disk via `mlock` on Linux/macOS. Acknowledge residual risk: a local-malware-with-debugger adversary can read running-process memory regardless. |
| T4 reads vault.db off a powered-off device | Full-file SQLCipher encryption with AES-256; KEK not on disk (stored in OS keychain, which is also disk-encrypted by the OS). |
| T1 sniffs OAuth traffic | `rustls` + webpki; HSTS not applicable client-side but cert validation strict; `dlopro.com` cert-pinned; no wildcard trust. |
| T6 delivers token with malicious claims | OAuth `state` + `nonce` validated on callback; `id_token` signature verified against provider JWKS; `aud` / `iss` / `exp` strictly checked; reject unknown algorithms (`alg=none` banned). |
| User's mail content leaks via crash report | Crash reports opt-in only; scrubber removes paths, query strings, and any buffer containing JSON that resembles a token. Default = crash reports off. |

### Denial of service

| Threat | Mitigation |
|---|---|
| T3 fills vault.db to exhaust disk | SQLite is robust to out-of-space; the app gracefully refuses writes and surfaces the error. No data corruption. |
| T7 takes down the Apple Worker | Apple OAuth is unavailable until the Worker recovers. Other providers unaffected. The Worker has its own uptime story in `accounthub-oauth-relay`. |
| T1 blocks provider APIs | User surfaces the error; no cascading failure — local vault remains accessible. |

### Elevation of privilege

| Threat | Mitigation |
|---|---|
| T2 via webview XSS invokes privileged IPC | Strict CSP; no `eval`, no `unsafe-inline`; all IPC commands validate inputs and require an unlocked-vault state where appropriate. |
| T3 escalates via Tauri bug to OS level | Tauri capabilities minimized; no blanket `fs:allow-*`; only specific paths granted. Follow Tauri CVE feed. The only capability today is `core:default` (`crates/gui/capabilities/default.json`). **That set is defined by Tauri, not by us, and grows with Tauri releases:** 2.10 → 2.12 added `app:supports_multiple_windows`, `tray:set_icon_with_as_template`, `window:activity_name` and `window:scene_identifier` with no change to our file. Review trigger: any diff in `crates/gui/gen/schemas/acl-manifests.json`. Before Phase 3 adds real IPC commands, replace `core:default` with an explicit list. |
| T5 in a dev dep escalates during build | Build runs in an isolated CI environment; release builds from clean tags; no `build.rs` that phones home or writes outside target/. |

## Migration-specific transitional threats (Phase 1 & 2 only)

- **Sidecar loopback exposure (Phase 1):** Python sidecar binds 127.0.0.1 on a kernel-assigned
  random port. Risk: another local process on the same machine could port-scan and hit the
  sidecar's endpoints. Mitigation: Rust shell passes a per-launch shared secret to the sidecar
  via stdin; every IPC call includes the secret; sidecar rejects unauthenticated requests.
  Also: localhost-only bind is enforced in code, not config.
- **Dual storage window (Phase 2):** the frontend speaks `invoke()` for vault operations but
  still uses `fetch('/api/…')` for OAuth + business logic. A coding mistake could persist vault
  data via the sidecar path. Mitigation: distinct function namespaces (`vault.*` vs. `api.*`
  in `web/src/api/`); compile-time lint that forbids `api.*` calls to persist vault data.
- **Schema migration = fresh start:** there's no risk of corrupt-data migration because there's
  no migration at all. Hosted-alpha users re-link providers in the desktop app. Release notes
  make this explicit.

## Residual risks we accept

1. **Master password loss = data loss.** No recovery path. Documented prominently; consider
   adding an optional "recovery code" printable at setup (Bitwarden-style) if users push back.
2. **Local-malware-with-debugger-on-live-process.** We can't fully defeat an adversary with
   PTRACE privilege on an unlocked process. Mitigation is minimized unlock window (auto-lock
   on idle) and OS-level hardening (notarized, sandboxed, hardened runtime on macOS).
3. **User-initiated OS keychain export.** macOS Keychain Access lets the user export their own
   KEK entry; Windows Credential Manager similarly. This is a feature, not a bug — it's the user
   exercising their ownership. But it's a theft vector if T9 coerces the user.
4. **libsecret absence on headless Linux.** CLI falls back to `--keyfile` (age-encrypted keyfile),
   trading OS-keychain protection for filesystem protection. Explicitly documented.

## Review log

| Date | Reviewer | Phase | Notes |
|---|---|---|---|
| 2026-04-13 | — | Phase 0 draft | Initial model |
| 2026-11-05 | Derek (decisions); Claude (cross-check against design docs 01–05 and CI) | Phase 0 close | Decisions: audience is the author and self-hosters, so A4 is each person's own `.p8`; `dlopro.com` is owned by the author and stays the relay domain (new asset A9). Corrections: the supply-chain row claimed cargo-vet and hash-pinning that were not in CI, now added and stated with their limits; SBOM marked as not yet in place; broken link to an out-of-repo plan removed. Additions: loopback-callback threat, signed-commit row, `core:default` growth and its review trigger. Sign-off is the merge of the PR carrying this row. |
