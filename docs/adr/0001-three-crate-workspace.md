# 0001. Three-crate Cargo workspace (`core` / `gui` / `cli`)

**Status:** Accepted
**Date:** 2026-04-13
**Supersedes:** —
**Superseded by:** —

## Context

The refined migration plan (`~/.claude/plans/woolly-coalescing-dragon.md`) commits to shipping
two binaries from this repo: a Tauri 2 desktop GUI and a clap-based CLI. Both surfaces consume
identical business logic (vault, OAuth, mail, discovery, closure) and must enforce identical
security invariants (crypto, keychain, zeroization).

Two shapes are viable:

1. **Single `src/` tree** with two `[[bin]]` entries in one `Cargo.toml`.
2. **Three-crate workspace** — one library (`core`) plus two binaries (`gui`, `cli`).

## Decision

We choose **three crates in a Cargo workspace**:

- `crates/core/` — library crate, Tauri-agnostic and clap-agnostic, holds all shared logic.
- `crates/gui/` — binary, depends on `core` and `tauri`.
- `crates/cli/` — binary, depends on `core` and `clap`.

Rules enforced by `cargo-deny` and CODEOWNERS (see `docs/quality-gates.md §7`):

- `core` must not depend on `tauri`, `clap`, `gui`, or `cli`.
- `gui` and `cli` must not share code except via `core`.
- Any PR touching `crates/core/src/` requires two reviewers.

Full architecture spec: `docs/design/01-workspace-architecture.md`.

## Consequences

**Easier:**
- Security-sensitive code concentrated in one crate with a stricter review gate.
- CLI remains viable on headless Linux without dragging in webview deps transitively.
- Unit tests for shared logic live next to the logic, with a `test-utils` feature exposing
  fakes (`FakeKeychain`, `InMemoryVault`, `MockProvider`) to all consumers uniformly.
- Future fourth shell (mobile, web, additional binary) drops in without disturbing `core`.

**Harder:**
- Compile times marginally longer than a single-crate layout (three crates vs. one).
  Mitigated by workspace-shared `target/` directory and `codegen-units = 1` only in release.
- Developers must resist reaching for a cross-binary shortcut; enforced by lint + cargo-deny.

**New risks:**
- Leaking Tauri-specific types through `core` (e.g. via an over-eager `pub use`) would
  invalidate the CLI build. Mitigation: `cli` has its own CI job that builds it in isolation;
  a Tauri dep creeping in fails that job before merge.

## Alternatives considered

### (A) Single crate, two `[[bin]]` entries
- **Pros:** simplest layout; fewer manifests.
- **Cons:** no hard line between GUI-specific and CLI-specific code; accidental `use`
  dependencies across binaries not caught by Cargo. The 2-reviewer rule can't scope to just
  the shared bits because everything lives in one crate.
- **Verdict:** rejected — the discipline this ADR aims to buy depends on the boundary.

### (B) Four crates — split `core` into `core-types` + `core-logic`
- **Pros:** even tighter boundary; DTOs in a minimal crate that binaries can depend on without
  pulling the full logic stack.
- **Cons:** premature over-engineering for the current scope; no concrete consumer needs the
  type-only crate yet. YAGNI.
- **Verdict:** rejected for now; can split later if a consumer materializes.

### (C) Multi-repo (separate repo for CLI)
- **Pros:** maximum isolation.
- **Cons:** forces a crates.io / git-dep discipline that's overhead for a solo project;
  version skew between GUI and CLI becomes a new class of bug.
- **Verdict:** rejected — single repo is the better default until someone else ships a third
  shell against `core`.

## References

- Design spec: `docs/design/01-workspace-architecture.md`
- Migration plan: `~/.claude/plans/woolly-coalescing-dragon.md`
- Quality gates: `docs/quality-gates.md`
