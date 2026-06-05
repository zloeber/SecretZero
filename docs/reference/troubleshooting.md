# Troubleshooting Guide

This guide helps you diagnose and resolve common issues with SecretZero. Issues are organized by category for easy navigation.

## Quick Diagnostics

Before diving into specific issues, run these commands to gather diagnostic information:

```bash
# Check SecretZero version
secretzero --version

# Validate configuration
secretzero validate

# Test provider connectivity
secretzero test

# Check Python version
python --version

# List installed packages
pip list | grep -E "(secretzero|boto3|azure|hvac)"
```

## Installation Issues

### Command Not Found

**Symptom:**

```bash
$ secretzero --version
bash: secretzero: command not found
```

**Causes & Solutions:**

#### 1. Package Not Installed

```bash
# Install SecretZero
pip install secretzero

# Verify installation
pip show secretzero
```

#### 2. Wrong Python/pip

```bash
# Check which Python/pip you're using
which python
which pip

# Use specific Python version
python3 -m pip install secretzero
python3 -m secretzero --version
```

#### 3. Not in PATH

```bash
# Find installation location
pip show secretzero | grep Location

# Add to PATH (Linux/macOS)
export PATH="$HOME/.local/bin:$PATH"

# Or use full path
~/.local/bin/secretzero --version
```

#### 4. Virtual Environment

```bash
# Activate virtual environment
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Then install
pip install secretzero
```

### Import Errors

**Symptom:**

```bash
ModuleNotFoundError: No module named 'secretzero'
```

**Solution:**

```bash
# Reinstall with force
pip install --force-reinstall secretzero

# Or install in development mode
git clone https://github.com/zloeber/SecretZero.git
cd SecretZero
pip install -e .
```

### Dependency Conflicts

**Symptom:**

```bash
ERROR: pip's dependency resolver does not currently take into account all the packages...
```

**Solution:**

```bash
# Create clean virtual environment
python -m venv clean-venv
source clean-venv/bin/activate

# Install SecretZero
pip install --upgrade pip
pip install secretzero[all]
```

### Python Version Issues

**Symptom:**

```bash
ERROR: Package 'secretzero' requires a different Python: 3.8.0 not in '>=3.9'
```

**Solution:**

```bash
# Check Python version
python --version

# Use Python 3.9+
python3.11 -m pip install secretzero
python3.11 -m secretzero --version
```

### Permission Errors

**Symptom:**

```bash
ERROR: Could not install packages due to an OSError: [Errno 13] Permission denied
```

**Solution:**

```bash
# Install for current user only
pip install --user secretzero

# Or use virtual environment (recommended)
python -m venv venv
source venv/bin/activate
pip install secretzero
```

## Configuration Errors

### Invalid YAML Syntax

**Symptom:**

```bash
$ secretzero validate
Error: YAML syntax error at line 15, column 3
```

**Solution:**

```bash
# Use YAML linter
pip install yamllint
yamllint Secretfile.yml

# Common issues:
# - Incorrect indentation (use 2 spaces, not tabs)
# - Missing colons
# - Unquoted special characters
```

**Example Fix:**

```yaml
# ❌ Incorrect (tabs, missing quotes)
secrets:
	api_key:
		value: my-key-with-:-colon

# ✅ Correct (spaces, quoted)
secrets:
  api_key:
    value: "my-key-with-:-colon"
```

### Missing Required Fields

**Symptom:**

```bash
Error: field required (type=value_error.missing)
  secrets -> 0 -> targets (field required)
```

**Solution:**

Every secret must have at least one target:

```yaml
secrets:
  api_key:
    template:
      type: api_key
      fields:
        - name: value
          generator:
            type: random-string
            length: 32
    # ✅ Add target
    targets:
      - type: local-file
        path: .env
        format: dotenv
```

### Variable Interpolation Failures

**Symptom:**

```bash
Error: Undefined variable 'var.environment'
```

