# secretzero sync

Generate and synchronize secrets to targets.

## Synopsis

```bash
secretzero sync [OPTIONS]
```

## Description

The `sync` command generates secret values according to your Secretfile configuration and stores them in the specified targets (local files, cloud providers, etc.). It's idempotent - running it multiple times will only generate new secrets when needed.

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--file`, `-f` | path | `Secretfile.yml` | Path to Secretfile |
| `--lockfile`, `-l` | path | `.gitsecrets.lock` | Path to lockfile |
| `--dry-run` | flag | `false` | Show what would be done without making changes |
| `--help` | flag | - | Show help message |

## Examples

### Basic Sync

Generate and sync all secrets:

```bash
secretzero sync
```

**Output:**

```
Synchronizing secrets...

✓ Processed 3 secrets
  • Generated: 2
  • Skipped: 1
  • Stored: 2

✓ Lockfile saved: .gitsecrets.lock
```

### Dry Run

Preview what would be generated without making changes:

```bash
secretzero sync --dry-run
```

**Output:**

```
DRY RUN: No changes will be made

Synchronizing secrets...

✓ Processed 3 secrets
  • Generated: 2
  • Skipped: 1
  • Stored: 0

Details:

  database_password [random_password]: would generate
    → aws/ssm_parameter: would store at /production/db-password

  api_key [static]: skipped (already exists in lockfile)

  redis_password [random_password]: would generate
    → aws/ssm_parameter: would store at /production/redis-password
    → kubernetes/kubernetes_secret: would store in default/redis-secret

This was a dry run. Use 'secretzero sync' to apply changes.
```

### Custom Files

Use specific Secretfile and lockfile:

```bash
secretzero sync --file Secretfile.prod.yml --lockfile .production.lock
```

Or using short forms:

```bash
secretzero sync -f Secretfile.prod.yml -l .production.lock
```

## How Sync Works

### 1. Load Configuration

Reads and validates the Secretfile:

```
Loading: Secretfile.yml
Validating configuration...
```

### 2. Load Lockfile

Reads existing lockfile (if any):

```
Loading lockfile: .gitsecrets.lock
```

### 3. Check Each Secret

For each secret in the Secretfile:

- Check if already generated (exists in lockfile)
- Check if one_time flag is set
- Determine if generation is needed

### 4. Generate Secrets

Generate new secret values for secrets that need them:

- Random passwords
- Random strings
- Static values
- Script outputs
- API responses

### 5. Store in Targets

Store generated secrets in configured targets:

- Local files (.env, JSON, YAML, TOML)
- AWS SSM Parameter Store
- AWS Secrets Manager
- HashiCorp Vault
- Azure Key Vault
- Kubernetes Secrets
- GitHub Actions Secrets
- GitLab CI/CD Variables
- Jenkins Credentials

### 6. Update Lockfile

Update lockfile with:

- SHA-256 hashes of generated values
- Creation and update timestamps
- Metadata about secrets

## Behavior

### Idempotent Operation

Sync is idempotent - running it multiple times won't regenerate secrets unnecessarily:

```bash
# First run - generates all secrets
secretzero sync
# Output: Generated: 3

# Second run - skips existing secrets
secretzero sync
# Output: Generated: 0, Skipped: 3
```

### One-Time Secrets

Secrets marked as `one_time` are never regenerated:

```yaml
secrets:
  - name: master_key
    kind: random_password
    one_time: true  # Generated once, never again
    config:
      length: 64
```

```bash
secretzero sync
# First run: generates master_key

secretzero sync
# Subsequent runs: always skips master_key
```

### Adding New Secrets

When you add new secrets to your Secretfile, only the new secrets are generated:

```yaml
# Original Secretfile.yml
secrets:
  - name: existing_secret
    kind: random_password

# Updated Secretfile.yml
secrets:
  - name: existing_secret
    kind: random_password
  - name: new_secret  # Added
    kind: random_password
```

```bash
secretzero sync
# Output: Generated: 1 (only new_secret)
#         Skipped: 1 (existing_secret)
```

### Multiple Targets

A single secret can be stored in multiple targets:

```yaml
secrets:
  - name: shared_secret
    kind: random_password
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /app/secret
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
```

The same generated value is stored in all targets:

```
database_password [random_password]: generated
  → aws/ssm_parameter: stored at /app/secret
  → local/file: stored in .env
```

## Complete Workflow

### Initial Setup

```bash
# 1. Create Secretfile
secretzero init

# 2. Customize configuration
vim Secretfile.yml

# 3. Validate
secretzero validate

# 4. Preview (dry run)
secretzero sync --dry-run

# 5. Generate secrets
secretzero sync
```

### After Modifying Secrets

```bash
# 1. Edit Secretfile
vim Secretfile.yml

# 2. Validate changes
secretzero validate

# 3. Preview changes
secretzero sync --dry-run

# 4. Apply changes
secretzero sync
```

### Environment-Specific Sync

```bash
# Development
ENVIRONMENT=dev secretzero sync -f Secretfile.dev.yml -l .dev.lock

# Staging
ENVIRONMENT=staging secretzero sync -f Secretfile.staging.yml -l .staging.lock

