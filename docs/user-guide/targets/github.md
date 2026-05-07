# GitHub Actions Secrets

GitHub Actions secrets targets allow you to securely store secrets in GitHub for use in CI/CD workflows. Secrets can be stored at repository, environment, or organization levels, providing flexible access control for different deployment scenarios.

## Overview

GitHub Actions provides three types of secrets:

- **Repository Secrets** - Available to all workflows in a repository
- **Environment Secrets** - Scoped to specific deployment environments (production, staging, etc.)
- **Organization Secrets** - Shared across multiple repositories in an organization

SecretZero integrates with GitHub's API to automatically create and update these secrets, handling encryption transparently using GitHub's public key infrastructure.

!!! warning "Secret Retrieval Limitation"
    GitHub's API does not allow retrieving secret values for security reasons. Once a secret is stored, it cannot be read back via the API. This is a GitHub security feature, not a SecretZero limitation.

## Use Cases

- **CI/CD Pipelines** - Automate deployment credentials for GitHub Actions workflows
- **Multi-Environment Deployments** - Manage separate secrets for production, staging, and development
- **Organization-Wide Credentials** - Share API keys and tokens across multiple repositories
- **Secret Rotation** - Regularly update secrets across all repositories from a single source
- **Infrastructure as Code** - Version control secret configurations without exposing values

## Prerequisites

### Required Dependencies

GitHub support requires the PyGithub library:

```bash
# Install with GitHub support
pip install secretzero[github]

# Or install PyGithub separately
pip install PyGithub
```

### GitHub Token Generation

You need a Personal Access Token (PAT) with appropriate permissions:

1. **GitHub.com:**
   - Navigate to: Settings → Developer settings → Personal access tokens → Tokens (classic)
   - Click "Generate new token (classic)"
   - Select required scopes (see below)
   - Generate and save the token securely

2. **GitHub Enterprise:**
   - Navigate to your GitHub Enterprise instance settings
   - Follow similar steps as GitHub.com
   - Note your GitHub Enterprise API URL

### Token Permissions and Scopes

Required scopes depend on the secret types you'll manage:

| Secret Type | Required Scope | Permission Level |
|-------------|----------------|------------------|
| Repository secrets | `repo` | Admin access to repository |
| Environment secrets | `repo` | Admin access to repository |
| Organization secrets | `admin:org` | Owner or admin in organization |

**Recommended token configuration:**
```
repo (Full control of private repositories)
├── repo:status
├── repo_deployment
├── public_repo
└── repo:invite

admin:org (Full control of orgs and teams)
├── write:org
├── read:org
└── manage_runners:org (optional, for self-hosted runners)
```

!!! tip "Fine-Grained Tokens"
    GitHub's fine-grained personal access tokens provide more granular control. For repository secrets, grant "Secrets" permission with read/write access.

## Target Types

SecretZero provides two target types for GitHub Actions secrets:

### GitHubSecretTarget

Stores secrets at repository or environment level.

**Provider Configuration:**
```yaml
providers:
  github:
    kind: github
    auth:
      kind: token
      config:
        token: ${GITHUB_TOKEN}
        # Optional: For GitHub Enterprise
        # api_url: https://github.mycompany.com/api/v3
```

### GitHubOrganizationSecretTarget

Stores secrets at organization level, shared across repositories.

**Provider Configuration:**
```yaml
providers:
  github:
    kind: github
    auth:
      kind: token
      config:
        token: ${GITHUB_TOKEN}
```

## Configuration Options

### Repository Secrets

Store secrets available to all workflows in a repository.

**Configuration:**
```yaml
targets:
  - provider: github
    kind: github_secret
    config:
      owner: username-or-org
      repo: repository-name
```

**Options:**

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| `owner` | string | Yes | Repository owner (username or organization) |
| `repo` | string | Yes | Repository name |

### Environment Secrets

Store secrets scoped to specific deployment environments.

**Configuration:**
```yaml
targets:
  - provider: github
    kind: github_secret
    config:
      owner: username-or-org
      repo: repository-name
      environment: production
```

**Options:**

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| `owner` | string | Yes | Repository owner (username or organization) |
| `repo` | string | Yes | Repository name |
| `environment` | string | Yes | Environment name (e.g., production, staging, development) |

**Environment Features:**
- Environment-specific protection rules
- Required reviewers before deployment
- Wait timers for staged rollouts
- Branch restrictions for environment access

### Organization Secrets

