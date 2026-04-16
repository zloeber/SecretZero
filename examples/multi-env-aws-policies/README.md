# Multi-Environment AWS + Local Dev Example

This example is fully self-contained in one folder and demonstrates:

- local development secrets generated into `.env.local` (non-tracked),
- AWS dev/staging/prod target lanes,
- provider identity policy enforcement for account + role + region.

## Files

- `Secretfile.yml` - Main manifest.
- `dev.szvar` - Expected identity for AWS dev lane.
- `staging.szvar` - Expected identity for AWS staging lane.
- `prod.szvar` - Expected identity for AWS production lane.
- `.gitignore` - Prevents local secret and lockfile tracking.

## What the policy enforces

`policies.aws_target_identity` requires all three fields from the current AWS identity:

- `account` must match `expected_aws_account`
- `arn` must match the assumed role `expected_aws_role`
- `region` must match `aws_region`

All AWS targets in this example attach:

```yaml
identity_policies: [aws_target_identity]
```

So sync is blocked if credentials do not match the selected lane.

## Local development workflow (no AWS required)

Run from repository root:

```bash
secretzero validate -f examples/multi-env-aws-policies/Secretfile.yml

secretzero sync \
  -f examples/multi-env-aws-policies/Secretfile.yml \
  --lockfile examples/multi-env-aws-policies/.gitsecrets.lock \
  --secret app_local_db_password
```

Result: `examples/multi-env-aws-policies/.env.local` is created/updated with `APP_DB_PASSWORD`.

## AWS environment workflows

Use the secret for the target lane with the matching `.szvar`.

### Dev

```bash
secretzero sync \
  -f examples/multi-env-aws-policies/Secretfile.yml \
  --var-file examples/multi-env-aws-policies/dev.szvar \
  --lockfile examples/multi-env-aws-policies/.gitsecrets.lock \
  --secret app_dev_api_token
```

### Staging

```bash
secretzero sync \
  -f examples/multi-env-aws-policies/Secretfile.yml \
  --var-file examples/multi-env-aws-policies/staging.szvar \
  --lockfile examples/multi-env-aws-policies/.gitsecrets.lock \
  --secret app_staging_api_token
```

### Production

```bash
secretzero sync \
  -f examples/multi-env-aws-policies/Secretfile.yml \
  --var-file examples/multi-env-aws-policies/prod.szvar \
  --lockfile examples/multi-env-aws-policies/.gitsecrets.lock \
  --secret app_prod_api_token
```

## Quick verification

- Check provider identity data:

```bash
secretzero status -f examples/multi-env-aws-policies/Secretfile.yml --format json
```

- Dry-run first when switching lanes:

```bash
secretzero sync \
  -f examples/multi-env-aws-policies/Secretfile.yml \
  --var-file examples/multi-env-aws-policies/prod.szvar \
  --lockfile examples/multi-env-aws-policies/.gitsecrets.lock \
  --secret app_prod_api_token \
  --dry-run
```
