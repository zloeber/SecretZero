---
name: agents
description: Always-loaded project anchor. Read this first. Contains project identity, non-negotiables, commands, and pointer to ROUTER.md for full context.
last_updated: 2026-04-10
---

# SecretZero

## What This Is
A Python CLI and optional API for declarative secrets-as-code workflows that validate, generate, sync, and audit secrets from `Secretfile.yml` into local and provider-backed targets using a hash-only lockfile.

## Non-Negotiables
- Never store plaintext secret values in files, logs, or lockfile entries; only SHA-256 hashes are persisted.
- Keep provider/generator/target dispatch in `BundleRegistry`; do not add provider-kind conditional chains in `SyncEngine`.
- Use Pydantic v2 APIs only (`model_dump()` / `model_dump_json()`), never v1-style `.dict()` / `.json()`.
- Register new providers/generators/targets through `_get_bundle_manifest()` and `_register_builtin_bundles()` (or entry points), not ad-hoc imports.
- Use Rich console output for user-facing CLI output (`Console.print()`), not raw `print()`.

## Commands
- Setup: `uv sync --all-extras && source .venv/bin/activate`
- Validate: `secretzero validate -f Secretfile.yml`
- Dry run: `secretzero sync --dry-run`
- Sync: `secretzero sync`
- Tests: `task test`
- Lint fix: `task lint:fix`
- Format: `task format`
- Schema: `task schema:update`
- Security: `task security:scan`
- Validation suite: `task test:validations`

## Scaffold Growth
After every task: if no pattern exists for the task type you just completed, create one. If a pattern or context file is now out of date, update it. The scaffold grows from real work, not just setup. See the GROW step in `ROUTER.md` for details.

## Navigation
At the start of every session, read `ROUTER.md` before doing anything else.
For full project context, patterns, and task guidance — everything is there.
