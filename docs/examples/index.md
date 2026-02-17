# Examples

This section provides practical, real-world examples of using SecretZero in various scenarios and environments. All examples are tested and production-ready.

## Example Categories

### [Complete Working Examples](complete.md)
End-to-end examples for common use cases with detailed explanations and step-by-step instructions.

### [GitHub Examples Repository](repository.md)
Access the complete collection of example Secretfiles in the GitHub repository with usage instructions.

## Quick Reference

### By Use Case

| Use Case | Description | Example File |
|----------|-------------|--------------|
| **Local Development** | Simple local-only setup | [local-only.yml](repository.md#local-only) |
| **AWS Deployment** | Production AWS configuration | [aws-only.yml](repository.md#aws-only) |
| **Multi-Cloud** | Distribute across providers | [multi-cloud.yml](repository.md#multi-cloud) |
| **Kubernetes** | Kubernetes native secrets | [kubernetes-basic.yml](repository.md#kubernetes-basic) |
| **CI/CD Integration** | GitHub Actions, GitLab CI | [github-actions.yml](repository.md#cicd-examples) |
| **API Management** | Managing via API | [api-example.yml](repository.md#api-example) |
| **Compliance** | SOC2, HIPAA, PCI-DSS | [compliance.yml](repository.md#compliance) |
| **Drift Detection** | Monitor unauthorized changes | [drift-detection.yml](repository.md#drift-detection) |
| **Rotation Policies** | Automated secret rotation | [rotation-policies.yml](repository.md#rotation-policies) |

### By Environment

| Environment | Best For | Example Files |
|-------------|----------|---------------|
| **Local Development** | Testing and development | local-only.yml |
| **Single Cloud (AWS)** | AWS-only deployments | aws-only.yml |
| **Single Cloud (Azure)** | Azure-only deployments | - |
| **Multi-Cloud** | Enterprise hybrid cloud | multi-cloud.yml |
| **Kubernetes** | Container orchestration | kubernetes-*.yml |
| **CI/CD Pipelines** | Automated workflows | github-actions.yml, gitlab-cicd.yml |
| **Jenkins** | Legacy CI/CD | jenkins-credentials.yml |

### By Complexity

#### Beginner (Getting Started)
- [local-only.yml](repository.md#local-only) - Minimal local setup
- [aws-only.yml](repository.md#aws-only) - Simple cloud deployment

#### Intermediate (Production Use)
- [kubernetes-basic.yml](repository.md#kubernetes-basic) - Kubernetes integration
- [github-actions.yml](repository.md#cicd-examples) - CI/CD integration
- [drift-detection.yml](repository.md#drift-detection) - Monitoring

#### Advanced (Enterprise)
- [multi-cloud.yml](repository.md#multi-cloud) - Multi-cloud strategy
- [kubernetes-complete.yml](repository.md#kubernetes-complete) - Full K8s setup
- [multi-cicd.yml](repository.md#multi-cicd) - Complex CI/CD

## Common Patterns

### Pattern 1: Local + Cloud Hybrid

Store secrets both locally for development and in cloud for production:

```yaml
secrets:
  - name: database_password
    kind: random_password
    targets:
      # Local development
      - provider: local
        kind: file
        config:
          path: .env
      # Production in AWS
      - provider: aws
        kind: ssm_parameter
        config:
          name: /prod/db/password
```

**Use Cases**: Development teams, gradual cloud migration

### Pattern 2: Environment-Specific Secrets

Use variables to customize secrets per environment:

```yaml
variables:
  environment: ${ENVIRONMENT:-dev}
  
secrets:
  - name: api_key_${var.environment}
    kind: random_string
    targets:
      - provider: aws
        config:
          name: /${var.environment}/api/key
```

**Use Cases**: Multi-environment deployments, staged rollouts

### Pattern 3: Secret Templates

Group related secrets together:

```yaml
templates:
  database_credentials:
    fields:
      username:
        generator:
          kind: static
          config:
            default: app_user
      password:
        generator:
          kind: random_password
          config:
            length: 32
      connection_string:
        generator:
          kind: template
          config:
            template: "postgresql://{{.username}}:{{.password}}@localhost:5432/mydb"
```

**Use Cases**: Complex credentials, connection strings

### Pattern 4: Rotation with Grace Period

Rotate secrets with overlapping validity:

```yaml
secrets:
  - name: api_key
    kind: random_string
    rotation_period: 90d
    config:
      grace_period: 7d  # Old key valid for 7 days
```

**Use Cases**: Zero-downtime rotation, gradual rollout

### Pattern 5: Compliance-Driven Configuration

Enforce compliance policies:

```yaml
policies:
  - name: soc2_compliance
    kind: compliance
    config:
      require_rotation: true
      max_rotation_period: 90d
      require_audit: true
      require_encryption: true
```

**Use Cases**: Regulated industries, security audits

## Integration Examples

### With Terraform

```hcl
# Use SecretZero-managed secrets in Terraform
data "aws_ssm_parameter" "db_password" {
  name = "/prod/db/password"
}

resource "aws_db_instance" "main" {
  password = data.aws_ssm_parameter.db_password.value
}
```

### With Docker Compose

```yaml
services:
  app:
    image: myapp:latest
    env_file:
      - .env  # Generated by SecretZero
```

### With Kubernetes

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: myapp
spec:
  containers:
  - name: app
    env:
    - name: DB_PASSWORD
      valueFrom:
        secretKeyRef:
          name: postgres-credentials
          key: password
```

### With Ansible

```yaml
- name: Use SecretZero secrets
  hosts: all
  tasks:
    - name: Get secret from AWS SSM
      aws_ssm_parameter_store:
        name: /prod/api/key
      register: api_key
```

## Workflow Examples

### Development Workflow

1. Create Secretfile locally
2. Test with `secretzero sync --dry-run`
3. Generate local secrets for development
4. Commit Secretfile (not secrets!)
5. Deploy to staging/production

```bash
# Local development
secretzero sync --dry-run
secretzero sync
source .env

# CI/CD pipeline
secretzero sync --file Secretfile.prod.yml
```

### Rotation Workflow

1. Check rotation status
2. Review secrets due for rotation
3. Execute rotation
4. Verify new secrets
5. Update applications

```bash
# Check status
secretzero rotation check

# Rotate due secrets
secretzero rotation execute

# Verify
secretzero show my_secret
```

### Compliance Workflow

1. Define policies in Secretfile
2. Run policy checks
3. Fix violations
4. Re-check compliance
5. Generate audit reports

```bash
# Check compliance
secretzero policy check

# Check specific policy
secretzero policy check --policy soc2

# Generate report
secretzero audit report --format json > audit.json
```

## Testing Examples

### Test Secret Generation

```bash
# Dry run to preview
secretzero sync --dry-run

# Test specific secret
secretzero generate my_secret --dry-run

# Validate Secretfile
secretzero validate
```

### Test Provider Connectivity

```bash
# Test all providers
secretzero test

# Test specific provider
secretzero test --provider aws

# Verbose output
secretzero test --verbose
```

### Test Rotation Logic

```bash
# Check what would be rotated
secretzero rotation check --verbose

# Dry run rotation
secretzero rotation execute --dry-run
```

## Troubleshooting Examples

### Debug Secret Generation

```bash
# Enable debug logging
secretzero sync --log-level debug

# Show detailed secret info
secretzero show my_secret --verbose

# Check lockfile
cat .gitsecrets.lock | jq '.secrets.my_secret'
```

### Debug Provider Issues

```bash
# Test provider authentication
secretzero test --provider aws --verbose

# Check provider configuration
secretzero config show --provider aws
```

### Debug Rotation Issues

```bash
# Check rotation eligibility
secretzero rotation check --secret my_secret

# Force rotation
secretzero rotation execute --secret my_secret --force
```

## Performance Examples

### Parallel Secret Generation

```yaml
# Enable parallel generation (future feature)
config:
  parallel_generation: true
  max_workers: 4
```

### Caching

```yaml
# Enable caching (future feature)
config:
  cache_enabled: true
  cache_ttl: 300
```

### Batching

```bash
# Batch operations
secretzero sync --batch-size 10

# Process specific secrets
secretzero sync --secrets "secret1,secret2,secret3"
```

## Security Examples

### Least Privilege Configuration

```yaml
providers:
  aws:
    kind: aws
    auth:
      kind: assume_role
      role_arn: arn:aws:iam::123456789012:role/SecretZeroMinimal
```

### Encrypted Configuration

```yaml
# Use encrypted variables (future feature)
variables:
  db_host:
    encrypted: true
    value: !encrypted |
      ENC[AES256_GCM,data:...,iv:...,tag:...]
```

### Audit Logging

```yaml
audit:
  enabled: true
  destination: file
  path: /var/log/secretzero/audit.log
  format: json
```

## Next Steps

- Browse [complete examples](complete.md) with detailed walkthroughs
- Explore the [GitHub repository](repository.md) for all example files
- Learn about [API usage](../user-guide/api/index.md)
- Read the [Configuration Guide](../user-guide/configuration/index.md)

## Contributing Examples

Have a useful example? Contribute it!

1. Create your example Secretfile
2. Add documentation explaining the use case
3. Test thoroughly
4. Submit a pull request

See [Contributing Guidelines](../contributing/index.md) for details.
