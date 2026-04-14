# 0005. Tauri IPC: specta type-sharing + coarse error envelope + command/event pairs + minimal capabilities

**Status:** Accepted
**Date:** 2026-04-13
**Supersedes:** —
**Superseded by:** —

## Context

Design doc `docs/design/05-tauri-ipc.md` defines the Rust ↔ TypeScript contract: what
commands exist, how errors and events cross the boundary, how session state is gated, and
how TypeScript types stay in lockstep with Rust types. Several decisions are load-bearing
for the Phase 3 frontend cutover; this ADR captures them.

## Decisions

### D1 — `specta` + `tauri-specta` for type sharing

TypeScript bindings are generated from Rust via `specta` / `tauri-specta`. Generated file
at `web/src/ipc/bindings.ts`, regenerated as part of the build. A `pnpm typecheck` CI step
fails if the frontend uses a command that doesn't exist or passes the wrong shape.

### D2 — Coarse `IpcError` envelope; redaction at the Rust boundary

`IpcError` is a seven-variant enum discriminated by `kind` (InvalidInput, Locked, NotFound,
Provider, Vault, Keychain, Internal). Each variant carries a `message` string that is
safe to show the user. The conversion `core::Error → IpcError` is the redaction point —
no path names, no stack traces, no token bytes, no internal types leak across.

### D3 — Long-running operations = command + event pair, never blocking

Commands that can take more than ~5 seconds (OAuth link flow, scan, long token refresh)
return a handle (`LinkHandle`, `ScanSession`, etc.) synchronously and emit events as
progress / completion occurs. Blocking commands would stall the Tauri command executor
and bog down other in-flight work.

### D4 — `AppState` shape: `RwLock<Session>` + `Arc<dyn SecretStore>` + `reqwest::Client`

The session is an enum (`FirstLaunch` / `Locked` / `Unlocked(Arc<UnlockedSession>)`) behind
a `tokio::sync::RwLock`. Commands gate on unlocked state via `AppState::unlocked()`, the
single chokepoint. Keychain and HTTP client live at app level, session-independent.

### D5 — Minimal Tauri capabilities; `withGlobalTauri: false`; `freezePrototype: true`

The main window ships with a bounded capability set — specific filesystem scope
(`$APPDATA/**`), `shell:allow-open` (browser hand-off only), `dialog:allow-save` /
`dialog:allow-open`, `deep-link:default`, `notification:allow-notify`. Explicitly absent:
`shell:allow-execute`, broad `fs:allow-*`, `http:*`, `clipboard:*`. Runtime hardening:
no `window.__TAURI__` global exposed, `Object.freeze(Object.prototype)` before app JS runs.

## Consequences

**Easier:**
- Adding a command is a ~20-line Rust change; the TS binding regenerates automatically and
  CI catches any frontend drift.
- Error handling on the frontend is ergonomic: `switch (e.kind) { case "Locked": … }`.
- No ambient Tauri magic on the webview; interactions are explicit imports from
  `@tauri-apps/api`.

**Harder:**
- `specta` + `tauri-specta` are active-development crates; major-version bumps may require
  small migrations. Mitigated by version-pinning and a stable-enough v2 release line.
- Events have no backpressure; runaway emitters (e.g. per-byte scan progress) could DOS
  the UI thread. Discipline enforced by the "does this event have a max rate?" reviewer
  checklist.
- Tauri capability files are a Tauri-specific DSL; reviewers need to know it. Flagged in
  `docs/quality-gates.md §7`; capability-file changes go through 2-reviewer approval.

**New risks:**
- `IpcError::Internal` string content is NOT rigorously lint-enforced against secret
  leakage. Review discipline is the sole mitigation. Acceptable given the small number of
  conversion sites and the 2-reviewer rule for `crates/core/src/`.
- Tauri major-version upgrades (Tauri 2 → 3 eventually) may ripple through the capability
  config schema. Pin major version; test upgrades on a branch.

## Alternatives considered

### (A) `ts-rs` for type sharing
- **Pros:** more mature / larger ecosystem.
- **Cons:** no native Tauri integration; every command needs hand-written TS glue; we'd
  build most of `tauri-specta` ourselves eventually.
- **Verdict:** rejected. `specta` saves scaffolding that `ts-rs` would require us to
  write from scratch.

### (B) Fine-grained error envelope (one variant per domain error)
- **Pros:** frontend can discriminate on every possible failure mode.
- **Cons:** every new domain error = a TS breaking change; catalog grows unboundedly;
  serialization leakage risk grows with every variant we forget to redact.
- **Verdict:** rejected. Coarse envelope + reviewer discipline is the better balance.

### (C) Blocking commands for long operations
- **Pros:** simpler wiring on the frontend (one `await`).
- **Cons:** stalls Tauri's command executor; bad UX (progress bars don't update);
  breaks the 2+ concurrent flows case (user linking Google + Meta in parallel).
- **Verdict:** rejected. Command + event pair is the idiomatic Tauri pattern.

### (D) `Mutex<Session>` instead of `RwLock<Session>`
- **Pros:** slightly simpler.
- **Cons:** every read acquires the write lock; commands serialize where they don't
  need to. At our QPS it may not matter in practice, but the contract is weaker.
- **Verdict:** rejected. RwLock is the correct semantic match.

### (E) Broad capability grants with in-code policy
- **Pros:** one place (Rust) decides what's allowed.
- **Cons:** defeats Tauri's security model; a compromised JS dep could invoke anything
  at all.
- **Verdict:** rejected. Capability file is the right policy layer; defense in depth is
  real here.

## References

- Design spec: `docs/design/05-tauri-ipc.md`
- Workspace: `docs/design/01-workspace-architecture.md` + ADR 0001
- Keychain: `docs/design/02-keychain-abstraction.md` + ADR 0002
- Vault: `docs/design/03-vault.md` + ADR 0003
- OAuth: `docs/design/04-oauth-providers.md` + ADR 0004
- Threat model: `docs/desktop-threat-model.md` (T2; residual risks)
- Refined plan: `~/.claude/plans/woolly-coalescing-dragon.md`
- Existing frontend API modules: `web/src/api/{auth,emails,scan,closures}.ts`
- Tauri 2: https://v2.tauri.app/
- specta: https://docs.rs/specta
- tauri-specta: https://docs.rs/tauri-specta
