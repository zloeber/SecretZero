# Variables

SecretZero supports dynamic configuration through variables, allowing you to create flexible, reusable secret configurations that work across multiple environments.

## Overview

Variables in SecretZero provide:

- **Dynamic configuration** - Change values without modifying the Secretfile
- **Environment-specific settings** - Different values for dev/staging/prod
- **DRY principle** - Define once, use everywhere
- **Environment variable integration** - Seamless integration with runtime environment
- **Jinja2 templating** - Powerful string interpolation

## Defining Variables

Variables are defined in the `variables` section of your Secretfile:

```yaml
version: '1.0'

variables:
  environment: production
  region: us-east-1
  app_name: myapp
  aws_account: "123456789012"
```

## Variable Types

### Static Variables

Simple key-value pairs defined in the Secretfile:

```yaml
variables:
  environment: production
  region: us-east-1
  app_name: myapp
```

### Environment Variables

Variables can pull values from environment variables using `${}` syntax:

```yaml
variables:
  # Required environment variable
  api_key: ${API_KEY}
  
  # With default fallback
  environment: ${ENVIRONMENT:-dev}
  
  # Optional with empty default
  debug_mode: ${DEBUG:-}
```

### Computed Variables

Variables can reference other variables:

```yaml
variables:
  environment: ${ENVIRONMENT:-dev}
  region: us-east-1
  app_name: myapp
  
  # Computed from other variables
  deployment_name: "{{var.app_name}}-{{var.environment}}"
  aws_prefix: "/{{var.environment}}/{{var.app_name}}"
```

## Variable Interpolation

### Jinja2 Syntax

SecretZero uses Jinja2-style variable interpolation with the `{{var.}}` prefix:

```yaml
secrets:
  - name: database_password
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          # Simple interpolation
          name: "/{{var.environment}}/db-password"
```

### With Default Values

Provide fallback values using the `or` operator:

```yaml
secrets:
  - name: api_secret
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          # Use variable or default to us-east-1
          region: "{{var.region or 'us-east-1'}}"
```

### Multiple Variables

Combine multiple variables in a single value:

```yaml
variables:
  environment: production
  app_name: myapp
  component: api

secrets:
  - name: service_config
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          # Combine multiple variables
          name: "/{{var.environment}}/{{var.app_name}}/{{var.component}}/secret"
          # Results in: /production/myapp/api/secret
```

### Conditional Logic

Use Jinja2 conditional expressions:

```yaml
variables:
  environment: production

secrets:
  - name: database_url
    kind: static
    config:
      # Different values based on environment
      default: "{{ 'prod-db.example.com' if var.environment == 'production' else 'dev-db.example.com' }}"
```

## Using Environment Variables

### Direct Environment Variable Access

Access environment variables directly in the Secretfile:

```yaml
variables:
  # Must exist in environment
  api_key: ${API_KEY}
  
  # With default value
  log_level: ${LOG_LEVEL:-info}
  
  # Numeric value
  max_connections: ${MAX_CONNECTIONS:-100}
  
  # Boolean-like value
  debug_enabled: ${DEBUG:-false}
```

### Environment Variable Priority

SecretZero checks environment variables in this order:

1. **Secret-specific environment variables** (uppercase secret name)
2. **General environment variables** (as defined in variables section)
3. **Default values** (from configuration)

```yaml
variables:
  environment: ${ENVIRONMENT:-dev}

secrets:
  # Checks environment variables in this order:
  # 1. DATABASE_PASSWORD (secret name in uppercase)
  # 2. Generator configuration
  # 3. Default generator behavior
  - name: database_password
    kind: random_password
    config:
      length: 32
```

### Setting Environment Variables

**Bash/Zsh:**

```bash
export ENVIRONMENT=production
export AWS_REGION=us-east-1
export API_KEY=sk_live_abc123

secretzero sync
```

**PowerShell:**

```powershell
$env:ENVIRONMENT = "production"
$env:AWS_REGION = "us-east-1"
$env:API_KEY = "sk_live_abc123"

secretzero sync
```

**.env file:**

```bash
# .env
ENVIRONMENT=production
AWS_REGION=us-east-1
API_KEY=sk_live_abc123
```

Load with:

```bash
export $(cat .env | xargs)
secretzero sync
```

## Common Patterns

### Multi-Environment Configuration

Use environment variable to switch between environments:

```yaml
variables:
  environment: ${ENVIRONMENT:-dev}
  
  # Environment-specific AWS accounts
  aws_account: "{{ '111111111111' if var.environment == 'production' else '222222222222' }}"
  
  # Environment-specific regions
  aws_region: "{{ 'us-east-1' if var.environment == 'production' else 'us-west-2' }}"

secrets:
  - name: app_secret
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: "/{{var.environment}}/app/secret"
          tags:
            Environment: "{{var.environment}}"
```

**Usage:**

```bash
# Development
ENVIRONMENT=dev secretzero sync

# Production
ENVIRONMENT=production secretzero sync
```

