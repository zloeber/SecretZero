# secretzero rotate

Rotate secrets based on rotation policies.

## Synopsis

```bash
secretzero rotate [SECRET_NAME] [OPTIONS]
```

## Description

The `rotate` command checks which secrets need rotation based on their `rotation_period` settings and regenerates them. It respects `one_time` flags and provides dry-run capabilities for safe previewing.

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `SECRET_NAME` | No | Specific secret to rotate (omit to check all) |

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--file`, `-f` | path | `Secretfile.yml` | Path to Secretfile |
| `--lockfile`, `-l` | path | `.gitsecrets.lock` | Path to lockfile |
| `--force` | flag | `false` | Force rotation even if not due |
| `--dry-run` | flag | `false` | Show what would be rotated without making changes |
| `--help` | flag | - | Show help message |

## Examples

### Check All Secrets

Check which secrets need rotation:

```bash
secretzero rotate --dry-run
```

**Output:**

```
Checking secrets for rotation...

  ⚠️  database_password: rotation due (last rotated 91 days ago, policy: 90d)
  ✓  api_key: not due for rotation (last rotated 30 days ago, policy: 90d)
  ⚠️  redis_password: rotation due (last rotated 95 days ago, policy: 90d)
  ⚠️  service_token: one_time secret (rotation disabled)

Found 2 secret(s) to rotate

DRY RUN: No changes will be made
  Would rotate: database_password
  Would rotate: redis_password
```

### Rotate Due Secrets

Rotate all secrets that are due for rotation:

```bash
secretzero rotate
```

**Output:**

```
Checking secrets for rotation...

  ⚠️  database_password: rotation due (last rotated 91 days ago, policy: 90d)
  ⚠️  redis_password: rotation due (last rotated 95 days ago, policy: 90d)

Found 2 secret(s) to rotate

Rotating secrets...

✓ Rotated 2 secrets

✓ Lockfile updated: .gitsecrets.lock
```

### Force Rotate Specific Secret

Force rotation of a specific secret even if not due:

```bash
secretzero rotate --force database_password
```

**Output:**

```
Checking secrets for rotation...

  ℹ️  database_password: forced rotation

Found 1 secret(s) to rotate

Rotating secrets...

✓ Rotated 1 secrets

✓ Lockfile updated: .gitsecrets.lock
```

### Rotate Specific Secret (If Due)

Rotate a specific secret only if due:

```bash
secretzero rotate api_key
```

## How Rotation Works

### 1. Check Rotation Requirements

For each secret, SecretZero checks:

- Does it have a `rotation_period` defined?
- Is it marked as `one_time`?
- When was it last rotated?
- Is rotation due based on policy?

### 2. Determine Rotation Status

```
Rotation Due = (Current Time - Last Rotated) >= Rotation Period
```

Example:

```yaml
secrets:
  - name: database_password
    rotation_period: 90d  # Rotate every 90 days
```

- Last rotated: 2024-01-01
- Current date: 2024-04-05 (94 days later)
- Status: ⚠️ Rotation due (94 days > 90 days)

### 3. Generate New Values

For secrets that need rotation:

- Generate new secret value using configured generator
- Update lockfile with new hash
- Update `last_rotated` timestamp
- Increment `rotation_count`

### 4. Store in Targets

Store new values in all configured targets:

- AWS SSM Parameter Store
- AWS Secrets Manager
- HashiCorp Vault
- Kubernetes Secrets
- Local files
- CI/CD platforms

### 5. Update Lockfile

Update lockfile with rotation metadata:

```yaml
secrets:
  database_password:
    hash: new_hash_value
    created_at: '2024-01-01T00:00:00Z'
    updated_at: '2024-04-05T10:30:00Z'
    last_rotated: '2024-04-05T10:30:00Z'  # Updated
    rotation_count: 3  # Incremented