**Solution:**

```yaml
# ❌ Variable not defined
secrets:
  api_key:
    targets:
      - type: aws-secretsmanager
        name: "/{{var.environment}}/api_key"

# ✅ Define variable with default
variables:
  environment: "{{env.ENVIRONMENT or 'development'}}"
```

### Invalid Generator Configuration

**Symptom:**

```bash
Error: Invalid generator type 'random_pasword' (typo)
```

**Solution:**

```bash
# List valid generator types
secretzero secret-types

# Common typos:
# - random_pasword → random-password
# - random_str → random-string
# - stattic → static
```

### Invalid Target Configuration

**Symptom:**

```bash
Error: Unknown target type 'aws_secrets_manager'
```

**Solution:**

```bash
# Check valid target types
secretzero secret-types

# Correct target type names:
# - aws-secretsmanager (not aws_secrets_manager)
# - aws-ssm-parameter (not aws_ssm_param)
# - local-file (not file)
```

## Provider Connectivity Issues

### AWS Authentication Failures

**Symptom:**

```bash
Error: Unable to locate credentials. You can configure credentials by running "aws configure".
```

**Diagnosis:**

```bash
# Check AWS credentials
aws sts get-caller-identity

# Check environment variables
env | grep AWS
```

**Solutions:**

#### Option 1: Environment Variables

```bash
export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
export AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
export AWS_DEFAULT_REGION=us-east-1

secretzero test
```

#### Option 2: AWS Profile

```bash
export AWS_PROFILE=myprofile
secretzero test
```

#### Option 3: AWS Configure

```bash
aws configure
secretzero test
```

#### Option 4: IAM Role (EC2/ECS)

```yaml
providers:
  aws:
    kind: aws
    auth:
      kind: ambient  # Uses IAM role automatically
```

### AWS Permission Denied

**Symptom:**

```bash
Error: An error occurred (AccessDenied) when calling the PutSecretValue operation
```

**Solution:**

Check IAM permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:CreateSecret",
        "secretsmanager:UpdateSecret",
        "secretsmanager:PutSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:*:*:secret:/myapp/*"
    }
  ]
}
```

For SSM Parameter Store:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ssm:PutParameter",
        "ssm:GetParameter",
        "ssm:DescribeParameters"
      ],
      "Resource": "arn:aws:ssm:*:*:parameter/myapp/*"
    }
  ]
}
```

### Azure Authentication Failures

**Symptom:**

```bash
Error: DefaultAzureCredential failed to retrieve a token
```

**Diagnosis:**

```bash
# Check Azure CLI login
az account show

# Check environment variables
env | grep AZURE
```

**Solutions:**

#### Option 1: Azure CLI

```bash
az login
secretzero test
```

#### Option 2: Environment Variables

```bash
export AZURE_CLIENT_ID=your-client-id
export AZURE_CLIENT_SECRET=your-client-secret
export AZURE_TENANT_ID=your-tenant-id
secretzero test
```

#### Option 3: Managed Identity (Azure VM/Container)

```yaml
providers:
  azure:
    kind: azure
    auth:
      kind: managed_identity
```

### Vault Connection Failures

**Symptom:**

```bash
Error: Unable to connect to Vault at http://localhost:8200
```

**Diagnosis:**

```bash
# Check Vault is running
curl http://localhost:8200/v1/sys/health

# Check Vault token
echo $VAULT_TOKEN
```

**Solutions:**

```bash
# Start Vault (development mode)
vault server -dev

# Set token
export VAULT_TOKEN=root

# Or use custom URL
export VAULT_ADDR=https://vault.example.com
export VAULT_TOKEN=your-token

secretzero test
```

### Kubernetes Connection Failures

**Symptom:**

```bash
Error: Unable to connect to Kubernetes cluster
```

**Diagnosis:**

```bash
# Check kubectl connectivity
kubectl cluster-info

# Check kubeconfig
kubectl config view
```

