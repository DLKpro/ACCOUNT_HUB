# 0006. Audience is self-hosters; Phase 0 supply-chain controls as built

**Status:** Accepted
**Date:** 2026-11-05
**Supersedes:** —
**Superseded by:** —

## Context

The Phase 0 close review (2026-11-05) checked `docs/desktop-threat-model.md` against design
docs 01–05 and against what CI actually runs. It surfaced three things no earlier document
decided:

1. Design 04 has the user import an Apple `.p8` on first Apple sign-in. That only works if
   every user has their own Apple developer account, but nothing said who the users are.
2. The Apple relay and its pinned certificate use `dlopro.com`, while the DLO Pro site is
   `dlopro.ca`. Nothing recorded whether `dlopro.com` was intended.
3. `docs/quality-gates.md` §7 lists controls that "land in Phase 0 CI". cargo-vet, the npm
   checks and signed commits on `main` did not exist.

## Decisions

### D1 — ACCOUNT_HUB is for its author and for self-hosters

Each person runs their own build with their own provider credentials (OAuth client IDs,
Apple `.p8`). The project does not ship a build with shared credentials to end users.
Design 04's "import your own `.p8`" flow stands as written.

### D2 — `dlopro.com` is the Apple relay domain

The domain is owned by the author and is separate from `dlopro.ca`. It stays the relay and
certificate-pin target in design 04. The registration is now a tracked asset (threat model
A9): auto-renew and registrar lock.

### D3 — `main` requires signed commits; CI is not a required check

Branch protection on `main`: signed commits required, enforced for admins, force-pushes and
deletion blocked. No required status checks and no required reviews.

### D4 — cargo-vet starts from a baseline of exemptions

`supply-chain/` imports audits from Mozilla, Google and the Bytecode Alliance. Every crate
they do not cover (367 on the day) is exempted as-is. `cargo vet --locked` in CI therefore
gates new and changed crates, not the existing tree.

### D5 — npm is gated at high severity, with a per-package licence allowlist

`npm audit --audit-level=high` for `web/` and the repo root. Licences are checked from the
lockfile by `scripts/check-npm-licenses.mjs`: permissive licences pass, anything else needs
a named per-package exception with a reason, mirroring `deny.toml`.

## Consequences

- **D1** keeps the Apple key out of any distributed artifact, so there is no shared secret
  to leak. It also means there is no "download and sign in with Apple" experience for a
  non-developer. Distributing to end users later requires a new ADR and a server-side
  signer (most likely in the relay Worker), and re-modelling A4, A6 and T7.
- **D2** makes a lapsed registration a security event, not only an outage.
- **D3** lets signed direct pushes and GitHub squash merges continue unchanged. A signed
  commit can still land with red CI. The 2-reviewer rule for `crates/core/src/` (§7) stays
  a convention with the Phase 0 carve-out in the revision log, not an enforced rule.
- **D4** is cheap to adopt but the exemption list is trust, not audit. Shrinking it is
  optional work; growing it for a new dependency is a deliberate, reviewable diff.
- **D5** leaves moderate npm advisories ungated. They are reviewed quarterly with the Rust
  advisory ignores. `legal/` is outside the gate (its only dependency is the wrangler CLI).

## Alternatives considered

- **Ship to end users now (D1).** Rejected: needs a server-side Apple signer and a support
  surface that Phases 1–3 do not plan for.
- **Require CI checks on `main` (D3).** Rejected for now: Rust CI is path-filtered, and a
  required check that never starts leaves a docs-only PR unmergeable. Requiring only the
  unfiltered Python checks would force every change through a PR. Revisit when the Python
  code is retired (Phase 3) and one always-on workflow can be the required check.
- **Audit the whole tree before adopting cargo-vet (D4).** Rejected: 463 crates; the gate
  on new crates is the value now.
- **Gate npm at moderate (D5).** Rejected: the remaining moderate advisory (minimatch inside
  typescript-eslint) has no upstream fix, and `npm audit` has no per-advisory ignore.
