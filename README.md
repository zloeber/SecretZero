# SecretZero

SecretZero is a secrets orchestration, lifecycle, and bootstrap engine.

<img 
    style="display: block; 
           margin-left: auto;
           margin-right: auto;
           width: 80%;"
    src="./docs/inc/secret0_angel_small.png" 
    alt="Secret0 Logo">
</img>

SecretZero is a secrets management tool that automates the creation, seeding, and lifecycle management of project secrets through self-documenting declarative manifests. The very first secrets you seed for a new project or environment (known in the industry as 'secret-zero') become timestamped, rotatable, and maintainable with git-compatible lock files.

## The Problem

If you have ever asked any of these questions about a new or existing codebase then SecretZero is for you!

- Where are all the secrets in my project?
- How do I generate new secrets, api keys, or certificates to deploy a whole new environment?
- How do I handle secret-zero?
- When were my critical project secrets last rotated?
- If I needed to bootstrap this entire project from scratch would I be able to do so without manually handling any secrets?
- How do I document my project's secrets surface area and requirements?

## Features

### Core Capabilities
- **Idempotent bootstrap** of initial secrets for one or more environments
- **Lockfile tracking** for secrets with rotation history and timestamps
- **Dual-purpose providers** that can both request/rotate new secrets and store them across a variety of environments
- **Type safety and validation** at every layer with strongly-typed Pydantic models
- **Multiple profiles** for targeting multiple environments independently
- **Manual secret fallbacks** via environment variables when automatic generation isn't possible
- **Self-documenting** secrets-as-code showing when secrets were created, from where, and where they are now

### Phase 6: Advanced Features (NEW)
- **Secret Rotation Policies** - Automated rotation based on configurable time periods (90d, 2w, etc.)
- **Policy Enforcement** - Validate secrets against rotation, compliance, and access control policies
- **Compliance Support** - Built-in SOC2 and ISO27001 compliance policies
- **Drift Detection** - Detect when secrets have been modified outside of SecretZero's control
- **Rotation Tracking** - Track rotation history, count, and last rotation timestamp in lockfile
- **One-time Secrets** - Support for secrets that should only be generated once

### Phase 7: API Service (NEW)
- **REST API** - FastAPI-based HTTP API for programmatic secret management
- **OpenAPI Documentation** - Interactive API docs with Swagger UI and ReDoc
- **API Authentication** - Secure API key-based authentication
- **Audit Logging** - Comprehensive audit trail for all API operations
- **Remote Management** - Manage secrets from CI/CD pipelines, scripts, or applications

### CLI Commands
```bash
# Initialize and validate
secretzero create                    # Create new Secretfile from template
secretzero init                      # Check and install provider dependencies
secretzero validate                # Validate Secretfile configuration
secretzero test                    # Test provider connectivity

# Secret management
secretzero sync                    # Generate and sync secrets to targets
secretzero sync --dry-run         # Preview changes without applying
secretzero sync -s db_password    # Sync only specific secret(s)
secretzero show <secret>          # Show secret metadata

# Visualization
secretzero graph                   # Generate visual flow diagram
secretzero graph --type detailed  # Show detailed configuration
secretzero graph --type architecture  # Show system architecture
secretzero graph --format terminal    # Text-based summary
secretzero graph --output diagram.md  # Save to file

# Rotation and policies (Phase 6)
secretzero rotate                  # Rotate secrets based on policies
secretzero rotate --dry-run       # Preview rotation status
secretzero rotate --force         # Force rotation even if not due
secretzero policy                  # Check policy compliance
secretzero drift                   # Detect drift in secrets

# Provider management
secretzero providers list          # List available providers
secretzero providers capabilities  # Show provider capabilities
secretzero providers token-info    # Show GitHub token permissions
secretzero providers token-info --provider github  # Explicit provider

# API Server (Phase 7)
secretzero-api                     # Start REST API server
```

### API Endpoints
```bash
# Health and documentation
GET  /                             # API info
GET  /health                       # Health check
GET  /docs                         # Interactive Swagger UI
GET  /redoc                        # ReDoc documentation

# Secret management
GET  /secrets                      # List all secrets
GET  /secrets/{name}/status        # Get secret status
POST /sync                         # Sync/generate secrets
POST /config/validate              # Validate configuration

# Rotation and policies
POST /rotation/check               # Check rotation status
POST /rotation/execute             # Execute rotation
POST /policy/check                 # Check policy compliance
POST /drift/check                  # Check for drift

# Audit and monitoring
GET  /audit/logs                   # Get audit logs
```

