#!/usr/bin/env node
// npm licence allowlist check. Reads the `license` field npm records for every
// package in a package-lock.json (lockfileVersion 3) and fails on anything
// that is not allowed below. No dependencies, no install needed.
//
// Usage:  node scripts/check-npm-licenses.mjs web/package-lock.json package-lock.json
// Exit 0: every package is allowed.  Exit 1: at least one is not (or has no licence).
//
// Policy mirrors deny.toml (docs/quality-gates.md §7): permissive licences are
// allowed outright; anything else is allowed per package, by name, with a
// reason. No blanket allow for copyleft.

import { readFileSync } from "node:fs";

// Permissive licences, allowed for any package.
const ALLOWED = new Set([
  "MIT",
  "Apache-2.0",
  "ISC",
  "BSD-2-Clause",
  "BSD-3-Clause",
  "0BSD",
  "BlueOak-1.0.0",
]);

// Per-package exceptions: licence -> package-name patterns it is accepted for.
// Re-review trigger for all of these: we vendor, patch or fork the package, or
// it moves from devDependencies into the shipped bundle.
const EXCEPTIONS = {
  // lightningcss (+ its per-platform binaries): CSS transformer used by
  // Tailwind/Vite at build time. Dev-only, used unmodified. MPL-2.0 is
  // file-level copyleft; same reasoning as the cssparser entries in deny.toml.
  "MPL-2.0": [/^lightningcss(-[a-z0-9-]+)?$/],
  // caniuse-lite: browser-support data consumed by browserslist at build time.
  "CC-BY-4.0": [/^caniuse-lite$/],
  // argparse: CLI parser pulled in by js-yaml (eslint). Dev-only.
  "Python-2.0": [/^argparse$/],
};

const packageName = (lockKey) => lockKey.split("node_modules/").pop();

function idAllowed(id, name) {
  if (ALLOWED.has(id)) return true;
  return (EXCEPTIONS[id] ?? []).some((re) => re.test(name));
}

// Minimal SPDX expression support: "A OR B" passes if any side passes,
// "A AND B" only if every side passes. Parentheses are flattened, which is
// enough for the simple expressions npm packages use.
function expressionAllowed(expr, name) {
  const flat = expr.replace(/[()]/g, " ").trim();
  return flat
    .split(/\s+OR\s+/)
    .some((alt) => alt.split(/\s+AND\s+/).every((id) => idAllowed(id.trim(), name)));
}

const lockfiles = process.argv.slice(2);
if (lockfiles.length === 0) {
  console.error("usage: check-npm-licenses.mjs <package-lock.json> [...]");
  process.exit(2);
}

let failures = 0;
for (const file of lockfiles) {
  const lock = JSON.parse(readFileSync(file, "utf8"));
  if (!lock.packages) {
    console.error(`${file}: no "packages" map (lockfileVersion 2+ required)`);
    process.exit(2);
  }
  let checked = 0;
  for (const [key, pkg] of Object.entries(lock.packages)) {
    if (key === "" || pkg.link) continue; // the project itself / workspace links
    checked += 1;
    const name = packageName(key);
    const licence = typeof pkg.license === "string" ? pkg.license : null;
    if (!licence) {
      console.error(`${file}: ${name}@${pkg.version}: no licence recorded`);
      failures += 1;
    } else if (!expressionAllowed(licence, name)) {
      console.error(`${file}: ${name}@${pkg.version}: licence "${licence}" is not allowed`);
      failures += 1;
    }
  }
  console.log(`${file}: ${checked} packages checked`);
}

if (failures > 0) {
  console.error(`\n${failures} package(s) failed the licence policy. See scripts/check-npm-licenses.mjs.`);
  process.exit(1);
}
console.log("npm licences ok");
