---
name: add-bundle
description: Add a new provider, generator, or target through bundle manifest registration.
triggers:
  - "add provider"
  - "add generator"
  - "add target"
  - "bundle"
edges:
  - target: context/architecture.md
    condition: when understanding registry-based dispatch model
  - target: context/conventions.md
    condition: when checking naming and implementation conventions
  - target: context/decisions.md
    condition: when validating why hard-coded branching is disallowed
  - target: patterns/debug-sync.md
    condition: when bundle registration succeeds but runtime dispatch fails
last_updated: 2026-04-10
---

# Add Bundle

## Context
Use this for provider/generator/target extensibility work under `src/secretzero/providers`, `src/secretzero/generators`, `src/secretzero/targets`, and `src/secretzero/bundles/registry.py`.

## Steps
1. Implement class in the correct module (`src/secretzero/providers/`, `src/secretzero/generators/`, or `src/secretzero/targets/`).
2. Ensure provider modules expose `_get_bundle_manifest()` with proper class-path mappings.
3. Register the provider manifest factory in `_register_builtin_bundles()` or ship through entry points.
4. Add optional dependency extras in `pyproject.toml` when new SDKs are required.
5. Validate with targeted tests and `secretzero providers` / sync dry-run paths.

## Gotchas
- Unknown kind errors usually mean registration path mismatch, not generator/target logic bugs.
- Provider capability auto-discovery depends on method naming prefixes.
- Missing optional extras can silently remove classes from runtime registration.

## Verify
- [ ] New kind appears via provider/bundle listing command paths.
- [ ] Sync dry-run can resolve and instantiate the new kind.
- [ ] Tests cover registration + behavior (happy path and failure mode).

## Debug
- Use `patterns/debug-sync.md` for unknown kind, unsupported target, or provider init failures.

## Update Scaffold
- [ ] Update `context/stack.md` and `context/architecture.md` for new external integrations.