# Production
ENVIRONMENT=production secretzero sync -f Secretfile.prod.yml -l .prod.lock
```

## Error Handling

### Target Storage Failures

If a target fails, the error is reported but sync continues:

```
Synchronizing secrets...

database_password [random_password]: generated
  → aws/ssm_parameter: ✓ stored
  → kubernetes/kubernetes_secret: ✗ failed: namespace not found

Errors:
  • database_password: Failed to store in kubernetes/kubernetes_secret: namespace 'production' not found
```

**Fix the error and re-run:**

```bash
# Create the missing namespace
kubectl create namespace production

# Re-run sync
secretzero sync
```

### Provider Authentication Failures

If provider authentication fails:

```
Error during sync: AWS authentication failed: Unable to locate credentials
```

**Solution:**

```bash
# Configure AWS credentials
aws configure

# Or use environment variables
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_REGION=us-east-1

# Re-run sync
secretzero sync
```

### Lockfile Conflicts

If lockfile is corrupted or has conflicts:

```
Error: Failed to load lockfile: invalid format
```

**Solutions:**

1. **Backup and regenerate:**

```bash
mv .gitsecrets.lock .gitsecrets.lock.backup
secretzero sync
```

2. **Fix lockfile format:**

Ensure lockfile is valid YAML and follows correct structure.

## Output Details

### Processed Secrets

```
✓ Processed 5 secrets
  • Generated: 2  # New secrets generated
  • Skipped: 3    # Existing secrets (not regenerated)
  • Stored: 4     # Total target storages
```

### Secret-Level Details

```
Details:

  database_password [random_password]: generated
    • Length: 32 characters
    → aws/ssm_parameter: stored at /production/db-password
    → local/file: stored in .env

  api_key [static]: skipped (already exists in lockfile)

  redis_password [random_password]: generated
    → aws/ssm_parameter: stored at /production/redis-password
```

### Template Secrets

For secrets using templates:

```
  app_credentials [templates.db_creds]: generated
    • username: skipped (static value unchanged)
    • password: generated
    • host: skipped (static value unchanged)
    → aws/secrets_manager: stored at /production/app-creds
```

## Best Practices

### 1. Always Dry Run First

```bash
# Preview in production
secretzero sync -f Secretfile.prod.yml --dry-run

# If looks good, apply
secretzero sync -f Secretfile.prod.yml
```

### 2. Validate Before Syncing

```bash
secretzero validate && secretzero sync
```

### 3. Use Environment Variables

```bash
# Set environment-specific variables
export ENVIRONMENT=production
export AWS_REGION=us-east-1

secretzero sync
```

### 4. Version Control Lockfile (Optional)

Consider committing lockfile (it contains only hashes):

```bash
git add .gitsecrets.lock
git commit -m "Update secret lockfile"
```

**Pros:**

- Track when secrets were generated
- Team visibility into secret state
- Audit trail

**Cons:**

- Even hashes can be sensitive
- May not align with security policies

### 5. Separate Lockfiles Per Environment

```bash
# Development lockfile
secretzero sync -f Secretfile.dev.yml -l .dev.lock

# Production lockfile
secretzero sync -f Secretfile.prod.yml -l .prod.lock
```

### 6. Automate in CI/CD

```yaml
# .github/workflows/secrets.yml
name: Sync Secrets

on:
  push:
    branches: [main]
    paths:
      - 'Secretfile.yml'

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install SecretZero
        run: pip install secretzero[all]
      
      - name: Validate Configuration
        run: secretzero validate
      
      - name: Sync Secrets
        run: secretzero sync
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          AWS_REGION: us-east-1
```

## Troubleshooting

### Nothing Generated

**Issue:** Sync reports "Generated: 0" but you expect secrets to be generated.

**Causes:**

1. Secrets already exist in lockfile
2. One-time secrets already generated
3. Configuration error

**Solution:**

```bash
# Check lockfile
cat .gitsecrets.lock

# Check specific secret
secretzero show database_password

# Force regeneration (see rotate command)
secretzero rotate --force database_password
```

### Sync Hangs

**Issue:** Sync command appears to hang.

**Causes:**

1. Slow provider API
2. Network issues
3. Large number of secrets

**Solution:**

```bash
# Enable verbose output
secretzero sync --verbose

# Check provider connectivity first
secretzero test
```

### Permission Denied

**Issue:** Cannot write to target location.

```
Error: Permission denied: .env
```

**Solution:**

```bash
# Check file permissions
ls -l .env

# Make writable
chmod 644 .env

# Or remove and recreate
rm .env
secretzero sync
```

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success - all secrets synced |
| `1` | Error - sync failed |
| `3` | Validation error |
| `4` | Provider connection error |

## Related Commands

- [`validate`](validate.md) - Validate configuration before sync
- [`show`](show.md) - Show information about synced secrets
- [`rotate`](rotate.md) - Rotate existing secrets
- [`drift`](drift.md) - Detect drift from expected state

## See Also

- [Configuration Guide](../configuration/index.md) - Learn about Secretfile
- [Providers](../providers/index.md) - Provider documentation
- [Targets](../targets/index.md) - Target storage types
- [Examples](../../examples/index.md) - Real-world examples
