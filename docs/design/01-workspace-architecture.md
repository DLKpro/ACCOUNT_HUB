# Design 01 — Rust Workspace Architecture

> First design spec in the ground-up series. Constrains every subsequent
> subsystem (keychain, vault, OAuth, IPC). See `docs/quality-gates.md §2`.

## Purpose

Define the Cargo workspace layout, crate boundaries, and dependency rules so that:

1. GUI and CLI binaries share **all** business logic via `core`, not via code duplication.
2. Security-sensitive code (crypto, keychain, vault, OAuth) lives in exactly one place and is
   protected by the 2-reviewer rule from `docs/quality-gates.md §7`.
3. `core` is Tauri-agnostic — the CLI can consume it without pulling a webview dep.
4. Testing is first-class: fake implementations of external dependencies (keychain, HTTP, time)
   are provided by `core` itself behind a `test-utils` feature.

## Layout

```
/Users/dlk/Developer/ACCOUNT_HUB/
├── Cargo.toml                # workspace root
├── rust-toolchain.toml       # pin toolchain
├── .cargo/config.toml        # build config, per-target rustflags
├── crates/
│   ├── core/                 # lib crate — all shared logic
│   │   ├── Cargo.toml
│   │   ├── src/
│   │   │   ├── lib.rs        # public re-exports
│   │   │   ├── error.rs      # unified Error enum (thiserror)
│   │   │   ├── session.rs    # UnlockedSession handle
│   │   │   ├── crypto/       # Argon2id KDF, zeroize wrappers, AEAD if needed
│   │   │   ├── keychain/     # SecretStore trait + impls (design 02)
│   │   │   ├── vault/        # SQLCipher, migrations (design 03)
│   │   │   ├── oauth/        # Provider trait + 4 impls (design 04)
│   │   │   ├── mail/         # Gmail, Graph, IMAP clients
│   │   │   ├── discovery/    # Scanner architecture (ports account_hub/discovery)
│   │   │   ├── closure/      # Closure registry (ports account_hub/data)
│   │   │   └── types/        # Shared DTOs — exported to TS via specta/ts-rs
│   │   ├── migrations/       # refinery SQL files, 0001_initial.sql onwards
│   │   └── tests/            # integration tests
│   ├── gui/                  # bin crate — Tauri 2 shell + React SPA
│   │   ├── Cargo.toml
│   │   ├── build.rs          # sidecar bundling (Phase 1 only, removed Phase 3)
│   │   ├── tauri.conf.json
│   │   ├── src/
│   │   │   ├── main.rs
│   │   │   ├── commands/     # Tauri IPC handlers (design 05)
│   │   │   └── deep_link.rs  # accounthub:// URI handler
│   │   └── dist/             # symlink or build output from web/
│   └── cli/                  # bin crate — clap terminal UI
│       ├── Cargo.toml
│       ├── src/
│       │   ├── main.rs
│       │   ├── commands/     # mirror Python CLI: auth, close, email, search
│       │   └── keyfile.rs    # age-encrypted keyfile fallback
│       └── tests/
├── web/                      # unchanged; Vite + React SPA
├── account_hub/              # unchanged during Phase 0; removed Phase 3
└── tests/                    # unchanged during Phase 0; ported Phase 3
```

## Dependency rules

| From → To | Allowed? | Notes |
|---|---|---|
| `gui` → `core` | ✅ | Primary consumer |
| `cli` → `core` | ✅ | Primary consumer |
| `core` → `gui` | ❌ | `core` must be Tauri-agnostic |
| `core` → `cli` | ❌ | `core` must be clap-agnostic |
| `gui` ↔ `cli` | ❌ | Siblings; no shared code between binaries (share via `core`) |
| `core` → `tauri` | ❌ | Breaks agnostic property |
| `core` → `clap` | ❌ | Breaks agnostic property |
| `gui` → `clap` | ❌ | GUI doesn't need CLI parsing |
| `cli` → `tauri` | ❌ | CLI doesn't need a webview |

Enforcement: `cargo-deny` rule (`[bans] deny = [...]`) with workspace-level ban list. A `gui`
dep sneaking into `core` fails CI.

## `core` public API surface

All external access to `core` goes through `lib.rs` re-exports. The module tree is an
implementation detail; outside consumers reach in only via:

```rust
// crates/core/src/lib.rs (sketch)
pub use error::{Error, Result};
pub use session::{LockedSession, UnlockedSession};

pub mod vault {
    pub use crate::vault::{Vault, VaultConfig};
    pub use crate::vault::models::*;  // LinkedEmail, DiscoveredAccount, etc.
}

pub mod oauth {
    pub use crate::oauth::{Provider, ProviderId, TokenSet, PkceFlow, DeviceCodeFlow};
}

pub mod keychain {
    pub use crate::keychain::{SecretStore, KeychainError};
}

pub mod types {
    pub use crate::types::*;  // DTOs exported to TS
}

// Top-level entry points
pub fn init(config: InitConfig) -> Result<LockedSession>;
```

- No `pub use` of internal details (e.g. `rusqlite` types) leak out. If a caller needs a DB
  row, `core` exposes its own type.
- DTOs in `types/` derive `serde::{Serialize, Deserialize}` and (when applicable) `specta::Type`
  so they generate matching TypeScript in Phase 3. Cross-cutting types live here, not per-module,
  so the TS codegen has a single source.

