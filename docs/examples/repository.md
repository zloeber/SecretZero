# GitHub Examples Repository

The SecretZero GitHub repository contains a comprehensive collection of example Secretfiles for various use cases and environments. This guide explains how to access and use these examples.

## Repository Location

All examples are located in the `examples/` directory of the main repository:

**GitHub**: [https://github.com/zloeber/SecretZero/tree/main/examples](https://github.com/zloeber/SecretZero/tree/main/examples)

## Available Examples

### Local Development

#### local-only.yml {#local-only}

**Purpose**: Simple local development setup with no cloud dependencies

**Features**:
- Local file storage only
- Random password and string generation
- Template-based configuration
- No cloud provider requirements

**Usage**:
```bash
# Copy the example
curl -O https://raw.githubusercontent.com/zloeber/SecretZero/main/examples/local-only.yml
mv local-only.yml Secretfile.yml

# Generate secrets
secretzero sync

# View generated files
cat .env
```

**Perfect For**:
- Getting started with SecretZero
- Local development environments
- Testing configurations
- No cloud access scenarios

---

### Cloud Provider Examples

#### aws-only.yml {#aws-only}

**Purpose**: Production-ready AWS deployment

**Features**:
- AWS SSM Parameter Store integration
- AWS Secrets Manager support
- Static secrets with validation
- Environment variable fallback

**Prerequisites**:
```bash
pip install secretzero[aws]
aws configure
```

**Usage**:
```bash
# Get the example
curl -O https://raw.githubusercontent.com/zloeber/SecretZero/main/examples/aws-only.yml
mv aws-only.yml Secretfile.yml

# Test connectivity
secretzero test --provider aws

# Deploy
secretzero sync --dry-run
secretzero sync
```

**Perfect For**:
- AWS-only deployments
- Production applications on AWS
- SSM Parameter Store users
- AWS Secrets Manager integration

---

#### multi-cloud.yml {#multi-cloud}

**Purpose**: Enterprise multi-cloud secret distribution

**Features**:
- Multi-cloud secret distribution (AWS, Azure, Vault)
- Local file + cloud providers
- Template-based secrets
- Variable interpolation
- Compliance metadata

**Prerequisites**:
```bash
pip install secretzero[all]
aws configure
az login
export VAULT_TOKEN=your-token
export VAULT_ADDR=https://vault.example.com
```

**Usage**:
```bash
# Get the example
curl -O https://raw.githubusercontent.com/zloeber/SecretZero/main/examples/multi-cloud.yml
mv multi-cloud.yml Secretfile.yml

# Test all providers
secretzero test

# Deploy
secretzero sync
```

**Perfect For**:
- Multi-cloud strategies
- Hybrid cloud deployments
- Enterprise environments
- Cloud migration scenarios

---

### Kubernetes Examples

#### kubernetes-basic.yml {#kubernetes-basic}

**Purpose**: Basic Kubernetes Secret management

**Features**:
- Kubernetes native Secrets
- Multiple secret types (Opaque, TLS)
- Labels and annotations
- Namespace support

**Prerequisites**:
```bash
pip install secretzero[kubernetes]
kubectl cluster-info
```

**Usage**:
```bash
# Get the example
curl -O https://raw.githubusercontent.com/zloeber/SecretZero/main/examples/kubernetes-basic.yml
mv kubernetes-basic.yml Secretfile.yml

# Deploy secrets
secretzero sync

# Verify
kubectl get secrets
kubectl describe secret myapp-db
```

**Perfect For**:
- Kubernetes beginners
- Simple K8s deployments
- Single namespace applications
- Getting started with K8s secrets

---

#### kubernetes-complete.yml {#kubernetes-complete}

**Purpose**: Advanced Kubernetes setup with all features

**Features**:
- Multi-namespace support
- Secret rotation
- ConfigMap integration
- External Secrets Operator
- Sealed Secrets support
- Advanced templates

**Usage**:
```bash
curl -O https://raw.githubusercontent.com/zloeber/SecretZero/main/examples/kubernetes-complete.yml
mv kubernetes-complete.yml Secretfile.yml
secretzero sync
```

**Perfect For**:
- Production Kubernetes
- Multi-namespace deployments
- Advanced secret management
- Enterprise K8s clusters

---

#### kubernetes-external-secrets.yml

**Purpose**: Integration with External Secrets Operator

**Features**:
- External Secrets Operator integration
- Cloud provider backends
- SecretStore configuration
- Auto-sync capabilities

**Prerequisites**:
```bash
# Install External Secrets Operator
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets
```

**Usage**:
```bash
curl -O https://raw.githubusercontent.com/zloeber/SecretZero/main/examples/kubernetes-external-secrets.yml
mv kubernetes-external-secrets.yml Secretfile.yml
secretzero sync
```

**Perfect For**:
- External Secrets Operator users
- GitOps workflows
- Cloud-native secret management
- Automated secret sync

---

#### kubernetes-multi-namespace.yml

**Purpose**: Secrets across multiple Kubernetes namespaces

**Features**:
- Multi-namespace deployment
- Shared secrets
- Namespace-specific secrets
- RBAC considerations

**Usage**:
```bash
curl -O https://raw.githubusercontent.com/zloeber/SecretZero/main/examples/kubernetes-multi-namespace.yml
mv kubernetes-multi-namespace.yml Secretfile.yml
secretzero sync
```

**Perfect For**:
- Multi-tenant clusters
- Microservices architectures
- Shared infrastructure
- Platform teams

---

### CI/CD Examples {#cicd-examples}

#### github-actions.yml

**Purpose**: GitHub Actions integration

**Features**:
- GitHub Actions workflow
- OIDC authentication
- Automated rotation
- Drift detection
- Policy enforcement

**Usage**:
1. Copy example to your repo
2. Set up GitHub secrets for credentials
3. Configure OIDC provider
4. Push to trigger workflow

**Workflow File** (`.github/workflows/secrets.yml`):
```yaml
name: Manage Secrets
on:
  schedule:
    - cron: '0 2 * * *'
  workflow_dispatch:

jobs:
  secrets:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: pip install secretzero[all]
      - run: secretzero sync
```

**Perfect For**:
- GitHub-hosted projects
- Automated workflows
- CI/CD pipelines
- GitHub Actions users

---

#### gitlab-cicd.yml

**Purpose**: GitLab CI/CD integration

**Features**:
- GitLab CI configuration
- Scheduled pipelines
- Multi-stage deployment
- Secret validation

**Usage**:
```bash
curl -O https://raw.githubusercontent.com/zloeber/SecretZero/main/examples/gitlab-cicd.yml
# Copy .gitlab-ci.yml example to your repo
git add Secretfile.yml .gitlab-ci.yml
git commit -m "Add secret management"
git push
```

**Perfect For**:
- GitLab users
- Self-hosted GitLab
- GitLab CI/CD pipelines
- DevOps workflows

---

#### jenkins-credentials.yml

**Purpose**: Jenkins integration

**Features**:
- Jenkins credential store
- Pipeline integration
- Jenkinsfile examples
- Credential rotation

**Usage**:
```bash
curl -O https://raw.githubusercontent.com/zloeber/SecretZero/main/examples/jenkins-credentials.yml
mv jenkins-credentials.yml Secretfile.yml
secretzero sync
```

**Perfect For**:
- Legacy Jenkins setups
- Hybrid CI/CD
- Enterprise CI/CD
- Jenkins users

---

#### multi-cicd.yml {#multi-cicd}

**Purpose**: Supporting multiple CI/CD platforms

**Features**:
- Multi-platform support
- Unified secret management
- Platform-specific outputs
- Comprehensive automation

**Usage**:
```bash
curl -O https://raw.githubusercontent.com/zloeber/SecretZero/main/examples/multi-cicd.yml
mv multi-cicd.yml Secretfile.yml
secretzero sync
```

**Perfect For**:
- Multi-platform organizations
- CI/CD migrations
- Hybrid environments
- Large engineering teams

---

### Specialized Examples

#### api-example.yml {#api-example}

**Purpose**: Demonstrating API usage and features

**Features**:
- Complete API configuration
- Rotation policies
- Policy compliance
- Audit logging examples

**Usage**:
```bash
curl -O https://raw.githubusercontent.com/zloeber/SecretZero/main/examples/api-example.yml
mv api-example.yml Secretfile.yml

# Start API server
export SECRETZERO_API_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
secretzero-api

# Use API
curl -H "X-API-Key: $SECRETZERO_API_KEY" http://localhost:8000/secrets
```

**Perfect For**:
- API integration
- Programmatic access
- Automation scripts
- External tools

---

#### compliance.yml {#compliance}

**Purpose**: Meeting compliance requirements

**Features**:
- SOC2 compliance
- HIPAA requirements
- PCI-DSS standards
- Audit logging
- Access controls

**Usage**:
```bash
curl -O https://raw.githubusercontent.com/zloeber/SecretZero/main/examples/compliance.yml
mv compliance.yml Secretfile.yml
secretzero policy check --fail-on-warning
secretzero sync
```

**Perfect For**:
- Regulated industries
- Compliance audits
- Security teams
- Enterprise governance

---

#### drift-detection.yml {#drift-detection}

**Purpose**: Monitoring for unauthorized changes

**Features**:
- Drift detection configuration
- Alerting setup
- Remediation workflows
- Monitoring integration

**Usage**:
```bash
curl -O https://raw.githubusercontent.com/zloeber/SecretZero/main/examples/drift-detection.yml
mv drift-detection.yml Secretfile.yml
secretzero drift check
```

**Perfect For**:
- Security monitoring
- Compliance enforcement
- Change detection
- Operations teams

---

#### rotation-policies.yml {#rotation-policies}

**Purpose**: Advanced rotation strategies

**Features**:
- Multiple rotation policies
- Grace periods
- Rotation schedules
- Automated workflows

**Usage**:
```bash
curl -O https://raw.githubusercontent.com/zloeber/SecretZero/main/examples/rotation-policies.yml
mv rotation-policies.yml Secretfile.yml
secretzero rotation check
secretzero rotation execute
```

**Perfect For**:
- Security best practices
- Automated rotation
- Zero-downtime updates
- Operational excellence

---

## Using Examples

### Method 1: Direct Download

Download a specific example directly:

```bash
# Download example
curl -O https://raw.githubusercontent.com/zloeber/SecretZero/main/examples/local-only.yml

# Rename to Secretfile.yml
mv local-only.yml Secretfile.yml

# Use it
secretzero sync
```

### Method 2: Clone Repository

Clone the entire repository to access all examples:

```bash
# Clone repository
git clone https://github.com/zloeber/SecretZero.git
cd SecretZero/examples

# Copy example to your project
cp aws-only.yml /path/to/your/project/Secretfile.yml
cd /path/to/your/project
secretzero sync
```

### Method 3: Browse on GitHub

Browse examples online:

1. Visit [https://github.com/zloeber/SecretZero/tree/main/examples](https://github.com/zloeber/SecretZero/tree/main/examples)
2. Click on any example file
3. Click "Raw" button
4. Copy the content
5. Paste into your `Secretfile.yml`

## Customizing Examples

All examples are templates - customize them for your needs:

### 1. Update Variables

```yaml
variables:
  environment: production  # Change to your environment
  region: us-west-2       # Change to your region
  app_name: myapp         # Change to your app name
```

### 2. Adjust Providers

```yaml
providers:
  aws:
    kind: aws
    auth:
      profile: production  # Use your AWS profile
```

### 3. Modify Secrets

```yaml
secrets:
  - name: my_custom_secret  # Rename to your needs
    kind: random_password
    config:
      length: 24           # Adjust parameters
```

### 4. Configure Policies

```yaml
policies:
  my_policy:
    kind: rotation
    config:
      max_rotation_period: 60d  # Adjust to your requirements
```

## Testing Examples

Always test examples before using in production:

```bash
# Validate configuration
secretzero validate

# Test provider connectivity
secretzero test

# Dry run
secretzero sync --dry-run

# Check policies
secretzero policy check

# Run actual sync
secretzero sync
```

## Contributing Examples

Have a useful example? Share it with the community!

### Steps to Contribute

1. **Create Your Example**:
```bash
# Create well-documented Secretfile
vim my-example.yml
```

2. **Test Thoroughly**:
```bash
secretzero validate
secretzero test
secretzero sync --dry-run
```

3. **Add Documentation**:
- Add comments explaining the configuration
- Include usage instructions
- Document prerequisites

4. **Submit Pull Request**:
```bash
git checkout -b add-my-example
git add examples/my-example.yml
git commit -m "Add example for [use case]"
git push origin add-my-example
# Create PR on GitHub
```

### Example Template

```yaml
# [Example Name]
# [Brief description of the use case]
#
# Prerequisites:
# - [Requirement 1]
# - [Requirement 2]
#
# Usage:
# 1. [Step 1]
# 2. [Step 2]
#
# Author: [Your Name]
# Last Updated: [Date]

version: '1.0'

metadata:
  description: [Detailed description]
  # ... more metadata

# ... rest of configuration
```

## Getting Help

### Documentation

- [Complete Examples](complete.md) - Detailed walkthroughs
- [API Reference](../user-guide/api/index.md) - API documentation
- [Configuration Guide](../user-guide/configuration/index.md) - Configuration reference

### Community

- **GitHub Issues**: [Report issues or ask questions](https://github.com/zloeber/SecretZero/issues)
- **Discussions**: [Community discussions](https://github.com/zloeber/SecretZero/discussions)
- **README**: [Main README](https://github.com/zloeber/SecretZero/blob/main/README.md)

### Example-Specific Help

For help with a specific example:

1. Check the comments in the example file
2. Search GitHub issues for related topics
3. Create a new issue with the "question" label

## Next Steps

- Browse [complete examples](complete.md) with detailed explanations
- Learn about [API usage](../user-guide/api/index.md)
- Read the [Configuration Guide](../user-guide/configuration/index.md)
- Check out [Best Practices](../user-guide/best-practices.md)
