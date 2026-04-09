---
name: debug-sync
description: Diagnosing failures in the secretzero sync pipeline — from config load through generation to target storage.
triggers:
  - "sync failed"
  - "sync error"
  - "debug sync"
  - "not storing"
  - "not generating"
  - "lockfile"
  - "target failed"
  - "provider not found"
  - "generator not found"
edges:
  - target: context/architecture.md
    condition: when tracing the full sync flow to find the failure boundary
  - target: patterns/add-bundle.md
    condition: when the failure is a missing provider/generator/target registration
  - target: patterns/add-secret.md
    condition: when the failure is in Secretfile configuration
last_updated: 2026-04-09
---

# Debug Sync

## Context

Load `context/architecture.md`. The sync pipeline has four failure boundaries:

1. **Config load** — Secretfile.yml parse / variable interpolation / Pydantic validation
2. **Provider connectivity** — `SyncEngine._validate_target_access()` runs before any generation
3. **Generation** — `BundleRegistry` lookup → generator instantiation → `generate_with_fallback()`
4. **Target storage** — provider auth → target class instantiation → `target.store()`

Identify which boundary failed before debugging further.

## Steps: Isolate the Boundary

**Step 1 — Config load:**
```bash
secretzero validate -f Secretfile.yml
# If this fails: fix YAML syntax, variable references, or Pydantic schema errors
# Use 'secretzero render' to inspect interpolated values
secretzero render -f Secretfile.yml
```

**Step 2 — Provider connectivity:**
```bash
secretzero sync --dry-run
# If this fails with "No accessible targets found": provider auth or network issue
# Check provider-specific env vars (VAULT_TOKEN, AWS credentials, GITHUB_TOKEN, etc.)
```

**Step 3 — Generation / target storage:**
```bash
secretzero sync -f Secretfile.yml  # watch output for per-secret errors
secretzero status                   # check what's in the lockfile after partial runs
```

## Failure Patterns and Fixes

**`ValueError: Unknown generator kind: 'X'`**
- The generator kind is not registered in `BundleRegistry`
- Check: `secretzero providers --bundles` to see what is registered
- Fix: install the provider extra (`pip install secretzero[aws]`), or add the generator to `_register_builtin_generators()` in `bundles/registry.py`

**`RuntimeError: Cannot sync secrets: No accessible targets found`**
- `SyncEngine._validate_target_access()` failed for all providers
- Check: provider auth env vars; provider service reachability; `secretzero init -f Secretfile.yml` to diagnose missing dependencies
- Note: `local` provider always passes this check — if only local targets are configured this error should not appear

**`error: 'X' generator requires provider 'Y' to be configured`**
- A `provider_backed` or `github_pat` generator references a provider name not in `providers:` block
- Fix: add the provider to the `providers:` section of `Secretfile.yml`

**Target status `"unsupported"` in sync output**
- The target `kind` string is not registered in `BundleRegistry`
- Check: correct spelling of the kind string against `TargetKind` enum values in `models.py`
- Fix: install the optional extra for that provider, or register the target class

**Target status `"error"` with `"Missing dependency: ..."`**
- Provider optional dependency not installed
- Fix: `pip install secretzero[<provider>]` where `<provider>` matches the extra name

**Secret shows `skipped: true` / `reason: "All targets already synced"`**
- The secret already exists in the lockfile with all targets tracked
- This is normal on re-runs. To force regeneration: `secretzero sync --force-rotation`
- To sync only missing targets (e.g., added a new target): just run `secretzero sync` — it detects untracked targets

**Secret shows `skipped: true` / `reason: "Cannot retrieve existing value for partial sync"`**
- A new target was added for an existing secret, but the existing value could not be retrieved from any tracked target (e.g., target is gone or unreachable)
- Fix: `secretzero sync --force-rotation --name <secret_name>` to regenerate the value and sync to all targets

**`one_time: true` secret never updates**
- Expected behaviour — `one_time: true` means "generate once and never again"
- To force an update: manually delete the secret's entry from `.gitsecrets.lock` (edit the JSON), then re-run sync

**Jinja2 variable silently empty**
- Typo in `{{var.some_key}}` or the variable is not defined
- Use `secretzero render` to inspect — empty strings in the output reveal the broken reference
- `SilentUndefined` in `ConfigLoader` swallows Jinja2 undefined errors; check spelling in `variables:` block

**`.gitsecrets.lock` has wrong content / stale state**
- `secretzero status` shows `secretfile_changed: true` if Secretfile was modified since last sync
- For a full reset: `rm .gitsecrets.lock && secretzero sync`

## What to Check When Debugging Tests

- Tests use `reset_bundle_registry()` from `secretzero.bundles` to get a fresh registry — if a test doesn't call this, it may see state from a previous test
- `Lockfile.load(path)` returns an empty `Lockfile()` if the path does not exist — tests can use `tmp_path / "test.lock"` for isolation
- Generator env var fallback: if `MY_SECRET` is set in the test environment, `generate_with_fallback("MY_SECRET")` returns the env var value, not a generated value — clear env vars in test setup

## Update Scaffold

- [ ] Update `.mex/ROUTER.md` "Known Issues" if a recurring failure is identified
- [ ] Update any `.mex/context/` files that are now out of date
- [ ] If a new failure pattern was found, add it to this file's "Failure Patterns" section
