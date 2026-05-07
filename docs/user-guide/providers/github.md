# GitHub Provider

The GitHub provider enables SecretZero to store and manage secrets in GitHub Actions. It supports token authentication for managing repository secrets and environment-specific secrets.

## Overview

The GitHub provider is ideal for:

- **CI/CD pipelines** using GitHub Actions workflows
- **Repository automation** requiring secure credential management
- **Multi-repository deployments** needing consistent secrets across repos
- **Environment-specific deployments** (production, staging, development)
- **Self-hosted GitHub** deployments that use a custom API base URL

### Supported Target Types

| Target Type | Description | Use Case |
|-------------|-------------|----------|
| `github_secret` | GitHub Actions secret (repository or environment) | Workflow credentials, API keys, deployment tokens, environment-specific secrets |

## Authentication

### Token Authentication

The GitHub provider uses Personal Access Tokens (PAT) or GitHub Apps for authentication.

```yaml
providers:
  github:
    kind: github
    auth:
      kind: token
      config:
        token: ${GITHUB_TOKEN}
```

**When to use**: All scenarios with GitHub Actions secret management.

### Creating a Personal Access Token

1. **Navigate to GitHub Settings**:
   - Go to [GitHub Settings](https://github.com/settings/tokens) → Developer settings → Personal access tokens → Tokens (classic)

2. **Generate new token (classic)**:
   - Click "Generate new token (classic)"
   - Give it a descriptive name (e.g., "SecretZero Token")
   - Set expiration (recommended: 90 days with rotation)

3. **Select scopes**:
   - `repo` - Full control of private repositories (required for repository secrets)
   - `workflow` - Update GitHub Action workflows (optional, for workflow management)

4. **Generate and save token**:
   - Click "Generate token"
   - Copy the token immediately (it won't be shown again)
   - Store securely or export as environment variable

5. **Set environment variable**:
   ```bash
   export GITHUB_TOKEN=ghp_your_token_here
   ```

### GitHub Enterprise Support

For GitHub Enterprise Server, specify a custom API URL:

```yaml
providers:
  github:
    kind: github
    auth:
      kind: token
      config:
        token: ${GITHUB_TOKEN}
        api_url: https://github.mycompany.com/api/v3
```

## Configuration

### Basic Configuration

```yaml
version: '1.0'

providers:
  github:
    kind: github
    auth:
      kind: token
      config:
        token: ${GITHUB_TOKEN}

secrets:
  - name: api_key
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      - provider: github
        kind: github_secret
        config:
          owner: myorganization
          repo: myrepo
```

### Multi-Repository Configuration

Deploy secrets to multiple repositories:

```yaml
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
      # Backend repository
      - provider: github
        kind: github_secret
        config:
          owner: myorg
          repo: backend-service
      
      # Frontend repository
      - provider: github
        kind: github_secret
        config:
          owner: myorg
          repo: frontend-app
      
      # Mobile repository
      - provider: github
        kind: github_secret
        config:
          owner: myorg
          repo: mobile-app
```

### Environment-Specific Configuration

Use environment secrets for production, staging, and development:

```yaml
providers:
  github:
    kind: github
    auth:
      kind: token
      config:
        token: ${GITHUB_TOKEN}

secrets:
  - name: database_password
    kind: random_password
    config:
      length: 32
      special: true
    targets:
      # Production environment
      - provider: github
        kind: github_secret
        config:
          owner: myorg
          repo: myapp
          environment: production
      
      # Staging environment
      - provider: github
        kind: github_secret
        config:
          owner: myorg
          repo: myapp
          environment: staging
      
      # Development environment (repository-level)
      - provider: github
        kind: github_secret
        config:
          owner: myorg
          repo: myapp
```

## Target Types

### GitHub Secret

The `github_secret` target type stores secrets in GitHub Actions. It supports both repository-level and environment-specific secrets based on configuration.

#### Configuration Options

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `owner` | string | Yes | - | Repository owner (user or organization) |
| `repo` | string | Yes | - | Repository name |
| `environment` | string | No | - | Environment name for environment-specific secrets |
| `secret_name` | string | No | secret name | Custom secret name (defaults to secret name in uppercase) |

#### Example: Repository Secret

```yaml
secrets:
  - name: api_key
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      - provider: github
        kind: github_secret
        config:
          owner: myorganization
          repo: myrepo
```

The secret will be available in workflows as `${{ secrets.API_KEY }}`.

#### Example: Custom Secret Name

```yaml
secrets:
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
          owner: myorg
          repo: myapp
          secret_name: DB_PASSWORD_PROD
```

The secret will be available as `${{ secrets.DB_PASSWORD_PROD }}`.

#### Example: Environment Secret

Environment secrets are created by adding an `environment` parameter:

```yaml
secrets:
  - name: database_url
    kind: static
    config:
      default: postgresql://prod-db.example.com:5432/myapp
    targets:
      - provider: github
        kind: github_secret
        config:
          owner: myorg
          repo: myapp
          environment: production
```

#### Example: Multi-Environment Secrets

Deploy the same secret to multiple environments:

```yaml
secrets:
  - name: api_endpoint
    kind: static
    config:
      default: https://api.example.com
    targets:
      # Production
      - provider: github
        kind: github_secret
        config:
          owner: myorg
          repo: myapp
          environment: production
          secret_name: API_ENDPOINT
      
      # Staging
      - provider: github
        kind: github_secret
        config:
          owner: myorg
          repo: myapp
          environment: staging
          secret_name: API_ENDPOINT
```

## Complete Examples

### Example 1: Simple Application Secrets

```yaml
version: '1.0'

variables:
  github_org: myorganization
  github_repo: myapp
  environment: production

providers:
  github:
    kind: github
    auth:
      kind: token
      config:
        token: ${GITHUB_TOKEN}

secrets:
  # API Key
  - name: api_key
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      - provider: github
        kind: github_secret
        config:
          owner: "{{var.github_org}}"
          repo: "{{var.github_repo}}"
  
  # Database Password
  - name: database_password
    kind: random_password
    rotation_period: 90d
    config:
      length: 32
      special: true
      exclude_characters: '"@/\`'
    targets:
      - provider: github
        kind: github_secret
        config:
          owner: "{{var.github_org}}"
          repo: "{{var.github_repo}}"
          environment: "{{var.environment}}"
  
  # JWT Signing Secret
  - name: jwt_secret
    kind: random_string
    config:
      length: 64
      charset: alphanumeric
    targets:
      - provider: github
        kind: github_secret
        config:
          owner: "{{var.github_org}}"
          repo: "{{var.github_repo}}"

metadata:
  project: "{{var.github_repo}}"
  owner: backend-team
```

### Example 2: Multi-Environment Setup

```yaml
version: '1.0'

variables:
  github_org: myorganization
  github_repo: myapp

providers:
  github:
    kind: github
    auth:
      kind: token
      config:
        token: ${GITHUB_TOKEN}

secrets:
  # Database credentials for all environments
  - name: database_password
    kind: random_password
    config:
      length: 32
      special: true
      exclude_characters: '"@/\'
    targets:
      # Production environment
      - provider: github
        kind: github_secret
        config:
          owner: "{{var.github_org}}"
          repo: "{{var.github_repo}}"
          environment: production
      
      # Staging environment
      - provider: github
        kind: github_secret
        config:
          owner: "{{var.github_org}}"
          repo: "{{var.github_repo}}"
          environment: staging
      
      # Development (repository-level)
      - provider: github
        kind: github_secret
        config:
          owner: "{{var.github_org}}"
          repo: "{{var.github_repo}}"
  
  # API endpoints (static values)
  - name: api_url
    kind: static
    config:
      default: https://api.example.com
    targets:
      # Production endpoint
      - provider: github
        kind: github_secret
        config:
          owner: "{{var.github_org}}"
          repo: "{{var.github_repo}}"
          environment: production
          secret_name: API_URL
  
  - name: api_url_staging
    kind: static
    config:
      default: https://staging-api.example.com
    targets:
      - provider: github
        kind: github_secret
        config:
          owner: "{{var.github_org}}"
          repo: "{{var.github_repo}}"
          environment: staging
          secret_name: API_URL
```

### Example 3: Multi-Repository Deployment

```yaml
version: '1.0'

variables:
  github_org: myorganization

providers:
  github:
    kind: github
    auth:
      kind: token
      config:
        token: ${GITHUB_TOKEN}

secrets:
  # Shared API key across services
  - name: external_api_key
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      # Backend service
      - provider: github
        kind: github_secret
        config:
          owner: "{{var.github_org}}"
          repo: backend-service
          environment: production
      
      # Frontend app
      - provider: github
        kind: github_secret
        config:
          owner: "{{var.github_org}}"
          repo: frontend-app
          environment: production
      
      # Worker service
      - provider: github
        kind: github_secret
        config:
          owner: "{{var.github_org}}"
          repo: worker-service
          environment: production
  
  # Service-specific secrets
  - name: database_password
    kind: random_password
    config:
      length: 32
      special: true
    targets:
      # Only backend needs database access
      - provider: github
        kind: github_secret
        config:
          owner: "{{var.github_org}}"
          repo: backend-service
          environment: production
      
      # Worker also needs database
      - provider: github
        kind: github_secret
        config:
          owner: "{{var.github_org}}"
          repo: worker-service
          environment: production
```

## PAT Permissions and Scopes

### Required Token Scopes

#### For Repository Secrets
- `repo` - Full control of private repositories
  - Grants access to create, update, and delete repository secrets
  - Required for both public and private repositories

#### For Environment Secrets
- `repo` - Full control of private repositories
  - Environment secrets require repository admin access
  - Same permissions as repository secrets

### Token Best Practices

1. **Use fine-grained tokens** when available:
   - Limit token scope to specific repositories
   - Set shorter expiration periods
   - Revoke tokens after use in CI/CD

2. **Rotate tokens regularly**:
   ```yaml
   # Document token expiration
   metadata:
     token_expires: 2024-12-31
     token_owner: devops-team
   ```

3. **Use different tokens for different purposes**:
   - Separate tokens for production and non-production
   - Different tokens per team or project
   - Dedicated tokens for automation

4. **Audit token usage**:
   - Review token activity in GitHub Settings
   - Monitor API rate limits
   - Track secret updates through lockfile

## Integration with GitHub Actions Workflows

### Using Secrets in Workflows

Once synced, secrets are available in your GitHub Actions workflows:

#### Repository Secret Usage

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Deploy with secrets
        run: |
          echo "API_KEY=${{ secrets.API_KEY }}" >> .env
          echo "DATABASE_PASSWORD=${{ secrets.DATABASE_PASSWORD }}" >> .env
          ./deploy.sh
        env:
          JWT_SECRET: ${{ secrets.JWT_SECRET }}
```

#### Environment Secret Usage

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy-prod:
    runs-on: ubuntu-latest
    environment: production  # Must specify environment
    steps:
      - uses: actions/checkout@v3
      
      - name: Deploy to production
        run: |
          echo "Deploying to production..."
          ./deploy.sh
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          API_KEY: ${{ secrets.API_KEY }}
```

### Environment Protection Rules

Combine environment secrets with protection rules:

```yaml
# .github/workflows/deploy.yml
name: Deploy with Approval

on:
  push:
    branches: [main]

jobs:
  deploy-staging:
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - name: Deploy to staging
        run: ./deploy.sh staging
        env:
          DATABASE_PASSWORD: ${{ secrets.DATABASE_PASSWORD }}
  
  deploy-production:
    needs: deploy-staging
    runs-on: ubuntu-latest
    environment: production  # Requires manual approval
    steps:
      - name: Deploy to production
        run: ./deploy.sh production
        env:
          DATABASE_PASSWORD: ${{ secrets.DATABASE_PASSWORD }}
```

Configure environment protection rules in GitHub:
1. Repository Settings → Environments → production
2. Required reviewers: Select team members
3. Wait timer: Optional deployment delay
4. Deployment branches: Limit to specific branches

## Best Practices

### 1. Use Environment Secrets for Production

```yaml
# Good: Environment-specific secrets with protection
secrets:
  - name: prod_db_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: github
        kind: github_secret
        config:
          owner: myorg
          repo: myapp
          environment: production  # Enables environment protection

# Avoid: Repository-level secrets for production
secrets:
  - name: prod_db_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: github
        kind: github_secret
        config:
          owner: myorg
          repo: myapp  # No environment protection
```

### 2. Rotate Tokens Regularly

```yaml
secrets:
  - name: api_key
    kind: random_string
    rotation_period: 90d  # Automatic rotation
    config:
      length: 32
    targets:
      - provider: github
        kind: github_secret
        config:
          owner: myorg
          repo: myapp
```

### 3. Use the Lockfile

```bash
# Generate lockfile on first sync
secretzero sync -f Secretfile.yml

# Commit lockfile to track secret lifecycle
git add .secretzero.lock
git commit -m "Update secret lockfile"

# Verify lockfile before syncing
secretzero sync -f Secretfile.yml --verify-lock
```

### 4. Implement Naming Conventions

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

### 5. Deploy to Multiple Repositories Consistently

When you need the same secret in multiple repositories, deploy it consistently:

```yaml
# Good: Deploy same secret to multiple repositories
secrets:
  - name: shared_api_key
    kind: random_string
    config:
      length: 32
    targets:
      - provider: github
        kind: github_secret
        config:
          owner: myorg
          repo: backend-service
      - provider: github
        kind: github_secret
        config:
          owner: myorg
          repo: frontend-app
      - provider: github
        kind: github_secret
        config:
          owner: myorg
          repo: worker-service

# Track with lockfile to ensure consistency
```

### 6. Audit Secret Access

```bash
# Use GitHub audit log to track secret access
# Organization Settings → Audit log → Filter by "secret"

# Monitor secret updates with lockfile
git log .secretzero.lock

# Review workflow runs that use secrets
# Actions → Select workflow → Review runs
```

### 7. Never Commit Tokens

```bash
# Add to .gitignore
echo "GITHUB_TOKEN" >> .gitignore
echo ".env" >> .gitignore
echo "*.secret" >> .gitignore

# Remove committed token
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch .env' --prune-empty --tag-name-filter cat -- --all
```

## Troubleshooting

### Authentication Failed

**Error**: `GitHub authentication failed. Check credentials and configuration.`

**Solutions**:

1. Verify token is set:
   ```bash
   echo $GITHUB_TOKEN
   ```

2. Test token with GitHub CLI:
   ```bash
   gh auth status
   # Or manually test
   curl -H "Authorization: token $GITHUB_TOKEN" \
     https://api.github.com/user
   ```

3. Check token hasn't expired:
   - Go to GitHub Settings → Developer settings → Personal access tokens
   - Verify token expiration date

4. Verify token scopes:
   ```bash
   curl -H "Authorization: token $GITHUB_TOKEN" \
     -I https://api.github.com/user | grep X-OAuth-Scopes
   ```

5. For GitHub Enterprise, verify API URL:
   ```bash
   curl -H "Authorization: token $GITHUB_TOKEN" \
     https://github.mycompany.com/api/v3/user
   ```

### Permission Denied

**Error**: `Resource not accessible by integration` or `403 Forbidden`

**Solutions**:

1. **For repository secrets**, ensure token has `repo` scope:
   ```bash
   # Check token scopes
   gh auth status
   
   # Regenerate token with correct scopes
   # Go to GitHub Settings → Developer settings → Personal access tokens
   # Select: repo (full control)
   ```

2. **For environment secrets**, ensure repository admin access:
   - Environment secrets require admin access to the repository
   - Check repository Settings → Manage access

3. Test permissions:
   ```bash
   # Test repository access
   gh api repos/myorg/myrepo/actions/secrets
   ```

### Secret Not Appearing in Workflows

**Error**: Secret is synced but not available in workflows

**Solutions**:

1. **Verify secret name** (case-sensitive):
   ```yaml
   # If secret name in SecretZero is: api_key
   # It becomes in GitHub: API_KEY (uppercase with underscores)
   
   # In workflow, use exact uppercase name:
   env:
     API_KEY: ${{ secrets.API_KEY }}  # Correct
     api_key: ${{ secrets.api_key }}  # Wrong - won't work
   ```

2. **For environment secrets**, ensure workflow specifies environment:
   ```yaml
   jobs:
     deploy:
       runs-on: ubuntu-latest
       environment: production  # Must specify environment
       steps:
         - name: Use environment secret
           run: echo ${{ secrets.DATABASE_PASSWORD }}
   ```

3. **Check secret in GitHub UI**:
   - Repository Settings → Secrets and variables → Actions
   - Verify secret exists and name matches

4. **Workflow permissions**:
   ```yaml
   # Ensure workflow has secrets access
   permissions:
     secrets: read  # May be needed in some setups
   ```

### Rate Limits

**Error**: `API rate limit exceeded` or `403 rate_limit_exceeded`

**Solutions**:

1. Check current rate limit:
   ```bash
   curl -H "Authorization: token $GITHUB_TOKEN" \
     https://api.github.com/rate_limit
   ```

2. **Authenticated requests** have higher limits:
   - Unauthenticated: 60 requests/hour
   - Authenticated: 5,000 requests/hour
   - GitHub Enterprise: Often higher limits

3. Implement backoff strategy:
   ```yaml
   # Space out secret syncs
   # Don't sync all repositories simultaneously
   ```

4. Deploy to multiple repositories efficiently:
   ```yaml
   # Batch secret deployments to minimize API calls
   # Use variables to manage multiple repositories
   ```

5. Cache SecretZero operations:
   ```bash
   # Use --dry-run to test without API calls
   secretzero sync --dry-run -f Secretfile.yml
   
   # Sync only changed secrets
   secretzero sync -f Secretfile.yml --incremental
   ```

### Secret Encryption Failed

**Error**: `Failed to encrypt secret` or `Public key not found`

**Solutions**:

1. SecretZero automatically handles encryption, but if issues occur:
   - Verify repository exists and is accessible
   - Check repository settings allow Actions

2. Test repository access:
   ```bash
   gh api repos/myorg/myrepo
   ```

3. Ensure Actions is enabled:
   - Repository Settings → Actions → General
   - Actions permissions: Allow all actions

### Environment Not Found

**Error**: `Environment does not exist`

**Solutions**:

1. **Create environment first**:
   - Repository Settings → Environments → New environment
   - Enter environment name (e.g., "production")

2. **Environment names are case-sensitive**:
   ```yaml
   # Must match exactly
   config:
     environment: production  # Must match GitHub UI
   ```

3. Create environments via GitHub CLI:
   ```bash
   # Create production environment
   gh api repos/myorg/myrepo/environments/production -X PUT
   ```

4. Verify environment exists:
   ```bash
   gh api repos/myorg/myrepo/environments
   ```

## GitHub Enterprise Support

### Configuration

```yaml
providers:
  github_enterprise:
    kind: github
    auth:
      kind: token
      config:
        token: ${GITHUB_ENTERPRISE_TOKEN}
        api_url: https://github.mycompany.com/api/v3

secrets:
  - name: api_key
    kind: random_string
    config:
      length: 32
    targets:
      - provider: github_enterprise
        kind: github_secret
        config:
          owner: myorg
          repo: myrepo
```

### API URL Format

- **GitHub Cloud**: `https://api.github.com` (default)
- **GitHub Enterprise Server**: `https://github.mycompany.com/api/v3`
- **GitHub AE**: `https://github.ae/api/v3`

### Testing Enterprise Connection

```bash
# Test API connectivity
curl -H "Authorization: token $GITHUB_ENTERPRISE_TOKEN" \
  https://github.mycompany.com/api/v3/user

# Test with SecretZero
secretzero test -f Secretfile.yml
```

### Enterprise-Specific Considerations

1. **SSL Certificates**:
   - Ensure valid SSL certificate
   - For self-signed certificates, configure trust

2. **Network Access**:
   - Verify network connectivity to enterprise server
   - Check firewall rules and proxy settings

3. **API Version**:
   - Use `/api/v3` endpoint for GitHub Enterprise Server
   - Verify API version compatibility

4. **Rate Limits**:
   - Enterprise may have different rate limits
   - Contact GitHub Enterprise admin for limits

## Cost and Limits

### GitHub Actions Usage

- **Public repositories**: Unlimited Actions minutes
- **Private repositories**: Free tier includes minutes (varies by plan)
- **Secrets**: No additional cost, included in GitHub plan

### Limits

- **Repository secrets**: Up to 100 secrets per repository
- **Environment secrets**: Up to 100 secrets per environment
- **Secret size**: Maximum 64 KB per secret
- **Secret name**: Maximum 512 characters

### Best Practices for Limits

1. Combine multiple values in JSON secrets when appropriate
2. Use environment variables for non-sensitive configuration
3. Implement secret cleanup for unused secrets
4. Plan secret naming conventions to stay within limits

## See Also

- [Providers Overview](index.md)
- [AWS Provider](aws.md)
- [Azure Provider](azure.md)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [GitHub Secrets Documentation](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [PyGithub Library](https://pygithub.readthedocs.io/)
