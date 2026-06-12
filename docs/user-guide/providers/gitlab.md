# GitLab Provider

The GitLab provider enables SecretZero to store and manage secrets in GitLab CI/CD variables. It supports token authentication for managing both project-level and group-level variables, with options for environment scoping, masking, and protection.

## Overview

The GitLab provider is ideal for:

- **CI/CD pipelines** using GitLab CI/CD workflows
- **Multi-project deployments** requiring consistent secrets across repositories
- **Environment-specific deployments** (production, staging, development)
- **Group-level secret sharing** across multiple projects in a GitLab group
- **Self-hosted GitLab instances** with custom URLs
- **Advanced GitLab CI/CD** setups on GitLab.com or self-managed instances

### Supported Target Types

| Target Type | Description | Use Case |
|-------------|-------------|----------|
| `gitlab_variable` | GitLab CI/CD project variable | Project-specific credentials, API keys, environment variables |
| `gitlab_group_variable` | GitLab CI/CD group variable | Shared secrets across all projects in a GitLab group |

### Supported Generator Kinds

| Generator | Description |
|-----------|-------------|
| `gitlab_project_token` | Create a scoped GitLab **project access token** via API (requires bootstrap PAT) |

### Project resolution (`project: auto`)

Targets and the `gitlab_project_token` generator accept `project: auto`. SecretZero resolves the project in this order:

1. Explicit `project` in target/generator config
2. Provider `project` / `project_id`
3. `CI_PROJECT_PATH` when running in GitLab CI
4. `git remote get-url origin` when the remote points at GitLab

See `examples/gitlab-project-token.yml` for a full manifest.

## Authentication

### Token Authentication

The GitLab provider uses Personal Access Tokens (PAT) or OAuth tokens for authentication.

```yaml
providers:
  gitlab:
    kind: gitlab
    auth:
      kind: token
      config:
        token: ${GITLAB_TOKEN}
```

**When to use**: All scenarios with GitLab CI/CD variable management.

### Creating a Personal Access Token

1. **Navigate to GitLab Settings**:
   - Go to GitLab → User Settings → Access Tokens
   - Or visit: `https://gitlab.com/-/profile/personal_access_tokens`

2. **Create a new token**:
   - Click "Add new token"
   - Give it a descriptive name (e.g., "SecretZero Token")
   - Set expiration (recommended: 90 days with rotation)

3. **Select scopes**:
   - `api` - Full API access (required for reading/writing variables)

