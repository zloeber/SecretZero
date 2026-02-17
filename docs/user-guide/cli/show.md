# secretzero show

Display information about a specific secret.

## Synopsis

```bash
secretzero show SECRET_NAME [OPTIONS]
```

## Description

The `show` command displays metadata about a secret, including its configuration, generation status, targets, and lockfile information.

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `SECRET_NAME` | Yes | Name of the secret to show |

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--file`, `-f` | path | `Secretfile.yml` | Path to Secretfile |
| `--lockfile`, `-l` | path | `.gitsecrets.lock` | Path to lockfile |
| `--help` | flag | - | Show help message |

## Examples

### Basic Usage

Show information about a secret:

```bash
secretzero show database_password
```

**Output:**

```
Secret: database_password

Kind            random_password
One-time        No
Rotation Period 90d
Generated       Yes
Created         2024-01-15T10:30:00Z
Updated         2024-01-15T10:30:00Z
Hash            9f86d081884c7d65...

Targets:
  • aws / ssm_parameter
  • local / file
```

### Secret Not Generated

For a secret that hasn't been generated yet:

```bash
secretzero show new_secret
```

**Output:**

```
Secret: new_secret

Kind            random_password
One-time        No
Rotation Period 30d
Generated       No

Targets:
  • aws / ssm_parameter
```

### With Custom Files

```bash
secretzero show api_key --file Secretfile.prod.yml --lockfile .prod.lock
```

## Output Fields

### Configuration

| Field | Description |
|-------|-------------|
| `Kind` | Generator type or template name |
| `One-time` | Whether secret is one-time only |
| `Rotation Period` | Rotation interval (if set) |

### Generation Status

| Field | Description |
|-------|-------------|
| `Generated` | Whether secret exists in lockfile |
| `Created` | When secret was first generated |
| `Updated` | When secret was last updated |
| `Hash` | SHA-256 hash (first 16 chars) |

### Targets

Lists all storage targets for the secret:

```
Targets:
  • aws / ssm_parameter
  • kubernetes / kubernetes_secret
  • local / file
```

## Use Cases

### Check Secret Status

Verify if a secret has been generated:

```bash
secretzero show database_password
```

Look for "Generated: Yes"

### Verify Rotation Period

Check if rotation period is set correctly:

```bash
secretzero show api_key
```

Look for "Rotation Period: 90d"

### List Targets

See where a secret is stored:

```bash
secretzero show shared_secret
```

Check the "Targets" section.

### Audit Secret Age

Check when a secret was created:

```bash
secretzero show database_password
```

Look for "Created" and "Updated" timestamps.

### Verify One-Time Status

Confirm a secret is marked as one-time:

```bash
secretzero show encryption_key
```

Look for "One-time: Yes"

## Integration Examples

### Script to Check All Secrets

```bash
#!/bin/bash
# check-secrets.sh

SECRETS=("database_password" "api_key" "redis_password")

echo "Secret Status Report"
echo "===================="
echo ""

for secret in "${SECRETS[@]}"; do
  echo "Checking $secret..."
  secretzero show "$secret" | grep -E "(Generated|Created|Rotation)"
  echo ""
done
```

### Check for Ungenerated Secrets

```bash
#!/bin/bash
# find-ungenerated.sh

# Extract secret names from Secretfile
SECRETS=$(yq '.secrets[].name' Secretfile.yml)

echo "Checking for ungenerated secrets..."
ungenerated=0

for secret in $SECRETS; do
  if secretzero show "$secret" | grep -q "Generated.*No"; then
    echo "❌ $secret not generated"
    ((ungenerated++))
  else
    echo "✅ $secret generated"
  fi
done

if [ $ungenerated -gt 0 ]; then
  echo ""
  echo "⚠️  $ungenerated secret(s) not generated"
  echo "Run 'secretzero sync' to generate them"
  exit 1
fi

echo ""
echo "✅ All secrets generated"
```

### Monitoring Script

```bash
#!/bin/bash
# monitor-secrets.sh

# Check secrets and alert if issues found
CRITICAL_SECRETS=("database_password" "api_secret_key")

for secret in "${CRITICAL_SECRETS[@]}"; do
  # Check if secret exists
  if ! secretzero show "$secret" &>/dev/null; then
    echo "ALERT: Secret $secret not found in configuration"
    # Send alert (email, Slack, PagerDuty, etc.)
    continue
  fi
  
  # Check if generated
  if secretzero show "$secret" | grep -q "Generated.*No"; then
    echo "ALERT: Secret $secret not generated"
    # Send alert
  fi
done
```

## Troubleshooting

### Secret Not Found

**Error:**

```
Error: Secret 'api_key' not found in Secretfile
```

**Solution:**

Check the secret name in your Secretfile:

```bash
# List all secrets
yq '.secrets[].name' Secretfile.yml
```

### Cannot Read Lockfile

**Error:**

```
Error: Cannot read lockfile: .gitsecrets.lock
```

**Solution:**

Generate secrets first:

```bash
secretzero sync
```

Or specify correct lockfile:

```bash
secretzero show my_secret --lockfile .production.lock
```

### Empty Output

**Issue:** Command runs but shows no information.

**Cause:** Secret exists in Secretfile but not in lockfile.

**Solution:**

Generate the secret:

```bash
secretzero sync
```

## Comparison with Other Commands

### show vs sync

- **show**: Display information (read-only)
- **sync**: Generate and store secrets (write operation)

```bash
# Check status
secretzero show database_password

# Generate if needed
secretzero sync
```

### show vs rotate

- **show**: Display current state
- **rotate**: Check and perform rotation

```bash
# Check rotation status
secretzero show database_password

# Perform rotation
secretzero rotate database_password
```

### show vs drift

- **show**: Configuration and lockfile information
- **drift**: Compare lockfile with actual targets

```bash
# Check configuration
secretzero show database_password

# Check for drift
secretzero drift database_password
```

## Best Practices

### 1. Verify After Sync

```bash
secretzero sync
secretzero show database_password
```

### 2. Check Before Rotation

```bash
# Check when secret was last updated
secretzero show api_key

# Rotate if needed
secretzero rotate api_key
```

### 3. Document Secret Status

```bash
# Generate report
echo "Secret Status Report - $(date)" > status.txt
for secret in $(yq '.secrets[].name' Secretfile.yml); do
  echo "" >> status.txt
  secretzero show "$secret" >> status.txt
done
```

### 4. Monitor Critical Secrets

```bash
# Check critical secrets daily
CRITICAL="database_password api_secret_key encryption_key"
for secret in $CRITICAL; do
  secretzero show "$secret" | grep -E "Generated|Rotation|Updated"
done
```

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success - secret found and displayed |
| `1` | Error - secret not found or other error |

## Related Commands

- [`sync`](sync.md) - Generate secrets
- [`rotate`](rotate.md) - Rotate secrets
- [`drift`](drift.md) - Detect drift
- [`validate`](validate.md) - Validate configuration

## See Also

- [Lockfile Documentation](../configuration/index.md#lockfile) - Lockfile structure
- [Secret Rotation](rotate.md) - Rotation workflows
- [Configuration Guide](../configuration/index.md) - Secretfile concepts