## How It Works

At its core SecretZero is a declarative manifest that defines your secret usage in a project then does its very best to help you request and seed your secrets. It is like a package dependency list but for your secrets. SecretZero processes a simple declarative configuration file in your project that lays out where your secrets come from and where they need to go. 


A user with all the correctly authenticated providers can run 'secretzero sync' to bootstrap the environment from scratch. SecretZero will validate if the environment has already been bootstrapped (lockfile) and attempt to automate requesting and storing them. In it's simplest form, you can use the local system to generate random passwords for you then store them into AWS Secrets Manager, A local .env file, Azure KeyVault, Kubernetes Secret, or Vault KV store.

SecretZero is composed of providers and secret types. Providers determine where you can request secrets from and how they can be stored. These are typically associated with an authenticated platform such as AWS, Azure, HashiCorp Vault, or external API endpoints. Secret types are expected secret formats such as generic random passwords, api tokens, database credentials, ssh keys, certificates, or more. Below is an ideal workflow without the details of authentication.

```mermaid
sequenceDiagram
  participant User
  participant SecretZero
  participant Vault as HashiCorp Vault
  participant LocalFS as Local Filesystem
  participant VaultKV as Vault KV Store

  User->>SecretZero: secretzero sync
  SecretZero->>Vault: Request random password generation
  Vault-->>SecretZero: Generated password
  SecretZero->>LocalFS: Write to .env file (template provider)
  SecretZero->>VaultKV: Store secret at kv/path
  SecretZero->>User: ✓ Secret synced to 2 targets
```

Here is a more complex example workflow for a randomly generated initial database credential that then gets stored in a local .env file, aws secret manager secret, and Hashicorp Vault KV store:

```mermaid
graph LR
  Source[Secret Source<br/>Local Generator]
  Secret[Secret Object<br/>postgres-password<br/>type: password]
  Target1[Target 1<br/>AWS Secrets Manager<br/>prod/db/postgres]
  Target2[Target 2<br/>Local .env File<br/>DATABASE_PASSWORD]
  Target3[Target 3<br/>Vault KV Store<br/>kv/prod/postgres]
  

  Source -->|generates| Secret
  Secret -->|syncs to| Target1
  Secret -->|syncs to| Target2
  Secret -->|syncs to| Target3
  
  style Source fill:#e1f5ff
  style Secret fill:#fff4e1
  style Target1 fill:#e8f5e9
  style Target2 fill:#e8f5e9
  style Target3 fill:#e8f5e9
```

Here is the sequence of events for a developer that needs to maintain a manually requested API key for their project using SecretZero to help bootstrap and create a lockfile for the process thus tracking and timestamping the process for future rotation.
```mermaid
sequenceDiagram
  participant User
  participant SecretZero
  participant ThirdParty as Third-Party Service
  participant GitLab as GitLab CI/CD Variable
  participant LockFile as .gitsecrets.lock

  User->>SecretZero: secretzero sync

  SecretZero->>GitLab: Check authentication status
  alt Not authenticated
    SecretZero->>User: ✗ Error: GitLab authentication required
    Note over SecretZero,User: Cannot proceed without credentials<br/>to write to target, GitLab CICD Variable
  else User is authenticated

    SecretZero->>LockFile: Check for existing entry
    alt Lockfile entry exists
      LockFile-->>SecretZero: Secret already synced
      SecretZero->>User: ✓ Skipped (already exists in lockfile)
    else No lockfile entry
      SecretZero->>User: Prompt: Enter API key for 'service-api-key'
      User->>ThirdParty: Manually create API key
      ThirdParty-->>User: API key value
      User->>SecretZero: Paste API key
      SecretZero->>GitLab: Store as CI/CD variable
      SecretZero->>LockFile: Update with metadata hash
      SecretZero->>User: ✓ Secret synced to GitLab + lockfile updated
    end
  end
```

Here is the sequence of events for a developer that needs to maintain an Azure Application ID credential for their project using SecretZero. Authentication is required to both request the credential via Azure API and store it in Azure Key Vault. If possible SecretZero providers will attempt to automatically request secrets. If that request fails then it fails back to manual prompting.

