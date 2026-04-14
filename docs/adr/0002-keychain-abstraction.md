# 0002. Keychain abstraction: `SecretStore` trait + four backends + opt-in age keyfile

**Status:** Accepted
**Date:** 2026-04-13
**Supersedes:** —
**Superseded by:** —

## Context

Design doc `docs/design/02-keychain-abstraction.md` defines the `SecretStore` abstraction
for storing the vault KEK, the Apple OAuth private key, and similar fixed-size named secrets.
The design makes several decisions that are load-bearing for downstream subsystems (vault
design 03, OAuth design 04), and at least one that diverges in nuance from the refined plan's
summary. Those decisions are captured here as a durable record.

## Decision

### D1 — Async `SecretStore` trait

`SecretStore`'s methods are `async fn` (via `async_trait`) rather than blocking.

### D2 — Typed `SecretKey` constants, not free-form strings

The public API exposes a small struct with private fields and named constants
(`SecretKey::VAULT_KEK`, `SecretKey::APPLE_CLIENT_SECRET_KEY`). No `fn new(service, account)`
constructor. New slots require a commit to the constants list.

### D3 — Four production backends + one test backend

- `MacosKeychain` — `keyring` crate, login keychain, `kSecAttrAccessibleWhenUnlocked`.
- `WindowsCredentialManager` — `keyring` crate, `CRED_PERSIST_LOCAL_MACHINE`.
- `LinuxSecretService` — `keyring` crate, Secret Service via D-Bus.
- `AgeKeyfile` — file-backed, age-encrypted, opt-in via CLI flag. Identity selection is a
  per-instance parameter (passphrase / X25519 file / age-ssh / YubiKey plugin).
- `FakeKeychain` — in-memory, behind `test-utils` feature, supports error-mode injection.

### D4 — GUI never falls back to `AgeKeyfile`

On Linux, if libsecret is unavailable, the GUI surfaces an actionable error and refuses to
operate. The `AgeKeyfile` path is a CLI / automation concession, not a desktop-app one.

### D5 — No biometric trait methods in v1

The initial trait has no `set_biometric_required` or equivalent. Biometric gating is a v1.1
concern; adding it now would be speculative API. When it lands, it will be either a new
method on `SecretStore` or a `SecretStoreBiometric: SecretStore` extension trait, decided
against a concrete design.

### D6 — `panic = "abort"` accepted; zeroize is defence-in-depth on the happy path

The workspace release profile aborts on panic, which skips `Drop`. `Zeroizing<Vec<u8>>`
therefore does **not** wipe memory on panic. This is accepted: cold-boot memory attacks are
out of the desktop-app threat model. Documented explicitly so a reviewer doesn't later
"fix" `panic = "abort"` under the impression that zeroize requires unwinding.

### D7 — First `AgeKeyfile` identity in v1 is X25519 identity file

Passphrase-based age and age-ssh and YubiKey-plugin variants are viable but not all required
at v1 ship. X25519 identity file is the simplest, mature, and covers the headless-automation
case. The other three are incremental additions that don't alter the trait.

## Consequences

**Easier:**
- Vault (design 03) consumes only the `SecretStore` trait; swapping backends doesn't change
  vault code.
- Writing tests for any secret-handling logic is trivial with `FakeKeychain`.
- The CLI's `--keyfile` option is a single-line wiring change — pass a different
  `KeychainBackend` at init.

**Harder:**
- Three real OS backends cannot be integration-tested in CI (no login session). Mitigated
  by `FakeKeychain` + per-OS manual verification during release. Acknowledged gap.
- `AgeKeyfile` brings a second dimension of configuration (identity type), documented via
  CLI help.

**New risks:**
- `keyring` crate CVE blast radius = all three OS backends. Mitigation: `cargo-audit` in CI
  catches it; single version pin makes the patch trivial.
- Plain-passphrase `AgeKeyfile` on a shared server trades OS-keychain protection for
  filesystem-permission protection. Documented in CLI help so users can't adopt it unknowingly.

## Alternatives considered

### (A) Sync trait, callers wrap `spawn_blocking`
- **Pros:** more honest about the underlying API; one less macro.
- **Cons:** every call site gains ceremony; biometric prompts (seconds long) would need
  explicit `spawn_blocking` everywhere; GUI code becomes uglier.
- **Verdict:** rejected. Async trait wins on caller ergonomics at the cost of one crate dep.

### (B) Free-form `&str` identifiers instead of typed `SecretKey`
- **Pros:** simpler API; no registry of constants.
- **Cons:** typos silently read/write a different slot; collisions with other apps'
  `"AccountHub"` namespace go undetected; code review can't enforce a closed set.
- **Verdict:** rejected. The constants registry is 20 lines of code that buys a whole class
  of bug prevention.

### (C) GUI falls back to `AgeKeyfile` automatically on Linux
- **Pros:** fewer user-facing errors.
- **Cons:** silently degrades security (OS-keychain → file-on-disk) without the user knowing;
  contradicts the principled posture of a credential-adjacent app.
- **Verdict:** rejected. An error that tells the user "install libsecret" is better than a
  silent degradation.

### (D) One unified backend that supports every mode
- **Pros:** fewer types.
- **Cons:** the backends have genuinely different semantics (libsecret's Collection model
  vs. Windows Credential Manager's flat list vs. macOS's SecItem attributes). Collapsing
  them leaks the union of their quirks to every caller.
- **Verdict:** rejected. The trait is the unified surface; the impls can differ beneath it.

## References

- Design spec: `docs/design/02-keychain-abstraction.md`
- Threat model: `docs/desktop-threat-model.md` (assets A1, A4; residual risk 2)
- Workspace architecture: `docs/design/01-workspace-architecture.md`
- Refined plan: `~/.claude/plans/woolly-coalescing-dragon.md` (keychain + --keyfile commitment)
