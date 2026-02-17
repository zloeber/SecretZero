# User Guide

Welcome to the SecretZero User Guide! This comprehensive reference covers everything you need to know about using SecretZero for secret management.

## What's in This Guide?

This guide is organized into three main sections covering configuration, CLI commands, and advanced topics.

## Quick Navigation

<div class="grid cards" markdown>

-   :material-cog: **Configuration**

    ---

    Learn how to configure SecretZero with Secretfile.yml, variables, and validation
    
    [Configuration Guide →](configuration/index.md)

-   :material-console: **CLI Reference**

    ---

    Complete reference for all SecretZero CLI commands and options
    
    [CLI Commands →](cli/index.md)

-   :material-api: **API Server**

    ---

    REST API for programmatic secret management
    
    [API Documentation →](api/index.md)

</div>

## Core Concepts

Before diving into the details, familiarize yourself with these core concepts:

### Secretfile.yml

The central configuration file that defines all your secrets, providers, targets, and policies. Think of it as your secret infrastructure-as-code.

```yaml
version: '1.0'

secrets:
  - name: my_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: aws
        kind: ssm_parameter
```

[Learn more about Secretfile →](configuration/secretfile.md)

### Providers

Providers are the backends where secrets are stored or retrieved. SecretZero supports:

- **Cloud**: AWS, Azure, HashiCorp Vault
- **CI/CD**: GitHub Actions, GitLab CI, Jenkins
- **Container**: Kubernetes
- **Local**: File storage in various formats

[Learn about providers →](providers/index.md)

### Generators

Generators create secret values using different methods:

- **random_password**: Cryptographically secure passwords
- **random_string**: Random alphanumeric strings
- **static**: Static values with validation
- **script**: Execute external scripts
- **api**: Fetch from external APIs

[Learn about generators →](generators/index.md)

### Targets

Targets specify where generated secrets should be stored. A single secret can have multiple targets, allowing you to sync secrets across different platforms.

[Learn about targets →](targets/index.md)

### Lockfile

The `.gitsecrets.lock` file tracks generated secrets using SHA-256 hashes, enabling:

- Idempotent secret generation
- Rotation tracking
- Drift detection
- Audit history

[Learn about lockfiles →](configuration/index.md#lockfile)

## Common Workflows

### Initial Setup

```bash
# Create a new Secretfile
secretzero init

# Validate configuration
secretzero validate

# Test provider connectivity
secretzero test
```

### Secret Generation

```bash
# Preview what would be generated
secretzero sync --dry-run

# Generate and sync secrets
secretzero sync

# Show information about a secret
secretzero show my_password
```

### Secret Rotation

```bash
# Check which secrets need rotation
secretzero rotate --dry-run

# Rotate secrets based on policies
secretzero rotate

# Force rotate a specific secret
secretzero rotate --force my_password
```

### Policy and Compliance

```bash
# Check policy compliance
secretzero policy

# Fail on warnings
secretzero policy --fail-on-warning

# Detect drift
secretzero drift
```

## Documentation Structure

### Configuration

Learn how to configure SecretZero:

- **[Configuration Overview](configuration/index.md)** - Core configuration concepts
- **[Secretfile Reference](configuration/secretfile.md)** - Complete Secretfile.yml specification
- **[Variables](configuration/variables.md)** - Variable interpolation and environment variables
- **[Validation](configuration/validation.md)** - Schema validation and error handling

### CLI Commands

Complete reference for all CLI commands:

- **[CLI Overview](cli/index.md)** - All available commands
- **[init](cli/init.md)** - Initialize new projects
- **[validate](cli/validate.md)** - Validate configuration
- **[sync](cli/sync.md)** - Generate and sync secrets
- **[show](cli/show.md)** - Display secret information
- **[rotate](cli/rotate.md)** - Rotate secrets
- **[policy](cli/policy.md)** - Check policy compliance
- **[drift](cli/drift.md)** - Detect configuration drift
- **[test](cli/test.md)** - Test provider connectivity

### Components

Deep dives into SecretZero components:

- **[Providers](providers/index.md)** - Provider configuration and authentication
- **[Generators](generators/index.md)** - Secret generation methods
- **[Targets](targets/index.md)** - Storage destinations

## Best Practices

### Secret Organization

```yaml
# Group related secrets using templates
templates:
  database_credentials:
    description: Database connection credentials
    fields:
      username:
        generator:
          kind: static
          config:
            default: dbuser
      password:
        generator:
          kind: random_password
          config:
            length: 32
```

### Environment Management

```yaml
# Use variables for environment-specific configuration
variables:
  environment: ${ENVIRONMENT:-dev}
  aws_region: ${AWS_REGION:-us-east-1}

secrets:
  - name: api_key
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /{{var.environment}}/api-key
```

### Rotation Policies

```yaml
# Define rotation policies for compliance
secrets:
  - name: database_password
    kind: random_password
    rotation_period: 90d  # SOC2 compliance
    config:
      length: 32
```

### One-Time Secrets

```yaml
# Secrets that should only be generated once
secrets:
  - name: encryption_key
    kind: random_password
    one_time: true
    rotation_period: 180d  # Warning only
    config:
      length: 64
```

## Getting Help

### Documentation

- **[Getting Started](../getting-started/index.md)** - New to SecretZero? Start here
- **[Examples](../examples/index.md)** - Real-world configuration examples
- **[Use Cases](../use-cases/index.md)** - Common usage patterns
- **[API Reference](api/index.md)** - REST API documentation
- **[FAQ](../reference/faq.md)** - Frequently asked questions
- **[Troubleshooting](../reference/troubleshooting.md)** - Common issues and solutions

### Community

- **GitHub**: [zloeber/SecretZero](https://github.com/zloeber/SecretZero)
- **Issues**: [Report bugs or request features](https://github.com/zloeber/SecretZero/issues)
- **Discussions**: [Ask questions and share ideas](https://github.com/zloeber/SecretZero/discussions)

## Next Steps

<div class="grid cards" markdown>

-   :material-file-cog: **Configure Your Project**

    ---

    Learn how to create and configure a Secretfile.yml
    
    [Configuration Guide →](configuration/index.md)

-   :material-terminal: **Master the CLI**

    ---

    Explore all available CLI commands and options
    
    [CLI Reference →](cli/index.md)

-   :material-book-multiple: **Explore Examples**

    ---

    Browse real-world configuration examples
    
    [View Examples →](../examples/index.md)

-   :material-lightbulb: **Learn Best Practices**

    ---

    Discover patterns and best practices
    
    [Use Cases →](../use-cases/index.md)

</div>
