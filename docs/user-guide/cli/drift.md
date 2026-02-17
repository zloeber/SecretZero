# secretzero drift

Detect drift between lockfile and actual targets.

## Synopsis

```bash
secretzero drift [SECRET_NAME] [OPTIONS]
```

## Description

The `drift` command checks if secrets have been modified outside of SecretZero's control by comparing the lockfile hashes with actual values in target storage locations.

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `SECRET_NAME` | No | Check specific secret (omit for all) |

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--file`, `-f` | path | `Secretfile.yml` | Path to Secretfile |
| `--lockfile`, `-l` | path | `.gitsecrets.lock` | Path to lockfile |
| `--help` | flag | - | Show help message |

## Examples

### Check All Secrets

Check all secrets for drift:

```bash
secretzero drift
```

**Output with no drift:**

```
Checking for drift...

  ✓ database_password: no drift detected
  ✓ api_key: no drift detected
  ✓ redis_password: no drift detected

No drift detected.
```

**Output with drift:**

```
Checking for drift...

  ⚠️ database_password: drift detected
      Expected hash: 9f86d081...
      Actual hash: 5e884898...
  ✓ api_key: no drift detected
  ⚠️ redis_password: drift detected
      Target aws/ssm_parameter: value changed externally

Drift detected. Run 'secretzero sync --force' to remediate.
```

### Check Specific Secret

Check a single secret:

```bash
secretzero drift database_password
```

### Custom Files

```bash
secretzero drift --file Secretfile.prod.yml --lockfile .prod.lock
```

## What is Drift?

**Drift** occurs when a secret's actual value doesn't match what SecretZero expects based on the lockfile. This can happen when:

1. **Manual changes** - Someone modifies the secret outside SecretZero
2. **External automation** - Other tools modify the secret
3. **Unauthorized access** - Malicious modification
4. **Configuration mismatch** - Multiple environments sharing storage

## How Drift Detection Works

### 1. Load Lockfile

Read expected secret hashes from lockfile:

```yaml
secrets:
  database_password:
    hash: 9f86d081884c7d659a2feaa0c55ad015...
```

### 2. Retrieve Actual Values

Fetch actual secret values from targets:

- AWS SSM Parameter Store
- AWS Secrets Manager
- HashiCorp Vault
- Azure Key Vault
- Kubernetes Secrets
- Local files

### 3. Compare Hashes

Calculate SHA-256 hash of actual value and compare:

```
Expected: 9f86d081884c7d659a2feaa0c55ad015...
Actual:   5e884898da28047151d0e56f8dc6292...
Result:   ⚠️ DRIFT DETECTED
```

### 4. Report Results

Report any discrepancies found.

## Drift Scenarios

### Manual Change

Someone manually changes a secret in AWS Console:

```
⚠️ database_password: drift detected
    Target: aws/ssm_parameter
    Reason: value changed in AWS Console
```

**Remediation:**

```bash
secretzero sync --force database_password
```

### Multiple Automation Tools

Another tool (Terraform, CloudFormation) manages the same secret:

```
⚠️ api_key: drift detected
    Target: aws/ssm_parameter
    Reason: value managed by multiple tools
```

**Remediation:**

Choose single source of truth - either SecretZero or the other tool.

### Unauthorized Access

Security incident - secret compromised:

```
⚠️ production_api_key: drift detected
    Target: aws/secrets_manager
    Reason: unauthorized modification
```

**Remediation:**

1. Investigate security incident
2. Rotate immediately: `secretzero rotate --force production_api_key`
3. Review access logs
4. Update access policies

### Configuration Sync Issues

Different environments accessing same storage:

```
⚠️ shared_secret: drift detected
    Reason: dev and prod using same SSM parameter path
```

**Remediation:**

Use environment-specific paths:

```yaml
variables:
  environment: ${ENVIRONMENT}

secrets:
  - name: shared_secret
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: "/{{var.environment}}/shared-secret"  # Environment-specific
```

## Workflows

### Regular Monitoring

Check for drift regularly:

```bash
# Daily drift check
secretzero drift

# If drift detected, investigate
secretzero show <secret_name>
```

### Automated Monitoring

```bash
#!/bin/bash
# drift-monitor.sh

secretzero drift

if [ $? -ne 0 ]; then
  echo "⚠️ Drift detected!"
  
  # Send alert
  curl -X POST https://hooks.slack.com/services/YOUR/WEBHOOK \
    -d '{"text":"⚠️ Secret drift detected in production"}'
  
  # Email notification
  echo "Drift detected in production secrets" | \
    mail -s "SecretZero Alert" security@example.com
