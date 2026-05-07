# GitLab CI/CD Variables

GitLab CI/CD variables targets allow you to securely store secrets in GitLab for use in CI/CD pipelines. Variables can be stored at project or group levels, providing flexible access control for different deployment scenarios and multi-project environments.

## Overview

GitLab CI/CD provides two types of variables:

- **Project Variables** - Available to all pipelines in a specific project
- **Group Variables** - Shared across all projects within a group (including subgroups)

SecretZero integrates with GitLab's API to automatically create and update these variables, with support for protected variables, masked variables, environment scoping, and file-type variables.

!!! info "Variable Retrieval Supported"
    Unlike GitHub Actions secrets, GitLab CI/CD variables **can be retrieved** via the API. SecretZero supports both storing and retrieving variable values from GitLab.

## Use Cases

- **CI/CD Pipelines** - Automate deployment credentials for GitLab CI/CD workflows
- **Multi-Project Deployments** - Share secrets across multiple projects using group variables
- **Environment-Specific Configuration** - Manage separate variables for production, staging, and development
- **Secret Rotation** - Regularly update secrets across all projects from a single source
- **Infrastructure as Code** - Version control variable configurations without exposing values
- **Multi-Environment Variables** - Use environment scopes to manage variables per environment

## Prerequisites

### Required Dependencies

GitLab support requires the python-gitlab library:

```bash
# Install with GitLab support
pip install secretzero[gitlab]

# Or install python-gitlab separately
pip install python-gitlab
```

### GitLab Token Generation

You need a Personal Access Token or Project Access Token with appropriate permissions:

1. **Personal Access Token:**
   - Navigate to: User Settings → Access Tokens
   - Name: "SecretZero"
   - Select required scopes (see below)
   - Set expiration date
   - Click "Create personal access token"
   - Save the token securely

2. **Project Access Token (GitLab 13.9+):**
   - Navigate to: Project → Settings → Access Tokens
   - Name: "SecretZero"
   - Select role and scopes
   - Create token

3. **Group Access Token (GitLab 14.7+):**
   - Navigate to: Group → Settings → Access Tokens
   - Name: "SecretZero"
   - Select role and scopes
   - Create token

### Token Permissions

Required scopes depend on the variable types you'll manage:

| Variable Type | Required Scope | Permission Level |
|---------------|----------------|------------------|
| Project variables | `api` or `write_repository` | Maintainer or Owner role |
| Group variables | `api` | Owner role in group |

**Recommended token configuration:**

For **project variables**:
```
api (Access the authenticated user's API)
  - Full read/write access to project CI/CD variables
```

Or more restrictive:
```
read_api (Read-only API access)
write_repository (Write access to the repository)
```

For **group variables**:
```
api (Full API access)
  - Required for group-level variable management
```

!!! tip "Self-Managed GitLab"
    If using a self-managed GitLab instance, you'll need to specify the custom URL in your provider configuration.

## Target Types

SecretZero provides two target types for GitLab CI/CD variables:

### GitLabVariableTarget

Stores variables at the project level, available to all pipelines in a specific project.

**Provider Configuration:**
```yaml
providers:
  gitlab:
    kind: gitlab
    auth:
      kind: token
      config:
        token: ${GITLAB_TOKEN}
        # Optional: For self-managed GitLab
        # url: https://gitlab.mycompany.com
```

### GitLabGroupVariableTarget

Stores variables at the group level, shared across all projects in a group and its subgroups.

**Provider Configuration:**
```yaml
providers:
  gitlab:
    kind: gitlab
    auth:
      kind: token
      config:
        token: ${GITLAB_TOKEN}
```

## Configuration Options

### Project Variables

Store variables available to all pipelines in a project.

**Configuration:**
```yaml
targets:
  - provider: gitlab
    kind: gitlab_variable
    config:
      project: group/project-name
      # or use project ID
      # project: 12345
```

