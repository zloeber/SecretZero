# Secretfile Reference

Complete reference documentation for `Secretfile.yml`, the declarative configuration file for SecretZero.

## YAML Schema Hint

Add this as the first line of your manifest so editors can validate and autocomplete from the published schema:

```yaml
# yaml-language-server: $schema=https://github.com/zloeber/SecretZero/raw/refs/heads/main/Secretfile.schema.json
```

## Overview

The Secretfile is a YAML file that defines all aspects of your secret management:

- **Secrets**: What secrets to generate and manage
- **Providers**: Where to store and retrieve secrets
- **Generators**: How to create secret values
- **Targets**: Storage destinations for secrets
- **Templates**: Reusable secret structures
- **Policies**: Compliance and rotation rules
- **Variables**: Dynamic configuration values

## Root Structure

```yaml
# yaml-language-server: $schema=https://github.com/zloeber/SecretZero/raw/refs/heads/main/Secretfile.schema.json
version: '1.0'              # Required: Schema version
variables: {}               # Optional: Variables for interpolation
environments: {}            # Optional: Named environment lanes
target_profiles: {}         # Optional: Reusable target defaults by lane
metadata: {}                # Optional: Project metadata
providers: {}               # Optional: Provider configurations
secrets: []                 # Required: Secret definitions
templates: {}               # Optional: Secret templates
policies: {}                # Optional: Policy definitions
labels: {}                  # Reserved for future use
annotations: {}             # Reserved for future use
```

## Version

**Type**: `string`  
**Required**: Yes  
**Description**: Schema version for the Secretfile

```yaml
version: '1.0'
```

Currently, only version `'1.0'` is supported.

## Variables

**Type**: `dict[string, any]`  
**Required**: No  
**Description**: Key-value pairs used for variable interpolation throughout the configuration

```yaml
variables:
  environment: dev
  region: us-east-1
  aws_account: "123456789012"
  app_name: myapp
```

### Variable Interpolation

Variables can be referenced using Jinja2-style syntax:

```yaml
# Direct reference
region: "{{var.region}}"

# With default value
region: "{{var.region or 'us-east-1'}}"

# In string templates
name: "/{{var.environment}}/{{var.app_name}}/secret"
```

### Environment Variable Fallback

Variables can fall back to environment variables:

```yaml
variables:
  # Use environment variable with fallback
  environment: ${ENVIRONMENT:-dev}
  
  # Must be provided via environment
  api_key: ${API_KEY}
  
  # Optional environment variable
  debug_mode: ${DEBUG:-false}
```

[Learn more about variables →](variables.md)

## Environments and Target Profiles

Use `environments` to declare named lanes with defaults for var files and lockfiles:

```yaml
environments:
  default: dev
  profiles:
    dev:
      var_files: ["env/dev.szvar"]
      lockfile: ".gitsecrets.dev.lock"
      target_profile: aws_dev
    prod:
      var_files: ["env/prod.szvar"]
      lockfile: ".gitsecrets.prod.lock"
      target_profile: aws_prod
```

Use `target_profiles` for lane-specific target overrides and identity policies:

```yaml
target_profiles:
  aws_prod:
    identity_policies: [aws_prod_identity]
    target_overrides:
      secrets_manager:
        name: /prod/default-token
```

Runtime precedence:

1. explicit runtime flags (`--var-file`, `--lockfile`) win
2. selected environment profile defaults apply
3. default lockfile derivation applies when neither is set

## Metadata

**Type**: `object`  
**Required**: No  
**Description**: Project metadata and compliance information

```yaml
metadata:
  project: my-application           # Project name
  owner: platform-team              # Team or person responsible
  environments:                     # Target environments
    - dev
    - staging
    - production
  compliance:                       # Compliance frameworks
    - soc2
    - iso27001
    - hipaa
  description: |
    Complete secret management configuration
    for production deployment.
```

### Metadata Fields

| Field | Type | Description |
|-------|------|-------------|
| `project` | `string` | Project or application name |
| `owner` | `string` | Team or individual responsible for secrets |
| `environments` | `list[string]` | List of target environments |
| `compliance` | `list[string]` | Compliance frameworks to adhere to |
| `description` | `string` | Free-form description of the configuration |

## Providers

**Type**: `dict[string, Provider]`  
**Required**: No  
**Description**: Provider configurations for secret storage and retrieval