**Solutions:**

```bash
# Set kubeconfig
export KUBECONFIG=/path/to/kubeconfig

# Or specify in Secretfile
providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient
      config:
        kubeconfig: /path/to/kubeconfig
        context: production
```

### GitHub Authentication Failures

**Symptom:**

```bash
Error: Bad credentials (401)
```

**Solution:**

```bash
# Generate Personal Access Token
# GitHub → Settings → Developer settings → Personal access tokens

# Set token
export GITHUB_TOKEN=ghp_your_token

secretzero test
```

**Required Scopes:**

- `repo` (for repository secrets)
- `admin:org` (for organization secrets)
- `workflow` (for Actions secrets)

### GitLab Authentication Failures

**Symptom:**

```bash
Error: 401 Unauthorized
```

**Solution:**

```bash
# Generate Personal Access Token
# GitLab → Preferences → Access Tokens

# Set token
export GITLAB_TOKEN=glpat-your-token

secretzero test
```

**Required Scopes:**

- `api` (full API access)
- `write_repository` (for variables)

## Secret Generation Issues

### Generator Not Found

**Symptom:**

```bash
Error: Unknown generator type 'my-custom-generator'
```

**Solution:**

Use a supported generator type:

```bash
# List available generators
secretzero secret-types

# Supported generators:
# - random-password
# - random-string
# - static
# - script
```

### Script Generator Timeout

**Symptom:**

```bash
Error: Script generator timed out after 30 seconds
```

**Solution:**

Increase timeout:

```yaml
generator:
  type: script
  command: long-running-command
  timeout: 120  # Increase to 120 seconds
```

### Script Generator Permission Denied

**Symptom:**

```bash
Error: Permission denied: 'my-script.sh'
```

**Solution:**

```bash
# Make script executable
chmod +x my-script.sh

# Or use interpreter explicitly
generator:
  type: script
  command: bash
  args:
    - my-script.sh
```

### Random Password Too Short

**Symptom:**

```bash
Error: Password length must be at least 8 characters
```

**Solution:**

```yaml
generator:
  type: random-password
  length: 32  # Minimum 8, recommended 32+
```

### Static Generator Validation Failed

**Symptom:**

```bash
Error: Value 'my-value' does not match pattern '^[a-z]+$'
```

**Solution:**

```yaml
# Option 1: Fix value to match pattern
generator:
  type: static
  value: myvalue  # Only lowercase letters

# Option 2: Update pattern
generator:
  type: static
  value: my-value
  validation: '^[a-z\-]+$'  # Allow hyphens
```

### Environment Variable Override Not Working

**Symptom:**

Secret still being generated even though environment variable is set.

**Diagnosis:**

```bash
# Check exact variable name format
# Format: {SECRET_NAME}_{FIELD_NAME} in UPPERCASE

# Example for secret "api_key" with field "value":
export API_KEY_VALUE="my-custom-value"
```

**Solution:**

```bash
# Correct format
export API_KEY_VALUE="my-value"
secretzero sync

# For template secrets
export DATABASE_CREDENTIALS_PASSWORD="my-password"
secretzero sync
```

## Target Storage Issues

### File Already Exists

**Symptom:**

```bash
Error: File .env already exists (use merge: true to append)
```

**Solution:**

```yaml
targets:
  - type: local-file
    path: .env
    format: dotenv
    merge: true  # ✅ Append/update instead of overwrite
```

### File Permission Denied

**Symptom:**

```bash
Error: Permission denied: '.env'
```

**Solution:**

```bash
# Check file permissions
ls -la .env

# Make writable
chmod u+w .env

# Or delete and regenerate
rm .env
secretzero sync
```

### Directory Not Found

**Symptom:**

```bash
Error: Directory 'config/secrets' does not exist
```

**Solution:**

SecretZero automatically creates parent directories. If this fails:

```bash
# Create directory manually
mkdir -p config/secrets

# Or check permissions on parent
ls -la config/
```

### AWS Secret Already Exists

**Symptom:**

```bash
Error: ResourceExistsException: The secret /myapp/api_key already exists
```

**Solution:**

```yaml
targets:
  - type: aws-secretsmanager
    name: /myapp/api_key
    # Option 1: Allow updates (recommended)
    update_existing: true
    
    # Option 2: Use different name
    # name: /myapp/api_key_v2
```

### Kubernetes Secret Not Found

**Symptom:**

```bash
Error: secrets "app-secrets" not found in namespace "production"
```

**Solution:**

```bash
# Create namespace first
kubectl create namespace production

# Or use existing namespace
kubectl get namespaces
```

## Lockfile Issues

### Lockfile Corrupted

**Symptom:**

```bash
Error: Invalid lockfile format
```

**Solution:**

```bash
# Backup existing lockfile
cp .gitsecrets.lock .gitsecrets.lock.backup

# Delete and regenerate
rm .gitsecrets.lock
secretzero sync
```

### Hash Mismatch

**Symptom:**

```bash
Warning: Lockfile hash doesn't match current secret
```

**Diagnosis:**

```bash
# Check for drift
secretzero drift

# Check secret status
secretzero show api_key
```

**Solution:**

```bash
# Option 1: Resync to update lockfile
secretzero sync

# Option 2: Force regenerate
secretzero sync --force
```

### Lockfile Git Conflicts

**Symptom:**

```
<<<<<<< HEAD
  "api_key": {
    "hash": "sha256:abc123..."
=======
  "api_key": {
    "hash": "sha256:def456..."
>>>>>>> branch
```

**Solution:**

```bash
# Keep one version (usually newer)
git checkout --theirs .gitsecrets.lock

# Then resync to update
secretzero sync
```

## Rotation Issues

### Rotation Not Due Yet

**Symptom:**

```bash
$ secretzero rotate
No secrets need rotation at this time.
```

**Solution:**

```bash
# Check rotation status
secretzero rotate --dry-run

# Force rotation if needed
secretzero rotate --force api_key
```

### One-Time Secret Can't Rotate

**Symptom:**

```bash
Warning: Secret 'master_key' is marked one_time, skipping rotation
```

**Explanation:**

This is expected behavior. One-time secrets are not rotated automatically.

**Solution:**

```bash
# To rotate anyway, remove from lockfile
secretzero sync --force master_key

# Or remove one_time flag
```

### Rotation Period Invalid

**Symptom:**

```bash
Error: Invalid rotation period '3 months'
```

**Solution:**

Use correct format:

```yaml
# ❌ Invalid formats
rotation:
  period: "3 months"
  period: "90 days"

# ✅ Valid formats
rotation:
  period: 90d    # Days
  period: 12w    # Weeks
  period: 3m     # Months
  period: 1y     # Years
```

## Policy Issues

### Policy Validation Failures

**Symptom:**

```bash
Error: Secret 'api_key' violates policy 'require_rotation'
```

**Solution:**

Add rotation period:

```yaml
secrets:
  api_key:
    rotation:
      period: 90d  # ✅ Add rotation period
```

### SOC2 Compliance Failures

**Symptom:**

```bash
Error: Secret 'db_password' exceeds max age of 90 days
```

**Solution:**

```yaml
secrets:
  db_password:
    rotation:
      period: 90d  # ✅ Must be ≤ 90 days for SOC2
```

### Access Policy Denials

**Symptom:**

```bash
Warning: Target 'local-file' is denied by policy 'cloud_only'
```

**Solution:**

```yaml
# Option 1: Remove denied target
targets:
  - type: aws-secretsmanager  # ✅ Allowed

# Option 2: Update policy
policies:
  cloud_only:
    type: access
    config:
      allowed_targets:
        - aws-secretsmanager
        - local-file  # ✅ Add to allowed list
```

