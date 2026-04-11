---
name: add-secret
description: Add simple or template-backed secrets to `Secretfile.yml` safely.
triggers:
  - "add secret"
  - "new secret"
  - "template secret"
edges:
  - target: context/architecture.md
    condition: when tracing generator-to-target flow for a new secret
  - target: patterns/secretfile-authoring.md
    condition: when secret edits require provider/variable config changes
  - target: patterns/debug-sync.md
    condition: when the new secret does not sync or is unexpectedly skipped
last_updated: 2026-04-10
---

# Add Secret

## Context
Use this when editing `Secretfile.yml` to add secrets or template instances that will sync through `SyncEngine`.

## Task: Add a Simple Secret

### Steps
1. Add a `secrets:` item with `name`, `kind`, `config`, and `targets`.
2. Use a supported generator kind and explicit target `provider` + `kind`.
3. Run `secretzero validate -f Secretfile.yml`.
4. Run `secretzero sync --dry-run`.
5. Run `secretzero sync` and confirm lockfile entry appears.

### Gotchas
- `one_time: true` will skip regeneration once present in lockfile.
- A set environment fallback variable can override generation.
- Wrong provider alias in target config leads to provider initialization errors.

### Verify
- [ ] Validate passes.
- [ ] Dry-run shows expected target actions.
- [ ] Sync writes to expected targets.
- [ ] `.gitsecrets.lock` stores hash metadata (not plaintext).

## Task: Add a Template Secret

### Steps
1. Define `templates.<name>.fields` and optional template-level targets.
2. Add a secret with `kind: templates.<name>`.
3. Validate and run dry-run/sync as above.

### Gotchas
- Field-level lockfile entries are keyed like `<secret>.<field>`.
- Template rendering is deferred until final render stage in sync.

### Verify
- [ ] All expected field entries are tracked.
- [ ] Template target output renders with all expected fields.

## Update Scaffold
- [ ] Update `.mex/ROUTER.md` if secret workflows materially changed.
- [ ] Update related context files if new generator/target behavior was discovered.
