# ACCOUNT_HUB Desktop — Threat Model

> Phase 0 deliverable. Reviewed at Phase 0 close; revised at each phase boundary.
> Companion to the migration plan (`~/.claude/plans/woolly-coalescing-dragon.md`) and
> quality gates (`docs/quality-gates.md`).

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
| A4 | **Apple private key** (OAuth client secret signer) | Allows impersonation of the ACCOUNT_HUB app to Apple; blast radius = Apple OAuth only but would allow account takeover of any Apple-linked user. |
| A5 | **Discovered-account catalog** (vault contents) | Reveals user's online footprint; sensitive even without live tokens. |
| A6 | **Cloudflare Worker deploy key** | Compromise allows attacker to redirect Apple OAuth callbacks to their own listener → phishing + token theft. |
| A7 | **App signing keys** (Apple Developer ID, Windows EV, GPG) | Compromise allows attacker to ship malicious updates that the updater will trust. |
| A8 | **Ed25519 auto-updater key** | Same blast radius as A7 but specific to the Tauri updater channel. |

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

### Tampering

| Threat | Mitigation |
|---|---|
| T3 modifies vault.db on disk | SQLCipher HMAC detects tampering; open fails with "file is not a database". |
| T3 modifies app binary to leak KEK | App binary signed; macOS Gatekeeper + Windows SmartScreen + Linux GPG verification detects tampering at launch. |
| T5 ships backdoored dependency | `cargo-audit`, `cargo-deny`, `cargo-vet`, `osv-scanner` in CI; all deps pinned by hash; SBOM per release. |
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
| T3 escalates via Tauri bug to OS level | Tauri capabilities minimized; no blanket `fs:allow-*`; only specific paths granted. Follow Tauri CVE feed. |
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
