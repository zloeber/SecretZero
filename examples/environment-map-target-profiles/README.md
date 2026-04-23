# Environment Map + Target Profiles Example

This example demonstrates:

- top-level `environments` lane map
- lane-specific `.szvar` files and lockfiles
- `target_profiles` for environment-specific default target behavior
- one shared secret definition that prompts manually once per environment lane
- environment-specific AWS identity guardrails driven by lane vars (`aws_account_id`, `aws_region`)

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

## Manual seed behavior (one prompt per environment)

The secret is defined once (`app_api_token`) as `kind: static` and `one_time: true`.
Because each lane uses its own lockfile, the first real sync per lane prompts once for that lane's value.

```bash
# Prompts once for dev
secretzero sync -f examples/environment-map-target-profiles/Secretfile.yml --environment dev

# Prompts once for staging
secretzero sync -f examples/environment-map-target-profiles/Secretfile.yml --environment staging

# Prompts once for prod
secretzero sync -f examples/environment-map-target-profiles/Secretfile.yml --environment prod
```

Each lane enforces `policies.aws_env_identity` against the AWS caller identity using values from
that lane's `.szvar` file, and the target path includes the lane name via `/${env}/app/api-token`.

## Runtime overrides still win

```bash
secretzero sync \
  -f examples/environment-map-target-profiles/Secretfile.yml \
  --environment prod \
  --var-file examples/environment-map-target-profiles/dev.szvar \
  --lockfile examples/environment-map-target-profiles/custom.lock \
  --dry-run
```
