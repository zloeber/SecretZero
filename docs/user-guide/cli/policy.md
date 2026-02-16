# secretzero policy

Check secrets against policy rules.

## Synopsis

```bash
secretzero policy [OPTIONS]
```

## Description

The `policy` command validates secrets against rotation, compliance, and access control policies defined in the Secretfile. It helps ensure your secrets meet organizational security requirements.

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--file`, `-f` | path | `Secretfile.yml` | Path to Secretfile |
| `--lockfile`, `-l` | path | `.gitsecrets.lock` | Path to lockfile |
| `--fail-on-warning` | flag | `false` | Exit with error code on warnings |
| `--help` | flag | - | Show help message |

## Examples

### Check Policy Compliance

Check all secrets against defined policies:

```bash
secretzero policy
```

**Output with no violations:**

```
Checking policy compliance...

✓ All secrets comply with policies
```

**Output with violations:**

```
Checking policy compliance...

Warnings:
  ⚠ database_password: No rotation_period defined
    → Add rotation_period to enable automatic rotation
  
  ⚠ api_token: Rotation period 180d exceeds policy maximum of 90d
    → Reduce rotation_period to 90d or less

Info:
  ℹ service_key: One-time secret cannot be automatically rotated

Summary:
  Errors: 0
  Warnings: 2
  Info: 1
```

### Fail on Warnings

Treat warnings as errors (useful for CI/CD):

```bash
secretzero policy --fail-on-warning
```

If warnings exist, exits with code 1.

### Check Specific File

```bash
secretzero policy --file Secretfile.prod.yml
```

## Policy Types

### Rotation Policies

Enforce rotation requirements:

```yaml
policies:
  rotation_required:
    kind: rotation
    require_rotation_period: true  # All secrets must have rotation_period
    severity: warning
    enabled: true
  
  max_rotation_age:
    kind: rotation
    max_age: 90d  # Maximum allowed rotation period
    severity: error
    enabled: true
  
  min_rotation_age:
    kind: rotation
    min_age: 7d  # Minimum allowed rotation period
    severity: warning
    enabled: true
```

**Checks:**

- ✅ Every secret has `rotation_period` defined
- ✅ Rotation periods are within allowed range
- ✅ Secrets are rotated on schedule

**Example violations:**

```
❌ api_key: No rotation_period defined
❌ db_password: Rotation period 365d exceeds maximum 90d
⚠️ temp_token: Rotation period 1d below recommended 7d
```

### Access Control Policies

Restrict allowed targets:

```yaml
policies:
  production_security:
    kind: access
    allowed_targets:  # Whitelist
      - ssm_parameter
      - secrets_manager
      - vault_kv
      - kubernetes_secret
    denied_targets:  # Blacklist
      - file  # No local files in production
    severity: error
    enabled: true
```

**Checks:**

- ✅ Secrets only use allowed target types
- ✅ Secrets don't use denied target types

**Example violations:**

```
❌ dev_secret: Uses forbidden target type 'file'
❌ test_key: Uses target type 'file' which is not in allowed list
```

### Complexity Policies

Enforce password complexity:

```yaml
policies:
  password_complexity:
    kind: complexity
    min_length: 16
    require_upper: true
    require_lower: true
    require_number: true
    require_special: true
    severity: error
    enabled: true
```

**Checks:**

- ✅ Passwords meet minimum length
- ✅ Required character types are included

**Example violations:**

```
❌ weak_password: Length 8 below minimum 16
❌ simple_password: Missing required special characters
```

## Severity Levels

Policies have three severity levels:

### error

Blocks operations and exits with error code:

```yaml
policies:
  critical_rotation:
    kind: rotation
    max_age: 90d
    severity: error  # Blocks sync if violated
    enabled: true
```

**Behavior:**

- ❌ Blocks `secretzero sync`
- ❌ Exits with code 5
- ❌ Must be fixed before proceeding

### warning

Allows operations but warns:

```yaml
policies:
  rotation_recommended:
    kind: rotation
    require_rotation_period: true
    severity: warning  # Warns but allows sync
    enabled: true
```

**Behavior:**

- ⚠️ Allows `secretzero sync`
- ⚠️ Exits with code 0 (unless `--fail-on-warning`)
- ⚠️ Should be fixed soon

### info

Informational only:

```yaml
policies:
  rotation_info:
    kind: rotation
    recommended_age: 90d
    severity: info  # Informational only
    enabled: true
```

**Behavior:**

- ℹ️ Always allows operations
- ℹ️ Exits with code 0
- ℹ️ Nice to know, no action required

## Common Policy Configurations

### SOC2 Compliance

```yaml
metadata:
  compliance:
    - soc2

policies:
  soc2_rotation:
    kind: rotation
    require_rotation_period: true
    max_age: 90d  # SOC2 requirement
    severity: error
    enabled: true
  
  soc2_storage:
    kind: access
    allowed_targets:
      - ssm_parameter
      - secrets_manager
      - vault_kv
      - azure_keyvault
      - kubernetes_secret
    severity: error
    enabled: true
  
  soc2_complexity:
    kind: complexity
    min_length: 16
    require_special: true
    severity: error
    enabled: true
```

### ISO27001 Compliance

```yaml
metadata:
  compliance:
    - iso27001