```mermaid
sequenceDiagram
  participant User
  participant SecretZero
  participant Azure as Azure AD API
  participant AzureKV as Azure Key Vault
  participant LockFile as .gitsecrets.lock

  User->>SecretZero: secretzero sync
  SecretZero->>Azure: Check authentication status
  alt Not authenticated
    SecretZero->>User: ✗ Error: Azure authentication required
    Note over SecretZero,User: Cannot proceed without credentials<br/>to write to target, Azure Key Vault
  else User is authenticated
    SecretZero->>LockFile: Check for existing entry
    alt Lockfile entry exists
      LockFile-->>SecretZero: Secret already synced
      SecretZero->>User: ✓ Skipped (already exists in lockfile)
    else No lockfile entry
      SecretZero->>Azure: Request new Application ID + client secret
      Azure-->>SecretZero: App ID & secret created
      SecretZero->>AzureKV: Store credentials
      SecretZero->>LockFile: Update with metadata hash
      SecretZero->>User: ✓ Secret auto-generated and synced to Azure Key Vault
    end
  end
```
Here is the sequence of events for a developer that needs to maintain an Azure Application ID credential for their project using SecretZero. Authentication is required to request the credential via Azure API. If Azure authentication fails, SecretZero falls back to manual credential entry. The credentials are then stored as a GitHub CI/CD secret that the user is authenticated against.

```mermaid
sequenceDiagram
  participant User
  participant SecretZero
  participant Azure as Azure AD API
  participant GitHub as GitHub Secret
  participant LockFile as .gitsecrets.lock

  User->>SecretZero: secretzero sync
  SecretZero->>LockFile: Check for existing entry
  alt Lockfile synced
    LockFile-->>SecretZero: Secret already synced
    SecretZero->>User: ✓ Skipped (already exists in lockfile)
  else Lockfile unsynced
    SecretZero->>GitHub: Check authentication status
    alt GitHub authenticated
      SecretZero->>Azure: Check authentication status
      alt Azure authenticated
        SecretZero->>Azure: Request new Application ID + client secret
        Azure-->>SecretZero: App ID & secret created
      else Not authenticated
        SecretZero->>User: ⚠ Azure Auth failed (falling back to manual entry)
        SecretZero->>User: Prompt: Enter Application ID
        User->>SecretZero: Provide App ID
        SecretZero->>User: Prompt: Enter client secret
        User->>SecretZero: Provide client secret
      end
    else
      SecretZero->>User: ⚠ GitHub Auth failed!
    end
    SecretZero->>GitHub: Store credentials as CI/CD secret
    SecretZero->>LockFile: Update with metadata hash
    SecretZero->>User: ✓ Secret synced to GitHub Actions + lockfile updated
  end
```

## Auto-Authentication

Not shown in the above workflows are the fact that SecretZero will attempt to also automatically authenticate via OIDC, environment variables, or whichever manner the provider is able to support.

### Checking Provider Permissions

SecretZero can introspect provider authentication tokens to verify they have the necessary permissions:

```bash
# Check GitHub token permissions and scopes
secretzero providers token-info

# Output shows:
# - User information
# - OAuth scopes (repo, workflow, admin:org, etc.)
# - Capabilities (can read repos, write secrets, etc.)
# - Links to documentation on permission requirements
```

This is useful for:
- **Troubleshooting** - Verify token has required scopes before attempting operations
- **Security auditing** - Document what permissions are granted to tokens
- **Compliance** - Ensure tokens follow principle of least privilege
- **Onboarding** - Help new team members create tokens with correct permissions

Currently supported providers: GitHub (more providers coming soon).

## Use Cases

### GitOps-First Infrastructure

Easy to read lockfiles are 100% git friendly. Perfect for teams deploying infrastructure via GitOps where secrets need automated provisioning across multiple environments without manual intervention.

### Multi-Cloud Secret Synchronization

Sync secrets across AWS Secrets Manager, Azure Key Vault, and HashiCorp Vault simultaneously from a single source of truth.

### Database Credential Bootstrapping

Generate and rotate database credentials (PostgreSQL, MySQL, MongoDB) during initial deployment or scheduled rotation cycles.

### Certificate Management

Automate creation and distribution of TLS certificates, SSH keypairs, and signing certificates across development, staging, and production environments.

### CI/CD Secret Provisioning

Bootstrap CI/CD pipeline secrets (GitHub Actions, GitLab CI, Jenkins) from centralized configuration without storing credentials in version control.

### Kubernetes Secret Seeding

Generate and deploy secrets to multiple Kubernetes clusters/namespaces during cluster initialization or application deployment.
- Generate externals secrets operator manifests for target secrets.

### Development Environment Setup

New team members can bootstrap their local `.env` files with production-like secrets in seconds without manual credential sharing.

### Compliance & Audit Requirements