4. **Generate and save token**:
   - Click "Create personal access token"
   - Copy the token immediately (it won't be shown again)
   - Token format: `glpat-xxxxxxxxxxxxxxxxxxxxx`

5. **Set environment variable**:
   ```bash
   export GITLAB_TOKEN=glpat-your_token_here
   ```

### Self-Hosted GitLab Support

For self-hosted GitLab instances, specify a custom URL:

```yaml
providers:
  gitlab:
    kind: gitlab
    auth:
      kind: token
      config:
        token: ${GITLAB_TOKEN}
        url: https://gitlab.mycompany.com
```

**Note**: The URL should be the base URL without `/api/v4` - the provider handles API path construction.

## Configuration

### Basic Configuration

```yaml
version: '1.0'

providers:
  gitlab:
    kind: gitlab
    auth:
      kind: token
      config:
        token: ${GITLAB_TOKEN}

secrets:
  - name: api_key
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: mygroup/myproject
          masked: true
          protected: false
```

### Multi-Project Configuration

Deploy secrets to multiple projects:

```yaml
providers:
  gitlab:
    kind: gitlab
    auth:
      kind: token
      config:
        token: ${GITLAB_TOKEN}

secrets:
  - name: shared_api_key
    kind: random_string
    config:
      length: 32
    targets:
      # Backend project
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: myorg/backend-service
          masked: true
      
      # Frontend project
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: myorg/frontend-app
          masked: true
      
      # Worker project
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: myorg/worker-service
          masked: true
```

### Group-Level Configuration

Share secrets across all projects in a group:

```yaml
providers:
  gitlab:
    kind: gitlab
    auth:
      kind: token
      config:
        token: ${GITLAB_TOKEN}

secrets:
  - name: shared_secret
    kind: random_string
    config:
      length: 64
    targets:
      # Group-level variable (available to all projects in group)
      - provider: gitlab
        kind: gitlab_group_variable
        config:
          group: myorganization
          masked: true
          protected: false
          environment_scope: "*"
```

### Environment-Specific Configuration

Use environment scopes for production, staging, and development:

```yaml
providers:
  gitlab:
    kind: gitlab
    auth:
      kind: token
      config:
        token: ${GITLAB_TOKEN}

secrets:
  - name: database_password
    kind: random_password
    config:
      length: 32
      special: true
    targets:
      # Production environment
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: myorg/myapp
          environment_scope: production
          protected: true
          masked: true
      
      # Staging environment
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: myorg/myapp
          environment_scope: staging
          protected: true
          masked: true
      
      # Development environment (all branches)
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: myorg/myapp
          environment_scope: development
          protected: false
          masked: true
```

## Target Types

### GitLab Project Variable

The `gitlab_variable` target type stores secrets in GitLab CI/CD project variables.

#### Configuration Options

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `project` | string | Yes | - | Project path (user/project or group/project), numeric ID, or `auto` |
| `environment_scope` | string | No | `*` | Environment scope (e.g., `production`, `staging`, `*` for all) |
| `protected` | boolean | No | `false` | Only available on protected branches/tags |
| `masked` | boolean | No | `true` | Hidden in job logs |
| `variable_type` | string | No | `env_var` | Variable type: `env_var` or `file` |

### GitLab Group Variable

The `gitlab_group_variable` target type stores secrets in GitLab CI/CD group variables, making them available to all projects in the group.

#### Configuration Options

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `group` | string | Yes | - | Group path or numeric ID |
| `environment_scope` | string | No | `*` | Environment scope (e.g., `production`, `staging`, `*` for all) |
| `protected` | boolean | No | `false` | Only available on protected branches/tags |
| `masked` | boolean | No | `true` | Hidden in job logs |
| `variable_type` | string | No | `env_var` | Variable type: `env_var` or `file` |

### GitLab Project Access Token Generator

The `gitlab_project_token` generator creates a scoped project access token using the GitLab API. Bootstrap authentication must be a **personal access token** (`GITLAB_TOKEN`) with `api` scope and Maintainer+ access on the project.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `provider` | string | Yes | - | Provider alias (e.g. `gitlab`) |
| `token_name` | string | Yes | - | GitLab project access token name |
| `scopes` | list | Yes | - | GitLab scopes (e.g. `api`, `read_repository`) |
| `project` | string | No | `auto` | Target project path/ID |
| `access_level` | integer | No | `40` | GitLab role level (30=Developer, 40=Maintainer) |
| `expires_in_days` | integer | No | `90` | Token lifetime in days |

On generation, SecretZero revokes any existing project access token with the same `token_name` before creating a new one.

#### Example: Project Variable

```yaml
secrets:
  - name: api_key
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: myorganization/myproject
          masked: true
          protected: false
```

The variable will be available in CI/CD as `$API_KEY`.

#### Example: Custom Variable Name

SecretZero converts secret names to uppercase for GitLab variables. The `secret_name` parameter in the YAML becomes the `key` field in GitLab.

```yaml
secrets:
  - name: database_password
    kind: random_password
    config:
      length: 32
      special: true
      exclude_characters: '"@/\`'
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: myorg/myapp
          masked: true
          protected: true
```

The variable will be available as `$DATABASE_PASSWORD`.

#### Example: Group Variable

```yaml
secrets:
  - name: shared_api_key
    kind: random_string
    config:
      length: 32
    targets:
      - provider: gitlab
        kind: gitlab_group_variable
        config:
          group: myorganization
          masked: true
          environment_scope: "*"
```

Available to all projects in the group as `$SHARED_API_KEY`.

#### Example: Environment-Scoped Variable

```yaml
secrets:
  - name: database_url
    kind: static
    config:
      default: postgresql://prod-db.example.com:5432/myapp
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: myorg/myapp
          environment_scope: production
          protected: true
```

Only available in production environment jobs.

#### Example: File Variable

```yaml
secrets:
  - name: service_account_key
    kind: static
    config:
      default: |
        {
          "type": "service_account",
          "project_id": "my-project",
          "private_key": "-----BEGIN PRIVATE KEY-----\n..."
        }
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: myorg/myapp
          variable_type: file
          masked: false
```

The variable value is written to a temporary file, and `$SERVICE_ACCOUNT_KEY` contains the file path.

#### Example: Protected Variable

```yaml
secrets:
  - name: prod_deploy_key
    kind: random_string
    config:
      length: 64
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: myorg/myapp
          protected: true
          masked: true
          environment_scope: production
```

Only available on protected branches and tags in production environment.

## Complete Examples

### Example 1: Simple Application Secrets

```yaml
version: '1.0'

variables:
  gitlab_project: myorganization/myapp
  environment: production

providers:
  gitlab:
    kind: gitlab
    auth:
      kind: token
      config:
        token: ${GITLAB_TOKEN}

secrets:
  # API Key
  - name: api_key
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: "{{var.gitlab_project}}"
          masked: true
          protected: false
  
  # Database Password
  - name: database_password
    kind: random_password
    rotation_period: 90d
    config:
      length: 32
      special: true
      exclude_characters: '"@/\`'
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: "{{var.gitlab_project}}"
          environment_scope: "{{var.environment}}"
          masked: true
          protected: true
  
  # JWT Signing Secret
  - name: jwt_secret
    kind: random_string
    config:
      length: 64
      charset: alphanumeric
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: "{{var.gitlab_project}}"
          masked: true

metadata:
  project: "{{var.gitlab_project}}"
  owner: backend-team
```

### Example 2: Multi-Environment Setup

```yaml
version: '1.0'

variables:
  gitlab_project: myorganization/myapp

providers:
  gitlab:
    kind: gitlab
    auth:
      kind: token
      config:
        token: ${GITLAB_TOKEN}

secrets:
  # Database credentials for all environments
  - name: database_password
    kind: random_password
    config:
      length: 32
      special: true
      exclude_characters: '"@/\`'
    targets:
      # Production environment
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: "{{var.gitlab_project}}"
          environment_scope: production
          protected: true
          masked: true
      
      # Staging environment
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: "{{var.gitlab_project}}"
          environment_scope: staging
          protected: true
          masked: true
      
      # Development environment
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: "{{var.gitlab_project}}"
          environment_scope: development
          protected: false
          masked: true
  
  # API endpoints (environment-specific static values)
  - name: api_url_prod
    kind: static
    config:
      default: https://api.example.com
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: "{{var.gitlab_project}}"
          variable_key: API_URL
          environment_scope: production
  
  - name: api_url_staging
    kind: static
    config:
      default: https://staging-api.example.com
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: "{{var.gitlab_project}}"
          variable_key: API_URL
          environment_scope: staging
```

### Example 3: Group-Level Shared Secrets

```yaml
version: '1.0'

variables:
  gitlab_group: myorganization

providers:
  gitlab:
    kind: gitlab
    auth:
      kind: token
      config:
        token: ${GITLAB_TOKEN}

secrets:
  # Shared API key across all projects
  - name: external_api_key
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      - provider: gitlab
        kind: gitlab_group_variable
        config:
          group: "{{var.gitlab_group}}"
          masked: true
          protected: false
          environment_scope: "*"
  
  # Shared authentication token
  - name: auth_token
    kind: random_string
    config:
      length: 64
    targets:
      - provider: gitlab
        kind: gitlab_group_variable
        config:
          group: "{{var.gitlab_group}}"
          masked: true
          environment_scope: "*"
  
  # Service account credentials (file type)
  - name: service_account
    kind: static
    config:
      default: |
        {
          "type": "service_account",
          "project_id": "shared-project"
        }
    targets:
      - provider: gitlab
        kind: gitlab_group_variable
        config:
          group: "{{var.gitlab_group}}"
          variable_type: file
          masked: false
```

### Example 4: Multi-Project Deployment

```yaml
version: '1.0'

variables:
  gitlab_org: myorganization

providers:
  gitlab:
    kind: gitlab
    auth:
      kind: token
      config:
        token: ${GITLAB_TOKEN}

secrets:
  # Shared API key across specific services
  - name: external_api_key
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      # Backend service
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: "{{var.gitlab_org}}/backend-service"
          environment_scope: production
          protected: true
          masked: true
      
      # Frontend app
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: "{{var.gitlab_org}}/frontend-app"
          environment_scope: production
          protected: true
          masked: true
      
      # Worker service
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: "{{var.gitlab_org}}/worker-service"
          environment_scope: production
          protected: true
          masked: true
  
  # Service-specific secrets
  - name: database_password
    kind: random_password
    config:
      length: 32
      special: true
    targets:
      # Only backend needs database access
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: "{{var.gitlab_org}}/backend-service"
          environment_scope: production
          protected: true
          masked: true
      
      # Worker also needs database
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: "{{var.gitlab_org}}/worker-service"
          environment_scope: production
          protected: true
          masked: true
```

### Example 5: Protected and Masked Variables

```yaml
version: '1.0'

providers:
  gitlab:
    kind: gitlab
    auth:
      kind: token
      config:
        token: ${GITLAB_TOKEN}

secrets:
  # Production secret - protected and masked
  - name: prod_api_key
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: myorg/myapp
          environment_scope: production
          protected: true  # Only on protected branches
          masked: true     # Hidden in logs
  
  # Staging secret - protected but visible
  - name: staging_api_key
    kind: random_string
    config:
      length: 32
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: myorg/myapp
          environment_scope: staging
          protected: true
          masked: false  # Visible in logs for debugging
  
  # Development secret - unprotected
  - name: dev_api_key
    kind: random_string
    config:
      length: 32
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: myorg/myapp
          environment_scope: development
          protected: false  # Available on all branches
          masked: true
```

## Token Permissions and Scopes

### Required Token Scopes

#### For All Variables
- `api` - Full API access
  - Grants access to create, update, and delete CI/CD variables
  - Required for both project-level and group-level variables
  - Includes read and write permissions

### Token Best Practices

1. **Use project/group access tokens** when available:
   - Limit token scope to specific projects or groups
   - Set shorter expiration periods
   - Revoke tokens after use in automated workflows

2. **Rotate tokens regularly**:
   ```yaml
   # Document token expiration
   metadata:
     token_expires: 2024-12-31
     token_owner: devops-team
   ```

3. **Use different tokens for different purposes**:
   - Separate tokens for production and non-production
   - Different tokens per team or project group
   - Dedicated tokens for automation

4. **Audit token usage**:
   - Review token activity in GitLab Settings → Access Tokens
   - Monitor API rate limits
   - Track variable updates through lockfile

### Required Permissions

#### For Project Variables
- **Maintainer role** or higher on the project
- Required permissions:
  - Read project settings
  - Manage CI/CD variables

#### For Group Variables
- **Owner role** or higher on the group
- Required permissions:
  - Manage group CI/CD variables
  - Access to all projects in group

## Integration with GitLab CI/CD Pipelines

### Using Variables in Pipelines

Once synced, variables are available in your `.gitlab-ci.yml`:

#### Basic Usage

```yaml
# .gitlab-ci.yml
deploy:
  stage: deploy
  script:
    - echo "API Key: $API_KEY"
    - echo "Database Password: $DATABASE_PASSWORD"
    - ./deploy.sh
  environment:
    name: production
```

#### Environment-Specific Usage

```yaml
# .gitlab-ci.yml
stages:
  - test
  - deploy

deploy_staging:
  stage: deploy
  script:
    - echo "Deploying to staging..."
    - echo "Database: $DATABASE_PASSWORD"
    - ./deploy.sh staging
  environment:
    name: staging
  only:
    - develop

deploy_production:
  stage: deploy
  script:
    - echo "Deploying to production..."
    - echo "Database: $DATABASE_PASSWORD"
    - ./deploy.sh production
  environment:
    name: production
  only:
    - main
```

#### File Variables Usage

```yaml
# .gitlab-ci.yml
deploy:
  stage: deploy
  script:
    # File variables are available as paths
    - cat $SERVICE_ACCOUNT_KEY
    - gcloud auth activate-service-account --key-file=$SERVICE_ACCOUNT_KEY
    - ./deploy.sh
  environment:
    name: production
```

#### Protected Variables Usage

```yaml
# .gitlab-ci.yml
deploy_prod:
  stage: deploy
  script:
    # Protected variables only available on protected branches
    - echo "Production deployment key: $PROD_DEPLOY_KEY"
    - ./deploy.sh production
  environment:
    name: production
  only:
    - main  # Must be a protected branch
```

### Manual Jobs with Approval

Combine protected variables with manual jobs:

```yaml
# .gitlab-ci.yml
deploy_staging:
  stage: deploy
  script:
    - ./deploy.sh staging
  environment:
    name: staging
    action: start
  only:
    - develop

deploy_production:
  stage: deploy
  script:
    - ./deploy.sh production
  environment:
    name: production
    action: start
  when: manual  # Requires manual trigger
  only:
    - main
  # Uses protected variables (only available on main)
```

### Multi-Environment Pipeline

```yaml
# .gitlab-ci.yml
stages:
  - build
  - test
  - deploy

variables:
  # Project-level variables (non-scoped)
  APP_NAME: myapp

build:
  stage: build
  script:
    - npm install
    - npm run build
  artifacts:
    paths:
      - dist/

test:
  stage: test
  script:
    - npm run test

deploy_dev:
  stage: deploy
  script:
    # Development-scoped variables
    - echo "API URL: $API_URL"
    - echo "Database: $DATABASE_PASSWORD"
    - ./deploy.sh
  environment:
    name: development
  only:
    - develop

deploy_staging:
  stage: deploy
  script:
    # Staging-scoped variables
    - echo "API URL: $API_URL"
    - echo "Database: $DATABASE_PASSWORD"
    - ./deploy.sh
  environment:
    name: staging
  only:
    - develop
  when: manual

deploy_prod:
  stage: deploy
  script:
    # Production-scoped variables (protected)
    - echo "API URL: $API_URL"
    - echo "Database: $DATABASE_PASSWORD"
    - ./deploy.sh
  environment:
    name: production
  only:
    - main
  when: manual
```

## Best Practices

### 1. Use Group Variables for Shared Secrets

```yaml
# Good: Share common secrets at group level
secrets:
  - name: shared_api_key
    kind: random_string
    config:
      length: 32
    targets:
      - provider: gitlab
        kind: gitlab_group_variable
        config:
          group: myorganization
          masked: true

# Avoid: Duplicating same secret across multiple projects
secrets:
  - name: shared_api_key
    kind: random_string
    config:
      length: 32
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: myorg/project1
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: myorg/project2
      # ... repeated for many projects
```

### 2. Mask Sensitive Variables

```yaml
# Good: Mask sensitive data
secrets:
  - name: api_key
    kind: random_string
    config:
      length: 32
      charset: alphanumeric  # Ensures maskable format
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: myorg/myapp
          masked: true  # Hidden in logs

# Avoid: Leaving sensitive data unmasked
secrets:
  - name: api_key
    kind: random_string
    config:
      length: 32
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: myorg/myapp
          masked: false  # Visible in logs
```

### 3. Use Protected Variables for Production

```yaml
# Good: Protect production secrets
secrets:
  - name: prod_db_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: myorg/myapp
          environment_scope: production
          protected: true  # Only on protected branches
          masked: true

# Avoid: Unprotected production secrets
secrets:
  - name: prod_db_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: myorg/myapp
          environment_scope: production
          protected: false  # Available on all branches
```

### 4. Use Environment Scopes

```yaml
# Good: Scope variables to environments
secrets:
  - name: database_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: myorg/myapp
          environment_scope: production
          protected: true

# Avoid: Global scope for environment-specific secrets
secrets:
  - name: prod_database_password  # Name indicates environment
    kind: random_password
    config:
      length: 32
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: myorg/myapp
          environment_scope: "*"  # Available to all environments
```

### 5. Rotate Tokens Regularly

```yaml
secrets:
  - name: api_key
    kind: random_string
    rotation_period: 90d  # Automatic rotation
    config:
      length: 32
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: myorg/myapp
          masked: true
```

### 6. Use the Lockfile

```bash
# Generate lockfile on first sync
secretzero sync -f Secretfile.yml

# Commit lockfile to track secret lifecycle
git add .secretzero.lock
git commit -m "Update secret lockfile"

# Verify lockfile before syncing
secretzero sync -f Secretfile.yml --verify-lock
```

### 7. Implement Naming Conventions

```yaml
# Good: Clear, consistent naming
secrets:
  - name: database_password      # Becomes DATABASE_PASSWORD
  - name: api_external_key       # Becomes API_EXTERNAL_KEY
  - name: jwt_signing_secret     # Becomes JWT_SIGNING_SECRET

# Avoid: Ambiguous names
secrets:
  - name: secret1
  - name: key
  - name: password
```

### 8. Audit Variable Access

```bash
# Use GitLab audit logs to track variable access
# Project Settings → Audit Events → Filter by "variable"

# Monitor variable updates with lockfile
git log .secretzero.lock

# Review CI/CD job logs for variable usage
# CI/CD → Pipelines → Select pipeline → Review jobs
```

### 9. Never Commit Tokens

```bash
# Add to .gitignore
echo "GITLAB_TOKEN" >> .gitignore
echo ".env" >> .gitignore
echo "*.secret" >> .gitignore

# Scan for accidentally committed secrets
git log -p | grep -i "glpat-"
```

### 10. Use File Variables for Complex Data

```yaml
# Good: Use file variables for JSON/credentials
secrets:
  - name: service_account_key
    kind: static
    config:
      default: |
        {
          "type": "service_account",
          "private_key": "..."
        }
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: myorg/myapp
          variable_type: file  # Writes to temp file
          masked: false  # JSON cannot be masked

# Avoid: Using env_var for large/complex data
secrets:
  - name: service_account_key
    kind: static
    config:
      default: '{"type":"service_account","private_key":"..."}'
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: myorg/myapp
          variable_type: env_var  # Complex JSON in env var
```

## Troubleshooting

### Authentication Failed

**Error**: `GitLab authentication failed`

**Solutions**:

1. Verify token is set:
   ```bash
   echo $GITLAB_TOKEN
   ```

2. Test token with GitLab API:
   ```bash
   curl --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
     "https://gitlab.com/api/v4/user"
   ```

3. Check token hasn't expired:
   - Go to GitLab → User Settings → Access Tokens
   - Verify token expiration date

4. Verify token scopes:
   ```bash
   curl --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
     "https://gitlab.com/api/v4/user" | jq .
   ```

5. For self-hosted GitLab, verify URL:
   ```bash
   curl --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
     "https://gitlab.mycompany.com/api/v4/user"
   ```

6. Test with SecretZero:
   ```bash
   secretzero test -f Secretfile.yml
   ```

### Permission Denied

**Error**: `403 Forbidden` or `Insufficient permissions`

**Solutions**:

1. **For project variables**, ensure Maintainer role:
   - Go to Project → Members
   - Verify you have at least Maintainer role
   - Token owner must have appropriate access

2. **For group variables**, ensure Owner role:
   - Go to Group → Members
   - Verify you have Owner role
   - Group variables require higher permissions

3. Test project access:
   ```bash
   curl --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
     "https://gitlab.com/api/v4/projects/myorg%2Fmyproject"
   ```

4. Test group access:
   ```bash
   curl --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
     "https://gitlab.com/api/v4/groups/myorg"
   ```

5. Verify token has `api` scope:
   - Recreate token with `api` scope if missing

### Variable Not Appearing in Pipeline

**Error**: Variable is synced but not available in CI/CD jobs

**Solutions**:

1. **Verify variable name** (case-sensitive):
   ```yaml
   # If secret name in SecretZero is: api_key
   # It becomes in GitLab: API_KEY (uppercase with underscores)
   
   # In pipeline, use exact uppercase name:
   script:
     - echo $API_KEY  # Correct
     - echo $api_key  # Wrong - won't work
   ```

2. **Check environment scope**:
   ```yaml
   # Variable scoped to 'production'
   deploy:
     script:
       - echo $DATABASE_PASSWORD
     environment:
       name: production  # Must match scope
   ```

3. **Verify protected variable settings**:
   ```yaml
   # Protected variable on main branch
   deploy:
     script:
       - echo $PROD_API_KEY
     only:
       - main  # Must be protected branch
   ```

4. **Check variable in GitLab UI**:
   - Project Settings → CI/CD → Variables
   - Verify variable exists and name matches
   - Check environment scope settings

5. **Review pipeline job logs**:
   - Look for variable expansion errors
   - Check if job has access to environment

### Invalid Characters in Variable Names

**Error**: `Invalid variable name` or `Variable name contains invalid characters`

**Solutions**:

1. **Use valid characters only** (alphanumeric and underscores):
   ```yaml
   # Good: Valid variable names
   secrets:
     - name: api_key           # Valid
     - name: database_password  # Valid
     - name: jwt_secret_key     # Valid
   
   # Bad: Invalid characters
   secrets:
     - name: api-key           # Hyphens not allowed
     - name: api.key           # Dots not allowed
     - name: api key           # Spaces not allowed
   ```

2. **Use custom variable names**:
   ```yaml
   secrets:
     - name: my-api-key  # Name with hyphens
       kind: random_string
       config:
         length: 32
       targets:
         - provider: gitlab
           kind: gitlab_variable
           config:
             project: myorg/myapp
             variable_key: MY_API_KEY  # Valid custom name
   ```

### Masked Variable Rejected

**Error**: `Variable value does not meet masking requirements`

**Solutions**:

1. **Ensure value is at least 8 characters**:
   ```yaml
   # Good: Long enough to mask
   secrets:
     - name: api_key
       kind: random_string
       config:
         length: 32  # Minimum 8 characters
       targets:
         - provider: gitlab
           kind: gitlab_variable
           config:
             project: myorg/myapp
             masked: true
   ```

2. **Remove special characters**:
   ```yaml
   # Good: Alphanumeric only (maskable)
   secrets:
     - name: api_key
       kind: random_string
       config:
         length: 32
         charset: alphanumeric  # No special chars
       targets:
         - provider: gitlab
           kind: gitlab_variable
           config:
             project: myorg/myapp
             masked: true
   
   # Bad: Special characters prevent masking
   secrets:
     - name: api_key
       kind: random_string
       config:
         length: 32
         charset: all  # Includes special chars
       targets:
         - provider: gitlab
           kind: gitlab_variable
           config:
             project: myorg/myapp
             masked: true  # Will fail
   ```

3. **Use file variables for complex data**:
   ```yaml
   # Good: File variables don't require masking
   secrets:
     - name: service_account_key
       kind: static
       config:
         default: '{"key": "value with spaces"}'
       targets:
         - provider: gitlab
           kind: gitlab_variable
           config:
             project: myorg/myapp
             variable_type: file
             masked: false
   ```

4. **Masked variable requirements**:
   - Minimum 8 characters
   - No spaces
   - No special regex characters
   - Must match pattern: `^[a-zA-Z0-9_+=/@:.~-]{8,}$`

### Project or Group Not Found

**Error**: `404 Project Not Found` or `404 Group Not Found`

**Solutions**:

1. **Verify project path**:
   ```bash
   # Check project exists and path is correct
   curl --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
     "https://gitlab.com/api/v4/projects/myorg%2Fmyproject"
   ```

2. **Use URL encoding** for special characters:
   ```yaml
   # Project path with special characters
   config:
     project: myorg/my-project  # Hyphen is OK
     # NOT: myorg/my project  # Space not allowed
   ```

3. **Use numeric project ID**:
   ```yaml
   # Alternative: Use numeric ID instead of path
   config:
     project: "12345678"  # Numeric project ID
   ```

4. **Verify group path**:
   ```bash
   # Check group exists
   curl --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
     "https://gitlab.com/api/v4/groups/myorg"
   ```

5. **Check access permissions**:
   - Verify you have access to the project/group
   - Token owner must be a member

### Rate Limits

**Error**: `429 Too Many Requests` or `Rate limit exceeded`

**Solutions**:

1. Check current rate limit:
   ```bash
   curl -I --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
     "https://gitlab.com/api/v4/user" | grep RateLimit
   ```

2. **Authenticated requests** have higher limits:
   - Unauthenticated: 10 requests/minute (per IP)
   - Authenticated: 2,000 requests/minute (per user)
   - Self-hosted: Configurable by admin

3. Implement delays for large deployments:
   ```yaml
   # Deploy to many projects with delays
   # Space out secret syncs
   ```

4. Deploy to group level instead of many projects:
   ```yaml
   # Good: Single group variable
   config:
     group: myorg
   
   # Avoid: Many individual project variables
   # (multiple API calls)
   ```

5. Use dry-run to test without API calls:
   ```bash
   secretzero sync --dry-run -f Secretfile.yml
   ```

## Self-Hosted GitLab Support

### Configuration

```yaml
providers:
  gitlab_selfhosted:
    kind: gitlab
    auth:
      kind: token
      config:
        token: ${GITLAB_SELFHOSTED_TOKEN}
        url: https://gitlab.mycompany.com

secrets:
  - name: api_key
    kind: random_string
    config:
      length: 32
    targets:
      - provider: gitlab_selfhosted
        kind: gitlab_variable
        config:
          project: myorg/myproject
          masked: true
```

### URL Format

- **GitLab.com**: `https://gitlab.com` (default, can be omitted)
- **Self-hosted GitLab**: `https://gitlab.mycompany.com`
- **Custom port**: `https://gitlab.mycompany.com:8443`

**Note**: Do not include `/api/v4` in the URL - the provider handles API path construction.

### Testing Self-Hosted Connection

```bash
# Test API connectivity
curl --header "PRIVATE-TOKEN: $GITLAB_SELFHOSTED_TOKEN" \
  "https://gitlab.mycompany.com/api/v4/user"

# Test with SecretZero
secretzero test -f Secretfile.yml
```

### Self-Hosted Specific Considerations

1. **SSL Certificates**:
   - Ensure valid SSL certificate
   - For self-signed certificates, configure trust in system

2. **Network Access**:
   - Verify network connectivity to GitLab server
   - Check firewall rules and proxy settings

3. **API Version**:
   - Uses `/api/v4` endpoint (GitLab 9.0+)
   - Verify GitLab version compatibility

4. **Rate Limits**:
   - Self-hosted instances may have custom rate limits
   - Contact GitLab admin for specific limits

5. **Authentication**:
   - LDAP/SAML users may have restrictions on API access
   - Verify API access is enabled for your account

## Cost and Limits

### GitLab CI/CD Usage

- **Public projects**: Unlimited CI/CD minutes on GitLab.com
- **Private projects**: Free tier includes minutes (varies by plan)
- **Variables**: No additional cost, included in GitLab plan

### Limits

- **Project variables**: Up to 200 variables per project
- **Group variables**: Up to 200 variables per group
- **Variable size**: Maximum 10 KB per variable value
- **Variable name**: Maximum 255 characters

### Best Practices for Limits

1. Use group variables for shared secrets to reduce per-project variable count
2. Use file variables for large data instead of environment variables
3. Implement variable cleanup for unused secrets
4. Plan naming conventions to stay organized within limits

## See Also

- [Providers Overview](index.md)
- [GitHub Provider](github.md)
- [AWS Provider](aws.md)
- [Azure Provider](azure.md)
- [GitLab CI/CD Documentation](https://docs.gitlab.com/ee/ci/)
- [GitLab CI/CD Variables Documentation](https://docs.gitlab.com/ee/ci/variables/)
- [python-gitlab Library](https://python-gitlab.readthedocs.io/)