### Provider Structure

```yaml
providers:
  provider_name:
    kind: provider_type              # Provider type (aws, azure, vault, etc.)
    auth:                            # Authentication configuration
      kind: auth_method              # Authentication method
      config: {}                     # Auth-specific config
      profiles: {}                   # Named auth profiles
      fallback_generator: static     # Fallback if retrieval fails
    config: {}                       # Provider-specific config
    fallback_generator: static       # Fallback generator
```

### Supported Provider Types

| Provider Kind | Description | Auth Methods |
|--------------|-------------|--------------|
| `aws` | AWS (SSM, Secrets Manager) | `ambient`, `assume_role` |
| `azure` | Azure Key Vault | `ambient`, `managed_identity` |
| `vault` | HashiCorp Vault | `token`, `approle` |
| `kubernetes` | Kubernetes Secrets | `ambient`, `serviceaccount` |
| `github` | GitHub Actions Secrets | `token` |
| `gitlab` | GitLab CI/CD Variables | `token` |
| `jenkins` | Jenkins Credentials | `token` |
| `local` | Local file storage | None required |

### AWS Provider Example

```yaml
providers:
  aws:
    kind: aws
    auth:
      kind: ambient                  # Use default AWS credentials
      config:
        region: us-east-1
        profile: default             # Optional AWS profile
      profiles:
        # Named profiles for different roles
        admin:
          kind: assume_role
          config:
            role_arn: arn:aws:iam::123456789012:role/SecretAdmin
            session_name: secretzero-admin
        readonly:
          kind: assume_role
          config:
            role_arn: arn:aws:iam::123456789012:role/SecretReadOnly
```

### Vault Provider Example

```yaml
providers:
  vault:
    kind: vault
    auth:
      kind: token
      config:
        url: https://vault.example.com
        token: ${VAULT_TOKEN}
        namespace: production        # Optional namespace
      profiles:
        default:
          kind: token
          config:
            token: ${VAULT_TOKEN}
            url: https://vault.example.com
        approle:
          kind: approle
          config:
            role_id: ${VAULT_ROLE_ID}
            secret_id: ${VAULT_SECRET_ID}
            url: https://vault.example.com
```

### Kubernetes Provider Example

```yaml
providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient                  # Use in-cluster config or kubeconfig
      config:
        context: production          # Optional kubectl context
        kubeconfig: ~/.kube/config   # Optional kubeconfig path
```

### Local Provider Example

```yaml
providers:
  local:
    kind: local
    config: {}                       # No auth required
```

## Secrets

**Type**: `list[Secret]`  
**Required**: Yes  
**Description**: List of secret definitions

### Secret Structure

```yaml
secrets:
  - name: secret_name                # Required: Unique identifier
    kind: generator_type             # Required: Generator or template
    vars: {}                         # Optional: Secret-specific variables
    config: {}                       # Optional: Generator configuration
    one_time: false                  # Optional: Generate only once
    rotation_period: "90d"           # Optional: Rotation interval
    targets: []                      # Required: Where to store secret
```

### Secret Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `string` | Yes | Unique identifier for the secret |
| `kind` | `string` | Yes | Generator type or template reference |
| `vars` | `dict` | No | Secret-specific variable overrides |
| `config` | `dict` | No | Generator configuration options |
| `one_time` | `bool` | No | Generate only once (default: `false`) |
| `rotation_period` | `string` | No | Rotation interval (e.g., `90d`, `30d`, `1w`) |
| `targets` | `list` | Yes | Storage destination configurations |

### Generator Kinds

#### random_password

Generate cryptographically secure random passwords:

```yaml
secrets:
  - name: db_password
    kind: random_password
    config:
      length: 32                     # Password length (default: 32)
      upper: true                    # Include uppercase (default: true)
      lower: true                    # Include lowercase (default: true)
      number: true                   # Include numbers (default: true)
      special: true                  # Include special chars (default: true)
      exclude_characters: '"@/\`'    # Characters to exclude
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /app/db-password
```

#### random_string

Generate random alphanumeric strings:

```yaml
secrets:
  - name: api_token
    kind: random_string
    config:
      length: 64                     # String length
      charset: hex                   # Character set: hex, base64, alphanumeric
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
```

#### static

Use a static value with optional validation:

```yaml
secrets:
  - name: api_key
    kind: static
    config:
      default: ${API_KEY}            # Value from environment
      validation: ^[a-zA-Z0-9]{40}$  # Regex validation pattern
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: /app/api-key
```

#### script

Execute an external script to generate the value:

```yaml
secrets:
  - name: custom_secret
    kind: script
    config:
      command: ./generate-secret.sh  # Script to execute
      timeout: 30                    # Timeout in seconds
      env:                           # Environment variables
        SECRET_TYPE: api_key
    targets:
      - provider: vault
        kind: vault_kv
        config:
          path: secret/data/custom
```

#### api

Fetch value from an external API:

```yaml
secrets:
  - name: external_token
    kind: api
    config:
      url: https://api.example.com/token
      method: POST                   # HTTP method (default: GET)
      headers:                       # Optional headers
        Authorization: Bearer ${AUTH_TOKEN}
      body:                          # Optional request body
        grant_type: client_credentials
      json_path: $.access_token      # Extract from JSON response
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: default
          secret_name: external-token
```

### Rotation Period Format

Rotation periods use a simple duration format:

- `d` = days (e.g., `90d` = 90 days)
- `w` = weeks (e.g., `2w` = 2 weeks)
- `m` = months (e.g., `3m` = 3 months)
- `y` = years (e.g., `1y` = 1 year)

```yaml
secrets:
  - name: short_lived
    rotation_period: 7d              # Weekly rotation
    
  - name: standard
    rotation_period: 90d             # Quarterly rotation
    
  - name: long_lived
    rotation_period: 1y              # Annual rotation
```

### One-Time Secrets

Secrets marked as `one_time` are generated once and never rotated:

```yaml
secrets:
  - name: encryption_master_key
    kind: random_password
    one_time: true                   # Generate once, never rotate
    rotation_period: 180d            # Emits warning only
    config:
      length: 64
      special: false
```

## Targets

**Type**: `list[Target]`  
**Required**: Yes (at least one target per secret)  
**Description**: Storage destinations for generated secrets

### Target Structure

```yaml
targets:
  - provider: provider_name          # Required: Provider reference
    kind: target_type                # Required: Storage type
    config: {}                       # Required: Target-specific config
```

### File Target (Local)

Store secrets in local files:

```yaml
targets:
  - provider: local
    kind: file
    config:
      path: .env                     # File path
      format: dotenv                 # Format: dotenv, json, yaml, toml, tfvars
      merge: true                    # Merge with existing file
      key: SECRET_NAME               # Optional key name override
```

**Supported formats**:

- `dotenv`: `KEY=value` format
- `json`: JSON object
- `yaml`: YAML document
- `toml`: TOML document

**Example outputs**:

```bash
# dotenv format (.env)
DB_PASSWORD=mysecretpassword123
API_KEY=abc123def456

# json format (secrets.json)
{
  "db_password": "mysecretpassword123",
  "api_key": "abc123def456"
}

# yaml format (secrets.yml)
db_password: mysecretpassword123
api_key: abc123def456
```

### AWS SSM Parameter Store

```yaml
targets:
  - provider: aws
    kind: ssm_parameter
    config:
      name: /app/secret              # Parameter name (path)
      type: SecureString             # Type: String, SecureString, StringList
      overwrite: true                # Overwrite existing
      description: "Database password"
      tags:                          # Optional tags
        Environment: production
        ManagedBy: secretzero
      kms_key_id: alias/aws/ssm      # Optional KMS key
```

### AWS Secrets Manager

```yaml
targets:
  - provider: aws
    kind: secrets_manager
    config:
      name: /app/secret              # Secret name
      description: "Application secret"
      kms_key_id: alias/aws/secretsmanager
      tags:
        Environment: production
      recovery_window_days: 30       # Deletion recovery window
```

### HashiCorp Vault KV

```yaml
targets:
  - provider: vault
    kind: vault_kv
    config:
      path: secret/data/app/db       # KV path (v2 API)
      key: password                  # Key within secret
      mount: secret                  # Mount point (default: secret)
      metadata:                      # Optional metadata
        max_versions: 10
        cas_required: false
```

### Azure Key Vault

