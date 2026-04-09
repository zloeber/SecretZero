---
name: agents
description: Always-loaded project anchor. Read this first. Contains project identity, non-negotiables, commands, and pointer to ROUTER.md for full context.
last_updated: 2026-04-09
---

# SecretZero

## What This Is

A Python CLI tool that automates the creation, seeding, rotation, and lifecycle management of project secrets via declarative `Secretfile.yml` manifests, storing generated values in cloud secret stores (Vault, AWS, Azure, GitHub, etc.) and tracking provenance in a committed lockfile.

## Non-Negotiables

- Never store plaintext secret values in the lockfile, logs, exception messages, or anywhere on disk — only SHA-256 hashes
- All provider, generator, and target dispatch goes through `BundleRegistry`; never add `if provider_kind == "X"` chains in `SyncEngine`
- Use Pydantic v2 API: `model_dump()` / `model_dump_json()`, never `.dict()` / `.json()`
- New providers/generators/targets must register via `_get_bundle_manifest()` factory and be listed in `_register_builtin_bundles()` in `bundles/registry.py`
- All user-facing CLI output uses `rich.console.Console`, never bare `print()`

## Commands

- Validate: `secretzero validate -f Secretfile.yml`
- Dry-run sync: `secretzero sync --dry-run`
- Sync: `secretzero sync`
- Force rotate: `secretzero sync --force-rotation`
- Status: `secretzero status`
- Policy check: `secretzero check`
- Test: `pytest`
- Lint: `ruff check src/`
- Format: `black src/`

## Scaffold Growth

After every task: if no pattern exists for the task type you just completed, create one. If a pattern or context file is now out of date, update it. The scaffold grows from real work, not just setup. See the GROW step in `ROUTER.md` for details.

## Navigation

At the start of every session, read `ROUTER.md` before doing anything else.
For full project context, patterns, and task guidance — everything is there.