**Options:**

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `project` | string | Yes | - | Project path (e.g., 'group/project') or numeric project ID |
| `protected` | boolean | No | `false` | Whether variable is protected (only available on protected branches/tags) |
| `masked` | boolean | No | `true` | Whether variable is masked in job logs |
| `environment_scope` | string | No | `*` | Environment scope (e.g., 'production', 'staging/*', '*' for all) |
| `variable_type` | string | No | `env_var` | Variable type: 'env_var' or 'file' |

### Group Variables

Store variables shared across all projects in a group.

**Configuration:**
```yaml
targets:
  - provider: gitlab
    kind: gitlab_group_variable
    config:
      group: my-group
      # or use group ID
      # group: 54321
```

**Options:**

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `group` | string | Yes | - | Group path (e.g., 'my-group') or numeric group ID |
| `protected` | boolean | No | `false` | Whether variable is protected |
| `masked` | boolean | No | `true` | Whether variable is masked in job logs |
| `environment_scope` | string | No | `*` | Environment scope |
| `variable_type` | string | No | `env_var` | Variable type: 'env_var' or 'file' |

### Variable Properties

#### Protected Variables

Protected variables are only available to pipelines running on protected branches or protected tags:

```yaml
config:
  protected: true  # Only on protected branches/tags
```

**Use cases:**
- Production deployment credentials
- Sensitive API keys
- Database passwords for production

**GitLab protection:**
- Configure protected branches: Repository → Settings → Repository → Protected branches
- Configure protected tags: Repository → Settings → Repository → Protected tags

#### Masked Variables

Masked variables are hidden in job logs, with their values replaced by `[masked]`:

```yaml
config:
  masked: true  # Hidden in logs
```

**Masking requirements:**
- Must be at least 8 characters long
- Must be a single line
- Must contain only base64 or hex characters (matching regex: `^[a-zA-Z0-9_+=/@:.-]+$`)
- Cannot have spaces

!!! warning "Masking Limitations"
    Complex values like JSON or multiline strings cannot be masked. Use file-type variables for such cases.

#### Environment Scope

Environment scopes restrict variables to specific environments:

```yaml
config:
  environment_scope: production    # Only in 'production' environment
  # environment_scope: staging/*   # All staging environments
  # environment_scope: review/*    # All review apps
  # environment_scope: "*"         # All environments (default)
```

**Environment scope patterns:**
- Exact match: `production`
- Wildcard suffix: `staging/*`
- Wildcard prefix: `*/production`
- All environments: `*`

**Precedence:** More specific scopes take precedence over less specific ones.

#### Variable Types

**Environment Variables (`env_var`):**
Standard environment variables accessible via `$VARIABLE_NAME`:

```yaml
config:
  variable_type: env_var  # Default
```

**File Variables (`file`):**
Variables written to temporary files, with the variable containing the file path:

```yaml
config:
  variable_type: file
```

**Use cases for file variables:**
- Service account keys (JSON)
- SSL certificates
- Configuration files
- SSH keys
- Kubeconfig files

## Complete Examples

### Basic Project Variable

Store a simple API key in a project:

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
  - name: API_KEY
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

### Group-Level Variables

Share variables across multiple projects in a group:

```yaml
version: '1.0'

variables:
  gitlab_group: mygroup

providers:
  gitlab:
    kind: gitlab
    auth:
      kind: token
      config:
        token: ${GITLAB_TOKEN}

secrets:
  # Shared Docker registry credentials
  - name: DOCKER_USERNAME
    kind: static
    config:
      value: ${DOCKER_USERNAME}
    targets:
      - provider: gitlab
        kind: gitlab_group_variable
        config:
          group: ${gitlab_group}
          masked: false  # Usernames typically don't need masking

  - name: DOCKER_PASSWORD
    kind: random_password
    config:
      length: 32
      special: false
    targets:
      - provider: gitlab
        kind: gitlab_group_variable
        config:
          group: ${gitlab_group}
          masked: true

  # Shared API endpoint
  - name: API_ENDPOINT
    kind: static
    config:
      value: https://api.mycompany.com
    targets:
      - provider: gitlab
        kind: gitlab_group_variable
        config:
          group: ${gitlab_group}
          masked: false
```

