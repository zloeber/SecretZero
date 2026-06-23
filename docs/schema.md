# Secretfile Schema Documentation

This document describes the complete schema for `Secretfile.yml`, the configuration file that defines secrets, providers, and targets for SecretZero.

## Raw JSON Schema

Download or reference the published JSON Schema directly:

- [`Secretfile.schema.json`](../Secretfile.schema.json) at the repository root (committed; refresh with `task schema:update`)
- MkDocs deploy copy under `docs/` (gitignored; generated via `secretzero schema export --output docs/Secretfile.schema.json` during `task docs:build`)
- Published site: [secret0.com/Secretfile.schema.json](https://secret0.com/Secretfile.schema.json)

Runtime validator and typing cleanups may not change schema field shape, but the generated
schema remains the source-of-truth contract for machine consumers.

## YAML Language Server Directive

For `Secretfile.yml` authoring, include this first line so YAML tooling uses the latest published schema:

```yaml
# yaml-language-server: $schema=https://github.com/zloeber/SecretZero/raw/refs/heads/main/Secretfile.schema.json
```

## Root Structure

```yaml
# yaml-language-server: $schema=https://github.com/zloeber/SecretZero/raw/refs/heads/main/Secretfile.schema.json
version: '1.0'              # Required: Schema version
variables: {}               # Optional: Variables for interpolation
metadata: {}                # Optional: Project metadata
providers: {}               # Optional: Provider configurations
secrets: []                 # Required: Secret definitions
templates: {}               # Optional: Secret templates
policies: {}                # Reserved for future use
labels: {}                  # Reserved for future use
annotations: {}             # Reserved for future use
```

## Version

**Type**: String  
**Required**: Yes  
**Description**: Schema version for the Secretfile

```yaml
version: '1.0'
```

## Variables

**Type**: Dictionary  
**Required**: No  
**Description**: Key-value pairs used for variable interpolation throughout the configuration

```yaml
variables:
  environment: dev
  region: us-east-1
  aws_account: "123456789012"
```

### Variable Interpolation

Variables can be referenced using Jinja2-style syntax:

```yaml
# Direct reference
region: "{{var.region}}"

# With default value
region: "{{var.region or 'us-east-1'}}"
```

## Metadata

**Type**: Object  
**Required**: No  
**Description**: Metadata about the project and its compliance requirements

```yaml
metadata:
  project: my-app              # Project name
  owner: platform-team         # Team or person responsible
  environments:                # List of environments
    - dev
    - staging
    - prod
  compliance:                  # Compliance frameworks
    - soc2
    - iso27001
```

### Metadata Fields

| Field | Type | Description |
|-------|------|-------------|
| `project` | string | Project or application name |
| `owner` | string | Team or individual responsible |
| `environments` | list[string] | List of target environments |
| `compliance` | list[string] | Compliance frameworks (soc2, iso27001, etc.) |

## Providers

**Type**: Dictionary  
**Required**: No  
**Description**: Configuration for secret providers (sources and storage backends)

```yaml
providers:
  aws:
    kind: aws                  # Provider type
    auth:
      kind: ambient            # Authentication method
      config:
        region: us-east-1
      profiles:                # Named auth profiles
        default:
          kind: ambient
        admin:
          kind: assume_role
          config:
            role_arn: arn:aws:iam::123:role/Admin
    config: {}                 # Provider-specific config
    fallback_generator: static # Fallback if provider unavailable
```

### Provider Fields

| Field | Type | Description |
|-------|------|-------------|
| `kind` | string | Provider type (aws, azure, vault, local, etc.) |
| `auth` | object | Authentication configuration |
| `config` | dict | Provider-specific configuration |
| `fallback_generator` | string | Generator to use if provider unavailable |

### Authentication Kinds

- `ambient`: Use environment credentials (IAM roles, managed identities)
- `token`: Use explicit token or API key
- `assume_role`: Assume a specific role
- `static`: Static credentials

## Secrets

**Type**: List  
**Required**: Yes (can be empty)  
**Description**: List of secret definitions

```yaml
secrets:
  - name: db_password          # Unique secret name
    kind: random_password      # Secret type or template reference
    vars: {}                   # Variables for this secret
    config:                    # Generator configuration
      length: 32
      special: true
    one_time: false            # Generate once and never rotate
    rotation_period: 90d       # Rotation period
    process_tags:               # Optional flow labels for graph tooling
      - auth_flow
    targets:                   # Where to store this secret
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
```

### Secret Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Unique identifier for the secret |
| `kind` | string | Generator type or template reference (e.g., `templates.my_template`) |
| `vars` | dict | Variables specific to this secret |
| `source` | object/null | Optional non-human source resolved before generator flow |
| `config` | dict | Configuration for the generator |
| `one_time` | boolean | If true, generate once and don't rotate |
| `rotation_period` | string | Rotation period (e.g., 90d, 6m, 1y) |
| `targets` | list | List of storage targets |
| `process_tags` | list of strings | Optional labels tying secrets to execution flows (e.g., `auth_flow`, `payment_gateway`) for GitNexus/MetaGit tooling |

### Secret Source (`source`)

`source` allows a secret value to be resolved from a non-human location before generation.

```yaml
secrets:
  - name: copied_token
    kind: static
    source:
      kind: provider_read
      required: true
      config:
        provider: aws
        kind: secrets_manager
        read:
          name: /prod/shared/token
```

AWS IAM user credential source example:

```yaml
secrets:
  - name: aws_iam_user_credentials
    kind: static
    source:
      kind: provider_read
      required: true
      config:
        provider: aws
        kind: iam_user
        method: retrieve_iam_user_credentials
        read:
          name: svc-secretzero-bot
          replace_oldest: true
```

#### Source fields

| Field | Type | Description |
|-------|------|-------------|
| `kind` | string | One of `file`, `env`, `secret_ref`, `provider_read` |
| `required` | boolean | If true (default), source resolution failure blocks the secret |
| `config` | dict | Source-kind-specific configuration |

#### `secret_ref` specifics

```yaml
source:
  kind: secret_ref
  config:
    secret: upstream_secret_name
    field: nested.optional.path
```

- `config.secret` is required and must be non-empty
- references are resolved in manifest order (the referenced secret must be resolved earlier)
- self-reference is invalid
- if `required: false`, unresolved source falls back to generator flow

### Generator Kinds

- `random_password`: Generate random passwords
- `random_string`: Generate random alphanumeric strings
- `static`: Static value with optional validation
- `script`: Execute external script
- `api`: Fetch from external API
- `gitlab_project_token`: Create a scoped GitLab project access token (requires bootstrap PAT)

## Templates

**Type**: Dictionary  
**Required**: No  
**Description**: Reusable secret templates with multiple fields

```yaml
templates:
  database_credentials:
    description: "Database connection credentials"
    fields:
      username:
        description: "Database username"
        generator:
          kind: static
          config:
            default: dbuser
        targets:
          - provider: aws
            kind: ssm_parameter
            config:
              name: /db/username
      password:
        description: "Database password"
        generator:
          kind: random_password
          config:
            length: 32
        targets:
          - provider: aws
            kind: ssm_parameter
            config:
              name: /db/password
              type: SecureString
    targets:                   # Template-level targets (apply to all fields)
      - provider: local
        kind: file
        config:
          path: .env.db
          format: dotenv
```

### Template Fields

| Field | Type | Description |
|-------|------|-------------|
| `description` | string | Template description |
| `fields` | dict | Dictionary of field definitions |
| `targets` | list | Template-level targets (apply to all fields unless overridden) |

### Template Field Structure

| Field | Type | Description |
|-------|------|-------------|
| `description` | string | Field description |
| `generator` | object | Generator configuration |
| `targets` | list | Field-specific targets (override template-level) |

## Targets

**Type**: Object  
**Required**: At least one target per secret  
**Description**: Defines where and how secrets are stored

```yaml
targets:
  - provider: aws             # Provider name from providers section
    kind: ssm_parameter       # Target type
    config:                   # Target-specific configuration
      name: /app/secret
      type: SecureString
      overwrite: true
```

### Target Kinds

| Kind | Description | Provider |
|------|-------------|----------|
| `file` | Local file | local |
| `ssm_parameter` | AWS SSM Parameter Store | aws |
| `secrets_manager` | AWS Secrets Manager | aws |
| `vault_kv` | HashiCorp Vault KV | vault |
| `azure_keyvault` | Azure Key Vault | azure |
| `kubernetes_secret` | Kubernetes Secret | kubernetes |
| `github_secret` | GitHub Actions Secret | github |
| `gitlab_variable` | GitLab CI/CD project variable | gitlab |
| `gitlab_group_variable` | GitLab CI/CD group variable | gitlab |

### File Target Configuration

```yaml
targets:
  - provider: local
    kind: file
    config:
      path: .env              # File path
      format: dotenv          # Format: dotenv, json, yaml, toml, tfvars
      merge: true             # Merge with existing content
```

### AWS SSM Parameter Configuration

```yaml
targets:
  - provider: aws
    kind: ssm_parameter
    config:
      name: /app/secret       # Parameter name
      type: SecureString      # Type: String, SecureString, StringList
      overwrite: true         # Overwrite if exists
```

### AWS Secrets Manager Configuration

```yaml
targets:
  - provider: aws
    kind: secrets_manager
    config:
      name: app/secret        # Secret name
      description: "App secret"
      overwrite: true
```

## Generator Configuration

### Random Password

```yaml
generator:
  kind: random_password
  config:
    length: 32                     # Password length
    upper: true                    # Include uppercase
    lower: true                    # Include lowercase
    number: true                   # Include numbers
    special: true                  # Include special characters
    exclude_characters: '"@/\`'    # Characters to exclude
```

### Static Value

```yaml
generator:
  kind: static
  config:
    default: default-value         # Default value
    validation: ^[a-zA-Z0-9]{40}$  # Regex validation pattern
    rotation_period: 90d           # Rotation period
```

### Script Generator

```yaml
generator:
  kind: script
  config:
    command: /path/to/script.sh    # Script to execute
    args: [arg1, arg2]             # Script arguments
    timeout: 30                    # Timeout in seconds
```

## Environment Variable Fallback

SecretZero automatically checks for environment variables before using generators:

For a secret named `db_password` with template `database_credentials` and field `username`:
- Checks: `DB_PASSWORD_USERNAME`
- If found, uses environment variable value
- If not found, uses configured generator

## Complete Example

```yaml
# yaml-language-server: $schema=https://github.com/zloeber/SecretZero/raw/refs/heads/main/Secretfile.schema.json
version: '1.0'

variables:
  environment: production
  region: us-east-1

metadata:
  project: my-app
  owner: platform-team
  environments: [dev, prod]
  compliance: [soc2]

providers:
  aws:
    kind: aws
    auth:
      kind: ambient
      config:
        region: "{{var.region}}"
  local:
    kind: local

secrets:
  - name: api_key
    kind: static
    config:
      validation: ^[a-zA-Z0-9]{40}$
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /app/api-key
          type: SecureString

  - name: db_creds
    kind: templates.database
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv

templates:
  database:
    description: "Database credentials"
    fields:
      username:
        description: "Username"
        generator:
          kind: static
          config:
            default: admin
      password:
        description: "Password"
        generator:
          kind: random_password
          config:
            length: 32
            special: true
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: db/credentials

policies: {}
labels: {}
annotations: {}
```

## Validation

Use the CLI to validate your Secretfile:

```bash
secretzero validate
```

This checks:
- Required fields are present
- Types are correct
- References are valid
- Variable interpolation is valid

## Best Practices

1. **Use Variables**: Store environment-specific values in variables
2. **Template Reuse**: Use templates for secrets with multiple related fields
3. **Naming Convention**: Use consistent naming (e.g., `app_name_secret_name`)
4. **Target Multiple Stores**: Store critical secrets in multiple locations
5. **Validation**: Use regex validation for static secrets
6. **Rotation**: Set rotation periods for all non-one-time secrets
7. **Metadata**: Always include project and owner metadata
8. **Provider Fallbacks**: Configure fallback generators for reliability