## Error handling

- `core::Error` is a `thiserror`-derived enum, exhaustive for library callers. Variants:
  `Vault(VaultError)`, `OAuth(OAuthError)`, `Keychain(KeychainError)`, `Io(io::Error)`,
  `Network(reqwest::Error)`, `InvalidInput(String)`.
- Per-module errors (`VaultError`, `OAuthError`, …) live inside the module and are also
  `thiserror` enums. The top-level `Error` wraps them via `#[from]`.
- Binaries (`gui`, `cli`) may use `anyhow` for application-layer error aggregation; `core`
  never uses `anyhow` — library errors are structured.
- Error messages must never include secrets. `Display` impls on error variants elide token/key
  bytes; enforced by a review checklist, not a test (can't reliably lint for this).

## Async runtime

- `tokio` with `rt-multi-thread` + `macros` features.
- `core` functions that do I/O are `async fn`. Binaries own the runtime.
- Blocking operations (SQLCipher, Argon2id hashing) run on `tokio::task::spawn_blocking` to
  avoid starving the async executor. This is critical — Argon2id at OWASP params takes
  ~100ms, blocking a task long enough to stall the UI.

## Feature flags

`core` features:

| Feature | Purpose | Default? |
|---|---|---|
| `test-utils` | Fake `SecretStore`, in-memory vault, fake clock, fake HTTP | off |
| `specta` | Generate TypeScript types from `core::types` | on (for `gui` build) |
| (no per-OS features) | per-OS code uses `cfg!(target_os)` internally | — |

`gui` features:

| Feature | Purpose | Default? |
|---|---|---|
| `sidecar` | Bundle Python sidecar (Phase 1 only) | on in Phase 1; off after |

`cli` features:

| Feature | Purpose | Default? |
|---|---|---|
| `keyfile-fallback` | age-encrypted keyfile unlock | on |

Rationale for not using per-OS features in `core`: feature flags encourage per-OS code drift.
Using `cfg!(target_os = "macos")` inside a single keychain module keeps all three impls in one
file where a reviewer can compare them.

## MSRV and toolchain

- Pin the Rust toolchain in `rust-toolchain.toml`. Start with **stable** (latest at time of
  Phase 0 kickoff). Document the reason for any bump in commit message.
- `edition = "2021"` across the workspace (2024 edition is still baking; revisit mid-Phase-3).
- `rust-version = "1.85"` minimum declared in `[workspace.package]` (adjust to whatever is
  stable at Phase 0 start).

## Build profiles

```toml
# Cargo.toml (workspace root)
[profile.release]
opt-level = 3
lto = "thin"
codegen-units = 1
strip = "symbols"
panic = "abort"         # smaller binary; no unwinding across FFI
overflow-checks = true  # paranoid: catch integer overflow even in release

[profile.dev]
opt-level = 0
debug = true

[profile.test]
opt-level = 1           # tests feel slow at opt-level 0 with SQLCipher + Argon2id
```

Note: `panic = "abort"` means no catch_unwind on panic. Acceptable for an app binary; ensures
no secret-bearing state survives a panic.

## Testing shape

- Unit tests in-crate: `#[cfg(test)] mod tests { … }` at the bottom of each module.
- Integration tests under `crates/{core,cli}/tests/` — one `.rs` per feature area.
- `crates/core` exposes a `test-utils` feature with fake implementations:
  - `FakeKeychain` — in-memory SecretStore.
  - `InMemoryVault` — SQLCipher in-memory DB (`:memory:`), pre-unlocked.
  - `MockProvider` — OAuth provider that returns canned responses; used by both core and binary tests.
- Property tests via `proptest`, at minimum covering the crypto layer.
- Fuzz targets under `crates/core/fuzz/` for deep-link parsing and OAuth callback query parsing.

## Review gates for `core/`

Per `docs/quality-gates.md §7`: any PR touching `crates/core/src/` (especially `crypto/`,
`keychain/`, `vault/`, `oauth/`) requires 2 reviewers. Enforced by GitHub `CODEOWNERS` + branch
protection — not by trust.

## Open questions

1. **`specta` vs. `ts-rs` for TypeScript codegen.** Both work; `specta` has better Tauri
   integration but `ts-rs` has a larger ecosystem. Decide at Phase 3 start (too early now).
2. **Do we want a separate `crates/core-ffi/` for potential future mobile/web integration?**
   YAGNI for now. Revisit only if a concrete mobile app appears on the roadmap.
3. **Should `core::Error` be `Clone`?** Downstream consumers might want to share errors in
   UI state. Default: no (inner `io::Error` / `reqwest::Error` aren't Clone). Provide a
   `Display`-based wrapper if a specific UI needs it.

## Consequences

- **Positive:** clear boundaries; core is testable and portable; no code duplication between
  GUI and CLI; security-sensitive code concentrated in one review-gated crate.
- **Negative:** compile times slightly longer than a single-crate layout (3 crates instead of 1).
  Acceptable given workspace-shared `target/` directory.
- **Future:** if a mobile or web shell is ever added, it drops in as a fourth binary (`crates/mobile/`)
  consuming `core` with no changes to the existing crates.

## Decision record

Captured as `docs/adr/0001-three-crate-workspace.md` once this design is accepted.
