# secretzero create

Create a new Secretfile from a template.

## Synopsis

```bash
secretzero create [OPTIONS]
```

## Description

The `create` command generates a starter `Secretfile.yml` with example configurations for different provider types. This is the recommended way to start a new SecretZero project.

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--template-type` | choice | `basic` | Template type to use |
| `--output`, `-o` | path | `Secretfile.yml` | Output file path |
| `--help` | flag | - | Show help message |

### Template Types

| Template | Description |
|----------|-------------|
| `basic` | Simple local file storage |
| `aws` | AWS SSM and Secrets Manager |
| `azure` | Azure Key Vault |
| `vault` | HashiCorp Vault |
| `kubernetes` | Kubernetes Secrets |

## Examples

### Basic Template

Create a basic Secretfile with local file storage:

```bash
secretzero create
```

**Generated Secretfile.yml:**

```yaml
# Secretfile.yml
version: '1.0'

# Variables for dynamic configuration
variables:
  environment: local
  region: us-east-1

# Optional metadata
metadata:
  project: my-project
  owner: platform-team
  environments:
    - dev
    - prod
  compliance:
    - soc2

# Provider configurations
providers:
  local:
    kind: local
    config: {}

# Secret definitions
secrets:
  - name: example_password
    kind: random_password
    config:
      length: 32
      special: true
      upper: true
      lower: true
      number: true
    targets:
      - provider: local
        kind: file
        config:
          path: .env.local
          format: dotenv
          merge: true

# Secret templates for complex secrets
templates: {}

# Reserved for future use
policies: {}
labels: {}
annotations: {}
```

### AWS Template

Create a Secretfile configured for AWS:

```bash
secretzero create --template-type aws
```

**Generated configuration includes:**

- AWS provider with SSM Parameter Store
- AWS Secrets Manager examples
- IAM role assumption examples
- Common AWS secret patterns

### Custom Output Location

Specify a different output file:

```bash
secretzero create --output my-secrets.yml
```

### Environment-Specific Files

Create separate files for different environments:

```bash
# Development
secretzero create -o Secretfile.dev.yml

# Staging
secretzero create -o Secretfile.staging.yml

# Production
secretzero create -o Secretfile.prod.yml --template-type aws
```

## After Initialization

After creating your Secretfile, follow these next steps:

### 1. Edit the Secretfile

Customize the generated configuration:

```bash
vim Secretfile.yml
```

Add your actual secrets, providers, and targets.

### 2. Validate Configuration

Check that your configuration is valid:

```bash
secretzero validate
```

Expected output:

```
Validating: Secretfile.yml
✓ Configuration is valid

Configuration Summary:
  Version: 1.0
  Variables: 2
  Providers: 1
  Secrets: 1
  Templates: 0
```

### 3. Test Providers

Verify provider connectivity:

```bash
secretzero test
```

### 4. Dry Run

Preview what would be generated:

```bash
secretzero sync --dry-run
```

### 5. Generate Secrets

Actually generate and sync secrets:

```bash
secretzero sync
```

## Complete Workflow Example

```bash
# 1. Initialize project
secretzero create --template-type aws

# 2. Customize configuration
vim Secretfile.yml

# 3. Set required environment variables
export ENVIRONMENT=production
export AWS_REGION=us-east-1

# 4. Validate
secretzero validate

# 5. Test provider connectivity
secretzero test

# 6. Preview changes
secretzero sync --dry-run

# 7. Generate secrets
secretzero sync
```

## Error Handling

### File Already Exists

**Error:**

```
Error: File already exists: Secretfile.yml
```

**Solutions:**

1. Use a different output file:

```bash
secretzero create -o Secretfile.new.yml
```

2. Remove existing file first:

```bash
rm Secretfile.yml
secretzero create
```

3. Backup and replace:

```bash
mv Secretfile.yml Secretfile.yml.backup
secretzero create
```

### Permission Denied

**Error:**

```
Error: Permission denied: Secretfile.yml
```

**Solution:**

Check directory permissions:

```bash
# Check current directory permissions
ls -ld .