policies:
  iso27001_rotation:
    kind: rotation
    require_rotation_period: true
    max_age: 90d
    severity: error
    enabled: true
  
  iso27001_access:
    kind: access
    denied_targets:
      - file  # No local file storage
    severity: error
    enabled: true
```

### Development Environment

```yaml
policies:
  dev_rotation:
    kind: rotation
    require_rotation_period: false
    severity: warning
    enabled: true
  
  dev_storage:
    kind: access
    # Allow any targets in development
    severity: info
    enabled: false
```

### Production Environment

```yaml
policies:
  prod_rotation:
    kind: rotation
    require_rotation_period: true
    max_age: 90d
    severity: error
    enabled: true
  
  prod_storage:
    kind: access
    allowed_targets:
      - ssm_parameter
      - secrets_manager
      - vault_kv
    severity: error
    enabled: true
  
  prod_complexity:
    kind: complexity
    min_length: 32
    require_upper: true
    require_lower: true
    require_number: true
    require_special: true
    severity: error
    enabled: true
```

## CI/CD Integration

### GitHub Actions

```yaml
name: Policy Check

on: [push, pull_request]

jobs:
  policy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install SecretZero
        run: pip install secretzero
      
      - name: Check Policy Compliance
        run: secretzero policy --fail-on-warning
```

### GitLab CI

```yaml
policy-check:
  stage: test
  image: python:3.11
  script:
    - pip install secretzero
    - secretzero policy --fail-on-warning
  only:
    - merge_requests
    - main
```

### Pre-commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

echo "Checking policy compliance..."
secretzero policy --fail-on-warning

if [ $? -ne 0 ]; then
  echo "❌ Policy violations found"
  echo "Fix policy issues or commit with --no-verify"
  exit 1
fi

echo "✅ Policy compliance check passed"
exit 0
```

## Workflows

### Regular Compliance Checks

```bash
# Daily policy check
secretzero policy

# Weekly detailed check with all environments
for env in dev staging prod; do
  echo "Checking $env..."
  secretzero policy -f "Secretfile.$env.yml" --fail-on-warning
done
```

### Policy-Driven Development

```bash
# 1. Add new secret
vim Secretfile.yml

# 2. Validate configuration
secretzero validate

# 3. Check policy compliance
secretzero policy --fail-on-warning

# 4. If compliant, sync
secretzero sync
```

### Compliance Reporting

```bash
#!/bin/bash
# generate-compliance-report.sh

echo "SecretZero Compliance Report"
echo "Generated: $(date)"
echo "=========================="
echo ""

# Check each environment
for env in dev staging prod; do
  echo "Environment: $env"
  echo "---"
  secretzero policy -f "Secretfile.$env.yml" 2>&1
  echo ""
done
```

## Best Practices

### 1. Start with Warnings

Begin with `severity: warning` for new policies:

```yaml
policies:
  new_rotation_policy:
    kind: rotation
    max_age: 90d
    severity: warning  # Start with warning
    enabled: true
```

After team adjusts, upgrade to `error`:

```yaml
policies:
  new_rotation_policy:
    kind: rotation
    max_age: 90d
    severity: error  # Enforce strictly
    enabled: true
```

### 2. Environment-Specific Policies

```yaml
# Secretfile.prod.yml
policies:
  prod_strict:
    kind: rotation
    max_age: 90d
    severity: error

# Secretfile.dev.yml
policies:
  dev_relaxed:
    kind: rotation
    max_age: 180d
    severity: warning
```

### 3. Document Policy Rationale

```yaml
policies:
  # SOC2 Control CC6.1: Logical and Physical Access Controls
  # Requirement: Passwords must be rotated every 90 days
  soc2_rotation:
    kind: rotation
    max_age: 90d
    severity: error
    enabled: true
```

### 4. Regular Policy Reviews

```bash
# Monthly policy review
echo "Policy Review - $(date)" > policy-review.txt
secretzero policy >> policy-review.txt

# Discuss findings in security meeting
```

### 5. Automate Policy Enforcement

```yaml
# CI/CD pipeline
steps:
  - name: Policy Check
    run: |
      secretzero policy --fail-on-warning || \
      (echo "Policy violations must be fixed before merge" && exit 1)
```

## Troubleshooting

### Policy Check Failing

**Issue:** Policy check fails unexpectedly.

**Debug:**

```bash
# Check policy configuration
yq '.policies' Secretfile.yml

# Validate Secretfile
secretzero validate

# Check specific secret
secretzero show secret_name
```

### False Positives

**Issue:** Policy reports violations that seem incorrect.

**Solutions:**

1. Check secret configuration:

```bash
secretzero show database_password
```

2. Verify policy rules:

```yaml
policies:
  my_policy:
    enabled: true  # Ensure policy is meant to be active
```

3. Adjust severity if needed:

```yaml
policies:
  my_policy:
    severity: info  # Downgrade if too strict
```

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success - all policies pass |
| `1` | General error |
| `5` | Policy violations (errors or warnings with `--fail-on-warning`) |

## Related Commands

- [`validate`](validate.md) - Validate configuration
- [`rotate`](rotate.md) - Rotate secrets
- [`sync`](sync.md) - Generate secrets
- [`show`](show.md) - Show secret details

## See Also

- [Policy Configuration](../configuration/secretfile.md#policies) - Policy definitions
- [Compliance Guide](../../use-cases/compliance.md) - Compliance requirements
- [Rotation Guide](rotate.md) - Secret rotation
