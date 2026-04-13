---
name: secretfile-authoring
description: Author or refactor `Secretfile.yml` with correct variable/provider structure.
triggers:
  - "secretfile"
  - "variables"
  - "var-file"
  - "provider config"
edges:
  - target: context/architecture.md
    condition: when understanding ConfigLoader and SyncEngine boundaries
  - target: context/setup.md
    condition: when command usage or environment setup is needed
  - target: patterns/add-secret.md
    condition: when authoring includes adding/changing secret entries
last_updated: 2026-04-13
---

# Secretfile Authoring

## Context
This pattern covers edits to `Secretfile.yml` structure (`variables`, `providers`, `templates`, `secrets`, `policies`) and var-file merge usage.

## Steps
1. Keep top-level sections explicit and valid for Pydantic model parsing.
2. Ensure provider aliases in `providers:` match references in all secret targets.
3. Validate interpolation assumptions with `secretzero render`.
4. Validate schema with `secretzero validate -f Secretfile.yml`.
5. Run `secretzero sync --dry-run` before real sync.

## Gotchas
- `${VAR}` interpolation is based on merged variable context in config flow, not implicit shell env substitution.
- Var-file ordering matters; later `--var-file` overrides earlier values.
- A typo in interpolated key paths can silently produce wrong/empty rendered values in downstream config.
- Secretfile root `version` is no longer required; manifest spec versioning is tracked in `.gitsecrets.lock` under `secretfile.manifest_spec_version`.

## Verify
- [ ] Render output contains expected provider paths and secret target config.
- [ ] Validation passes without schema/type errors.
- [ ] Dry-run output aligns with intended provider/target routes.

## Debug
- If sync fails after valid render/validate, follow `patterns/debug-sync.md`.

## Update Scaffold
- [ ] Add newly discovered authoring gotchas to this pattern.
