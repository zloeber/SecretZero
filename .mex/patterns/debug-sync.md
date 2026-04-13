---
name: debug-sync
description: Diagnose failures across config load, provider access, generation, storage, and lockfile update.
triggers:
  - "sync failed"
  - "unknown kind"
  - "provider not initialized"
  - "cannot sync secrets"
edges:
  - target: context/architecture.md
    condition: when identifying failure boundary in the sync flow
  - target: patterns/add-bundle.md
    condition: when failure is a registration or optional dependency problem
  - target: patterns/add-secret.md
    condition: when failure is caused by manifest/target/secret configuration
last_updated: 2026-04-10
---

# Debug Sync

## Context
Troubleshoot `secretzero sync` by isolating boundary: config parse/interpolation, provider validation, generation, target store, or lockfile/provenance updates.

## Steps
1. `secretzero validate -f Secretfile.yml`
2. `secretzero render -f Secretfile.yml`
3. `secretzero sync --dry-run`
4. `secretzero sync` and inspect per-secret target statuses.
5. `secretzero status` for lockfile and secretfile drift/change context.

## Common Failure Patterns
- **Lockfile unchanged after sync** -> If you use `--format json`, ensure you are on a version where JSON sync persists the lockfile; otherwise use text output or omit `--format json`. Also confirm you did not use `--dry-run` or `--plan` (both skip lockfile writes). `secretzero web --dry-run` also skips persisting the lockfile.
- **Unknown generator/target kind** -> registration missing or optional dependency not installed.
- **No accessible targets found** -> provider auth/config/connectivity issue.
- **Provider not initialized** -> target references provider alias not defined in `providers:`.
- **Partial sync skipped** -> existing value could not be retrieved from prior tracked targets.
- **Unexpected empty values** -> interpolation key typo or wrong var-file merge assumptions.

## Verify
- [ ] Boundary is identified before changing code/config.
- [ ] Fix is validated via dry-run and real sync.
- [ ] Lockfile state reflects intended sync outcome.

## Update Scaffold
- [ ] Add newly discovered recurring failures to this pattern.