### Protected and Masked Variables

Secure production credentials:

```yaml
version: '1.0'

variables:
  gitlab_project: mygroup/myproject

providers:
  gitlab:
    kind: gitlab
    auth:
      kind: token
      config:
        token: ${GITLAB_TOKEN}

secrets:
  # Production database password (protected & masked)
  - name: DATABASE_PASSWORD
    kind: random_password
    config:
      length: 32
      special: true
      exclude_characters: '"@/\`'
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${gitlab_project}
          protected: true     # Only on protected branches
          masked: true        # Hidden in logs
          environment_scope: production

  # API key (masked but not protected)
  - name: EXTERNAL_API_KEY
    kind: random_string
    config:
      length: 64
      charset: base64
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${gitlab_project}
          protected: false    # Available on all branches
          masked: true        # Hidden in logs

  # Public configuration (not protected or masked)
  - name: APP_VERSION
    kind: static
    config:
      value: "1.0.0"
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${gitlab_project}
          protected: false
          masked: false
```

### Environment-Specific Variables

Manage secrets for different environments:

```yaml
version: '1.0'

variables:
  gitlab_project: mygroup/myproject

providers:
  gitlab:
    kind: gitlab
    auth:
      kind: token
      config:
        token: ${GITLAB_TOKEN}

secrets:
  # Production database URL
  - name: DATABASE_URL
    kind: static
    config:
      value: postgresql://prod.example.com:5432/proddb
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${gitlab_project}
          environment_scope: production
          protected: true
          masked: true

  # Staging database URL
  - name: DATABASE_URL
    kind: static
    config:
      value: postgresql://staging.example.com:5432/stagingdb
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${gitlab_project}
          environment_scope: staging/*
          protected: false
          masked: true

  # Development database URL
  - name: DATABASE_URL
    kind: static
    config:
      value: postgresql://dev.example.com:5432/devdb
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${gitlab_project}
          environment_scope: development
          protected: false
          masked: false

  # API key with environment-specific values
  - name: STRIPE_API_KEY
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      # Production key
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${gitlab_project}
          environment_scope: production/*
          protected: true
          masked: true
      
      # Staging key
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${gitlab_project}
          environment_scope: staging/*
          protected: false
          masked: true
```

### File-Type Variables

Store credentials as files:

```yaml
version: '1.0'

variables:
  gitlab_project: mygroup/myproject

providers:
  gitlab:
    kind: gitlab
    auth:
      kind: token
      config:
        token: ${GITLAB_TOKEN}

secrets:
  # Service account key as JSON file
  - name: GCP_SERVICE_ACCOUNT_KEY
    kind: static
    config:
      value: |
        {
          "type": "service_account",
          "project_id": "my-project",
          "private_key_id": "key123",
          "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
          "client_email": "service@my-project.iam.gserviceaccount.com"
        }
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${gitlab_project}
          variable_type: file  # Creates file in CI job
          masked: false        # JSON cannot be masked
          protected: true

  # Kubeconfig file
  - name: KUBECONFIG
    kind: static
    config:
      value: |
        apiVersion: v1
        kind: Config
        clusters:
        - cluster:
            server: https://kubernetes.example.com
          name: production
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${gitlab_project}
          variable_type: file
          environment_scope: production

  # SSH private key
  - name: DEPLOY_SSH_KEY
    kind: static
    config:
      value: |
        -----BEGIN OPENSSH PRIVATE KEY-----
        b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtz
        ...
        -----END OPENSSH PRIVATE KEY-----
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${gitlab_project}
          variable_type: file
          protected: true
          masked: false  # Multiline content cannot be masked
```

### Multi-Project Inheritance

Share secrets across multiple projects with group and project variables:

```yaml
version: '1.0'

variables:
  gitlab_group: mycompany
  frontend_project: mycompany/frontend
  backend_project: mycompany/backend
  worker_project: mycompany/worker

providers:
  gitlab:
    kind: gitlab
    auth:
      kind: token
      config:
        token: ${GITLAB_TOKEN}

secrets:
  # Shared group-level credentials
  - name: SHARED_SECRET
    kind: random_string
    config:
      length: 64
      charset: base64
    targets:
      - provider: gitlab
        kind: gitlab_group_variable
        config:
          group: ${gitlab_group}
          masked: true

  - name: DOCKER_REGISTRY_PASSWORD
    kind: random_password
    config:
      length: 32
      special: false
    targets:
      - provider: gitlab
        kind: gitlab_group_variable
        config:
          group: ${gitlab_group}
          masked: true

  # Frontend-specific variables
  - name: SENTRY_DSN_FRONTEND
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${frontend_project}
          masked: true

  # Backend-specific variables
  - name: DATABASE_PASSWORD
    kind: random_password
    config:
      length: 32
      special: true
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${backend_project}
          environment_scope: production
          protected: true
          masked: true

  - name: JWT_SECRET
    kind: random_string
    config:
      length: 64
      charset: base64
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${backend_project}
          masked: true

  # Worker-specific variables
  - name: REDIS_PASSWORD
    kind: random_password
    config:
      length: 32
      special: false
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${worker_project}
          masked: true
```

### Self-Managed GitLab

Configure for self-managed GitLab instances:

```yaml
version: '1.0'

providers:
  gitlab:
    kind: gitlab
    auth:
      kind: token
      config:
        token: ${GITLAB_TOKEN}
        url: https://gitlab.mycompany.com  # Custom GitLab URL

secrets:
  - name: API_KEY
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: internal-group/internal-project
          masked: true
```

## Using Variables in .gitlab-ci.yml

Once secrets are synced to GitLab, they're available in your CI/CD pipelines.

### Environment Variables

```yaml
# .gitlab-ci.yml

stages:
  - build
  - test
  - deploy

build:
  stage: build
  script:
    - echo "Using API key: $API_KEY"
    - echo "Database: $DATABASE_URL"
    - npm install
    - npm run build

test:
  stage: test
  script:
    - npm test
  variables:
    TEST_DATABASE_URL: $DATABASE_URL

deploy:
  stage: deploy
  environment:
    name: production
    url: https://myapp.com
  script:
    # Variables are automatically available
    - echo "Deploying with password: $DATABASE_PASSWORD"
    - ./deploy.sh
  only:
    - main  # Only on main branch
```

### File Variables

File-type variables are written to temporary files:

```yaml
# .gitlab-ci.yml

deploy:
  stage: deploy
  script:
    # File variables contain the path to the temporary file
    - echo "Service account key is at: $GCP_SERVICE_ACCOUNT_KEY"
    - cat $GCP_SERVICE_ACCOUNT_KEY
    
    # Use with gcloud
    - gcloud auth activate-service-account --key-file=$GCP_SERVICE_ACCOUNT_KEY
    
    # Use with kubectl
    - kubectl --kubeconfig=$KUBECONFIG get pods
    
    # Use SSH key for deployment
    - chmod 600 $DEPLOY_SSH_KEY
    - ssh-add $DEPLOY_SSH_KEY
    - ssh user@server 'deploy-script.sh'
```

### Environment-Scoped Variables

Different values per environment:

```yaml
# .gitlab-ci.yml

.deploy:
  stage: deploy
  script:
    # DATABASE_URL varies by environment scope
    - echo "Deploying to: $CI_ENVIRONMENT_NAME"
    - echo "Database: $DATABASE_URL"
    - ./deploy.sh

deploy-development:
  extends: .deploy
  environment:
    name: development
  # Uses DATABASE_URL with environment_scope: development

deploy-staging:
  extends: .deploy
  environment:
    name: staging/feature-x
  # Uses DATABASE_URL with environment_scope: staging/*

deploy-production:
  extends: .deploy
  environment:
    name: production
  # Uses DATABASE_URL with environment_scope: production
  only:
    - main
```