```

## Rotation Period Format

Rotation periods use duration format:

| Format | Meaning | Example |
|--------|---------|---------|
| `Nd` | N days | `90d` = 90 days |
| `Nw` | N weeks | `2w` = 2 weeks |
| `Nm` | N months | `3m` = 3 months |
| `Ny` | N years | `1y` = 1 year |

**Common rotation periods:**

```yaml
secrets:
  # Weekly rotation
  - name: short_lived_token
    rotation_period: 7d
  
  # Monthly rotation
  - name: api_key
    rotation_period: 30d
  
  # Quarterly rotation (SOC2)
  - name: database_password
    rotation_period: 90d
  
  # Bi-annual rotation
  - name: encryption_key
    rotation_period: 180d
  
  # Annual rotation
  - name: root_certificate
    rotation_period: 1y
```

## One-Time Secrets

Secrets marked as `one_time` are never automatically rotated:

```yaml
secrets:
  - name: encryption_master_key
    kind: random_password
    one_time: true  # Never auto-rotate
    rotation_period: 180d  # Warning only
    config:
      length: 64
```

**Output when checking rotation:**

```
⚠️ encryption_master_key: one_time secret (rotation disabled)
```

**Manual rotation:**

Even one-time secrets can be force-rotated:

```bash
secretzero rotate --force encryption_master_key
```

⚠️ **Warning:** This should be done with extreme caution for one-time secrets!

## Compliance Use Cases

### SOC2 Compliance

SOC2 typically requires rotation every 90 days:

```yaml
metadata:
  compliance:
    - soc2

secrets:
  - name: database_password
    kind: random_password
    rotation_period: 90d  # SOC2 requirement
    config:
      length: 32
```

Verify compliance:

```bash
# Check rotation status
secretzero rotate --dry-run

# Check policy compliance
secretzero policy
```

### ISO27001 Compliance

ISO27001 may require different rotation periods:

```yaml
metadata:
  compliance:
    - iso27001

secrets:
  # Critical systems - 90 days
  - name: production_db_password
    rotation_period: 90d
  
  # Non-critical systems - 180 days
  - name: dev_db_password
    rotation_period: 180d
```

### Custom Compliance Policies

Define policies in your Secretfile:

```yaml
policies:
  rotation_required:
    kind: rotation
    require_rotation_period: true
    severity: error
    enabled: true
  
  max_rotation_age:
    kind: rotation
    max_age: 90d
    severity: error
    enabled: true
```

Check compliance:

```bash
secretzero policy --fail-on-warning
```

## Workflows

### Regular Rotation Check

Check for due rotations regularly:

```bash
# Weekly check
secretzero rotate --dry-run

# If secrets need rotation
secretzero rotate
```

### Scheduled Rotation

Automate with cron:

```bash
# /etc/cron.d/secretzero-rotation
# Check daily at 2 AM
0 2 * * * cd /path/to/project && secretzero rotate --dry-run | mail -s "Secret Rotation Status" admin@example.com

# Rotate weekly on Sunday at 3 AM
0 3 * * 0 cd /path/to/project && secretzero rotate
```

### CI/CD Pipeline Rotation

```yaml
# .github/workflows/rotate-secrets.yml
name: Rotate Secrets

on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly on Sunday
  workflow_dispatch:  # Manual trigger

jobs:
  rotate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install SecretZero
        run: pip install secretzero[all]
      
      - name: Check Rotation Status
        run: secretzero rotate --dry-run
      
      - name: Rotate Due Secrets
        run: secretzero rotate
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          AWS_REGION: us-east-1
      
      - name: Commit Lockfile
        run: |
          git config user.name "SecretZero Bot"
          git config user.email "bot@example.com"
          git add .gitsecrets.lock
          git commit -m "Rotate secrets [automated]" || true
          git push
```

### Emergency Rotation

Immediately rotate compromised secrets:

```bash
# Force rotate compromised secret
secretzero rotate --force api_key

