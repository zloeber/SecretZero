---
name: add-cli-command
description: Add or modify a `secretzero` CLI command in `cli.py` with consistent UX and verification.
triggers:
  - "add command"
  - "cli option"
  - "click command"
edges:
  - target: context/conventions.md
    condition: when applying command naming/output conventions
  - target: context/stack.md
    condition: when checking Click/Rich and task verification tooling
  - target: patterns/debug-sync.md
    condition: when command behavior fails at sync/runtime boundaries
last_updated: 2026-04-10
---

# Add CLI Command

## Context
`src/secretzero/cli.py` is the command surface. New behavior usually threads into existing config loading, sync execution, or reporting helpers.

## Steps
1. Add command under the `main` Click group with clear options and help text.
2. Reuse existing loader/sync/report functions instead of reimplementing logic.
3. Emit user-facing output via Rich console helpers.
4. Add/adjust tests under `tests/` for command success and failure paths.
5. Run lint/format/test tasks.

## Gotchas
- Inconsistent option naming can break command discoverability and docs expectations.
- Bypassing shared loader/sync helpers creates divergence across commands.
- Raw `print` output conflicts with existing terminal UX patterns.

## Verify
- [ ] Command appears in CLI help and executes with expected options.
- [ ] Error paths produce actionable user-facing output.
- [ ] Tests for new command behavior pass.

## Debug
- If command fails inside sync flow, jump to `patterns/debug-sync.md`.

## Update Scaffold
- [ ] Update `ROUTER.md` if command category materially changes agent workflows.
