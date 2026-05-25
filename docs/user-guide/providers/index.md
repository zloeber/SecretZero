# Providers Overview

Providers are the connectors that allow SecretZero to distribute secrets to various infrastructure platforms, cloud services, and CI/CD systems. Each provider handles authentication, connectivity, and the specific API interactions needed to securely store and manage secrets in its respective system.

## What are Providers?

Providers are modular components that:

- **Authenticate** with external services using various methods (tokens, credentials, ambient authentication)
- **Validate connectivity** to ensure the target system is reachable
- **Manage secrets** by creating, updating, and syncing secret values
- **Support multiple target types** for storing different kinds of secrets (parameters, key-value pairs, files, etc.)

## Available Providers

SecretZero supports the following providers:

| Provider | Description | Target Types | Use Cases |
|----------|-------------|--------------|-----------|
| [Local](local.md) | Local Filesystem | `file`, `template` | Local development, `.env` files, configuration files |
| [AWS](aws.md) | Amazon Web Services | `ssm_parameter`, `secrets_manager` | Cloud infrastructure, serverless apps, ECS/EKS |
| [Azure](azure.md) | Microsoft Azure | `key_vault` | Azure cloud services, App Service, AKS |
| [Vault](vault.md) | HashiCorp Vault | `kv` | Multi-cloud secrets, centralized secret management |
| [GitHub](github.md) | GitHub Actions | `github_secret` | CI/CD pipelines, GitHub workflows |
| [GitLab](gitlab.md) | GitLab CI/CD | `gitlab_variable`, `gitlab_group_variable` | CI/CD pipelines, GitLab runners |
| [Jenkins](jenkins.md) | Jenkins | `jenkins_credential` | Build automation, deployment pipelines |
| [Kubernetes](kubernetes.md) | Kubernetes | `kubernetes_secret`, `external_secret` | Container orchestration, microservices |
| [Vercel](vercel.md) | Vercel | `vercel_env` | Project environment variable delivery |
| [Keeper](keeper.md) | Keeper Password Manager | `keeper_record` | Vault record source/target via Commander SDK |
| [Entra Agent ID](entra-agent-id.md) | Microsoft Entra Agent ID | _provider-backed workflow_ | Agent blueprint identity governance |
| [Ansible Vault](ansible_vault.md) | Encrypted repo files | `ansible_vault_file` | Ansible-native encrypted file workflows |
| [SOPS](sops.md) | Encrypted repo files | `sops_file` | age/KMS/PGP-backed encrypted structured files |
| [git-crypt](git_crypt.md) | Encrypted repo files | `git_crypt_file` | Transparent git filter-based encryption |

!!! tip "Custom providers via bundles"
    Need a provider that isn't listed? SecretZero's [provider bundle system](../bundles/index.md) lets you create and install third-party providers as pip packages — no core changes required.

    ```bash
    secretzero scaffold-bundle mycloud --with-target mycloud_secret
    ```

## Common Authentication Patterns

### Ambient Authentication

Many providers support "ambient" authentication, which automatically discovers credentials from the environment:

```yaml
providers:
  aws:
    kind: aws
    auth:
      kind: ambient  # Uses IAM roles, env vars, or AWS profiles
      region: us-east-1
```

Ambient authentication typically checks for credentials in this order:
1. Environment variables
2. Configuration files (e.g., `~/.aws/credentials`)
3. Instance metadata (IAM roles for EC2, ECS, etc.)
4. Managed identities (Azure, GCP)

### Token-Based Authentication

For services that use API tokens or personal access tokens:

```yaml
providers:
  github:
    kind: github
    auth:
      kind: token
      config:
        token: ${GITHUB_TOKEN}  # From environment variable
```

### Credential-Based Authentication

For services requiring username/password or client credentials:

```yaml
providers:
  jenkins:
    kind: jenkins
    auth:
      kind: token
      config:
        url: https://jenkins.example.com
        username: admin
        token: ${JENKINS_TOKEN}
```

### Role-Based Authentication

For assuming roles or using service principals:

```yaml
providers:
  aws:
    kind: aws
    auth:
      kind: assume_role
      role_arn: arn:aws:iam::123456789012:role/SecretZeroRole
      region: us-east-1
```

## Provider Configuration Structure

All providers follow a consistent configuration structure:

```yaml
providers:
  <provider_name>:
    kind: <provider_type>      # Required: Provider type identifier
    auth:                       # Required: Authentication configuration
      kind: <auth_method>       # Authentication method
      config:                   # Auth-specific configuration
        <auth_parameters>
```

### Example: Multi-Provider Setup

```yaml
version: '1.0'

providers:
  # AWS with ambient authentication
  aws:
    kind: aws
    auth:
      kind: ambient
      region: us-east-1
  
  # Azure with managed identity
  azure:
    kind: azure
    auth:
      kind: managed_identity
  
  # Vault with token authentication
  vault:
    kind: vault
    auth:
      kind: token
      token: ${VAULT_TOKEN}
      url: https://vault.example.com
  
  # GitHub with personal access token
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
    targets:
      # Store in multiple providers
      - provider: aws
        kind: secrets_manager
        config:
          name: prod/db/password
      
      - provider: azure
        kind: key_vault
        config:
          vault_url: https://myapp.vault.azure.net
          secret_name: db-password
      
      - provider: vault
        kind: kv
        config:
          path: prod/db/password
```

## Using Providers with Targets

Providers work in conjunction with **targets** to determine where secrets are stored:

```yaml
secrets:
  - name: api_key
    kind: random_string
    config:
      length: 32
    targets:
      - provider: aws              # Which provider to use
        kind: ssm_parameter         # What type of storage
        config:                     # Provider-specific configuration
          name: /app/api-key
          type: SecureString
```

The `provider` field must match a provider defined in the `providers` section.

## Testing Provider Connectivity

Before syncing secrets, test your provider configuration:

```bash
# Test all providers
secretzero test

# Test specific provider
secretzero test --provider aws

# Test with verbose output
secretzero test --verbose
```

A successful test will show:
- ✓ Provider authentication successful
- ✓ Connection to service established
- ✓ Permission validation passed

## Environment Variables

Providers commonly use environment variables for sensitive credentials:

```bash
# AWS
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_REGION=us-east-1

# Azure
export AZURE_CLIENT_ID=your_client_id
export AZURE_CLIENT_SECRET=your_secret
export AZURE_TENANT_ID=your_tenant_id

# Vault
export VAULT_ADDR=https://vault.example.com
export VAULT_TOKEN=your_token

# GitHub
export GITHUB_TOKEN=ghp_your_token

# GitLab
export GITLAB_TOKEN=your_token

# Jenkins
export JENKINS_URL=https://jenkins.example.com
export JENKINS_USER=admin
export JENKINS_TOKEN=your_token
```

**Security Best Practice**: Never commit tokens or credentials to version control. Use environment variables or secure secret management for provider authentication.

## Provider Installation

Some providers require additional Python packages:

```bash
# Install specific provider dependencies
pip install secretzero[aws]      # AWS provider
pip install secretzero[azure]    # Azure provider
pip install secretzero[vault]    # Vault provider
pip install secretzero[github]   # GitHub provider
pip install secretzero[gitlab]   # GitLab provider
pip install secretzero[jenkins]  # Jenkins provider
pip install secretzero[k8s]      # Kubernetes provider

# Install all providers
pip install secretzero[all]
```

## Error Handling

Providers implement consistent error handling:

- **Authentication Errors**: Invalid credentials or expired tokens
- **Connection Errors**: Network issues or unreachable services
- **Permission Errors**: Insufficient privileges for operations
- **Configuration Errors**: Invalid or missing configuration parameters

Example error output:

```
ERROR: AWS provider test failed
Reason: AWS authentication failed. Check credentials and configuration.

Troubleshooting:
- Verify AWS credentials are set (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
- Check IAM permissions for secretsmanager:* and ssm:*
- Ensure region is correctly configured
```

