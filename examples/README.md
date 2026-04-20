# SecretZero Examples

This directory contains example Secretfile configurations demonstrating various use cases and features of SecretZero.

## Variable Override with .szvar Files

SecretZero supports `.szvar` files (similar to Terraform's `.tfvars`) for environment-specific variable overrides. This allows you to maintain a base Secretfile and override variables for different environments without modifying the main configuration.

### Example Files

- `variable-override.yml` - Base Secretfile with default variables
- `dev.szvar` - Development environment variables
- `prod.szvar` - Production environment variables

### Usage

```bash
# Use default variables from Secretfile
secretzero sync -f examples/variable-override.yml

# Override with dev environment variables
secretzero sync -f examples/variable-override.yml --var-file examples/dev.szvar

# Override with prod environment variables
secretzero sync -f examples/variable-override.yml --var-file examples/prod.szvar

# Use multiple variable files (later files take precedence)
secretzero sync -f examples/variable-override.yml \
  --var-file examples/base.szvar \
  --var-file examples/dev.szvar

# Render the final configuration to see merged variables
secretzero render -f examples/variable-override.yml --var-file examples/dev.szvar
```

### Benefits

- **Environment separation**: Keep environment-specific values in separate files
- **Version control**: Commit `.szvar` files for different environments
- **CI/CD integration**: Use different variable files in different pipelines
- **Debugging**: Use `secretzero render` to see the final merged configuration

## Examples

### 1. Local Development Only (`local-only.yml`)

Simple configuration for local development without cloud dependencies.

**Features:**
- Local file storage only
- Random password and string generation
- Template-based configuration
- No cloud provider requirements

**Usage:**
```bash
# Initialize from template
cp examples/local-only.yml Secretfile.yml

# Generate and sync secrets
secretzero sync

# View generated files
cat .env
cat config.json
```

### 2. AWS Only (`aws-only.yml`)

Production-ready configuration using AWS services.

**Features:**
- AWS SSM Parameter Store for database credentials
- AWS Secrets Manager for API keys
- Static secrets with validation
- Environment variable fallback

**Prerequisites:**
- AWS credentials configured (via `aws configure` or environment variables)
- Install AWS support: `pip install secretzero[aws]`

**Usage:**
```bash
# Copy example
cp examples/aws-only.yml Secretfile.yml

# Test AWS connectivity
secretzero test

# Sync secrets (dry-run first)
secretzero sync --dry-run
secretzero sync
```

### 3. Multi-Cloud Distribution (`multi-cloud.yml`)

Enterprise configuration distributing secrets across AWS, Azure, and HashiCorp Vault.

**Features:**
- Multi-cloud secret distribution
- Local file + 3 cloud providers
- Template-based secrets
- Variable interpolation
- Compliance metadata

**Prerequisites:**
- AWS credentials configured
- Azure credentials (`az login` or managed identity)
- Vault token and address
- Install all providers: `pip install secretzero[all]`

**Usage:**
```bash
# Copy example
cp examples/multi-cloud.yml Secretfile.yml

# Set required environment variables
export VAULT_TOKEN=your_token
export VAULT_ADDR=http://localhost:8200

# Test all provider connectivity
secretzero test

# Sync secrets (dry-run first)
secretzero sync --dry-run
secretzero sync
```

### 4. Script-Based SSH Keypair (`script-ssh-keypair/`)

Example project showing SSH keypair generation via the `script` generator.

**Features:**
- Uses `zsh` + `ssh-keygen` for keypair creation
- Template secret with `private_key` and `public_key` fields
- Local output file target (`generated/ssh-keypair.yml`)
- Local `.gitignore` for generated private key material

**Usage:**
```bash
secretzero validate -f examples/script-ssh-keypair/Secretfile.yml
secretzero sync --dry-run -f examples/script-ssh-keypair/Secretfile.yml
secretzero sync -f examples/script-ssh-keypair/Secretfile.yml
```

### 5. Entra Agent ID Blueprint (`entra-agent-id-blueprint.yml`)

Example showing Entra Agent Identity Blueprint lifecycle through the
`entra-agent-blueprint` generator kind and `entra-agent-id` provider.

**Features:**
- Blueprint create/update via Microsoft Graph preview shape
- Credential reconciliation (client secrets + federated credentials)
- Optional child `agentIdentity` declarations
- Metadata-only output target for GitOps review

**Usage:**
```bash
secretzero validate -f examples/entra-agent-id-blueprint.yml
secretzero sync --dry-run -f examples/entra-agent-id-blueprint.yml
secretzero sync -f examples/entra-agent-id-blueprint.yml
```

## Common Workflows

### Testing Configuration

Always test your configuration before syncing:

```bash
# Validate Secretfile syntax
secretzero validate

# Test provider connectivity
secretzero test

# Preview what would be created
secretzero sync --dry-run
```

### Environment-Specific Secrets

Use variables to customize for different environments:

```bash
# Development
secretzero sync --file Secretfile.yml --var environment=dev

# Production
secretzero sync --file Secretfile.yml --var environment=prod
```

### Viewing Secret Status

Check if secrets have been generated and synced:

```bash
# Show secret information
secretzero show database_password

# Check lockfile
cat .gitsecrets.lock
```

### One-Time Secrets

Secrets marked as `one_time: true` are generated once and never updated:

```yaml
secrets:
  - name: root_password
    kind: random_password
    one_time: true
    rotation_period: 90d  # Warning only, not auto-rotated
```

## Provider Configuration

### AWS

**Ambient Authentication** (recommended):
```yaml
providers:
  aws:
    kind: aws
    auth:
      kind: ambient
      region: us-east-1
```

**Profile-Based**:
```yaml
providers:
  aws:
    kind: aws
    auth:
      kind: profile
      profile: myprofile
      region: us-east-1
```

**Assume Role**:
```yaml
providers:
  aws:
    kind: aws
    auth:
      kind: assume_role
      role_arn: arn:aws:iam::123456789012:role/SecretAdmin
      region: us-east-1
```

### Azure

**Default Credential Chain** (recommended):
```yaml
providers:
  azure:
    kind: azure
    auth:
      kind: default
```

**Managed Identity**:
```yaml
providers:
  azure:
    kind: azure
    auth:
      kind: managed_identity
      client_id: 12345678-1234-1234-1234-123456789012
```

**Azure CLI**:
```yaml
providers:
  azure:
    kind: azure
    auth:
      kind: cli
```

### HashiCorp Vault

**Token Authentication**:
```yaml
providers:
  vault:
    kind: vault
    auth:
      kind: token
      token: ${VAULT_TOKEN}
      url: http://localhost:8200
```

**AppRole**:
```yaml
providers:
  vault:
    kind: vault
    auth:
      kind: approle
      role_id: ${VAULT_ROLE_ID}
      secret_id: ${VAULT_SECRET_ID}
      url: http://localhost:8200
```

## Target Types

### Local File
```yaml
targets:
  - provider: local
    kind: file
    config:
      path: .env
      format: dotenv  # or json, yaml, toml
      merge: true     # preserve existing content
```

### AWS SSM Parameter Store
```yaml
targets:
  - provider: aws
    kind: ssm_parameter
    config:
      name: /app/secret
      type: SecureString  # or String, StringList
      overwrite: true
      tier: Standard      # or Advanced
```

### AWS Secrets Manager
```yaml
targets:
  - provider: aws
    kind: secrets_manager
    config:
      name: app/secret
      description: My secret
      kms_key_id: alias/aws/secretsmanager  # optional
```

### Azure Key Vault
```yaml
targets:
  - provider: azure
    kind: key_vault
    config:
      vault_url: https://myvault.vault.azure.net
      secret_name: my-secret
```

### HashiCorp Vault KV
```yaml
targets:
  - provider: vault
    kind: kv
    config:
      path: app/secret
      mount_point: secret
      version: 2  # or 1 for KV v1
```

## Best Practices

1. **Always use dry-run first**: Test changes before applying
   ```bash
   secretzero sync --dry-run
   ```

2. **Test provider connectivity**: Verify authentication before syncing
   ```bash
   secretzero test
   ```

3. **Use environment variables for sensitive data**: Don't commit credentials
   ```yaml
   auth:
     token: ${VAULT_TOKEN}  # From environment
   ```

4. **Use one_time for critical secrets**: Prevent accidental overwrites
   ```yaml
   one_time: true
   ```

5. **Set rotation periods**: Track when secrets should be rotated
   ```yaml
   rotation_period: 90d
   ```

6. **Use templates for complex secrets**: Group related fields
   ```yaml
   kind: templates.credentials
   ```

7. **Store lockfile in version control**: Track secret lifecycle
   ```bash
   git add .gitsecrets.lock
   ```

8. **Exclude generated files**: Don't commit actual secrets
   ```gitignore
   .env*
   config.json
   ```

## Troubleshooting

### Authentication Failures

**AWS**:
```bash
# Check credentials
aws sts get-caller-identity

# Check environment variables
env | grep AWS
```

**Azure**:
```bash
# Login
az login

# Check account
az account show
```

**Vault**:
```bash
# Check token
vault token lookup

# Check connectivity
curl $VAULT_ADDR/v1/sys/health
```

### Missing Dependencies

If you see import errors, install the required provider:

```bash
# For AWS
pip install secretzero[aws]

# For Azure
pip install secretzero[azure]

# For Vault
pip install secretzero[vault]

# For all providers
pip install secretzero[all]
```

### Target Storage Failures

Check that you have proper permissions:

**AWS**:
- SSM: `ssm:PutParameter`, `ssm:GetParameter`
- Secrets Manager: `secretsmanager:CreateSecret`, `secretsmanager:UpdateSecret`

**Azure**:
- Key Vault: `Secret Set` and `Secret Get` permissions

**Vault**:
- KV: `write` and `read` permissions on the path

## Support

For more information:
- Documentation: `docs/`
- GitHub Issues: https://github.com/zloeber/SecretZero/issues
- Main README: `../README.md`