# Ensure you have write permission
chmod u+w .
```

## Template Customization

### Modifying the Basic Template

After initialization, customize for your use case:

**Add more secrets:**

```yaml
secrets:
  - name: database_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
  
  - name: api_key
    kind: static
    config:
      default: ${API_KEY}
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
```

**Add more providers:**

```yaml
providers:
  local:
    kind: local
    config: {}
  
  aws:
    kind: aws
    auth:
      kind: ambient
      config:
        region: us-east-1
```

**Add templates:**

```yaml
templates:
  database_credentials:
    description: Database connection credentials
    fields:
      username:
        generator:
          kind: static
          config:
            default: appuser
      password:
        generator:
          kind: random_password
          config:
            length: 32
```

## Best Practices

### 1. Use Appropriate Template

Choose the template that matches your infrastructure:

```bash
# Local development
secretzero create --template-type basic

# AWS deployment
secretzero create --template-type aws

# Kubernetes deployment
secretzero create --template-type kubernetes
```

### 2. Commit to Version Control

After initialization and customization:

```bash
git add Secretfile.yml
git commit -m "Initialize SecretZero configuration"
```

### 3. Document Requirements

Add comments to your Secretfile:

```yaml
# Secretfile.yml
version: '1.0'

# Required environment variables:
# - ENVIRONMENT: deployment environment (dev, staging, prod)
# - AWS_REGION: AWS region for resources
# - DATABASE_URL: database connection string

variables:
  environment: ${ENVIRONMENT}
  aws_region: ${AWS_REGION}
```

### 4. Use Environment-Specific Files

For multiple environments:

```bash
# Create base configuration
secretzero create -o Secretfile.base.yml

# Create environment-specific overrides
secretzero create -o Secretfile.dev.yml
secretzero create -o Secretfile.prod.yml --template-type aws
```

### 5. Start Simple

Begin with a basic configuration and add complexity as needed:

```yaml
# Start with one secret
secrets:
  - name: my_first_secret
    kind: random_password
    config:
      length: 32
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
```

Then expand:

```yaml
# Add more secrets, templates, providers as you grow
```

## Interactive Initialization

While SecretZero doesn't currently support interactive initialization, you can create a helper script:

```bash
#!/bin/bash
# init-secretzero.sh

echo "SecretZero Project Initialization"
echo "=================================="
echo ""

# Prompt for project details
read -p "Project name: " project_name
read -p "Owner/team: " owner
read -p "Environment (dev/staging/prod): " environment
read -p "Cloud provider (aws/azure/vault/kubernetes/none): " provider

# Create Secretfile based on provider
if [ "$provider" = "none" ]; then
  template="basic"
else
  template="$provider"
fi

secretzero create --template-type "$template"

# Customize with provided values
sed -i "s/project: my-project/project: $project_name/" Secretfile.yml
sed -i "s/owner: platform-team/owner: $owner/" Secretfile.yml
sed -i "s/environment: local/environment: $environment/" Secretfile.yml

echo ""
echo "Created Secretfile.yml for $project_name"
echo "Next steps:"
echo "  1. Edit Secretfile.yml to add your secrets"
echo "  2. Run 'secretzero validate' to check configuration"
echo "  3. Run 'secretzero sync --dry-run' to preview"
```

Make executable and use:

```bash
chmod +x init-secretzero.sh
./init-secretzero.sh
```

## Related Commands

- [`validate`](validate.md) - Validate the generated Secretfile
- [`test`](test.md) - Test provider connectivity
- [`sync`](sync.md) - Generate and sync secrets

## See Also

- [Configuration Guide](../configuration/index.md) - Learn about Secretfile structure
- [Secretfile Reference](../configuration/secretfile.md) - Complete Secretfile specification
- [Getting Started](../../getting-started/quickstart.md) - Step-by-step tutorial
- [Examples](../../examples/index.md) - Real-world examples

## Next Steps

After initializing your project:

1. **[Edit your Secretfile](../configuration/secretfile.md)** - Customize for your needs
2. **[Validate configuration](validate.md)** - Check for errors
3. **[Test providers](test.md)** - Verify connectivity
4. **[Sync secrets](sync.md)** - Generate and store secrets
