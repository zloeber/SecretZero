# GitHub Actions Integration

## Problem Statement

Managing secrets in GitHub Actions workflows presents several challenges:

- Manual secret creation through the GitHub UI is tedious and error-prone
- Difficult to track which secrets exist and when they were created
- No audit trail for secret rotation and updates
- Synchronizing secrets across multiple repositories is time-consuming
- No standardized way to bootstrap secrets for new projects

**SecretZero solves this** by automating GitHub Actions secret provisioning with a declarative configuration, complete audit trail, and support for repository, environment, and organization-level secrets.

## Prerequisites

- SecretZero installed with GitHub support: `pip install secretzero[cicd]`
- GitHub Personal Access Token with appropriate scopes
- Repository admin access (for repository secrets)
- Organization admin access (for organization secrets)
- Environment admin access (for environment-specific secrets)

## Authentication Setup

### 1. Generate GitHub Personal Access Token

There are two types of GitHub tokens:

#### Classic Personal Access Token (PAT)

**Limitations:**
- ❌ Cannot manage environment secrets
- ✅ Can manage repository secrets
- ✅ Can manage organization secrets

Create at [GitHub Settings → Tokens (classic)](https://github.com/settings/tokens):

**Required Scopes:**
- `repo` - For repository secrets
- `admin:org` - For organization secrets (optional)
- `workflow` - For updating workflow files (optional)

#### Fine-grained Personal Access Token (Recommended for Environments)

**Capabilities:**
- ✅ Can manage environment secrets
- ✅ Can manage repository secrets  
- ✅ Can manage organization secrets
- ✅ More granular permission control

Create at [GitHub Settings → Fine-grained tokens](https://github.com/settings/tokens?type=beta):

**Required Permissions:**
- **Actions**: Read and write (for workflow secrets)
- **Secrets**: Read and write (for managing secrets)
- **Environments**: Read and write (for environment secrets)
- **Administration**: Read and write (for repository settings)

### 2. Configure Environment

```bash
export GITHUB_TOKEN=ghp_your_personal_access_token_here
```

For GitHub Enterprise:

```bash
export GITHUB_TOKEN=ghp_your_token
export GITHUB_API_URL=https://github.mycompany.com/api/v3
```

## Configuration

### Basic Repository Secrets

Create `Secretfile.yml`:

```yaml
version: '1.0'

metadata:
  project: my-project
  owner: engineering-team

variables:
  github_org: myorganization
  github_repo: myrepo
  environment: production

providers:
  github:
    kind: github
    auth:
      kind: token
      config:
        token: ${GITHUB_TOKEN}
        # Optional: For GitHub Enterprise
        # api_url: ${GITHUB_API_URL}

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
      
      # GitHub Actions repository secret
      - provider: github
        kind: github_secret
        config:
          owner: ${github_org}
          repo: ${github_repo}
          secret_name: API_KEY

  # Database Password
  - name: database_password
    kind: random_password
    config:
      length: 32
      special: true
      exclude_characters: '"@/\`'
    targets:
      - provider: github
        kind: github_secret
        config:
          owner: ${github_org}
          repo: ${github_repo}
          secret_name: DATABASE_PASSWORD

  # JWT Secret
  - name: jwt_secret
    kind: random_string
    config:
      length: 64
      charset: alphanumeric
    targets:
      - provider: github
        kind: github_secret
        config:
          owner: ${github_org}
          repo: ${github_repo}
          secret_name: JWT_SECRET
```

### Environment-Specific Secrets

Scope secrets to GitHub environments (production, staging, etc.):

```yaml
secrets:
  # Production API Key
  - name: api_key_prod
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      - provider: github
        kind: github_secret
        config:
          owner: ${github_org}
          repo: ${github_repo}
          environment: production
          secret_name: API_KEY

  # Staging API Key
  - name: api_key_staging
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      - provider: github
        kind: github_secret
        config:
          owner: ${github_org}
          repo: ${github_repo}
          environment: staging
          secret_name: API_KEY
```

### Organization-Level Secrets

Share secrets across multiple repositories:

```yaml
secrets:
  - name: shared_api_key
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      - provider: github
        kind: github_secret
        config:
          org: ${github_org}
          secret_name: SHARED_API_KEY
          visibility: all  # Options: all, private, selected
          # For 'selected' visibility:
          # selected_repository_ids: [123456, 789012]
```

## Step-by-Step Instructions

### 1. Validate Configuration

```bash
secretzero validate

# Expected output:
# ✓ Configuration is valid
# ✓ Found 3 secrets
# ✓ GitHub provider configured correctly
```

### 2. Test Provider Connectivity

```bash
secretzero test

# Expected output:
# ✓ Testing GitHub provider...
# ✓ Authentication successful
# ✓ Repository access confirmed
# ✓ All providers ready
```

### 3. Preview Changes

```bash
secretzero sync --dry-run

# Expected output:
# [DRY RUN] Would create:
#   ✓ api_key → GitHub Secret (API_KEY) in myorganization/myrepo
#   ✓ database_password → GitHub Secret (DATABASE_PASSWORD) in myorganization/myrepo
#   ✓ jwt_secret → GitHub Secret (JWT_SECRET) in myorganization/myrepo
```

### 4. Sync Secrets to GitHub

```bash
secretzero sync

# Expected output:
# ✓ Generated api_key
# ✓ Created GitHub Secret: API_KEY
# ✓ Generated database_password
# ✓ Created GitHub Secret: DATABASE_PASSWORD
# ✓ Generated jwt_secret
# ✓ Created GitHub Secret: JWT_SECRET
# ✓ Updated .gitsecrets.lock
```

### 5. Verify in GitHub

Check your secrets:

```bash
# Via GitHub CLI
gh secret list --repo myorganization/myrepo

# Or visit:
# https://github.com/myorganization/myrepo/settings/secrets/actions
```

## Using Secrets in GitHub Actions

### Basic Workflow

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Deploy application
        env:
          API_KEY: ${{ secrets.API_KEY }}
          DATABASE_PASSWORD: ${{ secrets.DATABASE_PASSWORD }}
          JWT_SECRET: ${{ secrets.JWT_SECRET }}
        run: |
          echo "Deploying with secrets..."
          ./deploy.sh
```

### Environment-Specific Workflow

```yaml
name: Deploy to Production

on:
  release:
    types: [published]

jobs:
  deploy-production:
    runs-on: ubuntu-latest
    environment: production  # Links to environment secrets
    steps:
      - uses: actions/checkout@v4
      
      - name: Deploy to production
        env:
          API_KEY: ${{ secrets.API_KEY }}  # Uses production environment secret
        run: |
          echo "Deploying to production..."
          ./deploy.sh production
```

### Using Organization Secrets

```yaml
name: Build

on: [push]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Build with shared secrets
        env:
          SHARED_API_KEY: ${{ secrets.SHARED_API_KEY }}  # Organization secret
        run: |
          echo "Building..."
          npm run build
```

## Advanced Scenarios

### Multi-Repository Setup

Sync secrets to multiple repositories:

```yaml
version: '1.0'

variables:
  github_org: myorganization
  repositories:
    - frontend
    - backend
    - api

providers:
  github:
    kind: github
    auth:
      kind: token
      config:
        token: ${GITHUB_TOKEN}

secrets:
  - name: shared_api_key
    kind: random_string
    config:
      length: 32
    targets:
      # Sync to frontend repository
      - provider: github
        kind: github_secret
        config:
          owner: ${github_org}
          repo: frontend
          secret_name: API_KEY
      
      # Sync to backend repository
      - provider: github
        kind: github_secret
        config:
          owner: ${github_org}
          repo: backend
          secret_name: API_KEY
      
      # Sync to API repository
      - provider: github
        kind: github_secret
        config:
          owner: ${github_org}
          repo: api
          secret_name: API_KEY
```

### Automatic Secret Rotation in CI/CD

Create a workflow to rotate secrets automatically:

```yaml
# .github/workflows/rotate-secrets.yml
name: Rotate Secrets

on:
  schedule:
    # Run every 90 days
    - cron: '0 0 */90 * *'
  workflow_dispatch:  # Allow manual trigger

jobs:
  rotate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install SecretZero
        run: pip install secretzero[cicd]
      
      - name: Rotate secrets
        env:
          GITHUB_TOKEN: ${{ secrets.ADMIN_GITHUB_TOKEN }}
        run: |
          secretzero rotate --force
          secretzero sync
      
      - name: Commit lockfile changes
        run: |
          git config user.name "SecretZero Bot"
          git config user.email "bot@example.com"
          git add .gitsecrets.lock
          git commit -m "chore: rotate secrets"
          git push
```

### Compliance and Audit Trail

Track secret lifecycle with rotation policies:

```yaml
version: '1.0'

metadata:
  project: secure-app
  compliance:
    - soc2
    - iso27001

policies:
  critical_rotation:
    kind: rotation
    require_rotation_period: true
    max_age: 90d
    severity: error
    enabled: true

secrets:
  - name: production_api_key
    kind: random_string
    rotation_period: 90d  # Enforce 90-day rotation
    config:
      length: 32
    targets:
      - provider: github
        kind: github_secret
        config:
          owner: myorganization
          repo: production-app
          environment: production
          secret_name: API_KEY
```

Check compliance:

```bash
secretzero policy --fail-on-warning
secretzero rotate --dry-run  # See which secrets need rotation
```

### Bootstrap New Projects

Automate secret setup for new projects:

```bash
#!/bin/bash
# bootstrap-project.sh

PROJECT_NAME=$1
GITHUB_ORG="myorganization"

# Create repository
gh repo create "$GITHUB_ORG/$PROJECT_NAME" --private

# Generate Secretfile
cat > Secretfile.yml << EOF
version: '1.0'

variables:
  github_org: $GITHUB_ORG
  github_repo: $PROJECT_NAME

providers:
  github:
    kind: github
    auth:
      kind: token
      config:
        token: \${GITHUB_TOKEN}

secrets:
  - name: api_key
    kind: random_string
    config:
      length: 32
    targets:
      - provider: github
        kind: github_secret
        config:
          owner: \${github_org}
          repo: \${github_repo}
          secret_name: API_KEY
EOF

# Provision secrets
secretzero sync

echo "✓ Project $PROJECT_NAME created with secrets provisioned"
```

## Best Practices

### 1. Use Environment Secrets for Production

Protect production secrets with environment protection rules:

```yaml
targets:
  - provider: github
    kind: github_secret
    config:
      owner: myorg
      repo: myrepo
      environment: production  # Requires environment approval rules
      secret_name: API_KEY
```

In GitHub, configure environment protection rules:
- Settings → Environments → production → Protection rules
- Required reviewers
- Wait timer
- Deployment branches

### 2. Rotate Secrets Regularly

Implement automatic rotation:

```yaml
secrets:
  - name: api_key
    kind: random_string
    rotation_period: 90d  # Rotate every 90 days
    config:
      length: 32
    targets:
      - provider: github
        kind: github_secret
        config:
          owner: myorg
          repo: myrepo
          secret_name: API_KEY
```

### 3. Use Organization Secrets for Shared Resources

Centralize shared secrets:

```yaml
secrets:
  - name: npm_token
    kind: static
    config:
      default: ${NPM_TOKEN}
    targets:
      - provider: github
        kind: github_secret
        config:
          org: myorganization
          visibility: private  # All private repos
          secret_name: NPM_TOKEN
```

### 4. Track Changes in Lockfile

Commit `.gitsecrets.lock` for audit trail:

```bash
git add .gitsecrets.lock
git commit -m "chore: update secret rotation timestamps"
```

### 5. Use Descriptive Secret Names

Follow naming conventions:

```yaml
secrets:
  - name: production_database_password  # Clear and descriptive
    targets:
      - provider: github
        kind: github_secret
        config:
          secret_name: PRODUCTION_DATABASE_PASSWORD  # Matches convention
```

### 6. Never Commit GitHub Token

Add to `.gitignore`:

```gitignore
# Never commit tokens
.env
.env.*
**/*token*
**/*secret*

# Commit lockfile for tracking
!.gitsecrets.lock
```

## Troubleshooting

### Environment Secrets Fail with "Resource not accessible by personal access token"

**Problem**: `Failed to create environment secret: Resource not accessible by personal access token: 403`

**Cause**: Classic Personal Access Tokens (PATs) cannot manage environment secrets due to GitHub API limitations.

**Solutions**:

**Option 1: Use Fine-grained PAT (Recommended)**

```bash
# 1. Create Fine-grained PAT at:
#    https://github.com/settings/tokens?type=beta

# 2. Grant these permissions:
#    - Actions: Read and write
#    - Secrets: Read and write
#    - Environments: Read and write

# 3. Set the new token
export GITHUB_TOKEN=github_pat_your_fine_grained_token
```

**Option 2: Use Repository-level Secrets Instead**

```yaml
# Remove environment field from Secretfile
secrets:
  - name: api_key
    targets:
      - provider: github
        kind: github_secret
        config:
          owner: myorg
          repo: myrepo
          # Remove this line:
          # environment: production
```

**Verification**:

```bash
# Check what type of token you have
secretzero providers token-info

# Classic PAT output shows:
#   "No OAuth scopes found (may be a classic PAT)"
#   
# Fine-grained PAT output shows:
#   "OAuth Scopes: repo, workflow, ..."
```

### Authentication Failed

**Problem**: `Error: GitHub authentication failed`

**Solutions**:

```bash
# Verify token is set
echo $GITHUB_TOKEN

# Check token scopes
gh auth status

# Regenerate token with correct scopes
# Visit: https://github.com/settings/tokens

# For GitHub Enterprise, verify API URL
export GITHUB_API_URL=https://github.mycompany.com/api/v3
```

### Permission Denied

**Problem**: `Error: You do not have permission to set secrets`

**Solutions**:

- Repository secrets require **admin** access to the repository
- Organization secrets require **owner** role in the organization
- Environment secrets require **admin** access to the repository

### Secret Not Appearing in Workflow

**Problem**: Workflow can't access the secret

**Solutions**:

```yaml
# 1. Check secret name matches exactly (case-sensitive)
env:
  API_KEY: ${{ secrets.API_KEY }}  # Must match GitHub secret name

# 2. For environment secrets, specify environment in job
jobs:
  deploy:
    environment: production  # Required to access environment secrets
    steps:
      - name: Use secret
        env:
          API_KEY: ${{ secrets.API_KEY }}

# 3. Verify secret visibility for organization secrets
# Settings → Secrets → Organization secrets → SHARED_KEY → Repository access
```

### Rate Limiting

**Problem**: `Error: API rate limit exceeded`

**Solutions**:

```bash
# Use authenticated requests (increases rate limit)
export GITHUB_TOKEN=your_token

# Check current rate limit
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/rate_limit

# Wait for rate limit reset or use multiple tokens
```

### Secrets Not Syncing

**Problem**: `secretzero sync` completes but secrets don't appear

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
  github_org: mycompany
  github_repo: production-app

providers:
  github:
    kind: github
    auth:
      kind: token
      config:
        token: ${GITHUB_TOKEN}

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
      - provider: github
        kind: github_secret
        config:
          owner: ${github_org}
          repo: ${github_repo}
          environment: production
          secret_name: DATABASE_URL

  # API keys
  - name: stripe_api_key
    kind: static
    rotation_period: 90d
    config:
      default: ${STRIPE_API_KEY}
    targets:
      - provider: github
        kind: github_secret
        config:
          owner: ${github_org}
          repo: ${github_repo}
          environment: production
          secret_name: STRIPE_API_KEY

  # JWT signing key
  - name: jwt_secret
    kind: random_string
    rotation_period: 90d
    config:
      length: 64
      charset: base64
    targets:
      - provider: github
        kind: github_secret
        config:
          owner: ${github_org}
          repo: ${github_repo}
          environment: production
          secret_name: JWT_SECRET_KEY
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
gh secret list --repo mycompany/production-app
```

## Next Steps

- **[GitLab CI/CD](gitlab-cicd.md)** - Similar integration for GitLab
- **[Multi-Cloud Setup](multi-cloud.md)** - Sync secrets to cloud providers
- **[Compliance Scenarios](compliance.md)** - Implement compliance requirements
