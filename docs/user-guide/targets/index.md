# Targets Overview

Targets define where SecretZero stores and distributes your secrets. Each target represents a destination system that can receive and manage secrets, from local files to cloud services and CI/CD platforms.

## What are Targets?

Targets are the destination endpoints in SecretZero's secret distribution pipeline. After generating a secret, SecretZero pushes it to one or more targets specified in your configuration. This allows you to:

- **Centralize secret management** while distributing to multiple systems
- **Maintain consistency** across different environments and platforms
- **Automate secret rotation** across all configured targets
- **Support hybrid architectures** with mixed on-premises and cloud infrastructure

## Available Targets

### Local Development
- **[File Targets](local.md)** - Store secrets in local files (.env, JSON, YAML, TOML)

### Cloud Providers
- **[AWS Targets](aws.md)** - AWS Secrets Manager and SSM Parameter Store
- **[Azure Targets](azure.md)** - Azure Key Vault
- **[HashiCorp Vault](vault.md)** - Vault KV v1 and v2 engines

### CI/CD Platforms
- **[GitHub Actions](github.md)** - Repository, environment, and organization secrets
- **[GitLab CI/CD](gitlab.md)** - Project and group variables
- **[Jenkins](jenkins.md)** - Jenkins credentials (string, username/password)

### Container Orchestration
- **[Kubernetes](kubernetes.md)** - Native Secrets and External Secrets Operator

## How Targets Work

### Basic Target Configuration

Each target in your Secretfile requires:

1. **Provider** - The provider instance to use for authentication
2. **Kind** - The target type (e.g., `file`, `secrets_manager`, `kubernetes_secret`)
3. **Config** - Target-specific configuration options

```yaml
secrets:
  - name: database_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: myapp/db/password
          description: Database password
```

### Multi-Target Distribution

A single secret can be distributed to multiple targets simultaneously:

```yaml
secrets:
  - name: api_key
    kind: random_string
    config:
      length: 32
    targets:
      # Local development
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
      
      # AWS production
      - provider: aws
        kind: secrets_manager
        config:
          name: prod/api-key
      
      # CI/CD pipeline
      - provider: github
        kind: github_secret
        config:
          owner: myorg
          repo: myrepo
          environment: production
```

### Target Lifecycle

When SecretZero processes targets:

1. **Generation** - Secret value is generated according to its type
2. **Distribution** - Value is pushed to each configured target
3. **Verification** - Each target confirms successful storage (where supported)
4. **Tracking** - State is recorded in the lockfile for rotation management

## Common Configuration Patterns

### Environment-Based Targeting

Use variables to configure targets per environment:

```yaml
variables:
  environment: dev
  aws_region: us-east-1

secrets:
  - name: db_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /{{var.environment}}/db/password
          type: SecureString
```

### Conditional Targets

Target different systems based on context:

```yaml
secrets:
  - name: app_secret
    kind: random_string
    config:
      length: 32
    targets:
      # Always store locally
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
      
      # Production only
      - provider: aws
        kind: secrets_manager
        config:
          name: prod/app-secret
        when: "{{ var.environment == 'prod' }}"
```

### Backup Targets

Store secrets in multiple locations for redundancy:

```yaml
secrets:
  - name: encryption_key
    kind: random_string
    config:
      length: 64
    targets:
      # Primary storage
      - provider: aws
        kind: secrets_manager
        config:
          name: encryption-key
          kms_key_id: arn:aws:kms:...
      
      # Backup in different region/provider
      - provider: azure
        kind: key_vault
        config:
          vault_url: https://backup-vault.vault.azure.net
          secret_name: encryption-key
```

## Target Capabilities

Different targets support different operations:

| Target | Store | Retrieve | Delete | Update | Metadata |
|--------|-------|----------|--------|--------|----------|
| File | ✅ | ✅ | ✅ | ✅ | ❌ |
| AWS Secrets Manager | ✅ | ✅ | ✅ | ✅ | ✅ |
| AWS SSM Parameter | ✅ | ✅ | ✅ | ✅ | ✅ |
| Azure Key Vault | ✅ | ✅ | ✅ | ✅ | ✅ |
| HashiCorp Vault | ✅ | ✅ | ✅ | ✅ | ✅ |
| GitHub Actions | ✅ | ❌ | ❌ | ✅ | ❌ |
| GitLab CI/CD | ✅ | ✅ | ❌ | ✅ | ✅ |
| Jenkins | ✅ | ❌ | ❌ | ✅ | ✅ |
| Kubernetes | ✅ | ✅ | ✅ | ✅ | ✅ |

