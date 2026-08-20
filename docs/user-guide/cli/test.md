# secretzero test

Test provider connectivity and authentication.

## Synopsis

```bash
secretzero test [OPTIONS]
```

## Description

The `test` command validates that all configured providers can be authenticated and accessed successfully. It's useful for verifying setup before generating and syncing secrets.

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--file`, `-f` | path | `Secretfile.yml` | Path to Secretfile |
| `--help` | flag | - | Show help message |

## Examples

### Test All Providers

Test connectivity for all configured providers:

```bash
secretzero test
```

**Successful output:**

```
Testing Provider Connectivity:

  • aws: ✓ Connected to AWS (us-east-1)
  • vault: ✓ Connected to Vault (http://localhost:8200)
  • kubernetes: ✓ Connected to cluster 'production'
  • local: ✓ Local provider (always available)

All provider tests passed!
```

**Output with failures:**

```
Testing Provider Connectivity:

  • aws: ✓ Connected to AWS (us-east-1)
  • vault: ✗ Connection failed: invalid token
  • kubernetes: ✗ Context 'production' not found
  • local: ✓ Local provider (always available)

Some provider tests failed. Check the messages above.
```

### Test Specific File

Test providers in a specific Secretfile:

```bash
secretzero test --file Secretfile.prod.yml
```

## What Gets Tested

### Per Provider Type

#### AWS

- Credentials are valid
- Can assume roles (if configured)
- Can access specified region
- Required permissions exist

#### Azure

- Managed Identity or credentials valid
- Can authenticate to Key Vault
- Subscription access verified

#### Vault

- Token or AppRole authentication works
- Can connect to Vault server
- Namespace access (if configured)
- Required policies exist

#### Kubernetes

- Kubeconfig is valid
- Context exists and is accessible
- Can authenticate to cluster
- Required namespaces exist

#### GitHub

- Token is valid
- Has required scopes
- Can access specified repositories

#### GitLab

- Token is valid
- Can access specified projects

#### Jenkins

- Credentials are valid
- Can connect to Jenkins server
- Has required permissions

#### Local

Always succeeds (no authentication required)

## Provider Test Details

### AWS Provider

```yaml
providers:
  aws:
    kind: aws
    auth:
      kind: ambient
      config:
        region: us-east-1
```

**Tests:**

1. AWS credentials are configured
2. Can make API calls to AWS
3. Region is accessible
4. IAM permissions are sufficient

**Success:**

```
✓ Connected to AWS (us-east-1)
```

**Failures:**

```
✗ AWS authentication failed: Unable to locate credentials
✗ AWS connection failed: Region us-east-1 not accessible
✗ AWS permission denied: Insufficient IAM permissions
```

### Vault Provider

```yaml
providers:
  vault:
    kind: vault
    auth:
      kind: token
      config:
        url: https://vault.example.com
        token: ${VAULT_TOKEN}
```

**Tests:**

1. Can connect to Vault server
2. Token is valid
3. Has required policies
4. Namespace is accessible (if configured)

**Success:**

```
✓ Connected to Vault (https://vault.example.com)
```

**Failures:**

```
✗ Vault connection failed: dial tcp: connection refused
✗ Vault authentication failed: invalid token
✗ Vault permission denied: missing required policy
```

### Kubernetes Provider

```yaml
providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient
      config:
        context: production
```

**Tests:**

1. Kubeconfig exists and is valid
2. Context exists
3. Can authenticate to cluster
4. Can access required namespaces

**Success:**

```
✓ Connected to cluster 'production'
```

**Failures:**

```
✗ Kubeconfig not found
✗ Context 'production' not found
✗ Authentication failed: invalid credentials
✗ Namespace 'default' not accessible
```

### Local Provider

```yaml
providers:
  local:
    kind: local
```

**Tests:**

Always succeeds (no external dependencies)

**Success:**

```
✓ Local provider (always available)
```

## Troubleshooting Provider Issues

### AWS Authentication Failed

**Error:**

```
✗ AWS authentication failed: Unable to locate credentials
```

**Solutions:**

1. **Configure AWS CLI:**

```bash
aws configure
```

2. **Set environment variables:**

```bash
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_REGION=us-east-1
```

3. **Use AWS profile:**

```yaml
providers:
  aws:
    auth:
      kind: ambient
      config:
        profile: production
```

4. **Use IAM role (EC2/ECS/Lambda):**

```yaml
providers:
  aws:
    auth:
      kind: ambient  # Automatically uses IAM role
```

**Verify:**

```bash
aws sts get-caller-identity
```

### Vault Connection Failed

**Error:**

```
✗ Vault connection failed: dial tcp: connection refused
```

**Solutions:**

1. **Verify Vault is running:**

```bash
vault status
```

2. **Check Vault address:**

```bash
export VAULT_ADDR=http://localhost:8200
```

3. **Update Secretfile:**

```yaml
providers:
  vault:
    auth:
      kind: token
      config:
        url: http://localhost:8200  # Correct URL
        token: ${VAULT_TOKEN}
```

4. **Check network connectivity:**

```bash
curl -s http://localhost:8200/v1/sys/health
```

**Verify:**

```bash
vault token lookup
```

### Vault Authentication Failed

**Error:**

```
✗ Vault authentication failed: invalid token
```

**Solutions:**

1. **Get new token:**

```bash
vault login
export VAULT_TOKEN=$(cat ~/.vault-token)
```

2. **Check token expiration:**

```bash
vault token lookup
```

3. **Use AppRole instead:**

```yaml
providers:
  vault:
    auth:
      kind: approle
      config:
        role_id: ${VAULT_ROLE_ID}
        secret_id: ${VAULT_SECRET_ID}
```

### Kubernetes Context Not Found

**Error:**

```
✗ Context 'production' not found
```

**Solutions:**

1. **List available contexts:**

```bash
kubectl config get-contexts
```

2. **Use correct context:**

```yaml
providers:
  kubernetes:
    auth:
      kind: ambient
      config:
        context: correct-name  # Use actual context name
```

3. **Use current context:**

```yaml
providers:
  kubernetes:
    auth:
      kind: ambient  # Omit context to use current
```

4. **Set current context:**

```bash
kubectl config use-context production
```

### GitHub Authentication Failed

**Error:**

```
✗ GitHub authentication failed: bad credentials
```

**Solutions:**

1. **Create personal access token:**

Go to GitHub Settings → Developer settings → Personal access tokens

2. **Set environment variable:**

```bash
export GITHUB_TOKEN=ghp_your_token_here
```

3. **Update Secretfile:**

```yaml
providers:
  github:
    kind: github
    auth:
      kind: token
      config:
        token: ${GITHUB_TOKEN}
```

**Required scopes:**

- `repo` - Full repository access
- `admin:repo_hook` - Repository webhooks and services

**Verify:**

```bash
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user
```

### Permission Denied

**Error:**

```
✗ AWS permission denied: Insufficient IAM permissions
```

**Solutions:**

1. **Review required permissions**
2. **Update IAM policy**
3. **Use different credentials with sufficient permissions**

**Example IAM policy for AWS:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ssm:PutParameter",
        "ssm:GetParameter",
        "ssm:DescribeParameters",
        "secretsmanager:CreateSecret",
        "secretsmanager:UpdateSecret",
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "*"
    }
  ]
}
```

## Integration Examples

### Pre-Sync Check

```bash
#!/bin/bash
# Ensure providers are accessible before syncing

echo "Testing provider connectivity..."
if secretzero test; then
  echo "✅ All providers accessible"
  echo "Syncing secrets..."
  secretzero sync
else
  echo "❌ Provider test failed"
  echo "Fix connectivity issues before syncing"
  exit 1
fi
```

### CI/CD Pipeline

```yaml
# .github/workflows/secrets.yml
name: Manage Secrets

on:
  push:
    branches: [main]

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
      
      - name: Test Provider Connectivity
        run: secretzero test
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          AWS_REGION: us-east-1
          VAULT_ADDR: ${{ secrets.VAULT_ADDR }}
          VAULT_TOKEN: ${{ secrets.VAULT_TOKEN }}
      
      - name: Sync Secrets
        if: success()
        run: secretzero sync
```

### Environment Setup Validation

```bash
#!/bin/bash
# validate-environment.sh

echo "Validating SecretZero environment..."

# 1. Check configuration
echo "1. Validating Secretfile..."
secretzero validate

# 2. Test providers
echo "2. Testing provider connectivity..."
secretzero test

# 3. Check policies
echo "3. Checking policy compliance..."
secretzero policy

if [ $? -eq 0 ]; then
  echo "✅ Environment validation passed"
  exit 0
else
  echo "❌ Environment validation failed"
  exit 1
fi
```

## Best Practices

### 1. Test Before First Sync

```bash
# New environment setup
secretzero create
vim Secretfile.yml
secretzero validate
secretzero test  # Test before syncing
secretzero sync
```

### 2. Test After Configuration Changes

```bash
# After modifying providers
vim Secretfile.yml
secretzero validate
secretzero test  # Ensure new configuration works
secretzero sync
```

### 3. Regular Connectivity Checks

```bash
# Daily cron job
0 9 * * * cd /path/to/project && secretzero test || echo "Provider connectivity issue" | mail -s "Alert" admin@example.com
```

### 4. Test in CI/CD

Always test providers in CI/CD pipelines:

```yaml
steps:
  - name: Test Providers
    run: secretzero test
```

### 5. Document Provider Requirements

```yaml
# Secretfile.yml

# Provider requirements:
#
# AWS:
# - AWS credentials configured (aws configure)
# - IAM permissions: ssm:*, secretsmanager:*
#
# Vault:
# - VAULT_ADDR environment variable
# - VAULT_TOKEN environment variable
# - Policy: read/write on secret/data/*
#
# Kubernetes:
# - Valid kubeconfig
# - Context: production
# - Namespace: default

providers:
  aws:
    kind: aws
  vault:
    kind: vault
  kubernetes:
    kind: kubernetes
```

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All provider tests passed |
| `1` | Some provider tests failed |
| `4` | Provider connection error |

## Gated Live Validations

Optional live API checks live under `tests/validations/` and are skipped unless credentials are present. See `tests/validations/README.md`.

```bash
# GitLab group automation (Owner role on test group)
export GITLAB_TOKEN=glpat-...
export GITLAB_TEST_GROUP=myorg/mygroup
uv run pytest tests/validations/test_gitlab_group_live.py -v

# Azure DevOps Services
export AZDO_PAT=...
export AZDO_ORG=myorg
export AZDO_TEST_PROJECT=my-project
uv run pytest tests/validations/test_azdo_live.py -v
```

Example-manifest validation (no live credentials) remains:

```bash
task test:validations
```

## Related Commands

- [`validate`](validate.md) - Validate configuration
- [`sync`](sync.md) - Generate and sync secrets
- [`create`](create.md) - Create a new Secretfile
- [`init`](init.md) - Initialize project dependencies

## See Also

- [Provider Documentation](../providers/index.md) - Provider configuration
- [Troubleshooting Guide](../../reference/troubleshooting.md) - Common issues
- [Getting Started](../../getting-started/index.md) - Setup guide
