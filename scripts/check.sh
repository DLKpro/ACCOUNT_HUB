#!/usr/bin/env bash
# Run every check the Rust CI workflow runs, locally. Match this to
# .github/workflows/rust.yml — if CI gains a step, add it here too.
#
# Usage:   ./scripts/check.sh
# Exit 0:  all checks green.
# Exit n:  first failing check propagates its exit code.

set -euo pipefail

# Source cargo env if not already on PATH (for sessions that haven't sourced shell rc).
if ! command -v cargo >/dev/null 2>&1; then
  # shellcheck disable=SC1091
  [[ -f "$HOME/.cargo/env" ]] && source "$HOME/.cargo/env"
fi

echo "==> cargo fmt --all --check"
cargo fmt --all --check

echo "==> cargo clippy --workspace --all-targets --all-features -- -D warnings"
cargo clippy --workspace --all-targets --all-features -- -D warnings

echo "==> cargo test --workspace --all-features"
cargo test --workspace --all-features

echo "==> cargo doc --workspace --no-deps --all-features (RUSTDOCFLAGS=-D warnings)"
RUSTDOCFLAGS="-D warnings" cargo doc --workspace --no-deps --all-features

# cargo-deny is optional locally — install with: cargo install cargo-deny --locked --version 0.18.3
if command -v cargo-deny >/dev/null 2>&1; then
  echo "==> cargo deny check licenses bans sources"
  cargo deny --all-features check licenses bans sources
else
  echo "==> cargo-deny not installed locally; skipping (CI will run it)"
fi

echo
echo "All checks green."