Store secrets shared across multiple repositories.

**Configuration:**
```yaml
targets:
  - provider: github
    kind: github_organization_secret
    config:
      org: organization-name
      visibility: all
```

**Options:**

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `org` | string | Yes | - | Organization name |
| `visibility` | string | No | `all` | Secret visibility: `all`, `private`, or `selected` |
| `selected_repository_ids` | list | No | `[]` | List of repository IDs (required if visibility is `selected`) |

**Visibility Options:**
- `all` - Available to all repositories in the organization
- `private` - Available only to private repositories
- `selected` - Available only to specified repositories (requires `selected_repository_ids`)

!!! tip "Finding Repository IDs"
    Use the GitHub API or CLI to find repository IDs:
    ```bash
    gh api /repos/owner/repo --jq '.id'
    ```

## Complete Examples

### Basic Repository Secret

Store a simple API key in a repository:

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
  - name: API_KEY
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      - provider: github
        kind: github_secret
        config:
          owner: myusername
          repo: myapp
```

### Environment-Specific Secrets

Manage separate credentials for production and staging:

```yaml
version: '1.0'

variables:
  repo_owner: mycompany
  repo_name: webapp

providers:
  github:
    kind: github
    auth:
      kind: token
      config:
        token: ${GITHUB_TOKEN}

secrets:
  # Production database password
  - name: DATABASE_PASSWORD
    kind: random_password
    config:
      length: 32
      special: true
      exclude_characters: '"@/\`'
    targets:
      - provider: github
        kind: github_secret
        config:
          owner: ${repo_owner}
          repo: ${repo_name}
          environment: production

  # Staging database password
  - name: DATABASE_PASSWORD
    kind: random_password
    config:
      length: 32
      special: true
      exclude_characters: '"@/\`'
    targets:
      - provider: github
        kind: github_secret
        config:
          owner: ${repo_owner}
          repo: ${repo_name}
          environment: staging

  # API keys for both environments
  - name: STRIPE_API_KEY
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      - provider: github
        kind: github_secret
        config:
          owner: ${repo_owner}
          repo: ${repo_name}
          environment: production
      
      - provider: github
        kind: github_secret
        config:
          owner: ${repo_owner}
          repo: ${repo_name}
          environment: staging

  # JWT secret (repository-level, shared across environments)
  - name: JWT_SECRET
    kind: random_string
    config:
      length: 64
      charset: base64
    targets:
      - provider: github
        kind: github_secret
        config:
          owner: ${repo_owner}
          repo: ${repo_name}
```

### Organization-Wide Secrets

Share secrets across multiple repositories:

```yaml
version: '1.0'

variables:
  organization: mycompany

providers:
  github:
    kind: github
    auth:
      kind: token
      config:
        token: ${GITHUB_TOKEN}

secrets:
  # Shared Docker registry credentials
  - name: DOCKER_USERNAME
    kind: static
    config:
      value: mycompany-ci
    targets:
      - provider: github
        kind: github_organization_secret
        config:
          org: ${organization}
          visibility: all

  - name: DOCKER_PASSWORD
    kind: random_password
    config:
      length: 32
      special: false
    targets:
      - provider: github
        kind: github_organization_secret
        config:
          org: ${organization}
          visibility: all

  # NPM registry token for private packages
  - name: NPM_TOKEN
    kind: random_string
    config:
      length: 36
      charset: alphanumeric
    targets:
      - provider: github
        kind: github_organization_secret
        config:
          org: ${organization}
          visibility: private

  # Cloud provider credentials for deployment
  - name: AWS_ACCESS_KEY_ID
    kind: static
    config:
      value: ${AWS_ACCESS_KEY_ID}
    targets:
      - provider: github
        kind: github_organization_secret
        config:
          org: ${organization}
          visibility: all

  - name: AWS_SECRET_ACCESS_KEY
    kind: static
    config:
      value: ${AWS_SECRET_ACCESS_KEY}
    targets:
      - provider: github
        kind: github_organization_secret
        config:
          org: ${organization}
          visibility: all
```

### Multi-Repository Deployment

Deploy secrets to multiple repositories with different configurations:

```yaml
version: '1.0'

variables:
  org: mycompany
  repos:
    - frontend
    - backend
    - mobile-app

providers:
  github:
    kind: github
    auth:
      kind: token
      config:
        token: ${GITHUB_TOKEN}

