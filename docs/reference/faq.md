# Frequently Asked Questions (FAQ)

Common questions about SecretZero installation, configuration, usage, and troubleshooting.

## General Questions

### What is SecretZero?

SecretZero is a secrets management tool that automates the creation, seeding, and lifecycle management of project secrets through a declarative, schema-driven workflow. Think of it as "Terraform for secrets" - you declare what secrets you need, and SecretZero handles generation, storage, rotation, and compliance.

### Why should I use SecretZero?

Use SecretZero if you need to:

- **Bootstrap new environments** from scratch without manual secret handling
- **Track all secrets** in your project in a single source of truth
- **Automate rotation** of secrets based on compliance policies
- **Synchronize secrets** across multiple platforms (AWS, Azure, Kubernetes, etc.)
- **Document** your project's secrets surface area
- **Enforce compliance** with SOC2, ISO27001, or custom policies

### How is SecretZero different from other tools?

| Feature | SecretZero | HashiCorp Vault | AWS Secrets Manager | 1Password/Bitwarden |
|---------|-----------|----------------|---------------------|---------------------|
| **Declarative Config** | ✅ | ❌ | ❌ | ❌ |
| **Multi-Provider** | ✅ | ❌ | ❌ | Partial |
| **Secret Generation** | ✅ | Partial | ❌ | ❌ |
| **Rotation Policies** | ✅ | ✅ | ✅ | ❌ |
| **Lockfile Tracking** | ✅ | ❌ | ❌ | ❌ |
| **CI/CD Integration** | ✅ | Partial | Partial | Partial |
| **Local Development** | ✅ | Partial | ❌ | ✅ |

**Key Differences:**

- **Vault**: Runtime secret storage; SecretZero: Lifecycle management
- **AWS Secrets Manager**: AWS-only; SecretZero: Multi-cloud
- **1Password**: Human-oriented; SecretZero: Automation-oriented

### Is SecretZero production-ready?

Yes! SecretZero has:

- ✅ **200+ tests** with high code coverage
- ✅ **Zero security vulnerabilities** (CodeQL verified)
- ✅ **Battle-tested** across 7 development phases
- ✅ **SOC2/ISO27001** compliance support
- ✅ **Comprehensive documentation**

### Is SecretZero open source?

Yes, SecretZero is open source under the Apache 2.0 license. You can:

- Use it commercially
- Modify and distribute
- Contribute improvements
- View the source code

