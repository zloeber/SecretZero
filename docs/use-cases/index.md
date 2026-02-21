# Use Cases

This section provides practical, real-world examples of using SecretZero in different scenarios. Each use case includes complete working configurations, step-by-step instructions, and best practices.

## Overview

SecretZero is designed to solve common challenges in secret management across different environments and platforms. Whether you're setting up local development, deploying to cloud infrastructure, or implementing compliance requirements, these use cases will guide you through the process.

## Available Use Cases

### Development & Local Setup

- **[Local Development](local-development.md)** - Set up local development environments with `.env` files and local secret management
    - Generate development secrets
    - Create `.env` files automatically
    - Maintain local-only secrets
    - Quick project bootstrapping

### CI/CD Integration

- **[GitHub Actions](github-actions.md)** - Complete integration with GitHub Actions workflows
    - Repository and environment secrets
    - Organization-level secrets
    - Automated secret provisioning
    - Workflow examples

- **[GitLab CI/CD](gitlab-cicd.md)** - Manage GitLab CI/CD variables and pipeline secrets
    - Project and group variables
    - Environment scoping
    - Protected and masked variables
    - File variables for credentials

- **[Jenkins Pipelines](jenkins.md)** - Integrate with Jenkins credential management
    - String and username/password credentials
    - SSH keys and API tokens
    - Credential scope management
    - Pipeline integration

### Kubernetes & Container Orchestration

- **[Kubernetes Deployment](kubernetes.md)** - Kubernetes secret management and External Secrets Operator
    - Native Kubernetes secrets
    - External Secrets Operator integration
    - Multi-namespace deployments
    - GitOps workflows

### Cloud & Infrastructure

- **[Multi-Cloud Setup](multi-cloud.md)** - Manage secrets across AWS, Azure, and HashiCorp Vault
    - Cross-cloud synchronization
    - Cloud-specific storage (AWS Secrets Manager, Azure Key Vault)
    - Hybrid cloud deployments
    - Disaster recovery scenarios

### Compliance & Governance

- **[Compliance Scenarios](compliance.md)** - SOC2 and ISO27001 compliance requirements
    - Rotation policies
    - Audit trails
    - Policy enforcement
    - Compliance reporting

### Augmentation & Adoption

- **[Augmentation Guides](augmenting.md)** - Augment your secret management tools
    - dotenv files
    - AWS Secrets Manager
    - HashiCorp Vault
    - From manual processes

## How to Use These Use Cases

Each use case follows a consistent structure:

1. **Problem Statement** - The challenge being addressed
2. **Prerequisites** - What you need before starting
3. **Configuration** - Complete working `Secretfile.yml` example
4. **Step-by-Step Instructions** - Detailed walkthrough
5. **Best Practices** - Recommendations and tips
6. **Troubleshooting** - Common issues and solutions

## Getting Started

If you're new to SecretZero, we recommend starting with:

1. **[Local Development](local-development.md)** - Learn the basics without cloud dependencies
2. **[GitHub Actions](github-actions.md)** or **[GitLab CI/CD](gitlab-cicd.md)** - Add CI/CD integration
3. **[Multi-Cloud Setup](multi-cloud.md)** - Scale to production infrastructure

## Need Help?

- 📚 Check the [User Guide](../user-guide/index.md) for detailed documentation
- 💡 Browse [Examples](../examples/index.md) for more configuration samples
- 🐛 Visit [Troubleshooting](../reference/troubleshooting.md) for common issues
- 💬 Open an [issue on GitHub](https://github.com/zloeber/SecretZero/issues) for support

## Contributing

Have a use case you'd like to share? We welcome contributions! See our [Contributing Guide](../contributing/index.md) for details.