secrets:
  # Shared API endpoint
  - name: API_ENDPOINT
    kind: static
    config:
      value: https://api.mycompany.com
    targets:
      - provider: github
        kind: github_secret
        config:
          owner: ${org}
          repo: frontend
      
      - provider: github
        kind: github_secret
        config:
          owner: ${org}
          repo: backend
      
      - provider: github
        kind: github_secret
        config:
          owner: ${org}
          repo: mobile-app

  # Frontend-specific secrets
  - name: SENTRY_DSN_FRONTEND
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      - provider: github
        kind: github_secret
        config:
          owner: ${org}
          repo: frontend

  # Backend-specific secrets
  - name: DATABASE_URL
    kind: static
    config:
      value: ${DATABASE_URL}
    targets:
      - provider: github
        kind: github_secret
        config:
          owner: ${org}
          repo: backend
          environment: production

  # Mobile-specific secrets
  - name: FIREBASE_CONFIG
    kind: static
    config:
      value: ${FIREBASE_CONFIG}
    targets:
      - provider: github
        kind: github_secret
        config:
          owner: ${org}
          repo: mobile-app
```

### Selected Repository Access

Grant organization secrets to specific repositories only:

```yaml
version: '1.0'

variables:
  organization: mycompany
  # Repository IDs can be found using: gh api /repos/owner/repo --jq '.id'
  production_repos:
    - 123456789  # mycompany/api-production
    - 234567890  # mycompany/web-production
    - 345678901  # mycompany/worker-production

providers:
  github:
    kind: github
    auth:
      kind: token
      config:
        token: ${GITHUB_TOKEN}

secrets:
  # Production-only database credentials
  - name: PROD_DB_PASSWORD
    kind: random_password
    config:
      length: 32
      special: true
    targets:
      - provider: github
        kind: github_organization_secret
        config:
          org: ${organization}
          visibility: selected
          selected_repository_ids: ${production_repos}

  # Production API keys
  - name: PROD_API_KEY
    kind: random_string
    config:
      length: 64
      charset: base64
    targets:
      - provider: github
        kind: github_organization_secret
        config:
          org: ${organization}
          visibility: selected
          selected_repository_ids: ${production_repos}
```

## Using Secrets in GitHub Actions Workflows

Once secrets are stored in GitHub, they can be accessed in workflow files.

### Repository Secrets

```yaml
name: Deploy Application

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Configure environment
        run: |
          echo "API_KEY=${{ secrets.API_KEY }}" >> .env
          echo "JWT_SECRET=${{ secrets.JWT_SECRET }}" >> .env
      
      - name: Deploy
        run: ./deploy.sh
```

### Environment Secrets

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy-staging:
    runs-on: ubuntu-latest
    environment: staging
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Deploy to staging
        env:
          DATABASE_PASSWORD: ${{ secrets.DATABASE_PASSWORD }}
          STRIPE_API_KEY: ${{ secrets.STRIPE_API_KEY }}
        run: ./deploy.sh staging

  deploy-production:
    runs-on: ubuntu-latest
    environment: production
    needs: deploy-staging
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Deploy to production
        env:
          DATABASE_PASSWORD: ${{ secrets.DATABASE_PASSWORD }}
          STRIPE_API_KEY: ${{ secrets.STRIPE_API_KEY }}
        run: ./deploy.sh production
```

### Organization Secrets

```yaml
name: Build and Push Docker Image

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Log in to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}
      
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          push: true
          tags: mycompany/myapp:latest
```

### Multiple Environments with Matrix

```yaml
name: Deploy to Multiple Environments

on:
  workflow_dispatch:
    inputs:
      environment:
        description: 'Environment to deploy'
        required: true
        type: choice
        options:
          - development
          - staging
          - production

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: ${{ github.event.inputs.environment }}
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Deploy to ${{ github.event.inputs.environment }}
        env:
          DATABASE_PASSWORD: ${{ secrets.DATABASE_PASSWORD }}
          API_KEY: ${{ secrets.API_KEY }}
        run: |
          echo "Deploying to ${{ github.event.inputs.environment }}"
          ./deploy.sh ${{ github.event.inputs.environment }}
```

## Best Practices

### 1. Use Environment Protection

Configure environment protection rules for production secrets:

```yaml
# Repository Settings → Environments → production

# Protection rules:
- Required reviewers: 2
- Wait timer: 5 minutes
- Allowed branches: main, release/*
- Environment secrets: DATABASE_PASSWORD, API_KEY
```