```yaml
targets:
  - provider: azure
    kind: azure_keyvault
    config:
      vault_name: my-keyvault        # Key Vault name
      secret_name: db-password       # Secret name
      content_type: text/plain       # Optional content type
      tags:
        Environment: production
      expiration_date: "2025-12-31"  # Optional expiration
```

### Kubernetes Secret

```yaml
targets:
  - provider: kubernetes
    kind: kubernetes_secret
    config:
      namespace: default             # Kubernetes namespace
      secret_name: app-secret        # Secret name
      data_key: password             # Key within secret data
      secret_type: Opaque            # Secret type (default: Opaque)
      labels:                        # Optional labels
        app: myapp
        env: production
      annotations:                   # Optional annotations
        description: "Database password"
```

**Kubernetes Secret Types**:

- `Opaque`: General-purpose secret (default)
- `kubernetes.io/tls`: TLS certificate and key
- `kubernetes.io/dockerconfigjson`: Docker registry credentials
- `kubernetes.io/basic-auth`: Basic authentication credentials
- `kubernetes.io/ssh-auth`: SSH authentication credentials
- `kubernetes.io/service-account-token`: Service account token

### GitHub Actions Secret

```yaml
targets:
  - provider: github
    kind: github_secret
    config:
      repository: owner/repo         # Repository (org/repo or user/repo)
      secret_name: DB_PASSWORD       # Secret name (uppercase)
      scope: repo                    # Scope: repo, environment, org
      environment: production        # Required if scope=environment
```

### GitLab CI/CD Variable

```yaml
targets:
  - provider: gitlab
    kind: gitlab_variable
    config:
      project: group/project         # Project path
      variable_name: DB_PASSWORD     # Variable name (uppercase)
      protected: true                # Protected variable
      masked: true                   # Masked in logs
      scope: production              # Optional environment scope
```

### Jenkins Credential

```yaml
targets:
  - provider: jenkins
    kind: jenkins_credential
    config:
      credential_id: db-password     # Credential ID
      description: "Database password"
      credential_type: string        # Type: string, username_password
      scope: GLOBAL                  # Scope: GLOBAL, SYSTEM
```

## Templates

**Type**: `dict[string, Template]`  
**Required**: No  
**Description**: Reusable secret structures with multiple fields

### Template Structure

```yaml
templates:
  template_name:
    description: Template description
    fields:
      field_name:
        description: Field description
        generator:
          kind: generator_type
          config: {}
        targets: []                  # Optional field-specific targets
    targets: []                      # Optional template-level targets
```

### Example: Database Credentials

```yaml
templates:
  database_credentials:
    description: Complete database connection credentials
    fields:
      host:
        description: Database hostname
        generator:
          kind: static
          config:
            default: db.example.com
      port:
        description: Database port
        generator:
          kind: static
          config:
            default: "5432"
      database:
        description: Database name
        generator:
          kind: static
          config:
            default: appdb
      username:
        description: Database username
        generator:
          kind: static
          config:
            default: appuser
      password:
        description: Database password
        generator:
          kind: random_password
          config:
            length: 32
            special: true
            exclude_characters: '"@/\`'
    targets:
      # All fields stored together
      - provider: aws
        kind: secrets_manager
        config:
          name: /production/database
      
      # Also as environment variables
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv

# Use the template
secrets:
  - name: production_database
    kind: templates.database_credentials
```

### Example: OAuth Credentials

```yaml
templates:
  oauth_credentials:
    description: OAuth 2.0 client credentials
    fields:
      client_id:
        description: OAuth client ID
        generator:
          kind: static
          config:
            default: ${OAUTH_CLIENT_ID}
            validation: ^[a-zA-Z0-9\-\_]{32}$
      client_secret:
        description: OAuth client secret
        generator:
          kind: random_password
          config:
            length: 64
            special: false
      redirect_uri:
        description: OAuth redirect URI
        generator:
          kind: static
          config:
            default: https://app.example.com/oauth/callback
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: production
          secret_name: oauth-credentials
          secret_type: Opaque

secrets:
  - name: auth_provider
    kind: templates.oauth_credentials
```

### Template Field Targets

Fields can have their own targets that override template-level targets:

```yaml
templates:
  multi_target:
    description: Template with field-specific targets
    fields:
      public_key:
        generator:
          kind: static
          config:
            default: ${PUBLIC_KEY}
        targets:
          # Public key goes to non-sensitive location
          - provider: local
            kind: file
            config:
              path: public.key
      
      private_key:
        generator:
          kind: static
          config:
            default: ${PRIVATE_KEY}
        targets:
          # Private key goes to secure storage
          - provider: aws
            kind: secrets_manager
            config:
              name: /app/private-key
```

## Policies

**Type**: `dict[string, Policy]`  
**Required**: No  
**Description**: Compliance and security policy definitions

### Policy Structure

```yaml
policies:
  policy_name:
    kind: policy_type              # Policy type
    enabled: true                  # Enable/disable policy
    severity: error                # Severity: error, warning, info
    # Policy-specific configuration
```

### Rotation Policy

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
    max_age: 90d                   # Maximum rotation period
    severity: error
    enabled: true
  
  min_rotation_age:
    kind: rotation
    min_age: 7d                    # Minimum rotation period
    severity: warning
    enabled: true
```

### Access Control Policy

Restrict allowed targets:

```yaml
policies:
  production_security:
    kind: access
    allowed_targets:               # Whitelist of allowed targets
      - ssm_parameter
      - secrets_manager
      - vault_kv
      - kubernetes_secret
    denied_targets:                # Blacklist of denied targets
      - file                       # No local files in production
    severity: error
    enabled: true
```

### Complexity Policy

Enforce password complexity:

```yaml
policies:
  password_complexity:
    kind: complexity
    min_length: 16                 # Minimum password length
    require_upper: true            # Must include uppercase
    require_lower: true            # Must include lowercase
    require_number: true           # Must include numbers
    require_special: true          # Must include special chars
    severity: error
    enabled: true
```

## Complete Example

Here's a comprehensive example combining all features:

```yaml
# yaml-language-server: $schema=https://github.com/zloeber/SecretZero/raw/refs/heads/main/Secretfile.schema.json
version: '1.0'

# Dynamic variables
variables:
  environment: ${ENVIRONMENT:-production}
  aws_region: ${AWS_REGION:-us-east-1}
  aws_account: ${AWS_ACCOUNT_ID}
  app_name: myapp

# Project metadata
metadata:
  project: myapp
  owner: platform-team
  environments:
    - production
    - staging
  compliance:
    - soc2
    - iso27001

# Provider configurations
providers:
  aws:
    kind: aws
    auth:
      kind: ambient
      config:
        region: "{{var.aws_region}}"
      profiles:
        admin:
          kind: assume_role
          config:
            role_arn: "arn:aws:iam::{{var.aws_account}}:role/SecretAdmin"
  
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient
      config:
        context: "{{var.environment}}"

# Policies
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

# Templates
templates:
  database_credentials:
    description: Database credentials template
    fields:
      username:
        description: Database username
        generator:
          kind: static
          config:
            default: "{{var.app_name}}_user"
      password:
        description: Database password
        generator:
          kind: random_password
          config:
            length: 32
            special: true
            exclude_characters: '"@/\`'
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: "/{{var.environment}}/{{var.app_name}}/database"

# Secrets
secrets:
  # Using template
  - name: main_database
    kind: templates.database_credentials
    rotation_period: 90d
  
  # Simple password
  - name: redis_password
    kind: random_password
    rotation_period: 90d
    config:
      length: 32
      special: false
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: "/{{var.environment}}/{{var.app_name}}/redis-password"
          type: SecureString
      
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: "{{var.app_name}}"
          secret_name: redis-password
          data_key: password
  
  # API key from environment
  - name: stripe_api_key
    kind: static
    config:
      default: ${STRIPE_API_KEY}
      validation: ^sk_(test|live)_[a-zA-Z0-9]{24,}$
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: "/{{var.environment}}/stripe/api-key"
```

## Next Steps

<div class="grid cards" markdown>

-   :material-variable: **Variables**

    ---

    Learn about variable interpolation and environment variables
    
    [Variable Guide →](variables.md)

-   :material-check-circle: **Validation**

    ---

    Understand configuration validation and error handling
    
    [Validation Reference →](validation.md)

-   :material-book-open-variant: **Examples**

    ---

    Explore real-world Secretfile examples
    
    [View Examples →](../../examples/index.md)

-   :material-console: **CLI Commands**

    ---

    Learn how to use the CLI with your Secretfile
    
    [CLI Reference →](../cli/index.md)

</div>