### Resource Naming Convention

Establish consistent naming patterns:

```yaml
variables:
  environment: ${ENVIRONMENT:-dev}
  app_name: myapp
  team: platform
  
  # Standardized prefix
  secret_prefix: "/{{var.team}}/{{var.app_name}}/{{var.environment}}"

secrets:
  - name: database_password
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          # Results in: /platform/myapp/dev/database-password
          name: "{{var.secret_prefix}}/database-password"
  
  - name: api_key
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          # Results in: /platform/myapp/dev/api-key
          name: "{{var.secret_prefix}}/api-key"
```

### Dynamic Tagging

Apply consistent tags using variables:

```yaml
variables:
  environment: ${ENVIRONMENT:-dev}
  project: myapp
  owner: platform-team
  cost_center: engineering

secrets:
  - name: app_secret
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /app/secret
          tags:
            Environment: "{{var.environment}}"
            Project: "{{var.project}}"
            Owner: "{{var.owner}}"
            CostCenter: "{{var.cost_center}}"
            ManagedBy: secretzero
```

### Provider Configuration

Configure providers dynamically:

```yaml
variables:
  aws_region: ${AWS_REGION:-us-east-1}
  aws_profile: ${AWS_PROFILE:-default}
  vault_url: ${VAULT_ADDR:-http://localhost:8200}
  k8s_context: ${KUBE_CONTEXT:-default}

providers:
  aws:
    kind: aws
    auth:
      kind: ambient
      config:
        region: "{{var.aws_region}}"
        profile: "{{var.aws_profile}}"
  
  vault:
    kind: vault
    auth:
      kind: token
      config:
        url: "{{var.vault_url}}"
        token: ${VAULT_TOKEN}
  
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient
      config:
        context: "{{var.k8s_context}}"
```

### Secret Templates with Variables

Use variables in template field defaults:

```yaml
variables:
  db_host: ${DB_HOST:-localhost}
  db_port: ${DB_PORT:-5432}
  db_name: ${DB_NAME:-appdb}
  db_user: ${DB_USER:-appuser}

templates:
  database_config:
    description: Database configuration
    fields:
      host:
        generator:
          kind: static
          config:
            default: "{{var.db_host}}"
      port:
        generator:
          kind: static
          config:
            default: "{{var.db_port}}"
      database:
        generator:
          kind: static
          config:
            default: "{{var.db_name}}"
      username:
        generator:
          kind: static
          config:
            default: "{{var.db_user}}"
      password:
        generator:
          kind: random_password
          config:
            length: 32

secrets:
  - name: app_database
    kind: templates.database_config
```

## Advanced Techniques

### Variable Validation

Validate variable values using conditions:

```yaml
variables:
  environment: ${ENVIRONMENT:-dev}

secrets:
  - name: production_secret
    kind: random_password
    config:
      # Only generate if environment is production
      enabled: "{{ var.environment == 'production' }}"
```

### Nested Variable References

Build complex values from multiple variables:

```yaml
variables:
  project: myapp
  environment: production
  region: us-east-1
  
  # Nested references
  base_path: "/{{var.project}}/{{var.environment}}"
  full_path: "{{var.base_path}}/{{var.region}}"

secrets:
  - name: app_secret
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          # Uses full_path which references base_path
          name: "{{var.full_path}}/secret"
```

### List and Dictionary Variables

Use structured data in variables:

```yaml
variables:
  environments:
    - dev
    - staging
    - production
  
  regions:
    primary: us-east-1
    secondary: us-west-2

secrets:
  - name: multi_region_secret
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          # Access dictionary values
          region: "{{var.regions.primary}}"
```

### Per-Secret Variables

Override variables for specific secrets:

```yaml
variables:
  environment: production
  region: us-east-1

secrets:
  - name: special_secret
    # Override variables for this secret only
    vars:
      environment: staging
      region: us-west-2
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          # Uses overridden values
          name: "/{{var.environment}}/secret"
```

## Environment-Specific Files

### Separate Secretfiles

Maintain separate Secretfiles for each environment:

```bash
# File structure
Secretfile.base.yml      # Common configuration
Secretfile.dev.yml       # Development overrides
Secretfile.staging.yml   # Staging overrides
Secretfile.prod.yml      # Production overrides
```

**Base configuration:**

```yaml
# Secretfile.base.yml
version: '1.0'

variables:
  app_name: myapp

secrets:
  - name: database_password
    kind: random_password
    config:
      length: 32
```

**Production configuration:**

```yaml
# Secretfile.prod.yml
version: '1.0'

variables:
  app_name: myapp
  environment: production
  aws_region: us-east-1

providers:
  aws:
    kind: aws
    auth:
      kind: assume_role
      config:
        role_arn: arn:aws:iam::111111111111:role/ProdSecrets

secrets:
  - name: database_password
    kind: random_password
    rotation_period: 90d
    config:
      length: 32
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: /production/db-password
```

**Usage:**