## Best Practices

### 1. Use Ambient Authentication When Possible

Prefer ambient authentication over hardcoded credentials:

```yaml
# Good: Uses ambient authentication
providers:
  aws:
    kind: aws
    auth:
      kind: ambient
      region: us-east-1

# Avoid: Hardcoded credentials (use env vars instead)
providers:
  aws:
    kind: aws
    auth:
      kind: ambient
      region: us-east-1
      # Don't hardcode access_key and secret_key
```

### 2. Separate Providers by Environment

Use different provider configurations for different environments:

```yaml
# Development
providers:
  aws_dev:
    kind: aws
    auth:
      kind: profile
      profile: dev-account
      region: us-west-2

# Production
providers:
  aws_prod:
    kind: aws
    auth:
      kind: assume_role
      role_arn: arn:aws:iam::123456789012:role/ProductionRole
      region: us-east-1
```

### 3. Minimize Provider Permissions

Grant providers only the permissions they need:

- AWS: `secretsmanager:GetSecretValue`, `secretsmanager:PutSecretValue`, `ssm:GetParameter`, `ssm:PutParameter`
- Azure: `Key Vault Secrets Officer` role
- Vault: Read/write policies on specific paths
- GitHub: `repo` scope for repository secrets
- GitLab: `api` scope for CI/CD variables
- Jenkins: API token with Credentials/Create and Credentials/Update permissions
- Kubernetes: RBAC role with `get`, `create`, `update` on secrets

### 4. Use Provider Aliases for Multiple Accounts

When working with multiple accounts of the same provider:

```yaml
providers:
  aws_account_a:
    kind: aws
    auth:
      kind: profile
      profile: account-a
  
  aws_account_b:
    kind: aws
    auth:
      kind: profile
      profile: account-b

secrets:
  - name: shared_secret
    kind: random_password
    config:
      length: 32
    targets:
      - provider: aws_account_a
        kind: secrets_manager
        config:
          name: shared/secret
      
      - provider: aws_account_b
        kind: secrets_manager
        config:
          name: shared/secret
```

### 5. Test Before Production Deployment

Always test provider connectivity before deploying to production:

```bash
# Dry-run to see what would change
secretzero sync --dry-run

# Test connectivity
secretzero test

# Sync with confirmation
secretzero sync
```

## Next Steps

- [AWS Provider Documentation](aws.md)
- [Azure Provider Documentation](azure.md)
- [HashiCorp Vault Provider Documentation](vault.md)
- [GitHub Provider Documentation](github.md)
- [GitLab Provider Documentation](gitlab.md)
- [Jenkins Provider Documentation](jenkins.md)
- [Kubernetes Provider Documentation](kubernetes.md)
- [Vercel Provider Documentation](vercel.md)
- [Keeper Provider Documentation](keeper.md)
- [Entra Agent ID Provider Documentation](entra-agent-id.md)
- [Encrypted-in-git Workflows](encrypted-repo-workflows.md)
- [Ansible Vault Provider Documentation](ansible_vault.md)
- [SOPS Provider Documentation](sops.md)
- [git-crypt Provider Documentation](git_crypt.md)

## Troubleshooting

### Provider Not Found

```
ERROR: Unknown provider kind: 'aws'
```

**Solution**: Install the provider package:
```bash
pip install secretzero[aws]
```

### Authentication Failed

```
ERROR: Provider authentication failed
```

**Solutions**:
1. Verify credentials are correctly set in environment variables
2. Check that credentials haven't expired
3. Ensure the authentication method matches your environment
4. Verify network connectivity to the service

### Permission Denied

```
ERROR: Insufficient permissions
```

**Solutions**:
1. Review IAM policies or role assignments
2. Ensure the service account has necessary permissions
3. Check for IP restrictions or firewall rules
4. Verify MFA requirements are met

### Connection Timeout

```
ERROR: Connection timeout
```

**Solutions**:
1. Check network connectivity
2. Verify service URLs are correct
3. Check for proxy or firewall issues
4. Ensure the service is running and accessible