This ensures:
- Manual approval before production deployments
- Time for rollback if issues detected
- Restricted branch access to production

### 2. Prefer OIDC Over Static Credentials

For cloud providers, use OpenID Connect instead of static credentials:

```yaml
# Don't store cloud credentials as secrets
# Instead, configure OIDC trust relationships

name: Deploy to AWS

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/GitHubActions
          aws-region: us-east-1
      
      - name: Deploy
        run: ./deploy.sh
```

**Benefits:**
- No long-lived credentials
- Automatic token rotation
- Audit trail via cloud provider logs
- Reduced secret sprawl

### 3. Rotate Secrets Regularly

Automate secret rotation with SecretZero:

```bash
# Rotate secrets monthly via cron job
0 0 1 * * cd /opt/secretzero && secretzero sync -f Secretfile.yml

# Or use GitHub Actions workflow
name: Rotate Secrets
on:
  schedule:
    - cron: '0 0 1 * *'  # Monthly
  workflow_dispatch:

jobs:
  rotate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup SecretZero
        run: pip install secretzero[github]
      
      - name: Rotate secrets
        env:
          GITHUB_TOKEN: ${{ secrets.ADMIN_GITHUB_TOKEN }}
        run: secretzero sync -f Secretfile.yml
```

### 4. Use Descriptive Secret Names

Follow naming conventions:

```yaml
# Good: Clear purpose and scope
DATABASE_PASSWORD
AWS_ACCESS_KEY_ID
STRIPE_API_KEY_PRODUCTION
SENTRY_DSN_FRONTEND

# Bad: Ambiguous or unclear
PASSWORD
KEY
SECRET
TOKEN
```

### 5. Separate Secrets by Environment

Don't share secrets across environments:

```yaml
# Good: Environment-specific
secrets:
  - name: DATABASE_PASSWORD
    targets:
      - config:
          environment: production
  
  - name: DATABASE_PASSWORD
    targets:
      - config:
          environment: staging

# Bad: Shared across environments
secrets:
  - name: DATABASE_PASSWORD
    targets:
      - config:
          owner: mycompany
          repo: myapp
```

### 6. Document Secret Requirements

Maintain documentation of required secrets:

```yaml
# secrets.md
# Required Secrets

## Repository Secrets
- `API_KEY` - Third-party API authentication
- `JWT_SECRET` - JWT token signing key

## Environment Secrets (production)
- `DATABASE_PASSWORD` - Production database password
- `STRIPE_API_KEY` - Production Stripe API key

## Organization Secrets
- `DOCKER_USERNAME` - Docker Hub username
- `DOCKER_PASSWORD` - Docker Hub password
```

### 7. Use the Lockfile

Track secret changes with SecretZero's lockfile:

```yaml
# Commit .secretzero.lock to track secret metadata
git add .secretzero.lock
git commit -m "Update secret configurations"
```

**Benefits:**
- Audit trail of secret changes
- Prevent accidental updates
- Coordinate updates across team

### 8. Implement Least Privilege

Grant minimal permissions:

```yaml
# Organization secrets: Use 'selected' visibility
visibility: selected
selected_repository_ids: [123456]  # Only repositories that need it

# Repository secrets: Use environment secrets when possible
environment: production  # Restricted to production deployments

# Token permissions: Grant minimum scopes
# Don't grant admin:org if only repo access needed
```

## Security Considerations

### Secret Scanning

GitHub automatically scans for accidentally committed secrets:

```yaml
# .github/secret_scanning.yml
# Additional patterns to detect

patterns:
  - name: Custom API Key
    pattern: 'mycompany_key_[a-zA-Z0-9]{32}'
    description: MyCompany API keys
```

**Best practices:**
- Review secret scanning alerts immediately
- Rotate compromised secrets within 1 hour
- Update SecretZero configurations if secrets leaked
- Investigate how secret was exposed

### Audit Logs

Monitor secret access in GitHub audit logs:

1. **Organization Audit Log:**
   - Settings → Organization → Audit log
   - Filter by `action:org.create_actions_secret`
   - Review who accessed secrets

2. **Automated Monitoring:**
   ```bash
   # Export audit logs for analysis
   gh api /orgs/mycompany/audit-log \
     --jq '.[] | select(.action | contains("secret"))' \
     > secret_audit.json
   ```

3. **Alert on Suspicious Activity:**
   - New secrets created outside SecretZero
   - Secrets accessed from unusual IP addresses
   - Excessive secret modifications

### Secret Encryption