Maintain an auditable lockfile showing when secrets were created, last rotated, and where they're deployed for SOC2/ISO compliance.

### Secret-Zero Problem

Solve the "where do the first secrets come from" challenge when deploying greenfield infrastructure or disaster recovery scenarios.

### API Key Lifecycle Management

Track and rotate third-party API keys (Stripe, SendGrid, Twilio) across multiple services while maintaining synchronization.

### Microservices Secret Coordination

Ensure all microservices receive consistent shared secrets (JWT signing keys, encryption keys) across distributed deployments.

### Environment Parity Testing

Quickly spin up ephemeral test environments with production-like secrets for integration testing without exposing real credentials.


# Components

These are the core components of this application.

## Secrets

Secrets are usually just a text or dict type. In our case we use a schema of allowed values so that we can easily map out a secret type when requesting it from the provider (kinda need to know what you are asking for right?). This is really a contract used for expected data from a provider and then expressed in targets.

> **NOTE** All secrets have a source and at least 1 or more targets.

## Providers

Providers are similar to terraform providers and are often an authentication point granting API access to secret sources or targets.

Secret sources are provider bound. If authentication fails, the user is (optionally) prompted for secrets manually as a failover. This is often necessary if there is a manual request somewhere in your bootstrap process.

## Installation

### Basic Installation

```bash
pip install secretzero
```

### With Provider Support

```bash
# AWS support
pip install secretzero[aws]

# Azure support
pip install secretzero[azure]

# Vault support
pip install secretzero[vault]

# Kubernetes support
pip install secretzero[kubernetes]

# CI/CD support (GitHub, GitLab, Jenkins)
pip install secretzero[cicd]

# API server support
pip install secretzero[api]

# Everything
pip install secretzero[all]
```

## Installation (Development)

```bash
# Clone the repository
git clone https://github.com/zloeber/SecretZero.git
cd SecretZero

# Create virtual environment (include pip and other tools)
uv sync --all-extras
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
uv pip install -e ".[dev]"
```

## Quick Start

### CLI Usage

```bash
# List supported secret types
secretzero secret-types

# Show detailed configuration for a specific type
secretzero secret-types --type password --verbose

# Create a new manifest from template
secretzero create --template-type basic

# Validate your manifest
secretzero validate

# Test provider connectivity
secretzero test

# Generate and sync secrets (dry-run)
secretzero sync --dry-run
```

### API Server

```bash
# Install API dependencies
pip install secretzero[api]

# Set API key (optional, enables authentication)
export SECRETZERO_API_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")

# Start server
secretzero-api

# Server runs on http://localhost:8000
# Visit http://localhost:8000/docs for interactive API documentation
```

### API Usage Examples

```bash
# Health check
curl http://localhost:8000/health

# List secrets (with authentication)
curl -H "X-API-Key: $SECRETZERO_API_KEY" http://localhost:8000/secrets

# Sync secrets
curl -X POST -H "X-API-Key: $SECRETZERO_API_KEY" \
  -H "Content-Type: application/json" \
  http://localhost:8000/sync \
  -d '{"dry_run": true, "force": false}'

# Check rotation status
curl -X POST -H "X-API-Key: $SECRETZERO_API_KEY" \
  -H "Content-Type: application/json" \
  http://localhost:8000/rotation/check \
  -d '{}'
```

For more API examples, see [docs/api-getting-started.md](docs/api-getting-started.md).

# Actually create and deploy secrets
secretzero sync
```

## Example Manifest

** See [Secretfile.yml](./Secretfile.yml) **

## Documentation

- **[Docs][./docs]**
- **[Extending SecretZero](./docs/extending.md)** - Guide for adding new secret types and providers

## Security

SecretZero is designed with security as a priority:

- ✅ No plaintext secrets in lock files (only metadata hashes)
- ✅ Schema-driven validation at every layer
- ✅ Type-safe implementations with Pydantic
- ✅ Idempotent operations to prevent accidental overwrites
- ✅ Audit trail through lock file tracking

## License

[Apache](./LICENSE)

# FAQs

## Relationship to External Secrets Operator

SecretZero is designed to complement, not replace, the External Secrets Operator. 

SecretZero manages secret creation, bootstrap, lifecycle, and auditability upstream, while External Secrets handles runtime projection into Kubernetes.

## Relationship to [Vault|Infiscal|Others]

A secrets management solution like Infisical is a strong control plane for secret storage and policy. SecretZero compliments this and other secrets solutions by adding deterministic orchestration and cross-provider lifecycle modeling. We simply map out the secrets from inception to usage and beyond.