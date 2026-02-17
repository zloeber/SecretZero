# GitLab CI/CD Integration

## Problem Statement

Managing secrets in GitLab CI/CD involves several pain points:

- Manual variable creation through GitLab UI is tedious
- Difficult to manage secrets across multiple projects and groups
- No standardized approach to environment-specific variables
- Tracking secret rotation and compliance is challenging
- Synchronizing secrets between projects requires manual copying

**SecretZero solves this** by providing declarative GitLab variable management with support for project variables, group variables, environment scoping, and protection levels.

## Prerequisites

- SecretZero installed with GitLab support: `pip install secretzero[cicd]`
- GitLab Personal Access Token with `api` scope
- Maintainer role (for project variables)
- Owner role (for group variables)

## Authentication Setup

### 1. Generate GitLab Personal Access Token

Create a token at [GitLab → User Settings → Access Tokens](https://gitlab.com/-/profile/personal_access_tokens):

**Required Scopes:**
- `api` - Full API access (required for reading/writing variables)

### 2. Configure Environment

```bash
export GITLAB_TOKEN=glpat-your_personal_access_token_here
```

For self-hosted GitLab:

```bash
export GITLAB_TOKEN=glpat-your_token
export GITLAB_URL=https://gitlab.mycompany.com
```

## Configuration

### Basic Project Variables

Create `Secretfile.yml`:

```yaml
version: '1.0'

metadata:
  project: my-application
  owner: backend-team

variables:
  gitlab_project: mygroup/myproject
  environment_scope: production

providers:
  gitlab:
    kind: gitlab
    auth:
      kind: token
      config:
        token: ${GITLAB_TOKEN}
        # Optional: For self-hosted GitLab
        # url: ${GITLAB_URL}

secrets:
  # API Key
  - name: api_key
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      # Local development
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true
      
      # GitLab project variable
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${gitlab_project}
          variable_name: API_KEY
          masked: true  # Hide in job logs
          protected: false  # Available to all branches

  # Database Password
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
          project: ${gitlab_project}
          variable_name: DATABASE_PASSWORD
          masked: true
          protected: true  # Only on protected branches
          environment_scope: production

  # JWT Secret
  - name: jwt_secret
    kind: random_string
    config:
      length: 64
      charset: alphanumeric
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${gitlab_project}
          variable_name: JWT_SECRET
          masked: true
          protected: true
```

### Environment Scoping

Restrict variables to specific environments:

```yaml
secrets:
  # Production API Key
  - name: api_key_prod
    kind: random_string
    config:
      length: 32
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${gitlab_project}
          variable_name: API_KEY
          environment_scope: production
          protected: true
          masked: true

  # Staging API Key
  - name: api_key_staging
    kind: random_string
    config:
      length: 32
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${gitlab_project}
          variable_name: API_KEY
          environment_scope: staging
          protected: false
          masked: true
```

### Group Variables

Share secrets across multiple projects:

```yaml
variables:
  gitlab_group: mygroup

secrets:
  - name: shared_secret
    kind: random_string
    config:
      length: 64
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          group: ${gitlab_group}
          variable_name: SHARED_SECRET
          masked: true
          protected: false
          environment_scope: "*"  # All environments
```

### File Variables

Store credentials as files in CI jobs:

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
          project: ${gitlab_project}
          variable_name: SERVICE_ACCOUNT_KEY
          variable_type: file  # Creates temp file in CI
          masked: false  # JSON cannot be masked
```

## Step-by-Step Instructions

### 1. Validate Configuration

```bash
secretzero validate

# Expected output:
# ✓ Configuration is valid
# ✓ Found 3 secrets
# ✓ GitLab provider configured correctly
```

### 2. Test Provider Connectivity

```bash
secretzero test

# Expected output:
# ✓ Testing GitLab provider...
# ✓ Authentication successful
# ✓ Project access confirmed: mygroup/myproject
# ✓ All providers ready
```

### 3. Preview Changes

```bash
secretzero sync --dry-run

# Expected output:
# [DRY RUN] Would create:
#   ✓ api_key → GitLab Variable (API_KEY) in mygroup/myproject
#   ✓ database_password → GitLab Variable (DATABASE_PASSWORD) in mygroup/myproject [protected]
#   ✓ jwt_secret → GitLab Variable (JWT_SECRET) in mygroup/myproject [protected, masked]
```

### 4. Sync Secrets to GitLab

```bash
secretzero sync

# Expected output:
# ✓ Generated api_key
# ✓ Created GitLab Variable: API_KEY (masked)
# ✓ Generated database_password
# ✓ Created GitLab Variable: DATABASE_PASSWORD (protected, masked)
# ✓ Generated jwt_secret
# ✓ Created GitLab Variable: JWT_SECRET (protected, masked)
# ✓ Updated .gitsecrets.lock
```

### 5. Verify in GitLab

Check your variables:

```bash
# Via GitLab CLI
glab variable list --repo mygroup/myproject

# Or visit:
# https://gitlab.com/mygroup/myproject/-/settings/ci_cd
# Expand "Variables" section
```

## Using Variables in GitLab CI/CD

### Basic Pipeline

```yaml
# .gitlab-ci.yml
stages:
  - deploy

deploy:
  stage: deploy
  environment:
    name: production
  script:
    - echo "API Key: $API_KEY"
    - echo "Database Password: $DATABASE_PASSWORD"
    - ./deploy.sh
  only:
    - main
```

### Environment-Specific Pipeline

```yaml
# .gitlab-ci.yml
stages:
  - deploy

deploy-staging:
  stage: deploy
  environment:
    name: staging
  variables:
    # Uses API_KEY with environment_scope: staging
    DEPLOY_ENV: staging
  script:
    - echo "Deploying to staging with API_KEY=$API_KEY"
    - ./deploy.sh staging
  only:
    - develop

deploy-production:
  stage: deploy
  environment:
    name: production
  variables:
    # Uses API_KEY with environment_scope: production
    DEPLOY_ENV: production
  script:
    - echo "Deploying to production"
    - ./deploy.sh production
  only:
    - main
```

### Using File Variables

```yaml
# .gitlab-ci.yml
deploy:
  stage: deploy
  script:
    # File variables are accessible via path stored in variable
    - cat $SERVICE_ACCOUNT_KEY
    - gcloud auth activate-service-account --key-file=$SERVICE_ACCOUNT_KEY
    - ./deploy.sh
```

## Advanced Scenarios

### Multi-Project Setup

Sync secrets to multiple projects:

```yaml
version: '1.0'

variables:
  gitlab_group: mygroup
  projects:
    - frontend
    - backend
    - api

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
      # Frontend project
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${gitlab_group}/frontend
          variable_name: API_KEY
          masked: true
      
      # Backend project
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${gitlab_group}/backend
          variable_name: API_KEY
          masked: true
      
      # API project
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${gitlab_group}/api
          variable_name: API_KEY
          masked: true
```

### Automatic Secret Rotation

Create a pipeline to rotate secrets automatically:

```yaml
# .gitlab-ci.yml
stages:
  - rotate

rotate-secrets:
  stage: rotate
  image: python:3.11
  before_script:
    - pip install secretzero[cicd]
  script:
    - secretzero rotate --force
    - secretzero sync
    - |
      git config user.name "SecretZero Bot"
      git config user.email "bot@example.com"
      git add .gitsecrets.lock
      git commit -m "chore: rotate secrets"
      git push https://oauth2:${GITLAB_TOKEN}@${CI_SERVER_HOST}/${CI_PROJECT_PATH}.git HEAD:${CI_COMMIT_REF_NAME}
  only:
    - schedules
  variables:
    GITLAB_TOKEN: $ADMIN_GITLAB_TOKEN
```

Set up a schedule:
- Go to CI/CD → Schedules
- Create new schedule: "Rotate Secrets"
- Interval: Every 90 days
- Target branch: main

### Group-Wide Secrets

Manage secrets for an entire group:

```yaml
version: '1.0'

variables:
  gitlab_group: platform-team

providers:
  gitlab:
    kind: gitlab
    auth:
      kind: token
      config:
        token: ${GITLAB_TOKEN}

secrets:
  # NPM token for all projects
  - name: npm_token
    kind: static
    config:
      default: ${NPM_TOKEN}
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          group: ${gitlab_group}
          variable_name: NPM_TOKEN
          masked: true
          environment_scope: "*"

  # Docker registry credentials
  - name: docker_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          group: ${gitlab_group}
          variable_name: DOCKER_PASSWORD
          masked: true
          environment_scope: "*"
```

### Protected vs. Unprotected Branches

Control variable access by branch protection:

```yaml
secrets:
  # Development - unprotected (all branches)
  - name: dev_api_key
    kind: random_string
    config:
      length: 32
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${gitlab_project}
          variable_name: API_KEY
          environment_scope: development
          protected: false  # Available on all branches
          masked: true

  # Production - protected (only protected branches)
  - name: prod_api_key
    kind: random_string
    config:
      length: 32
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${gitlab_project}
          variable_name: API_KEY
          environment_scope: production
          protected: true  # Only on protected branches (main, tags)
          masked: true
```

## Best Practices

### 1. Use Masked Variables for Sensitive Data

Always mask secrets to hide them in job logs:

```yaml
config:
  masked: true  # Hides value in CI logs
```

**Masking Requirements:**
- Minimum 8 characters
- No spaces
- Must match regex: `[a-zA-Z0-9_+=/@:.~-]{8,}`

### 2. Use Protected Variables for Production

Restrict production secrets to protected branches:

```yaml
config:
  protected: true  # Only on protected branches/tags
  environment_scope: production
```

In GitLab, configure protected branches:
- Settings → Repository → Protected branches
- Protect `main` and release tags

### 3. Scope Variables to Environments

Prevent variable leakage between environments:

```yaml
config:
  environment_scope: production  # Only in production jobs
```

### 4. Use Group Variables for Shared Resources

Centralize common secrets:

```yaml
targets:
  - provider: gitlab
    kind: gitlab_variable
    config:
      group: platform-team  # Accessible to all group projects
      variable_name: SHARED_SECRET
```

### 5. Use File Variables for Complex Credentials

Store JSON, certificates, or multi-line credentials:

```yaml
config:
  variable_type: file  # Creates temporary file
  masked: false  # Complex formats can't be masked
```

### 6. Track Changes in Lockfile

Commit `.gitsecrets.lock` for audit trail:

```bash
git add .gitsecrets.lock
git commit -m "chore: update GitLab variables"
```

## Troubleshooting

### Authentication Failed

**Problem**: `Error: GitLab authentication failed`

**Solutions**:

```bash
# Verify token is set
echo $GITLAB_TOKEN

# Test token manually
curl --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "https://gitlab.com/api/v4/user"

# For self-hosted GitLab
curl --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "$GITLAB_URL/api/v4/user"

# Ensure token has 'api' scope
# Regenerate at: https://gitlab.com/-/profile/personal_access_tokens
```

### Permission Denied

**Problem**: `Error: You do not have permission to set variables`

**Solutions**:

- Project variables require **Maintainer** role or higher
- Group variables require **Owner** role
- Check your access level:
  - Project: Settings → Members
  - Group: Group → Members

### Variable Not Appearing in Pipeline

**Problem**: Pipeline job can't access the variable

**Solutions**:

```yaml
# 1. Check environment scope matches
# Variable with environment_scope: production
deploy:
  environment:
    name: production  # Must match

# 2. Check if variable is protected
# Protected variables only work on protected branches
# Settings → Repository → Protected branches

# 3. Verify variable name (case-sensitive)
script:
  - echo $API_KEY  # Must match exactly

# 4. For file variables, use the path
script:
  - cat $SERVICE_ACCOUNT_KEY  # Contains file path
```

### Masked Variable Rejected

**Problem**: `Error: Variable value doesn't meet masking requirements`

**Solutions**:

```yaml
# Requirements for masked variables:
# - At least 8 characters
# - No spaces
# - Only: a-zA-Z0-9_+=/@:.~-

# Option 1: Adjust secret generation
secrets:
  - name: api_key
    kind: random_string
    config:
      length: 32  # Ensure >= 8 characters
      charset: alphanumeric  # No special characters

# Option 2: Use file variables for complex formats
targets:
  - provider: gitlab
    kind: gitlab_variable
    config:
      variable_type: file  # Files don't require masking
      masked: false
```

### Variables Not Syncing

**Problem**: `secretzero sync` completes but variables don't appear

**Solutions**:

```bash
# 1. Verify provider configuration
secretzero test

# 2. Check lockfile for sync status
cat .gitsecrets.lock

# 3. Force re-sync
secretzero sync --force

# 4. Enable debug logging
secretzero sync --verbose

# 5. Verify project path
# Must be: group/project or group/subgroup/project
```

### Rate Limiting

**Problem**: `Error: API rate limit exceeded`

**Solutions**:

```bash
# Check rate limit status
curl --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "https://gitlab.com/api/v4/user"

# Response headers show limits:
# ratelimit-limit: 2000
# ratelimit-remaining: 1500
# ratelimit-reset: 1623456789

# Wait for rate limit reset or upgrade to GitLab Premium
```

## Complete Example

Full production-ready configuration:

```yaml
version: '1.0'

metadata:
  project: production-app
  owner: platform-team
  compliance:
    - soc2

variables:
  gitlab_group: mycompany
  gitlab_project: mycompany/production-app

providers:
  gitlab:
    kind: gitlab
    auth:
      kind: token
      config:
        token: ${GITLAB_TOKEN}

policies:
  production_rotation:
    kind: rotation
    require_rotation_period: true
    max_age: 90d
    severity: error
    enabled: true

secrets:
  # Database credentials
  - name: database_url
    kind: random_password
    rotation_period: 90d
    config:
      length: 32
      special: true
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${gitlab_project}
          variable_name: DATABASE_URL
          environment_scope: production
          protected: true
          masked: true

  # API keys
  - name: stripe_api_key
    kind: static
    rotation_period: 90d
    config:
      default: ${STRIPE_API_KEY}
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${gitlab_project}
          variable_name: STRIPE_API_KEY
          environment_scope: production
          protected: true
          masked: true

  # Service account key (file variable)
  - name: gcp_service_account
    kind: static
    config:
      default: ${GCP_SERVICE_ACCOUNT_JSON}
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          project: ${gitlab_project}
          variable_name: GCP_SERVICE_ACCOUNT_KEY
          variable_type: file
          environment_scope: production
          protected: true
          masked: false

  # Shared NPM token (group level)
  - name: npm_token
    kind: static
    config:
      default: ${NPM_TOKEN}
    targets:
      - provider: gitlab
        kind: gitlab_variable
        config:
          group: ${gitlab_group}
          variable_name: NPM_TOKEN
          environment_scope: "*"
          protected: false
          masked: true
```

Deploy:

```bash
# Validate
secretzero validate

# Check compliance
secretzero policy

# Preview
secretzero sync --dry-run

# Deploy
secretzero sync

# Verify
glab variable list --repo mycompany/production-app
```

## Next Steps

- **[GitHub Actions](github-actions.md)** - Similar integration for GitHub
- **[Multi-Cloud Setup](multi-cloud.md)** - Sync secrets to cloud providers
- **[Compliance Scenarios](compliance.md)** - Implement compliance requirements