# Verify rotation
secretzero show api_key
```

## Best Practices

### 1. Regular Dry Runs

Check rotation status regularly:

```bash
# Daily check
secretzero rotate --dry-run
```

### 2. Staged Rotation

Rotate in stages for critical systems:

```bash
# Stage 1: Rotate development
secretzero rotate -f Secretfile.dev.yml

# Test applications

# Stage 2: Rotate staging
secretzero rotate -f Secretfile.staging.yml

# Test applications

# Stage 3: Rotate production
secretzero rotate -f Secretfile.prod.yml
```

### 3. Notification on Rotation

Send notifications when rotation occurs:

```bash
#!/bin/bash
# rotate-with-notification.sh

if secretzero rotate --dry-run | grep -q "Found [1-9]"; then
  # Secrets need rotation
  echo "Rotating secrets..."
  secretzero rotate
  
  # Send notification
  curl -X POST https://hooks.slack.com/services/YOUR/WEBHOOK/URL \
    -d '{"text":"Secrets rotated successfully"}'
else
  echo "No secrets need rotation"
fi
```

### 4. Document Rotation Procedures

Create rotation runbook:

```markdown
# Secret Rotation Procedure

## Pre-Rotation

1. Verify all applications are healthy
2. Check recent incidents
3. Review rotation schedule

## Rotation

1. Check rotation status: `secretzero rotate --dry-run`
2. Notify team
3. Rotate secrets: `secretzero rotate`
4. Verify rotation: `secretzero show <secret_name>`

## Post-Rotation

1. Monitor application health
2. Check error logs
3. Verify connectivity
4. Update documentation

## Rollback

If issues occur:
1. Restore from lockfile backup
2. Re-sync previous values
3. Investigate root cause
```

### 5. Backup Before Rotation

```bash
#!/bin/bash
# safe-rotate.sh

# Backup lockfile
cp .gitsecrets.lock .gitsecrets.lock.backup

# Rotate
if secretzero rotate; then
  echo "✅ Rotation successful"
  rm .gitsecrets.lock.backup
else
  echo "❌ Rotation failed - restoring backup"
  mv .gitsecrets.lock.backup .gitsecrets.lock
  exit 1
fi
```

## Troubleshooting

### No Secrets Rotated

**Issue:** Rotate command runs but rotates nothing.

**Causes:**

1. No rotation policies defined
2. No secrets due for rotation
3. All secrets marked as one_time

**Solution:**

```bash
# Check rotation configuration
yq '.secrets[] | {name: .name, rotation_period: .rotation_period, one_time: .one_time}' Secretfile.yml

# Force rotation if needed
secretzero rotate --force secret_name
```

### Rotation Fails for Some Secrets

**Issue:** Some secrets rotate, others fail.

**Cause:** Provider authentication or connectivity issues.

**Solution:**

```bash
# Test provider connectivity
secretzero test

# Check error messages
secretzero rotate --verbose

# Retry failed rotations
secretzero rotate
```

### One-Time Secret Warning

**Issue:** Warning about one-time secret rotation.

```
⚠️ master_key: one_time secret (rotation disabled)
```

**This is expected behavior.** One-time secrets are not automatically rotated.

**To rotate manually:**

```bash
# Only if absolutely necessary
secretzero rotate --force master_key
```

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success - all rotations completed |
| `1` | Error - rotation failed |
| `4` | Provider connection error |

## Related Commands

- [`show`](show.md) - Check rotation status
- [`policy`](policy.md) - Check rotation policies
- [`sync`](sync.md) - Initial secret generation
- [`drift`](drift.md) - Detect unauthorized changes

## See Also

- [Rotation Configuration](../configuration/secretfile.md#rotation-period-format) - Rotation settings
- [Policy Enforcement](policy.md) - Rotation policies
- [Compliance Guide](../../use-cases/compliance.md) - Compliance requirements