```bash
# Development
secretzero sync -f Secretfile.dev.yml

# Production
secretzero sync -f Secretfile.prod.yml
```

### Variable Files

Load variables from external files:

```yaml
# variables.yml
environment: production
aws_region: us-east-1
app_name: myapp
```

```yaml
# Secretfile.yml
version: '1.0'

variables:
  # Load from environment, which can be set from external file
  environment: ${ENVIRONMENT}
  aws_region: ${AWS_REGION}
  app_name: ${APP_NAME}
```

**Load and run:**

```bash
export $(cat variables.yml | grep -v '^#' | xargs)
secretzero sync
```

## Best Practices

### 1. Use Descriptive Variable Names

```yaml
# Good
variables:
  database_host: db.example.com
  api_endpoint_url: https://api.example.com
  max_connection_pool_size: 20

# Avoid
variables:
  db: db.example.com
  url: https://api.example.com
  max: 20
```

### 2. Provide Sensible Defaults

```yaml
variables:
  # Always provide defaults for optional settings
  log_level: ${LOG_LEVEL:-info}
  timeout_seconds: ${TIMEOUT:-30}
  retry_attempts: ${RETRY_ATTEMPTS:-3}
  
  # Don't provide defaults for required settings
  api_key: ${API_KEY}
  database_password: ${DATABASE_PASSWORD}
```

### 3. Document Variable Requirements

```yaml
# Secretfile.yml
version: '1.0'

# Required environment variables:
# - ENVIRONMENT: deployment environment (dev, staging, production)
# - AWS_REGION: AWS region for resources
# - API_KEY: external service API key
#
# Optional environment variables:
# - LOG_LEVEL: logging level (default: info)
# - DEBUG: enable debug mode (default: false)

variables:
  environment: ${ENVIRONMENT}
  aws_region: ${AWS_REGION}
  api_key: ${API_KEY}
  log_level: ${LOG_LEVEL:-info}
  debug: ${DEBUG:-false}
```

### 4. Group Related Variables

```yaml
variables:
  # Environment
  environment: ${ENVIRONMENT:-dev}
  
  # AWS Configuration
  aws_region: ${AWS_REGION:-us-east-1}
  aws_account: ${AWS_ACCOUNT_ID}
  aws_profile: ${AWS_PROFILE:-default}
  
  # Application
  app_name: myapp
  app_version: ${APP_VERSION:-1.0.0}
  
  # Database
  db_host: ${DB_HOST:-localhost}
  db_port: ${DB_PORT:-5432}
  db_name: ${DB_NAME:-appdb}
```

### 5. Use Variables for All Environment-Specific Values

```yaml
variables:
  environment: ${ENVIRONMENT:-dev}
  region: ${AWS_REGION:-us-east-1}

secrets:
  - name: app_config
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          # Don't hardcode environment-specific values
          name: "/{{var.environment}}/config"
          tags:
            Environment: "{{var.environment}}"
            Region: "{{var.region}}"
```

### 6. Validate Critical Variables

Ensure critical variables are set before execution:

```bash
#!/bin/bash
# validate-env.sh

required_vars=(
  "ENVIRONMENT"
  "AWS_REGION"
  "API_KEY"
)

for var in "${required_vars[@]}"; do
  if [ -z "${!var}" ]; then
    echo "Error: Required variable $var is not set"
    exit 1
  fi
done

echo "All required variables are set"
secretzero sync
```

## Troubleshooting

### Variable Not Defined Error

**Error:**

```
Error: Variable 'environment' is not defined
```

**Solution:**

Define the variable or set it in environment:

```bash
export ENVIRONMENT=production
secretzero sync
```

### Environment Variable Not Expanding

**Issue:** `${VAR}` appearing literally in output

**Cause:** Environment variable syntax vs variable interpolation

```yaml
# Wrong - This is for environment variable substitution
variables:
  key: ${API_KEY}  # Processed by shell/system

# Right - This is for SecretZero variable interpolation
secrets:
  - name: test
    config:
      # Use variable interpolation for SecretZero variables
      value: "{{var.key}}"
```

### Circular Variable Reference

**Error:**

```
Error: Circular variable reference detected: var.a -> var.b -> var.a
```

**Solution:**

Avoid circular dependencies:

```yaml
# Wrong
variables:
  a: "{{var.b}}"
  b: "{{var.a}}"

# Right
variables:
  base: myapp
  name: "{{var.base}}-service"
```

## Next Steps

<div class="grid cards" markdown>

-   :material-file-document: **Secretfile Reference**

    ---

    Complete specification of Secretfile.yml
    
    [Read Reference →](secretfile.md)

-   :material-check-circle: **Validation**

    ---

    Learn about configuration validation
    
    [Validation Guide →](validation.md)

-   :material-console: **CLI Commands**

    ---

    Use variables with CLI commands
    
    [CLI Reference →](../cli/index.md)

-   :material-book-open-variant: **Examples**

    ---

    See variables in real-world examples
    
    [View Examples →](../../examples/index.md)

</div>