fi
```

### CI/CD Drift Detection

```yaml
# .github/workflows/drift-check.yml
name: Drift Detection

on:
  schedule:
    - cron: '0 */4 * * *'  # Every 4 hours
  workflow_dispatch:

jobs:
  drift:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install SecretZero
        run: pip install secretzero[all]
      
      - name: Check for Drift
        run: secretzero drift
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
      
      - name: Create Issue on Drift
        if: failure()
        uses: actions/github-script@v6
        with:
          script: |
            github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: 'Secret Drift Detected',
              body: 'Drift detected in production secrets. Please investigate.',
              labels: ['security', 'urgent']
            })
```

### Remediation Workflow

```bash
#!/bin/bash
# remediate-drift.sh

echo "Checking for drift..."
if secretzero drift; then
  echo "✅ No drift detected"
  exit 0
fi

echo "⚠️ Drift detected"
echo ""
echo "Options:"
echo "1. Accept changes and update lockfile"
echo "2. Revert to SecretZero values"
echo "3. Investigate manually"
read -p "Choice (1/2/3): " choice

case $choice in
  1)
    echo "Updating lockfile to match current state..."
    # Implementation depends on your needs
    ;;
  2)
    echo "Reverting to SecretZero values..."
    secretzero sync --force
    ;;
  3)
    echo "Manual investigation required"
    echo "Check these secrets:"
    secretzero drift | grep "⚠️"
    ;;
esac
```

## Best Practices

### 1. Regular Drift Checks

Schedule regular checks:

```bash
# Cron: every 4 hours
0 */4 * * * cd /path/to/project && secretzero drift || echo "Drift detected!" | mail -s "Alert" admin@example.com
```

### 2. Alert on Drift

Integrate with alerting systems:

```bash
#!/bin/bash
if ! secretzero drift; then
  # Send to PagerDuty, Slack, email, etc.
  trigger-alert "Secret drift detected"
fi
```

### 3. Investigate Before Remediation

Don't automatically remediate - investigate first:

```bash
# 1. Detect drift
secretzero drift

# 2. Investigate
secretzero show database_password
aws ssm get-parameter --name /app/db-password

# 3. Determine root cause
# 4. Take appropriate action
```

### 4. Prevent Drift

Use policies and access controls:

- Restrict who can modify secrets
- Use infrastructure-as-code
- Enable audit logging
- Monitor access patterns

### 5. Document Drift Incidents

```markdown
# Drift Incident Log

## 2024-01-15: API Key Drift

**Detected:** 2024-01-15 10:30 UTC
**Secret:** production_api_key
**Root Cause:** Manual change in AWS Console by dev team
**Resolution:** Reverted to SecretZero value, educated team
**Prevention:** Updated IAM policies to restrict manual changes
```

## Troubleshooting

### False Positive Drift

**Issue:** Drift reported but values are actually the same.

**Causes:**

1. Different encoding or formatting
2. Trailing whitespace
3. Line ending differences

**Solution:**

```bash
# Check actual value
aws ssm get-parameter --name /app/secret --with-decryption

# Compare with expected
secretzero show my_secret

# If values match, may need to re-sync lockfile
```

### Cannot Check Drift

**Issue:** Drift check fails.

**Causes:**

1. Provider authentication failed
2. Secret doesn't exist in target
3. Lockfile missing

**Solution:**

```bash
# Test provider connectivity
secretzero test

# Verify secret exists
secretzero show my_secret

# Re-generate if needed
secretzero sync
```

### Persistent Drift

**Issue:** Drift keeps reappearing.

**Cause:** External automation or manual changes.

**Solution:**

1. Identify source of changes:

```bash
# AWS CloudTrail
aws cloudtrail lookup-events --lookup-attributes AttributeKey=ResourceName,AttributeValue=/app/secret

# Kubernetes audit logs
kubectl logs -n kube-system audit-policy-webhook-...
```

2. Stop external automation or choose single source of truth

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | No drift detected |
| `1` | Drift detected |
| `4` | Provider connection error |

## Related Commands

- [`show`](show.md) - Show secret details
- [`sync`](sync.md) - Remediate drift
- [`rotate`](rotate.md) - Rotate compromised secrets
- [`validate`](validate.md) - Validate configuration

## See Also

- [Security Best Practices](../../reference/security.md) - Security guidelines
- [Provider Documentation](../providers/index.md) - Provider configuration
- [Monitoring Guide](../../use-cases/monitoring.md) - Monitoring strategies