## API Service Issues

### API Server Won't Start

**Symptom:**

```bash
Error: [Errno 98] Address already in use
```

**Solution:**

```bash
# Check what's using port 8000
lsof -i :8000

# Use different port
export SECRETZERO_PORT=9000
secretzero-api
```

### API Authentication Failed

**Symptom:**

```bash
$ curl http://localhost:8000/secrets
{"detail":"Missing API key"}
```

**Solution:**

```bash
# Set API key
export SECRETZERO_API_KEY="your-api-key"

# Include in request
curl -H "X-API-Key: $SECRETZERO_API_KEY" \
  http://localhost:8000/secrets
```

### API Returns 404

**Symptom:**

```bash
$ curl http://localhost:8000/api/secrets
{"detail":"Not Found"}
```

**Solution:**

Endpoints don't have `/api` prefix:

```bash
# ❌ Incorrect
curl http://localhost:8000/api/secrets

# ✅ Correct
curl http://localhost:8000/secrets
```

## CI/CD Issues

### GitHub Actions: Command Not Found

**Symptom:**

```yaml
Run secretzero sync
secretzero: command not found
```

**Solution:**

Install SecretZero first:

```yaml
steps:
  - name: Install SecretZero
    run: pip install secretzero[aws]
  
  - name: Sync Secrets
    run: secretzero sync
```

### GitLab CI: Authentication Failed

**Symptom:**

```
Error: Unable to connect to AWS
```

**Solution:**

Add credentials as CI/CD variables:

```yaml
sync-secrets:
  script:
    - pip install secretzero[aws]
    - secretzero sync
  variables:
    AWS_ACCESS_KEY_ID: $AWS_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY: $AWS_SECRET_ACCESS_KEY
```

### Jenkins: Pipeline Fails

**Symptom:**

```
Error: secretzero: not found
```

**Solution:**

```groovy
pipeline {
  agent any
  stages {
    stage('Sync Secrets') {
      steps {
        sh '''
          python3 -m pip install secretzero[all]
          python3 -m secretzero sync
        '''
      }
    }
  }
}
```

## Performance Issues

### Slow Secret Generation

**Symptom:**

Sync takes a long time to complete.

**Diagnosis:**

```bash
# Use dry-run to see what's slow
time secretzero sync --dry-run
```

**Solutions:**

1. **Script Generators**: Check script execution time
2. **Cloud Targets**: Check network latency
3. **Many Secrets**: Consider batching

### High Memory Usage

**Symptom:**

SecretZero using excessive memory.

**Solutions:**

1. Reduce number of secrets per sync
2. Split into multiple Secretfiles
3. Use `--force` only when necessary

## Getting More Help

### Enable Debug Logging

```bash
# Set log level
export SECRETZERO_LOG_LEVEL=DEBUG

# Run command
secretzero sync
```

### Collect Diagnostic Information

```bash
# System info
cat > diagnostic.txt << EOF
SecretZero Version: $(secretzero --version)
Python Version: $(python --version)
OS: $(uname -a)
Installed Packages: $(pip list | grep -E "(secretzero|boto3|azure|hvac)")
EOF

# Attach to issue
```

### Report a Bug

If none of these solutions work, please [open an issue](https://github.com/zloeber/SecretZero/issues) with:

1. SecretZero version
2. Python version
3. Operating system
4. Full error message
5. Steps to reproduce
6. Redacted configuration (remove sensitive data)

### Additional Resources

- [FAQ](faq.md) - Common questions
- [Architecture](architecture.md) - Technical details
- [GitHub Discussions](https://github.com/zloeber/SecretZero/issues) - Community support
- [Examples](../examples/index.md) - Working configurations

## See Also

- [Installation Guide](../getting-started/installation.md)
- [Configuration Reference](../schema.md)
- [CLI Reference](cli.md)
- [API Documentation](../api-getting-started.md)
