# Configuration Overview

SecretZero uses a declarative configuration approach where all your secrets, providers, and policies are defined in a `Secretfile.yml`. This page provides an overview of configuration concepts and structure.

For contract-level automation and CI validation, treat `Secretfile.schema.json` as authoritative.

## Configuration Files

### Secretfile.yml

The primary configuration file that defines:

- Secret definitions and generation rules
- Provider configurations and authentication
- Target storage locations
- Templates for complex secrets
- Rotation policies and compliance rules
- Variables for dynamic configuration

**Location**: Project root (default: `./Secretfile.yml`)

```yaml
version: '1.0'

variables:
  environment: production

providers:
  aws:
    kind: aws
    auth:
      kind: ambient

secrets:
  - name: database_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /app/db-password
```

[Complete Secretfile Reference →](secretfile.md)

### Lockfile

The lockfile (`.gitsecrets.lock`) is automatically generated and tracks:

- Generated secret hashes (SHA-256)
- Creation and update timestamps
- Rotation history and counts
- Secret metadata

**Location**: Project root (default: `./.gitsecrets.lock`)

!!! warning "Version Control"
    The lockfile contains hashes, not actual secret values. Default recommendation is to commit lockfiles, using one lockfile per environment lane for GitOps/IaC workflows. See [Lockfile Version Control Policy](../lockfile-version-control-policy.md).

**Example lockfile structure**:

```yaml
version: '1.0'
secrets:
  database_password:
    hash: 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08
    created_at: '2024-01-15T10:30:00Z'
    updated_at: '2024-01-15T10:30:00Z'
    last_rotated: '2024-01-15T10:30:00Z'
    rotation_count: 0
    metadata:
      kind: random_password
      length: 32
```

## Configuration Hierarchy

SecretZero resolves configuration in the following order (highest to lowest priority):

1. **Environment Variables** - Runtime environment variables
2. **Command-line Arguments** - CLI flags and options
3. **Secretfile Variables** - Variables defined in `variables` section
4. **Provider Defaults** - Default provider configurations
5. **Built-in Defaults** - SecretZero's default values

### Example

```yaml
variables:
  # Can be overridden by environment variable: AWS_REGION
  aws_region: us-east-1
  
  # Use environment variable with fallback
  environment: ${ENVIRONMENT:-dev}

providers:
  aws:
    config:
      # Variable interpolation with fallback
      region: "{{var.aws_region or 'us-west-2'}}"
```

## Core Concepts

### Providers

Providers are the backends for storing and retrieving secrets. They handle:

- Authentication and authorization
- Secret storage and retrieval
- Provider-specific operations

**Supported provider types**:

- **Cloud**: `aws`, `azure`, `vault`
- **CI/CD**: `github`, `gitlab`, `jenkins` (GitLab supports `gitlab_variable`, `gitlab_group_variable`, and `gitlab_project_token` generator with `project: auto`)
- **Container**: `kubernetes`
- **Local**: `local` (file-based)

Each provider can have multiple named configurations:

```yaml
providers:
  aws-prod:
    kind: aws
    auth:
      kind: assume_role
      config:
        role_arn: arn:aws:iam::123456789012:role/Prod
  
  aws-dev:
    kind: aws
    auth:
      kind: ambient
      config:
        profile: dev
```

### Secrets

Secrets are the core entities managed by SecretZero. Each secret definition includes:

- **Name**: Unique identifier for the secret
- **Kind**: Generator type or template reference
- **Source** (optional): Non-human value source resolved before generation
- **Config**: Generator-specific configuration
- **Targets**: Where to store the generated value
- **Rotation Policy**: When to regenerate the secret
- **Process tags** (optional): Short labels (for example `auth_flow`) used by GitNexus/MetaGit overlays to relate secrets to execution flows

```yaml
secrets:
  - name: api_key
    kind: random_password
    rotation_period: 90d
    process_tags:
      - auth_flow
    one_time: false
    config:
      length: 64
      special: false
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: /prod/api-key
```

### Secret Sources (`source`)

Use `source` to resolve a value from non-human inputs before generator execution.

```yaml
secrets:
  - name: app_api_token
    kind: static
    source:
      kind: secret_ref
      required: true
      config:
        secret: shared_seed_token
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: /prod/app/api-token
```

Supported kinds:

- `file`: `config.path` required; optional `format`, `key`, `encoding`
- `env`: `config.name` required; optional `trim`
- `secret_ref`: `config.secret` required; optional `field`
- `provider_read`: `config.provider`, `config.kind`, and object `config.read` required; optional `field`, `profile`, `method`

Example (`provider_read` from AWS IAM user, writing JSON payload):

```yaml
secrets:
  - name: aws_iam_user_credentials
    kind: static
    source:
      kind: provider_read
      config:
        provider: aws
        kind: iam_user
        method: retrieve_iam_user_credentials
        read:
          name: svc-secretzero-bot
          replace_oldest: true
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: /prod/iam/svc-secretzero-bot
          format: json
```

`secret_ref` behavior:

- references a previously resolved non-template secret in the same sync run
- self-reference is rejected
- if `required: false`, unresolved sources fall back to normal generator flow

### Templates

Templates define reusable secret structures with multiple fields:

```yaml
templates:
  database_credentials:
    description: Complete database connection credentials
    fields:
      host:
        generator:
          kind: static
          config:
            default: db.example.com
      port:
        generator:
          kind: static
          config:
            default: "5432"
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
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: json

# Use the template
secrets:
  - name: prod_database
    kind: templates.database_credentials
```

### Targets

Targets specify where generated secrets should be stored. A single secret can have multiple targets:

```yaml
secrets:
  - name: shared_secret
    kind: random_password
    config:
      length: 32
    targets:
      # Store in AWS
      - provider: aws
        kind: ssm_parameter
        config:
          name: /app/secret
      
      # Also store locally
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv

      # Or push to Terraform var file (HCL assignments)
      - provider: local
        kind: file
        config:
          path: terraform/terraform.tfvars
          format: tfvars
          merge: true
      
      # And in Kubernetes
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: production
          secret_name: app-secret
```

### Variables

Variables enable dynamic configuration and reusability:

```yaml
variables:
  environment: production
  region: us-east-1
  app_name: myapp

secrets:
  - name: config_secret
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          # Variable interpolation using Jinja2 syntax
          name: /{{var.environment}}/{{var.app_name}}/secret
          tags:
            Environment: "{{var.environment}}"
            Region: "{{var.region}}"
```

[Learn more about variables →](variables.md)

### Policies

Policies enforce compliance and security requirements:

```yaml
policies:
  rotation_required:
    kind: rotation
    require_rotation_period: true
    severity: warning
    enabled: true
  
  max_rotation_age:
    kind: rotation
    max_age: 90d
    severity: error
    enabled: true
  
  production_security:
    kind: access
    allowed_targets:
      - ssm_parameter
      - secrets_manager
      - vault_kv
    severity: error
    enabled: true
```

**Provider identity** (`kind: provider_identity`) restricts sync to matching authenticated principals (AWS account, Vault policies, etc.). See [Provider identity policies →](provider-identity-policies.md).

## Configuration Validation

SecretZero validates your configuration before execution:

### Schema Validation

Validates structure and required fields:

```bash
secretzero validate
```

Output:
```
Validating: Secretfile.yml
✓ Configuration is valid

Configuration Summary:
  Version: 1.0
  Variables: 3
  Providers: 2
  Secrets: 5
  Templates: 1
```

### Provider Testing

Tests provider connectivity and authentication:

```bash
secretzero test
```

Output:
```
Testing Provider Connectivity:

  • aws: ✓ Connected to AWS (us-east-1)
  • vault: ✓ Connected to Vault (http://localhost:8200)
  • local: ✓ Local provider (always available)

All provider tests passed!
```

### Policy Checking

Validates compliance with defined policies:

```bash
secretzero policy
```

Output:
```
Checking policy compliance...

Warnings:
  ⚠ api_token: No rotation_period defined
    → Add rotation_period to enable automatic rotation

Summary:
  Errors: 0
  Warnings: 1
  Info: 0
```

[Learn more about validation →](validation.md)

## Environment-Specific Configuration

### Using Variables

Define environment-specific values:

```yaml
variables:
  environment: ${ENVIRONMENT:-dev}
  aws_account: ${AWS_ACCOUNT_ID}
  
secrets:
  - name: app_secret
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /{{var.environment}}/app/secret
```

### Multiple Secretfiles

Manage different environments with separate files:

```bash
# Development
secretzero sync -f Secretfile.dev.yml

# Production
secretzero sync -f Secretfile.prod.yml
```

### Variable Files

Load variables from external sources:

```yaml
# Secretfile.yml
version: '1.0'

variables:
  # Load from environment
  environment: ${ENVIRONMENT}
  region: ${AWS_REGION}
  
  # Or provide defaults
  app_name: ${APP_NAME:-myapp}
```

## Configuration Best Practices

### 1. Use Version Control

Commit `Secretfile.yml` to track changes:

```bash
git add Secretfile.yml
git commit -m "Add database credentials configuration"
```

### 2. Separate Environments

Use variables or separate files for different environments:

```yaml
variables:
  environment: ${ENVIRONMENT:-dev}

secrets:
  - name: database_url
    kind: static
    config:
      default: ${DATABASE_URL}
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /{{var.environment}}/database-url
```

### 3. Document Your Secrets

Use metadata and descriptions:

```yaml
metadata:
  project: myapp
  owner: platform-team
  description: Production secrets for MyApp

templates:
  api_credentials:
    description: External API authentication credentials
    fields:
      api_key:
        description: API key from provider dashboard
        generator:
          kind: static
```

### 4. Implement Rotation Policies

Define rotation periods for all secrets:

```yaml
secrets:
  - name: database_password
    kind: random_password
    rotation_period: 90d  # SOC2 compliance
    config:
      length: 32
```

### 5. Use Templates for Complex Secrets

Group related secret fields:

```yaml
templates:
  oauth_credentials:
    description: OAuth client credentials
    fields:
      client_id:
        generator:
          kind: static
      client_secret:
        generator:
          kind: random_password
          config:
            length: 64
      redirect_uri:
        generator:
          kind: static
```

### 6. Validate Before Syncing

Always validate configuration first:

```bash
# Validate
secretzero validate

# Test providers
secretzero test

# Check policies
secretzero policy

# Dry run
secretzero sync --dry-run

# Execute
secretzero sync
```

## Next Steps

<div class="grid cards" markdown>

-   :material-file-document: **Secretfile Reference**

    ---

    Complete specification of all Secretfile.yml fields and options
    
    [Read Reference →](secretfile.md)

-   :material-variable: **Variables**

    ---

    Learn about variable interpolation and environment variables
    
    [Learn About Variables →](variables.md)

-   :material-check-circle: **Validation**

    ---

    Understand schema validation and error handling
    
    [Validation Guide →](validation.md)

-   :material-console: **CLI Commands**

    ---

    Learn how to use SecretZero commands
    
    [CLI Reference →](../cli/index.md)

</div>