GitHub handles secret encryption automatically:

- Secrets encrypted at rest using AES-256-GCM
- Encryption keys rotated regularly by GitHub
- Secrets decrypted only during workflow execution
- No plaintext storage in GitHub's systems

**SecretZero's role:**
1. Generates secret values
2. Fetches repository public key via API
3. Encrypts secret using libsodium (sealed box)
4. Sends encrypted value to GitHub
5. GitHub stores encrypted secret

### Environment Protection

Configure environment protection for sensitive deployments:

```yaml
# Repository Settings → Environments → production

# Required reviewers
required_reviewers:
  - security-team
  - ops-team

# Wait timer
wait_timer: 300  # 5 minutes

# Deployment branches
deployment_branches:
  custom_branches:
    - main
    - release/*

# Secrets
secrets:
  - DATABASE_PASSWORD
  - API_KEY
```

### Network Restrictions

Limit workflow execution:

```yaml
# Only allow workflows from specific IPs
# (GitHub Enterprise only)

name: Secure Deploy
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: self-hosted  # Use self-hosted runner in VPN
    
    steps:
      - name: Deploy
        run: ./deploy.sh
```

### Webhook Security

Secure webhooks that might trigger workflows:

```yaml
name: Webhook Triggered Deploy

on:
  repository_dispatch:
    types: [deploy]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
      - name: Verify webhook signature
        env:
          WEBHOOK_SECRET: ${{ secrets.WEBHOOK_SECRET }}
        run: |
          # Verify HMAC signature
          ./verify_signature.sh
      
      - name: Deploy if verified
        run: ./deploy.sh
```

## Troubleshooting

### Authentication Failed

**Symptom:** Error: "Bad credentials" or "401 Unauthorized"

**Solutions:**

1. **Verify token is valid:**
   ```bash
   # Test authentication
   curl -H "Authorization: token ${GITHUB_TOKEN}" \
     https://api.github.com/user
   ```

2. **Check token hasn't expired:**
   - Personal access tokens can expire
   - Regenerate if expired

3. **Verify token has correct scopes:**
   ```bash
   # Check token scopes
   curl -I -H "Authorization: token ${GITHUB_TOKEN}" \
     https://api.github.com/user | grep x-oauth-scopes
   ```

4. **For GitHub Enterprise, verify API URL:**
   ```yaml
   providers:
     github:
       auth:
         config:
           token: ${GITHUB_TOKEN}
           api_url: https://github.company.com/api/v3  # Correct URL
   ```

### Permission Denied

**Symptom:** Error: "Resource not accessible by integration" or "403 Forbidden"

**Solutions:**

1. **Repository secrets - verify repo access:**
   - Token owner must have admin access to repository
   - Required scope: `repo`

2. **Organization secrets - verify org permissions:**
   - Token owner must be organization owner or have admin rights
   - Required scope: `admin:org`

3. **Environment secrets - verify environment access:**
   - Repository admins can manage environment secrets
   - Environments must exist before adding secrets

4. **Check organization SSO:**
   ```bash
   # If using SSO, authorize token
   # GitHub → Settings → Applications → Authorized OAuth Apps
   # Click "Authorize" next to your organization
   ```

### Secret Not Appearing in Workflows

**Symptom:** Secret is created but `${{ secrets.SECRET_NAME }}` is empty

**Solutions:**

1. **Verify secret name matches exactly:**
   ```yaml
   # Secret names are case-sensitive
   secrets:
     - name: API_KEY  # Must use API_KEY, not api_key
   
   # In workflow:
   ${{ secrets.API_KEY }}  # Must match exactly
   ```

2. **For environment secrets, specify environment:**
   ```yaml
   jobs:
     deploy:
       environment: production  # Required for environment secrets
       steps:
         - name: Use secret
           env:
             PASSWORD: ${{ secrets.DATABASE_PASSWORD }}
   ```

3. **Check organization secret visibility:**
   ```yaml
   # If visibility: selected, repository must be in selected_repository_ids
   config:
     visibility: selected
     selected_repository_ids:
       - 123456  # Must include current repository ID
   ```

4. **Verify secret was created successfully:**
   ```bash
   # Check repository secrets
   gh secret list --repo owner/repo
   
   # Check organization secrets
   gh secret list --org organization
   ```

### Token Scope Issues

**Symptom:** Some operations work, others fail with permission errors

**Solutions:**

