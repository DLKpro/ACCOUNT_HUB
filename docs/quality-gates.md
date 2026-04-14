# Quality Gates — ACCOUNT_HUB Desktop Migration

> Companion to the migration plan at `~/.claude/plans/woolly-coalescing-dragon.md`.
> This is a living document. Every phase adds a row to [§9 Phase Ledger](#9-phase-ledger);
> every rule that gets revised gets an entry in [§10 Revision Log](#10-revision-log).

## Purpose

ACCOUNT_HUB is credential-adjacent — the threat model is closer to 1Password / Bitwarden Desktop
than a typical productivity app. "Done correctly" means:

1. No regression in security posture; measurable improvements in the end-state.
2. Every feature working today works in the Rust app.
3. No scenario where a user's linked accounts disappear or silently corrupt.
4. Each migration phase produces a shippable, rollbackable artifact.
5. No compromised dependency lands in a signed release.

The practices below are the mechanisms that deliver those outcomes.

---

## 1. Risk-first sequencing

Before committing to a phase, spike its thinnest assumptions.

| Spike | Validates | Must happen before |
|---|---|---|
| Tauri 2 + PyInstaller sidecar + sign + notarize on macOS | End-to-end signing chain | Phase 1 macOS alpha |
| Tauri 2 sign + ship on Windows (pre-EV-warmup) | Windows alpha path | Phase 1 Windows alpha |
| Tauri 2 + GPG-signed AppImage on Ubuntu + Fedora | Linux alpha path | Phase 1 Linux alpha |
| `accounthub://` deep-link handler on all three OSes | Custom URI dispatch | Phase 1 deep-link routing |
| Cross-process SQLCipher access (GUI + CLI concurrent, `fs2` advisory lock + WAL) | Multi-process vault safety | Phase 2 vault implementation |
| Entra portal check: loopback+PKCE permitted for public clients on user's tenant | Microsoft flow switch assumption | Phase 3 MS OAuth port |
| Tauri IPC type-sharing with TypeScript frontend (specta or ts-rs) | Contract-test feasibility | Phase 3 frontend cutover |

**Rule:** If a spike invalidates a plan assumption, update the plan before proceeding. Don't
silently route around a broken assumption — update `woolly-coalescing-dragon.md` and log the
change in [§10 Revision Log](#10-revision-log).

## 2. Design-before-code per subsystem

Every subsystem gets a written spec under `docs/design/` **before** implementation begins.
The spec covers:

- Purpose and public API surface (trait signatures, error types, invariants).
- Data ownership and lifecycle (who creates, who destroys, concurrency assumptions).
- Test plan (unit, property, integration — named tests, not prose).
- Security properties (what an attacker can and cannot do).
- Open questions (explicitly listed; resolved before code review).

Subsystem design order (ground up; each constrains the next):

1. ✅ `docs/design/01-workspace-architecture.md` — Cargo workspace + crate boundaries (accepted, ADR 0001)
2. ✅ `docs/design/02-keychain-abstraction.md` — `SecretStore` trait + per-OS impls + keyfile fallback (accepted, ADR 0002)
3. ✅ `docs/design/03-vault.md` — SQLCipher schema, KEK wrap, WAL, multi-process access (accepted, ADR 0003)
4. ✅ `docs/design/04-oauth-providers.md` — `Provider` trait, loopback+PKCE, Apple relay, token lifecycle (accepted, ADR 0004)
5. ✅ `docs/design/05-tauri-ipc.md` — command shapes, error envelope, type-sharing with frontend (accepted, ADR 0005)

**All five ground-up design docs accepted.** Phase 2/3 implementation work is unblocked on
the design-spec front; only Phase 0 procurement (Apple Developer ID, Windows EV cert) and
Tauri-app scaffolding remain before Phase 1 can start.

Design docs reference back to the plan and are updated if decisions shift.

## 3. Test coverage ratchet

**The existing Python test suite encodes years of bug fixes.** Treat any test dropped without
a Rust equivalent as a regression waiting to happen.

- Every `tests/test_services/*.py` file must have a Rust equivalent under `crates/core/tests/`
  before the Python module it covers is deleted.
- Every `tests/test_cli/*.py` file must have a Rust equivalent under `crates/cli/tests/` before
  the Python CLI subcommand it covers is deleted.
- `tests/test_api/*.py` is the exception: it tests REST endpoints that don't survive migration.
  It's dropped without replacement — Tauri IPC contract tests (§4) cover the new surface.

On top, add what Python didn't have:

- **Property-based tests** (`proptest` crate) for every crypto path: Argon2id determinism,
  SQLCipher key-wrap round-trip, OAuth state nonce uniqueness, token encryption if retained.
- **Integration tests** with a fake OAuth provider (`axum` fixture or `wiremock`) so the full
  PKCE dance runs without hitting real Google/MS/Apple/Meta on every CI run.
- **Fuzz targets** (`cargo-fuzz`) on at least: deep-link URI parsing, OAuth callback query
  parsing, any code that deserializes untrusted bytes.

## 4. Contract tests between frontend and backend

The Tauri IPC surface is the new "API". It must not drift silently.

- Generate TypeScript types from Rust (`specta` or `ts-rs`) as part of the build — not hand-written.
- Snapshot-test the generated `.d.ts` file; diff reviewed on every PR.
- Every new IPC command added in Rust fails CI until its TypeScript consumer exists.
- Every frontend call site has a typed wrapper — no `invoke('foo', args as any)` allowed.

## 5. Phase gates as CI checklists (not prose)

Every phase's "exit criteria" in the migration plan becomes a CI job that returns green/red.
Phase advances only when the check is green on **all three OSes**.

- CI job per phase: `phase-0-exit`, `phase-1-exit`, etc.
- Each job runs the plan's exit criteria as literal scripts (e.g. `lsof -i` check, `sqlite3
  vault.db ".tables"` expected to fail without key, etc.).
- Phase-complete commit tagged as `v0-phase-0`, `v0-phase-1`, etc. — these are the rollback points.
- No `git revert` past a phase tag without a written postmortem.

## 6. Security review ladder

Security review is layered, not a single end-of-line step.

| Moment | Reviewer | Scope |
|---|---|---|
| Phase 0 close | Internal (user) | Threat model doc + workspace design |
| Phase 2 start | Internal (user) | Vault + keychain + crypto specs, **before** coding |
| Phase 3 mid | Internal (user) | OAuth port diff vs. current Python behavior |
| Phase 4 | External pentester | Full app: vault, OAuth, IPC, updater, signing chain |

The Phase 4 external test is non-negotiable for a credential-adjacent app. Budget for it now,
not at the end.

## 7. Supply chain hygiene (from day zero)

All of these land in Phase 0 CI, not retrofitted later:

- `cargo-audit` — known-vulnerability scan, fails CI on any advisory.
- `cargo-deny` — license allowlist + dupe check + ban policy for risky crates.
- `cargo-vet` — trust policy for dependency audits; required for all new deps.
- `osv-scanner` — cross-ecosystem vuln feed (catches things `cargo-audit` misses).
- npm: `pnpm audit` + `pnpm licenses list` in CI.
- All deps pinned by hash: `Cargo.lock` and `pnpm-lock.yaml` committed; no range specifiers
  in production `dependencies` blocks.
- SBOM generated per release (CycloneDX, via `cargo-cyclonedx`).
- Signed commits enforced on `main`; 2-reviewer rule for anything touching `crates/core/src/`
  (crypto, keychain, vault).
- Release signing keys in a hardware token or GitHub Environments with required reviewers.

**A compromised dependency in a signed release is worse than an unsigned compromise** — the
signature launders the compromise. Hygiene is not optional.

## 8. ADR discipline for divergences

When a design decision diverges from the plan, or a spike invalidates a plan assumption,
capture it as an ADR under `docs/adr/NNNN-short-title.md`.

Template:

```markdown
# NNNN. Short title

**Status:** Proposed | Accepted | Superseded by ADR-MMMM
**Date:** YYYY-MM-DD

## Context
What prompted this decision? What's the relevant section of the plan?

## Decision
What are we doing?

## Consequences
What becomes easier, what becomes harder, what new risks are introduced?

## Alternatives considered
What else did we look at, and why not?
```

Rule: if the reasoning for a decision can't be reconstructed from the plan + the code six
months from now, the decision needs an ADR.

## 9. Phase Ledger

| Phase | Status | Exit criteria met | Tag | Notes |
|---|---|---|---|---|
| Pre-Phase-0 (Worker extract) | Not started | — | — | Depends on new GitHub repo (user) |
| Phase 0 (Scaffold + procurement) | In progress | 3/4 | — | Scaffold + local CI + Tauri dev loop all green; only procurement + threat-model review outstanding |
| Phase 1 (Hybrid shipping) | Not started | — | — | |
| Phase 2 (Storage + secrets to Rust) | Not started | — | — | |
| Phase 3 (Retire Python sidecar, port CLI) | Not started | — | — | |
| Phase 4 (Harden + release) | Not started | — | — | |

### Phase 0 exit checklist (live)

- [x] Cargo workspace scaffolded; `cargo check --workspace` green locally.
- [x] `cargo clippy --workspace --all-targets -- -D warnings` green locally.
- [x] `cargo test --workspace` green (1 unit test passing).
- [x] `cargo fmt --all --check` green.
- [x] GitHub Actions `rust.yml` written: check + audit + deny + osv-scan on macOS + Windows + Linux.
- [x] `deny.toml` written with license allowlist + source restrictions.
- [ ] `rust.yml` proven green on an actual PR (pending — W1 push will be the first trigger).
- [x] Tauri 2 config in `crates/gui/` (b71128a scaffold + W1 path fixes).
- [x] `npm run tauri:dev` opens the React SPA in a Tauri window (verified 2026-04-14: Vite ready in 243 ms, dev build 12.92 s, `account-hub-gui` binary launched, curl :3000 → HTTP 200).
- [ ] `docs/desktop-threat-model.md` reviewed at Phase 0 close (scheduled for when other exit items are met).
- [ ] Apple Developer ID enrolled (user action — procurement).
- [ ] Windows EV code-signing cert ordered (user action — procurement; long lead time).
- [ ] GPG key for AppImage signatures generated (user action).

## 10. Revision Log

| Date | Section touched | Change | Why |
|---|---|---|---|
| 2026-04-13 | All | Initial draft | Phase 0 kickoff |
| 2026-04-13 | §9 Phase Ledger | Expanded Phase 0 into a live checklist; marked the 5 items completed in this session | Tighter granularity than "In progress" for a multi-session phase |
| 2026-04-13 | Workspace Cargo.toml | `rust_2018_idioms` bumped to `{ level = "warn", priority = -1 }` | Root-cause fix for clippy `lint_groups_priority` — lint groups need explicit priority to allow individual-lint overrides |
| 2026-04-13 | `crates/core/src/session.rs` | Removed `async fn unlock()` stub | Clippy flagged `unused_async`; root-cause fix is "don't ship API that doesn't work yet" rather than silencing the lint. Real impl lands in Phase 2 |
| 2026-04-13 | `crates/{gui,cli}/src/main.rs` | Dropped `fn main() -> anyhow::Result<()>` wrapper | Clippy `unnecessary_wraps` — stub main never returns Err; add Result back when real startup code lands |
| 2026-04-13 | §7 Supply chain | Documented carve-out: Phase 0 foundational commits push directly to `main` (solo project, stubs only, no `crates/core/src/` crypto yet). 2-reviewer rule re-engages when real crypto/keychain/vault code lands in Phase 2+. | Adapt the rule to reality without silencing it; tripwire is "when `crates/core/src/{crypto,keychain,vault}/` gets non-stub content" |
| 2026-04-13 | §5 Phase gates | Added `scripts/check.sh` — runs every CI step locally in the same order. First CI run failed on `cargo doc -D warnings` after locally running only fmt/clippy/test/check. Script is the root-cause fix: a single command that mirrors the CI workflow, removing the "forgot to run X" class of failure. | CI caught the real issue, but the feedback loop is faster when local == CI |
| 2026-04-13 | §7 Supply chain / cargo-deny | Pinned `cargo-deny` to 0.18.3 and scoped its `check` subcommand to `licenses bans sources` (not the full `check`). Reason: 0.19+ requires Rust 1.88.0, newer than the pinned 1.85.0; 0.18 can't parse CVSS 4.0 advisory entries. `cargo-audit` runs in a separate job and is the sole source of truth for advisories. Revisit when the toolchain moves to 1.88+ | Upstream toolchain-version skew; ADR unnecessary since it's a pin / config scoping, not a design divergence |
| 2026-04-13 | §7 Supply chain / cargo-deny | Added `[licenses.private] ignore = true` to `deny.toml`. The three workspace crates use `license = "Proprietary"` (not SPDX); all are `publish = false`. The directive exempts our own non-published crates from license scrutiny without loosening third-party license requirements. | Idiomatic cargo-deny config for workspace-internal crates |
| 2026-04-13 | §7 Supply chain / cargo-deny | Pinned workspace `core` dep with `version = "=0.0.1"` alongside `path`. cargo-deny's wildcard check treats version-less path deps as wildcards; the pinned version keeps `wildcards = "deny"` strict for external deps. | Idiomatic for workspace-internal crates that may be published later |
| 2026-04-13 | Design doc 02 accepted | `docs/design/02-keychain-abstraction.md` + ADR 0002: async `SecretStore` trait, typed `SecretKey` constants, four production backends (`MacosKeychain` / `WindowsCredentialManager` / `LinuxSecretService` / `AgeKeyfile`) + `FakeKeychain` for tests. GUI never falls back to keyfile; CLI opts in via `--keyfile`. No biometric trait methods in v1. `panic = "abort"` accepted as out-of-scope for cold-boot memory attacks. First `AgeKeyfile` identity to ship = X25519 file. | Second in the ground-up design order; unblocks vault design 03 |
| 2026-04-13 | Design doc 03 accepted | `docs/design/03-vault.md` + ADR 0003 + `crates/core/migrations/V0001__initial.sql`: SQLCipher via rusqlite + bundled-sqlcipher; single connection per vault serialized by `parking_lot::Mutex`; async bridge via `tokio::task::spawn_blocking`; WAL + `fs2` exclusive lock for rekey/migration; `refinery` for migrations; five surviving tables (`linked_email`, `oauth_state`, `scan_session`, `discovered_account`, `closure_request`); three auth-only tables retired not ported; no per-column encryption (SQLCipher whole-file is the answer); INTEGER unix-seconds timestamps; no user_id columns (single-user vault). | Third in the ground-up design order; centerpiece of the app's security posture |
| 2026-04-13 | Design doc 04 accepted | `docs/design/04-oauth-providers.md` + ADR 0004: narrow `Provider` trait (4 methods + optional `revoke`); shared `OAuthFlow` orchestrator owns PKCE/state/nonce/loopback/vault; Microsoft switched from device-code to loopback+PKCE (device-code kept as corp-tenant fallback); Apple client secret is an ES256-signed JWT with 3-minute exp (not 6 months); Apple Worker relay cert-pinned via SHA-256 SPKI; state carries `:<loopback-port>` for Worker routing; `hyper` directly for loopback server (not axum); one shared `reqwest::Client` with rustls + webpki-roots; tokens carried as `SecretString` end-to-end; refresh scheduler runs under `UnlockedSession`. | Fourth in the ground-up design order; unblocks Phase 3 Rust OAuth port |
| 2026-04-13 | Design doc 05 accepted | `docs/design/05-tauri-ipc.md` + ADR 0005: specta + tauri-specta for type sharing (TS bindings regenerate as part of build); coarse 7-variant `IpcError` envelope with redaction at the core → IPC boundary (no paths, tokens, stack traces, or internal types leak); long-running ops use command + event pairs (LinkHandle returned sync, completion via event) rather than blocking commands; `AppState = RwLock<Session> + Arc<dyn SecretStore> + reqwest::Client`; minimal Tauri capabilities (no shell-exec, no broad fs, no http plugin, no clipboard); runtime hardening with `withGlobalTauri: false` + `freezePrototype: true`; every command validates inputs even though webview ships with app. Full command catalog (session, linked_email, scan, closure) replaces the 22 `apiFetch` call sites in `web/src/api/*.ts`. | Fifth and final ground-up design; unblocks Phase 3 frontend cutover from `fetch` to `invoke()` |

| 2026-04-14 | W1 wrap-up | `.gitignore` + index cleanup: root and `legal/node_modules/` were committed in b71128a before the gitignore rules took effect (901 + 884 files). `git rm -r --cached` to untrack without disk deletion; added `legal/node_modules/` explicitly to match the existing `web/node_modules/` pattern. | Repo hygiene; keeping generated node_modules out of source control |
| 2026-04-14 | W1 wrap-up / `deny.toml` | Added per-crate MPL-2.0 exceptions for 5 Tauri transitive deps: `cssparser`, `cssparser-macros`, `dtoa-short`, `selectors` (Servo CSS parser family via `kuchikiki` → `tauri-utils`) and `option-ext` (via `dirs-sys` → `dirs`). MPL-2.0 is weak file-level copyleft; unmodified library use incurs only attribution, which Tauri's release-build machinery handles. **Blanket MPL-2.0 allow rejected per risk j**; re-review is triggered if we vendor/patch/fork any of these. | Tauri scaffold pulled new licenses; risk j requires per-crate scrutiny |
| 2026-04-14 | W1 wrap-up / Rust toolchain | `rust-toolchain.toml` was bumped `1.85.0 → 1.94.1` during b71128a Tauri scaffold: transitive deps from Tauri 2 require rustc ≥1.88. This also supersedes the cargo-deny 0.18.3 pin rationale (revision-log entry 2026-04-13) on the toolchain-version side, though we keep 0.18.3 for the CVSS 4.0 advisory-parser workaround until `cargo-deny` proper adds CVSS 4.0 support. | Toolchain bump was forced by Tauri's MSRV; one log entry captures both the bump and the unchanged parts of the cargo-deny stance |
| 2026-04-14 | W1 wrap-up / workspace alias | `Cargo.toml` workspace dep renamed `core` → `account_hub_core`. `core` shadowed the stdlib crate of the same name inside proc-macro expansions (e.g. `tauri::generate_context!` references `core::option::Option`). The explicit alias removes the shadowing without changing the crate-on-disk name (`crates/core/` stays put). | Required for `tauri::generate_context!` to compile; same reason a lot of Rust codebases avoid naming internal crates after stdlib modules |
| 2026-04-14 | W1 wrap-up / Tauri dev scripts | Two pre-existing bugs in the scaffold blocked `npm run tauri:dev` until actually run: (1) `package.json` placed `--config` before the subcommand (`tauri --config ... dev`) but Tauri 2 makes `--config` a dev/build subcommand flag; reordered to `tauri dev --config ...` and stripped bogus `--config` from `tauri` + `tauri:icon`. (2) `tauri.conf.json` `beforeDevCommand: npm --prefix ../../web run dev` resolved `../../` relative to the tauri CLI's invocation CWD (repo root), not relative to the config file, yielding `/Users/<user>/web/`; changed to `./web`. `frontendDist` stays config-relative — that one is correctly pointed. | Root-cause fix for the "`tauri:dev` never exercised" known issue at session pause |
| 2026-04-14 | §9 Phase Ledger | Phase 0 exit criteria met moved from 2/4 → 3/4; Tauri config and `tauri:dev` boxes checked. Only procurement + threat-model review remain before Phase 0 close. | Progress tracking |

**All five ground-up design docs accepted as of 2026-04-13.** Design-spec work complete;
subsequent revision-log entries are implementation-driven.

---

## Rollback + pre-cutover safety

- The hosted app (Railway) stays online until a signed macOS `.dmg` has survived a fresh-install
  OAuth round-trip for all four providers on a clean VM. Tearing down the hosted surface before
  Phase 1 is proven removes the only rollback path.
- The Apple OAuth Worker (`accounthub-oauth-relay`) is the single point of failure for Apple
  sign-in across the entire migration. Any change to it goes through staging first; cutover is
  a named deployment event, not a casual merge.
- Before any `rm -rf account_hub/` style operation in Phase 3, run `cargo test` + `pnpm test` +
  the Phase 3 exit-criteria checklist green. Deletion is the last step, not the first.

## Problem-response protocol

When something breaks during migration work:

1. **Stop.** Don't retry the failing command with variations.
2. **Read the actual error.** Not the summary; the full output.
3. **Identify the root cause.** What contract was violated? What assumption was wrong?
4. **Fix the root cause.** Not the symptom.
5. **Add a test** that would have caught this, so it doesn't happen again.
6. If the root cause is a plan assumption, update the plan and log it in [§10](#10-revision-log).

Band-aids (disabling a check, commenting out a test, `|| true` in a script, `# TODO: fix later`)
are not acceptable shortcuts.