### Protected Variables

Protected variables only available on protected branches:

```yaml
# .gitlab-ci.yml

deploy-production:
  stage: deploy
  environment:
    name: production
  script:
    # DATABASE_PASSWORD only available if this runs on protected branch
    - echo "Production password: $DATABASE_PASSWORD"
    - ./deploy.sh production
  only:
    - main  # main must be a protected branch
```

### Group Variables

Group variables are available to all projects:

```yaml
# .gitlab-ci.yml (in any project within the group)

build:
  stage: build
  script:
    # SHARED_SECRET available from group variables
    - echo "Shared secret: $SHARED_SECRET"
    
    # Login to Docker registry with group credentials
    - echo "$DOCKER_REGISTRY_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin registry.example.com
    
    - docker build -t myimage .
    - docker push myimage
```

## Best Practices

### 1. Use Masking for Sensitive Values

Mask all sensitive data to prevent exposure in logs:

```yaml
config:
  masked: true  # Always mask passwords, keys, tokens
```

**Remember masking requirements:**
- At least 8 characters
- Single line
- Only base64/hex characters
- No spaces

### 2. Protect Production Variables

Use protected variables for production secrets:

```yaml
config:
  protected: true       # Only on protected branches
  environment_scope: production
```

**Configure protected branches:**
1. Go to Repository → Settings → Repository → Protected branches
2. Protect your production branch (e.g., `main`)
3. Set allowed to merge and push permissions

### 3. Use Environment Scopes

Scope variables to specific environments:

```yaml
# Production
config:
  environment_scope: production

# Staging (all staging environments)
config:
  environment_scope: staging/*

# All review apps
config:
  environment_scope: review/*
```

**Benefits:**
- Prevents accidental use of production credentials in staging
- Allows same variable name with different values per environment
- Improves security by limiting variable exposure

### 4. Use File Variables for Complex Data

For JSON, multiline, or binary data:

```yaml
config:
  variable_type: file  # Creates temporary file
  masked: false        # Complex formats can't be masked
```

### 5. Organize with Group Variables

Share common secrets at group level:

```yaml
# Group variables for shared credentials
- name: DOCKER_PASSWORD
  targets:
    - kind: gitlab_group_variable
      config:
        group: mygroup

# Project variables for specific secrets
- name: DATABASE_PASSWORD
  targets:
    - kind: gitlab_variable
      config:
        project: mygroup/myproject
```

### 6. Use Descriptive Names

Follow naming conventions:

```yaml
# Good: Clear purpose
DATABASE_PASSWORD
AWS_ACCESS_KEY_ID
STRIPE_API_KEY_PRODUCTION
SENTRY_DSN_FRONTEND

# Bad: Ambiguous
PASSWORD
KEY
SECRET
TOKEN
```

### 7. Rotate Secrets Regularly

Automate rotation with SecretZero:

```yaml
# .gitlab-ci.yml - scheduled rotation
rotate-secrets:
  stage: maintenance
  script:
    - pip install secretzero[gitlab]
    - secretzero sync -f Secretfile.yml
  only:
    - schedules  # Run on schedule
  variables:
    GITLAB_TOKEN: $GITLAB_ADMIN_TOKEN
```

**Schedule in GitLab:**
- Go to CI/CD → Schedules
- Create new schedule (e.g., monthly)
- Runs pipeline to rotate secrets

### 8. Use Project Access Tokens

Prefer project access tokens over personal tokens:

```yaml
# Benefits:
# - Scoped to specific project
# - Not tied to individual user
# - Easier to manage and rotate
# - Clear audit trail
```

### 9. Document Variable Requirements

Maintain documentation:

```markdown
# Required Variables

## Project Variables
- `DATABASE_PASSWORD` - PostgreSQL database password (protected, masked)
- `API_KEY` - External API key (masked)
- `JWT_SECRET` - JWT signing key (masked)

## Group Variables
- `DOCKER_PASSWORD` - Docker registry password (masked)
- `SHARED_SECRET` - Shared secret across projects (masked)

## Environment Scopes
- `production` - Production environment variables
- `staging/*` - All staging environments
- `*` - All environments (shared variables)
```

## Security Considerations

### Variable Visibility

GitLab CI/CD variables have different visibility levels:

1. **Masked variables:** Hidden in job logs
2. **Protected variables:** Only available on protected branches/tags
3. **Environment-scoped variables:** Restricted to specific environments

**Recommendation:**
```yaml
# High-security variables (production)
config:
  protected: true
  masked: true
  environment_scope: production

# Medium-security variables (staging)
config:
  protected: false
  masked: true
  environment_scope: staging/*

# Low-security variables (all environments)
config:
  protected: false
  masked: false
  environment_scope: "*"
```

### Audit Events

GitLab tracks all variable changes in audit events:

1. **Project Audit Events:**
   - Settings → Audit Events
   - Shows who created/modified/deleted variables

2. **Group Audit Events:**
   - Group Settings → Audit Events
   - Tracks group-level variable changes

3. **Instance Audit Events (GitLab Premium+):**
   - Admin Area → Audit Events
   - Instance-wide audit trail

**Monitor for:**
- Unauthorized variable creation
- Unexpected modifications
- Variable deletions
- Access from unusual IP addresses

### Variable Encryption

GitLab encrypts variables at rest:

- Encrypted using AES-256-GCM
- Encryption keys stored separately from database
- Decrypted only during job execution
- Never stored in plaintext

**SecretZero's role:**
1. Generates secret values
2. Sends values to GitLab API
3. GitLab encrypts and stores
4. Variables decrypted during CI/CD jobs

### Access Control

Control who can manage variables:

| Role | Project Variables | Group Variables |
|------|-------------------|-----------------|
| Guest | No access | No access |
| Reporter | View | View (if enabled) |
| Developer | View | View (if enabled) |
| Maintainer | Create/Edit/Delete | View (if enabled) |
| Owner | Create/Edit/Delete | Create/Edit/Delete |

**Best practices:**
- Grant Maintainer role only to trusted users
- Use Owner role sparingly for group variables
- Review permissions regularly
- Use project access tokens for automation

### Protected Branches and Tags

Configure protection rules:

```yaml
# Protected Branches
# Repository → Settings → Repository → Protected branches

Protect: main
Allowed to merge: Maintainers
Allowed to push: No one
Allowed to force push: No

# Protected Tags
# Repository → Settings → Repository → Protected tags

Protect: v*
Allowed to create: Maintainers
```

**Benefits:**
- Protected variables only exposed on protected refs
- Prevents accidental production deployments
- Enforces code review process

### IP Allowlisting

Restrict API access by IP (GitLab Premium+):

```yaml
# Admin Area → Settings → Network → Outbound requests

# Allowlist IPs for API access
- 203.0.113.0/24  # Office network
- 198.51.100.50   # CI runner
```

### Token Security

Protect your GitLab tokens:

```bash
# Use environment variables
export GITLAB_TOKEN=glpat-xxxxxxxxxxxx

# Never commit tokens
echo "GITLAB_TOKEN=*" >> .gitignore

# Set expiration dates
# Tokens → Set expiration (recommended: 90 days)

# Rotate regularly
# Recommended: Rotate every 3 months
```

## Troubleshooting

### Authentication Failed

**Symptom:** Error: "401 Unauthorized" or "Invalid token"

**Solutions:**

1. **Verify token is valid:**
   ```bash
   # Test authentication
   curl --header "PRIVATE-TOKEN: ${GITLAB_TOKEN}" \
     https://gitlab.com/api/v4/user
   ```

2. **Check token hasn't expired:**
   - Navigate to: User Settings → Access Tokens
   - Check expiration date
   - Regenerate if expired

3. **Verify token scopes:**
   ```bash
   # Token must have 'api' scope
   # Check in GitLab: User Settings → Access Tokens → Active tokens
   ```

4. **For self-managed GitLab, verify URL:**
   ```yaml
   providers:
     gitlab:
       auth:
         config:
           token: ${GITLAB_TOKEN}
           url: https://gitlab.mycompany.com  # Correct URL
   ```

### Permission Denied

**Symptom:** Error: "403 Forbidden" or "Insufficient permissions"

**Solutions:**

1. **Project variables - verify role:**
   - Token owner must have Maintainer or Owner role
   - Check: Project → Members

2. **Group variables - verify role:**
   - Token owner must have Owner role in group
   - Check: Group → Members

3. **Project access tokens - verify role:**
   - Token must have Maintainer or Owner role
   - Check: Project → Settings → Access Tokens

4. **Check project visibility:**
   ```bash
   # Public projects: Token needs 'api' scope
   # Private projects: Token needs 'api' scope + project membership
   ```

### Variable Not Appearing in Jobs

**Symptom:** Variable is created but `$VARIABLE_NAME` is empty in CI/CD

**Solutions:**

1. **Verify variable name matches exactly:**
   ```yaml
   # Variable names are case-sensitive
   secrets:
     - name: API_KEY  # Must use API_KEY, not api_key
   
   # In .gitlab-ci.yml:
   - echo $API_KEY  # Must match exactly
   ```

2. **Check environment scope:**
   ```yaml
   # If environment_scope is 'production'
   # Variable only available in 'production' environment
   
   deploy:
     environment:
       name: production  # Must match environment_scope
   ```

3. **Verify protected variable settings:**
   ```yaml
   # Protected variables only available on protected branches
   
   # Check if branch is protected:
   # Repository → Settings → Repository → Protected branches
   ```

4. **Group variables - check inheritance:**
   ```bash
   # Group variables available to all projects in group
   # Verify project is in correct group
   # Check: Project → Details → Group
   ```

5. **File variables - use as path:**
   ```yaml
   # File variables contain path, not content
   
   script:
     - cat $SERVICE_ACCOUNT_KEY  # Correct
     - echo $SERVICE_ACCOUNT_KEY  # Shows file path
   ```

### Masked Variable Rejected

**Symptom:** Error: "Variable value does not meet mask requirements"

**Solutions:**

1. **Check length requirement:**
   ```yaml
   # Must be at least 8 characters
   config:
     length: 8  # Minimum for masking
   ```

2. **Remove special characters:**
   ```yaml
   # Only base64/hex characters allowed
   config:
     charset: alphanumeric  # Safe for masking
     special: false         # No special characters
   ```

3. **No spaces allowed:**
   ```yaml
   # Single line, no spaces
   config:
     value: "NoSpacesAllowed"  # Good
     # value: "Has Spaces"      # Bad - masking fails
   ```

4. **Use file variables for complex values:**
   ```yaml
   # JSON, multiline, etc. cannot be masked
   config:
     variable_type: file  # Use file instead
     masked: false        # Disable masking
   ```

### Project/Group Not Found

**Symptom:** Error: "404 Not Found" or "Project not found"

**Solutions:**

1. **Verify project path:**
   ```yaml
   config:
     project: group/project-name  # Use full path
     # or
     project: 12345  # Use numeric project ID
   ```

2. **Find project ID:**
   ```bash
   # Using GitLab API
   curl --header "PRIVATE-TOKEN: ${GITLAB_TOKEN}" \
     "https://gitlab.com/api/v4/projects/group%2Fproject-name"
   
   # Or check in GitLab UI:
   # Project → Settings → General → Project ID
   ```

3. **Check group path:**
   ```yaml
   config:
     group: my-group  # Use group path
     # or
     group: 54321  # Use numeric group ID
   ```

4. **Verify project visibility:**
   ```bash
   # Private projects require project membership
   # Public projects accessible with token
   ```

### Environment Scope Issues

**Symptom:** Variables not available in expected environments

**Solutions:**

1. **Check scope pattern:**
   ```yaml
   # Exact match
   environment_scope: production
   
   # Wildcard patterns
   environment_scope: staging/*  # All staging environments
   environment_scope: review/*   # All review apps
   environment_scope: "*"        # All environments
   ```

2. **Verify environment name:**
   ```yaml
   # .gitlab-ci.yml
   deploy:
     environment:
       name: production  # Must match environment_scope
   ```

3. **Check scope precedence:**
   ```
   # More specific scopes take precedence
   # production > staging/* > *
   
   # If multiple scopes match, most specific wins
   ```

4. **List existing variables:**
   ```bash
   # Check what scopes are configured
   curl --header "PRIVATE-TOKEN: ${GITLAB_TOKEN}" \
     "https://gitlab.com/api/v4/projects/12345/variables"
   ```

### File Variable Issues

**Symptom:** File variable not working as expected

**Solutions:**

1. **Verify variable type:**
   ```yaml
   config:
     variable_type: file  # Must be 'file', not 'env_var'
   ```

2. **Use as file path:**
   ```yaml
   # .gitlab-ci.yml
   script:
     # Variable contains path to file
     - echo "File is at: $MY_FILE_VAR"
     - cat $MY_FILE_VAR  # Read file content
     - ls -la $MY_FILE_VAR  # Check file exists
   ```

3. **Check file permissions:**
   ```yaml
   script:
     - chmod 600 $SSH_KEY  # Set appropriate permissions
     - ssh-add $SSH_KEY
   ```

4. **Multiline content:**
   ```yaml
   # Ensure multiline content is properly formatted
   config:
     value: |
       Line 1
       Line 2
       Line 3
   ```

### Self-Managed GitLab Issues

**Symptom:** Connection errors with self-managed GitLab

**Solutions:**

1. **Verify URL format:**
   ```yaml
   providers:
     gitlab:
       auth:
         config:
           url: https://gitlab.mycompany.com  # No /api/v4 suffix
   ```

2. **Check SSL certificate:**
   ```bash
   # Test connectivity
   curl -v https://gitlab.mycompany.com/api/v4/version
   
   # If self-signed cert, may need to configure trust
   ```

3. **Verify API is accessible:**
   ```bash
   # Test API endpoint
   curl --header "PRIVATE-TOKEN: ${GITLAB_TOKEN}" \
     https://gitlab.mycompany.com/api/v4/user
   ```

4. **Check firewall rules:**
   - Ensure outbound HTTPS (443) access
   - Verify corporate proxy settings

### Debugging Tips

1. **Enable debug logging:**
   ```bash
   secretzero sync -f Secretfile.yml --log-level debug
   ```

2. **Test with dry-run:**
   ```bash
   secretzero sync -f Secretfile.yml --dry-run
   ```

3. **Verify provider connectivity:**
   ```bash
   secretzero test -f Secretfile.yml
   ```

4. **Check variable in GitLab UI:**
   - Project → Settings → CI/CD → Variables
   - Group → Settings → CI/CD → Variables

5. **Test API access:**
   ```bash
   # List project variables
   curl --header "PRIVATE-TOKEN: ${GITLAB_TOKEN}" \
     "https://gitlab.com/api/v4/projects/12345/variables"
   
   # Get specific variable
   curl --header "PRIVATE-TOKEN: ${GITLAB_TOKEN}" \
     "https://gitlab.com/api/v4/projects/12345/variables/API_KEY"
   ```

6. **Check CI/CD job logs:**
   - Look for variable-related errors
   - Check if variables are being masked
   - Verify environment scope matches

## Next Steps

- Learn about [GitHub Actions Secrets](github.md) for GitHub workflows
- Explore [Kubernetes Secrets](kubernetes.md) for container orchestration
- Review [HashiCorp Vault](vault.md) for centralized secret storage
- Check [complete examples](../../examples/index.md) for more patterns
- Read about [secret rotation strategies](../../advanced/rotation/index.md)
