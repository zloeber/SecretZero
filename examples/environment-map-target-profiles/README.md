# Environment Map + Target Profiles Example

This example demonstrates:

- top-level `environments` lane map
- lane-specific `.szvar` files and lockfiles
- `target_profiles` for environment-specific default target behavior

## Validate

```bash
secretzero validate -f examples/environment-map-target-profiles/Secretfile.yml
```

## Sync by lane

```bash
# Uses environments.default (dev)
secretzero sync -f examples/environment-map-target-profiles/Secretfile.yml --dry-run

# Explicit lane selection
secretzero sync -f examples/environment-map-target-profiles/Secretfile.yml --environment staging --dry-run
secretzero sync -f examples/environment-map-target-profiles/Secretfile.yml --environment prod --dry-run
```

## Runtime overrides still win

```bash
secretzero sync \
  -f examples/environment-map-target-profiles/Secretfile.yml \
  --environment prod \
  --var-file examples/environment-map-target-profiles/dev.szvar \
  --lockfile examples/environment-map-target-profiles/custom.lock \
  --dry-run
```