See [LICENSE](https://github.com/zloeber/SecretZero/blob/main/LICENSE) for details.

### Isn't committing `Secretfile.yml` insecure if someone can infer our secrets from source?

Great question. Short answer: **No, `Secretfile.yml` is a map, not the treasure chest.**

`Secretfile.yml` intentionally describes:

- what secret *types* exist (for example: `db_password`, `api_token`)
- where they should go (AWS Secrets Manager, `.env`, Kubernetes, etc.)
- how they are generated or sourced

It does **not** store the actual secret values. SecretZero keeps plaintext out of git and tracks only metadata plus hashes in `.gitsecrets.lock`.

If an attacker already has full access to your source repository, they can usually infer your application's sensitive areas anyway ("this app probably has a DB password" is not exactly Sherlock Holmes-level deduction). The security boundary is the **secret value**, not the fact that your app uses one.

Think of it this way:

- `Secretfile.yml` is your security **runbook**
- your secret managers/providers hold the actual **nuclear launch codes**

Hiding the runbook doesn't make the codes safer if code access is already compromised. What *does* help is:

- keeping secret values out of code and commits (SecretZero does this)
- using least-privilege IAM/provider policies
- rotating secrets regularly
- auditing access and drift

So yes, keep `Secretfile.yml` in version control. That's a feature, not a leak.

### Are git-encrypted providers (SOPS, git-crypt, Ansible Vault) really "secret zero"?

Short answer: **not by themselves**. In most setups, they are encrypted transport/storage lanes, not the initial trust anchor.

What's going on:

- SOPS still needs access to your KMS/age/PGP identity.
- git-crypt still needs an unlock key.
- Ansible Vault still needs a vault password or password source.

That bootstrap credential is the actual "secret zero" in your chain of trust.

In SecretZero terms, these providers are best understood as **target adapters** for encrypted-in-git workflows. They are useful (and supported) because teams often need to land managed secrets into repository-encrypted artifacts for downstream tooling, review, or promotion workflows.

So the practical model is:

- SecretZero manages generation/rotation/lifecycle.
- Encrypted-in-git targets handle at-rest representation in the repo.
- Your bootstrap credential (KMS identity, vault pass, git-crypt key) remains the true initial secret zero.

It's less "we hid the secret under a rug" and more "we put it in a locked safe, then manage who holds the key shard."

## Installation & Setup

### What are the system requirements?

- **Python**: 3.9, 3.10, 3.11, or 3.12
- **Operating System**: Linux, macOS, or Windows
- **pip**: Latest version recommended

Optional dependencies based on providers you use.

### How do I install SecretZero?

Basic installation:

```bash
pip install secretzero
```

With specific providers:

```bash
# AWS support
pip install secretzero[aws]

# All providers
pip install secretzero[all]
```

See the [Installation Guide](../getting-started/installation.md) for details.

### Do I need cloud accounts to use SecretZero?

No! SecretZero works perfectly for local development:

```yaml
targets:
  - type: local-file
    path: .env
    format: dotenv
```

Cloud providers are optional and only needed if you want to store secrets in AWS, Azure, etc.

### How do I upgrade SecretZero?

```bash
pip install --upgrade secretzero
```

With all dependencies:

```bash
pip install --upgrade secretzero[all]
```

SecretZero maintains backward compatibility with existing `Secretfile.yml` and lockfiles.

### Can I use SecretZero in Docker?

Yes! Example Dockerfile:

```dockerfile
FROM python:3.11-slim

# Install SecretZero
RUN pip install secretzero[all]

# Copy configuration
COPY Secretfile.yml /app/
WORKDIR /app

# Run SecretZero
CMD ["secretzero", "sync"]
```

Build and run:

```bash
docker build -t secretzero .
docker run -v $(pwd):/app secretzero
```

## Configuration

### How do I create a Secretfile?

Initialize with a template:

```bash
secretzero create
```

Or create manually:

```yaml
version: "1.0"

metadata:
  name: my-project

secrets:
  api_key:
    template:
      type: api_key
      fields:
        - name: value
          generator:
            type: random-string
            length: 32
    targets:
      - type: local-file
        path: .env
        format: dotenv
```

See [First Project](../getting-started/first-project.md) for a complete walkthrough.

### Can I use environment variables in the Secretfile?

Yes! Use Jinja2 templating:

```yaml
variables:
  environment: "{{env.ENVIRONMENT or 'development'}}"
  region: "{{env.AWS_REGION or 'us-east-1'}}"

secrets:
  api_key:
    targets:
      - type: aws-secretsmanager
        name: "/{{var.environment}}/api_key"
        region: "{{var.region}}"
```

### How do I manage secrets for multiple environments?

**Option 1: Variables**

```yaml
variables:
  environment: "{{env.ENVIRONMENT}}"

secrets:
  api_key:
    targets:
      - type: aws-secretsmanager
        name: "/{{var.environment}}/api_key"
```

```bash
ENVIRONMENT=production secretzero sync
ENVIRONMENT=staging secretzero sync
```

**Option 2: Separate Lockfiles**

```bash
secretzero sync --lockfile .gitsecrets-prod.lock
secretzero sync --lockfile .gitsecrets-staging.lock
```

**Option 3: Separate Secretfiles**

```bash
secretzero sync --file Secretfile-prod.yml
secretzero sync --file Secretfile-staging.yml
```

### Can I use existing secrets instead of generating new ones?

Yes! Set environment variables matching the secret name:

```bash
export API_KEY="my-existing-key"
secretzero sync
```

SecretZero checks environment variables first before generating.

### How do I validate my Secretfile?

```bash
secretzero validate
```

This checks:

- ✅ YAML syntax
- ✅ Required fields
- ✅ Type validation
- ✅ Provider configuration
- ✅ Generator configuration

## Cloud Providers

### Which cloud providers are supported?

- **AWS**: Secrets Manager, SSM Parameter Store
- **Azure**: Key Vault
- **HashiCorp Vault**: KV v1 & v2
- **GitHub Actions**: Repository, environment, and organization secrets
- **GitLab CI/CD**: Project and group variables
- **Jenkins**: String and username/password credentials
- **Kubernetes**: Native Secrets and External Secrets Operator

### How do I authenticate with AWS?

SecretZero uses standard AWS credential chain:

```yaml
providers:
  aws:
    kind: aws
    auth:
      kind: ambient  # Uses default credential chain
      config:
        region: us-east-1
```

Supported methods:

1. Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
2. AWS credentials file (`~/.aws/credentials`)
3. IAM roles (EC2 instance profiles, ECS task roles)
4. AWS profiles

```bash
export AWS_PROFILE=myprofile
secretzero sync
```

### How do I authenticate with Azure?

```yaml
providers:
  azure:
    kind: azure
    auth:
      kind: default  # Uses Azure credential chain
```

Supported methods:

1. Environment variables
2. Managed Identity (in Azure VMs/containers)
3. Azure CLI (`az login`)
4. Visual Studio Code credentials

### How do I test provider connectivity?

```bash
secretzero test
```

This verifies:

- ✅ Authentication is working
- ✅ Network connectivity
- ✅ Required permissions
- ✅ Provider configuration

### What AWS permissions does SecretZero need?

**For Secrets Manager:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:CreateSecret",
        "secretsmanager:UpdateSecret",
        "secretsmanager:DescribeSecret",
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:*:*:secret:/myapp/*"
    }
  ]
}
```

**For SSM Parameter Store:**

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

## Secret Generation

### What types of secrets can SecretZero generate?

- **Random Passwords**: Cryptographically secure passwords
- **Random Strings**: Alphanumeric tokens, hex strings, etc.
- **Static Values**: Usernames, URLs, configuration values
- **Script-Generated**: SSH keys, certificates, custom values
- **API-Generated**: Fetch from external APIs (planned)

### How secure are generated passwords?

Very secure! SecretZero uses:

- Python's `secrets` module (cryptographically secure)
- System entropy sources
- Configurable length (default: 32 characters)
- Customizable character sets

Generated passwords have high entropy (e.g., 32 chars = ~192 bits of entropy with full character set).

### Can I customize password requirements?

Yes! Full control over character sets:

```yaml
generator:
  type: random-password
  length: 32
  include_upper: true
  include_lower: true
  include_numbers: true
  include_symbols: true
  exclude_characters: '"@/\`'  # Exclude problematic chars
```

### How do I generate SSH keys?

Use the `script` generator:

```yaml
generator:
  type: script
  command: ssh-keygen
  args:
    - -t
    - rsa
    - -b
    - "4096"
    - -f
    - /dev/stdout
    - -N
    - ""
```

Or use dedicated tools like `ssh-keygen` directly and import the keys as static values.

### Can I use external APIs to generate secrets?

Not directly in current version, but you can use the `script` generator to call APIs:

```yaml
generator:
  type: script
  command: curl
  args:
    - -s
    - https://api.example.com/generate-key
```

Native API generator support is planned for future releases.

## Secret Storage

### Where can I store secrets?

**Local Storage:**

- `.env` files (dotenv format)
- JSON files
- YAML files
- TOML files

**Cloud Storage:**

- AWS Secrets Manager
- AWS SSM Parameter Store
- Azure Key Vault
- HashiCorp Vault

**CI/CD Platforms:**

- GitHub Actions Secrets
- GitLab CI/CD Variables
- Jenkins Credentials

**Container Platforms:**

- Kubernetes Secrets
- External Secrets Operator

### Can I store the same secret in multiple locations?

Yes! That's a core feature:

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
    targets:
      - type: local-file
        path: .env
      - type: aws-secretsmanager
        name: /myapp/api_key
      - type: kubernetes-secret
        namespace: production
```

The same value is stored in all targets.

### Can dict/object secrets be auto-mapped to key/value entries in AWS targets?

Not today. For AWS `secrets_manager` and `ssm_parameter` targets, dict/object secret values are stored as a single JSON string payload, not automatically exploded into separate key/value entries.

What this means:

- A dict source value is preserved, but as one JSON blob in the target value field.
- SecretZero does not currently provide automatic per-attribute mapping (for example `username` -> one key, `password` -> another key) for these AWS targets.

Recommended workaround:

- Use template field modeling (`templates.*`) or separate secret definitions when you need explicit per-key target mapping behavior.

### What happens if one target fails?

SecretZero continues with other targets and reports errors at the end:

```
✓ Generated secret: api_key
  ✓ Wrote to: .env
  ✗ Failed to write to: AWS Secrets Manager (No credentials)
  ✓ Wrote to: Kubernetes

Summary:
  Generated: 1
  Targets Updated: 2
  Targets Failed: 1
```

The lockfile is still updated for successful targets.

### How do I update an existing secret?

**Option 1: Force Sync**

```bash
secretzero sync --force
```

**Option 2: Rotate**

```bash
secretzero rotate api_key --force
```

**Option 3: Change Configuration**

Modify the generator config in `Secretfile.yml`, then:

```bash
secretzero sync
```

## Rotation & Compliance

### How does secret rotation work?

1. Define rotation period:
   ```yaml
   rotation:
     period: 90d
   ```

2. Check rotation status:
   ```bash
   secretzero rotate --dry-run
   ```

3. Rotate due secrets:
   ```bash
   secretzero rotate
   ```

The lockfile tracks `last_rotated` timestamp and `rotation_count`.

### What rotation periods are supported?

- **Days**: `7d`, `30d`, `90d`
- **Weeks**: `1w`, `2w`, `4w`
- **Months**: `1m`, `3m`, `6m`
- **Years**: `1y`, `2y`

### Can I prevent a secret from being rotated?

Yes! Use `one_time: true`:

```yaml
secrets:
  master_key:
    one_time: true
```

This generates the secret once and never rotates it automatically.

### How do I enforce SOC2 compliance?

Add SOC2 to metadata:

```yaml
metadata:
  compliance:
    - soc2
```

SecretZero automatically checks:

- ✅ All secrets have rotation periods
- ✅ Rotation periods ≤ 90 days
- ✅ Secrets are tracked in lockfile

Verify compliance:

```bash
secretzero policy
```

### What's the difference between rotation and regeneration?

**Rotation:**

- Scheduled based on time period
- Updates `last_rotated` timestamp
- Increments `rotation_count`
- Respects `one_time` flag

**Regeneration (force sync):**

- Manual operation
- Ignores rotation schedule
- Doesn't update rotation metadata
- Ignores `one_time` flag with `--force`

## Lockfile

### What is the lockfile?

The lockfile (`.gitsecrets.lock`) tracks secret state:

- SHA-256 hashes of secret values
- Creation and update timestamps
- Rotation history
- Target information

**It does NOT contain actual secret values.**

### Is it safe to commit the lockfile?

**Yes!** The lockfile contains only:

- One-way SHA-256 hashes
- Timestamps
- Metadata

No actual secret values are stored. Committing it enables:

- ✅ Drift detection
- ✅ Audit trails
- ✅ Team synchronization

For GitOps/IaC usage, the recommended policy is to commit lockfiles and use one lockfile per environment lane. See [Lockfile Version Control Policy](../user-guide/lockfile-version-control-policy.md).

### What if I lose the lockfile?

No problem! Just regenerate:

```bash
secretzero sync
```

SecretZero will:

1. Detect missing lockfile
2. Generate new hashes for current secrets
3. Create new lockfile

**Note**: You'll lose rotation history.

### Can I manually edit the lockfile?

Not recommended! The lockfile is auto-generated and managed by SecretZero. Manual edits may cause:

- Incorrect drift detection
- Failed validation
- Sync issues

If you need to reset, just delete it and run `secretzero sync`.

## CI/CD Integration

### How do I use SecretZero in CI/CD?

**GitHub Actions Example:**

```yaml
name: Sync Secrets

on:
  push:
    branches: [main]

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Install SecretZero
        run: pip install secretzero[aws]
      
      - name: Sync Secrets
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        run: secretzero sync
```

**GitLab CI Example:**

```yaml
sync-secrets:
  image: python:3.11
  script:
    - pip install secretzero[aws]
    - secretzero sync
  variables:
    AWS_ACCESS_KEY_ID: $AWS_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY: $AWS_SECRET_ACCESS_KEY
```

### How do I enforce policies in CI/CD?

Add a policy check step:

```yaml
- name: Check Policies
  run: |
    secretzero policy --fail-on-warning
```

This fails the CI pipeline if any policy violations are found.

### Can SecretZero read secrets from CI/CD platforms?

SecretZero primarily **writes** secrets to CI/CD platforms (GitHub Actions, GitLab CI/CD, Jenkins).

For reading, use the native tools:

- GitHub: `${{ secrets.SECRET_NAME }}`
- GitLab: `$SECRET_NAME`
- Jenkins: `credentials('secret-id')`

### How do I rotate secrets automatically in CI/CD?

**Scheduled GitHub Action:**

```yaml
name: Rotate Secrets

on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly

jobs:
  rotate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Install SecretZero
        run: pip install secretzero[all]
      - name: Rotate Secrets
        run: secretzero rotate
```

## API Service

### How do I start the API server?

```bash
# Generate API key
export SECRETZERO_API_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")

# Start server
secretzero-api
```

Access at `http://localhost:8000`

### What endpoints are available?

- `GET /` - API information
- `GET /health` - Health check
- `POST /config/validate` - Validate Secretfile
- `GET /secrets` - List secrets
- `GET /secrets/{name}/status` - Get secret status
- `POST /sync` - Sync secrets
- `POST /rotation/check` - Check rotation
- `POST /rotation/execute` - Execute rotation
- `POST /policy/check` - Check policies
- `POST /drift/check` - Detect drift
- `GET /audit/logs` - Get audit logs

See the [API Getting Started Guide](../api-getting-started.md) for details.

### How do I authenticate API requests?

Use the `X-API-Key` header:

```bash
curl -H "X-API-Key: $SECRETZERO_API_KEY" \
  http://localhost:8000/secrets
```

### Can I deploy the API in production?

Yes! Recommendations:

1. **Use HTTPS**: Deploy behind reverse proxy (nginx, Traefik)
2. **Rotate API Keys**: Regular key rotation
3. **Rate Limiting**: Add rate limiting middleware
4. **Network Policies**: Restrict access via firewall
5. **Monitoring**: Add metrics and alerting

See production deployment guide in [API documentation](../api-getting-started.md#production-deployment).

## Troubleshooting

### SecretZero command not found

**Cause**: Package not installed or not in PATH

**Solution**:

```bash
# Verify installation
pip show secretzero

# Reinstall
pip install --force-reinstall secretzero

# Check PATH
which secretzero
```

### Checking Provider Permissions

SecretZero can introspect provider authentication tokens to verify they have the necessary permissions:

```bash
# Check GitHub token permissions and scopes
secretzero providers token-info

# Output shows:
# - User information
# - OAuth scopes (repo, workflow, admin:org, etc.)
# - Capabilities (can read repos, write secrets, etc.)
# - Links to documentation on permission requirements
```

This is useful for:
- **Troubleshooting** - Verify token has required scopes before attempting operations
- **Security auditing** - Document what permissions are granted to tokens
- **Compliance** - Ensure tokens follow principle of least privilege
- **Onboarding** - Help new team members create tokens with correct permissions

Currently supported providers: GitHub (more providers coming soon).


### Import errors for cloud providers

**Error**: `ModuleNotFoundError: No module named 'boto3'`

**Cause**: Optional dependencies not installed

**Solution**:

```bash
# Install AWS support
pip install secretzero[aws]

# Or install all providers
pip install secretzero[all]
```

### AWS authentication failed

**Error**: `Unable to locate credentials`

**Solution**:

```bash
# Check AWS credentials
aws sts get-caller-identity

# Set credentials
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_DEFAULT_REGION=us-east-1

# Or use AWS profile
export AWS_PROFILE=myprofile
```

### Secret not being generated

**Issue**: Secret shows as "skipped"

**Possible Causes**:

1. **One-time secret**: Already exists in lockfile
   ```bash
   secretzero show <secret-name>
   # Use --force to regenerate
   secretzero sync --force
   ```

2. **Environment variable set**: Overriding generation
   ```bash
   env | grep <SECRET_NAME>
   # Unset to use generator
   unset SECRET_NAME
   ```

### Lockfile conflicts

**Error**: Hash mismatch in lockfile

**Solution**:

```bash
# Check for drift
secretzero drift

# Force resync
secretzero sync --force

# Or regenerate lockfile
rm .gitsecrets.lock
secretzero sync
```

## Getting Help

### Where can I get support?

- **Documentation**: [secretzero.readthedocs.io](https://secretzero.readthedocs.io)
- **GitHub Issues**: [Report bugs](https://github.com/zloeber/SecretZero/issues)
- **Discussions**: [Ask questions](https://github.com/zloeber/SecretZero/discussions)
- **Examples**: [View examples](../examples/index.md)

### How do I report a bug?

1. Check [existing issues](https://github.com/zloeber/SecretZero/issues)
2. Create new issue with:
   - SecretZero version (`secretzero --version`)
   - Python version (`python --version`)
   - Operating system
   - Steps to reproduce
   - Expected vs actual behavior
   - Relevant logs (redact sensitive info)

### How do I request a feature?

Open a [feature request](https://github.com/zloeber/SecretZero/issues/new) with:

- Use case description
- Proposed solution
- Alternative solutions considered
- Impact on existing functionality

### How can I contribute?

See the [Contributing Guide](../contributing/index.md) for:

- Code contribution guidelines
- Development setup
- Testing requirements
- Pull request process

## See Also

- [Installation Guide](../getting-started/installation.md)
- [Quick Start](../getting-started/quickstart.md)
- [First Project Tutorial](../getting-started/first-project.md)
- [Troubleshooting Guide](troubleshooting.md)
- [Architecture](architecture.md)