1. **Audit current scopes:**
   ```bash
   curl -I -H "Authorization: token ${GITHUB_TOKEN}" \
     https://api.github.com/user \
     | grep x-oauth-scopes
   ```

2. **Required scopes by operation:**
   ```
   Repository secrets:    repo
   Environment secrets:   repo
   Organization secrets:  admin:org
   Read repositories:     repo (or public_repo for public only)
   ```

3. **Regenerate token with correct scopes:**
   - GitHub → Settings → Developer settings → Personal access tokens
   - Delete old token
   - Create new token with all required scopes

### Repository Not Found

**Symptom:** Error: "Not Found" or "404" for repository operations

**Solutions:**

1. **Verify repository path:**
   ```yaml
   config:
     owner: mycompany  # Organization or username
     repo: myrepo      # Repository name (not URL)
   ```

2. **Check repository visibility:**
   - Private repositories require `repo` scope
   - Public repositories require `public_repo` scope minimum

3. **Verify organization membership:**
   ```bash
   # Check if user is org member
   gh api /orgs/mycompany/members/myusername
   ```

### Environment Not Found

**Symptom:** Error: "Environment not found" when creating environment secrets

**Solutions:**

1. **Create environment first:**
   - Go to repository Settings → Environments
   - Click "New environment"
   - Name must match exactly (case-sensitive)

2. **Or create via API:**
   ```bash
   gh api -X PUT /repos/owner/repo/environments/production \
     -f wait_timer=0 \
     -f prevent_self_review=false
   ```

3. **Then sync secrets:**
   ```bash
   secretzero sync -f Secretfile.yml
   ```

### Rate Limiting

**Symptom:** Error: "API rate limit exceeded"

**Solutions:**

1. **Check rate limit status:**
   ```bash
   curl -H "Authorization: token ${GITHUB_TOKEN}" \
     https://api.github.com/rate_limit
   ```

2. **Authenticated requests have higher limits:**
   - Unauthenticated: 60 requests/hour
   - Authenticated: 5,000 requests/hour
   - GitHub Enterprise: Often higher limits

3. **Implement exponential backoff:**
   - SecretZero handles this automatically
   - Wait for rate limit reset if needed

4. **Batch operations when possible:**
   ```bash
   # Sync all secrets at once instead of individually
   secretzero sync -f Secretfile.yml
   ```

### GitHub Enterprise Connectivity

**Symptom:** Connection errors with GitHub Enterprise

**Solutions:**

1. **Verify API URL format:**
   ```yaml
   providers:
     github:
       auth:
         config:
           api_url: https://github.company.com/api/v3
           # Note: Includes /api/v3 suffix
   ```

2. **Check SSL certificate:**
   ```bash
   # Test connectivity
   curl -v https://github.company.com/api/v3
   
   # If self-signed cert, may need to configure trust
   ```

3. **Verify firewall rules:**
   - Ensure outbound HTTPS (443) access
   - Check corporate proxy settings

4. **Test with curl first:**
   ```bash
   curl -H "Authorization: token ${GITHUB_TOKEN}" \
     https://github.company.com/api/v3/user
   ```

### Secret Value Truncated

**Symptom:** Secret appears truncated or corrupted in workflows

**Solutions:**

1. **Check for special characters:**
   ```yaml
   # Exclude problematic characters
   secrets:
     - name: PASSWORD
       kind: random_password
       config:
         exclude_characters: '"@/\`$'  # Exclude shell special chars
   ```

2. **Verify encoding:**
   - GitHub secrets support UTF-8
   - Binary data must be base64 encoded

3. **Check secret length limits:**
   - Maximum secret size: 64 KB
   - Large secrets should be stored elsewhere (e.g., AWS Secrets Manager)

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

4. **Check secret metadata (not values):**
   ```bash
   # List repository secrets
   gh secret list --repo owner/repo
   
   # View secret details (not value)
   gh api /repos/owner/repo/actions/secrets/SECRET_NAME
   ```

5. **Review GitHub Actions workflow logs:**
   - Secrets are redacted in logs
   - Look for error messages about missing secrets
   - Check workflow permissions

## Next Steps

- Learn about [AWS Secrets Manager](aws-secrets-manager.md) for cloud-native secrets
- Explore [Kubernetes Secrets](kubernetes.md) for container orchestration
- Review [HashiCorp Vault](vault.md) for centralized secret storage
- Check [complete examples](../../examples/index.md) for more patterns
- Read about [secret rotation strategies](../../advanced/rotation/index.md)