**Note**: Some targets (GitHub, Jenkins) don't support retrieval for security reasons.

## Best Practices

### 1. Use Appropriate Target Types

Match targets to your use case:

- **Local files** for development environments
- **Cloud secret managers** for production workloads
- **CI/CD secrets** for pipeline credentials
- **Kubernetes secrets** for containerized applications

### 2. Implement Defense in Depth

Store critical secrets in multiple independent targets:

```yaml
secrets:
  - name: master_key
    kind: random_string
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: master-key
      - provider: vault
        kind: kv
        config:
          path: security/master-key
```

### 3. Use Target-Specific Features

Leverage platform-specific capabilities:

- **AWS KMS encryption** for Secrets Manager
- **Azure Key Vault access policies** for fine-grained control
- **Kubernetes labels and annotations** for organization
- **Vault versions** for audit trails

### 4. Document Target Configuration

Include metadata to track target usage:

```yaml
secrets:
  - name: api_key
    kind: random_string
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: api-key
          description: "API key for external service XYZ"
          tags:
            - key: Owner
              value: platform-team
            - key: Purpose
              value: external-api
```

### 5. Test Target Connectivity

Before deploying, verify target access:

```bash
# Test all targets in configuration
secretzero test -f Secretfile.yml

# Test specific provider
secretzero test -f Secretfile.yml --provider aws
```

## Target Security Considerations

### Encryption at Rest

Most cloud targets provide encryption by default:

- **AWS Secrets Manager** - Encrypted with AWS KMS
- **Azure Key Vault** - Encrypted with Azure-managed keys
- **HashiCorp Vault** - Configurable encryption backend
- **Kubernetes Secrets** - Requires etcd encryption configuration

### Access Control

Configure least-privilege access:

```yaml
# AWS - Use IAM policies
providers:
  aws:
    kind: aws
    auth:
      kind: ambient  # Uses IAM roles
      region: us-east-1

# Azure - Use managed identities
providers:
  azure:
    kind: azure
    auth:
      kind: default  # Uses managed identity

# Kubernetes - Use RBAC
providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient  # Uses service account
```

### Audit Logging

Enable audit trails on target systems:

- **AWS CloudTrail** for Secrets Manager/SSM access
- **Azure Monitor** for Key Vault operations
- **Vault audit devices** for Vault access
- **Kubernetes audit logs** for Secret operations

## Troubleshooting

### Target Connection Failures

If targets fail to connect:

1. **Verify credentials** - Ensure provider authentication is working
2. **Check permissions** - Verify IAM/RBAC policies allow secret operations
3. **Test connectivity** - Use `secretzero test` to diagnose issues
4. **Review logs** - Check SecretZero logs for detailed error messages

### Secret Not Appearing

If secrets aren't appearing in targets:

1. **Check target configuration** - Verify paths, names, and parameters
2. **Review lockfile** - Confirm secret was generated and tracked
3. **Verify target support** - Some targets don't support retrieval
4. **Check target system** - Log into target system to verify directly

### Permission Denied Errors

Common permission issues and solutions:

```bash
# AWS - Missing IAM permissions
# Solution: Add secretsmanager:PutSecretValue or ssm:PutParameter

# Azure - Missing Key Vault access policy
# Solution: Add "Set" permission in access policies

# Kubernetes - Missing RBAC permissions
# Solution: Create Role with secrets create/update permissions

# GitHub/GitLab - Insufficient token scope
# Solution: Regenerate token with required scopes
```

## Next Steps

- Explore specific target documentation for detailed configuration
- Review [providers documentation](../providers/index.md) for authentication setup
- Check [examples](../../examples/index.md) for real-world configurations
- Read [best practices](../../use-cases/best-practices.md) for production deployments
