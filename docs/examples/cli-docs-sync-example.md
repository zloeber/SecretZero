# secretzero sync (Example Integration)

Generate and synchronize secrets to targets.

!!! tip "This is an example page"
    This page demonstrates how to integrate auto-generated CLI documentation with your existing manual content.

## Overview

The `sync` command is the workhorse of SecretZero. It reads your Secretfile, generates secrets according to configured generators, and deploys them to all specified targets.

### Key Features

- ✅ **Idempotent** - Safe to run multiple times without regenerating secrets
- ✅ **Dry-run mode** - Preview changes before applying
- ✅ **Selective sync** - Sync only specific secrets with `--secret` flag
- ✅ **Variable files** - Override variables with `.szvar` files
- ✅ **Clean mode** - Remove orphaned lockfile entries (new!)

## Command Reference (Auto-Generated)

::: mkdocs-click
    :module: secretzero.cli
    :command: sync
    :prog_name: secretzero sync
    :depth: 0
    :style: table

---

*The above reference is automatically generated from the source code and always reflects the current CLI options.*

## Examples

### Basic Usage

Generate and sync all secrets:

```bash
secretzero sync
```

**Output:**

```
Synchronizing secrets...

Summary
✓ Success: 3 secret(s) stored
⊙ Skipped: 1 secret(s) skipped

✓ Lockfile saved: .gitsecrets.lock
```

### Dry Run

Preview what would be generated without making changes:

```bash
secretzero sync --dry-run
```

### Sync Specific Secrets

Sync only certain secrets:

```bash
# Single secret
secretzero sync --secret database_password

# Multiple secrets
secretzero sync --secret database_password --secret api_key

# Short form
secretzero sync -s database_password -s api_key
```

### Custom Secretfile and Lockfile

Use specific files:

```bash
secretzero sync --file Secretfile.prod.yml --lockfile .production.lock

# Short form
secretzero sync -f Secretfile.prod.yml -l .production.lock
```

### Variable File Overrides

Override variables for different environments:

```bash
# Single variable file
secretzero sync --var-file prod.szvar

# Multiple variable files (merged in order)
secretzero sync --var-file base.szvar --var-file prod.szvar

# Short form
secretzero sync -v base.szvar -v prod.szvar
```

### Clean Orphaned Entries

Remove lockfile entries that no longer have a corresponding secret in the Secretfile:

```bash
# Clean during sync
secretzero sync --clean

# Preview what would be cleaned
secretzero sync --clean --dry-run
```

**Output:**

```
Summary
✓ Success: 2 secret(s) stored
🗑 Cleaned: 3 orphaned lockfile entries

Cleaned Lockfile Entries (3 orphaned)
╭──────────┬───────────────┬─────────╮
│  Status  │ Secret Name   │ Result  │
├──────────┼───────────────┼─────────┤
│    🗑     │ old_secret_1  │ Removed │
│    🗑     │ old_secret_2  │ Removed │
│    🗑     │ old_secret_3  │ Removed │
╰──────────┴───────────────┴─────────╯
```

### Execution Plan

Show detailed plan without applying changes:

```bash
secretzero sync --plan
```

**Output:**

```
PLAN: Showing execution plan without applying changes

Execution Plan
╭────────┬─────────────────┬─────────────────┬──────────╮
│ Action │ Secret Name     │ Type            │ Targets  │
├────────┼─────────────────┼─────────────────┼──────────┤
│ create │ database_password│ random_password│ aws/ssm  │
│ update │ api_key         │ static          │ local/file│
│ skip   │ master_key      │ random_password │ local/file│
╰────────┴─────────────────┴─────────────────┴──────────╯

Plan summary: 2 create/update, 1 skip

Run 'secretzero sync' to apply this plan.
```

### JSON Output

Get machine-readable output:

```bash
secretzero sync --format json
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

### 3. Clean Orphans (if --clean)

If `--clean` flag is used, removes lockfile entries that don't have a corresponding secret in the Secretfile.

### 4. Check Each Secret

For each secret in the Secretfile:

- Check if already generated (exists in lockfile)
- Check if `one_time` flag is set
- Determine if generation is needed

### 5. Generate Secrets

Generate new secret values for secrets that need them:

- Random passwords
- Random strings
- Static values
- Script outputs
- API responses

### 6. Store in Targets

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

### 7. Update Lockfile

Update lockfile with:

- SHA-256 hashes of generated values
- Creation and update timestamps
- Secretfile hash for change detection
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

  # Add new secret
  - name: new_secret
    kind: random_password
```

```bash
secretzero sync
# Only generates: new_secret
# Skips: existing_secret
```

## Best Practices

### 1. Always Test with --dry-run First

Before running sync in production, preview changes:

```bash
# Preview first
secretzero sync --dry-run

# Or use plan for detailed view
secretzero sync --plan

# Then apply
secretzero sync
```

### 2. Use Variable Files for Environments

Keep environment-specific configuration in `.szvar` files:

```bash
# Development
secretzero sync --var-file dev.szvar

# Production
secretzero sync --var-file prod.szvar
```

### 3. Commit Lockfiles

Always commit lockfiles to version control:

```bash
git add .gitsecrets.lock
git commit -m "Update secrets lockfile"
```

This provides:
- Audit trail of secret changes
- Change detection via diffs
- Rollback capability

### 4. Clean Periodically

Remove orphaned entries when refactoring:

```bash
# After removing secrets from Secretfile
secretzero sync --clean
```

### 5. Use Selective Sync in CI/CD

Only sync secrets needed for specific jobs:

```bash
# GitHub Actions
secretzero sync --secret github_token --no-prompt

# Only sync API secrets
secretzero sync -s api_key -s api_secret
```

## Troubleshooting

### Secret Not Generated

If a secret isn't generated:

1. Check if it exists in lockfile (use `secretzero status`)
2. Check if `one_time: true` is set
3. Use `--dry-run` to see why it's skipped

### Provider Connection Errors

If you see "No accessible targets":

```bash
# Test provider connectivity first
secretzero test

# Check specific provider
secretzero test --provider aws
```

### Lockfile Conflicts

If lockfile has merge conflicts:

1. **Don't manually edit** lockfile during conflicts
2. Run `secretzero sync` after resolving merge
3. The lockfile will be regenerated correctly

## Related Commands

- [`secretzero validate`](../user-guide/cli/validate.md) - Validate Secretfile before syncing
- [`secretzero status`](../status.md) - Check current sync status
- [`secretzero rotate`](../user-guide/cli/rotate.md) - Rotate existing secrets
- [`secretzero test`](../user-guide/cli/test.md) - Test provider connectivity

## See Also

- [Configuration Guide](../user-guide/configuration/index.md)
- [Provider Setup](../user-guide/providers/index.md)
- [Target Configuration](../user-guide/targets/index.md)
@@- [Target Configuration](../user-guide/targets/index.md)
- [Configuration Guide](../user-guide/configuration/index.md)
- [Provider Setup](../user-guide/providers/index.md)
- [Target Configuration](../user-guide/targets/index.md)
