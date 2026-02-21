# HashiCorp Vault Target

SecretZero supports **HashiCorp Vault** KV (Key-Value) secret engines for secure secret storage. Vault provides a unified interface for secret management across hybrid cloud, multi-cloud, and on-premises environments with advanced features like dynamic secrets, encryption as a service, and comprehensive audit logging.

## Overview

HashiCorp Vault KV targets allow you to:

- Store secrets in Vault's KV secret engines (v1 and v2)
- Leverage Vault's encryption and security features
- Integrate with multiple authentication methods (Token, AppRole, Kubernetes, AWS, Azure)
- Enable secret versioning and rollback (KV v2)
- Organize secrets hierarchically with custom mount points
- Implement fine-grained access control with Vault policies
- Audit all secret access with Vault's audit logging
- Deploy in hybrid and multi-cloud environments
- Use namespaces for multi-tenancy (Vault Enterprise)

## Prerequisites

### Installation

HashiCorp Vault support requires the HVAC (HashiCorp Vault API Client) library:

```bash
# Install with Vault support
pip install secretzero[vault]

# Or install hvac directly
pip install hvac
```

### Vault Server Setup

Ensure you have a Vault server running:

```bash
# Development server (not for production)
vault server -dev

# Production server requires configuration file
vault server -config=vault-config.hcl
```

For production deployments, see [Vault deployment guide](https://developer.hashicorp.com/vault/tutorials/day-one-raft/raft-deployment-guide).

## Authentication Methods

Vault supports multiple authentication methods. SecretZero integrates with the most common ones.

### Token Authentication

The simplest method, suitable for development and automation:

```yaml
providers:
  vault:
    kind: vault
    auth:
      kind: token
      url: https://vault.example.com:8200
      token: hvs.CAESID...  # Or use VAULT_TOKEN env var
```

**Environment variables:**
```bash
export VAULT_ADDR=https://vault.example.com:8200
export VAULT_TOKEN=hvs.CAESID...
```

```yaml
providers:
  vault:
    kind: vault
    auth:
      kind: token
      # url and token read from environment
```

### AppRole Authentication

Recommended for machine-to-machine authentication:

```yaml
providers:
  vault:
    kind: vault
    auth:
      kind: approle
      url: https://vault.example.com:8200
      role_id: 1234abcd-56ef-78gh-90ij-klmnopqrstuv
      secret_id: 9876zyxw-54vu-32ts-10rq-ponmlkjihgfe
```

**Setup AppRole:**
```bash
# Enable AppRole auth
vault auth enable approle

# Create role
vault write auth/approle/role/secretzero \
  token_policies="secretzero-policy" \
  token_ttl=1h \
  token_max_ttl=4h

# Get role ID
vault read auth/approle/role/secretzero/role-id

# Generate secret ID
vault write -f auth/approle/role/secretzero/secret-id
```

### Kubernetes Authentication

For applications running in Kubernetes:

```yaml
providers:
  vault:
    kind: vault
    auth:
      kind: kubernetes
      url: https://vault.example.com:8200
      role: secretzero-role
      # JWT token read from /var/run/secrets/kubernetes.io/serviceaccount/token
```

**Setup Kubernetes auth:**
```bash
# Enable Kubernetes auth
vault auth enable kubernetes

# Configure Kubernetes auth
vault write auth/kubernetes/config \
  kubernetes_host=https://kubernetes.default.svc:443

# Create role
vault write auth/kubernetes/role/secretzero-role \
  bound_service_account_names=secretzero \
  bound_service_account_namespaces=default \
  policies=secretzero-policy \
  ttl=1h
```

### AWS IAM Authentication

For AWS environments using IAM credentials:

```yaml
providers:
  vault:
    kind: vault
    auth:
      kind: aws
      url: https://vault.example.com:8200
      role: secretzero-role
      # Uses AWS credentials from environment/instance profile
```

### Azure Authentication

For Azure environments using managed identities:

```yaml
providers:
  vault:
    kind: vault
    auth:
      kind: azure
      url: https://vault.example.com:8200
      role: secretzero-role
      # Uses Azure managed identity
```

## KV Secret Engines

Vault provides two versions of the KV secret engine with different capabilities.

### KV Version 2 (Recommended)

KV v2 provides secret versioning, allowing you to track changes and roll back to previous versions.

**Features:**
- **Versioning** - Every secret update creates a new version
- **Metadata** - Track creation time, custom metadata
- **Soft delete** - Deleted versions can be undeleted
- **Check-and-Set** - Prevent concurrent updates
- **TTL** - Set automatic secret expiration

**Default mount:** `secret/`

### KV Version 1 (Legacy)

KV v1 provides simple key-value storage without versioning.

**Features:**
- **Simple storage** - Store and retrieve values
- **No versioning** - Updates overwrite previous values
- **Lower overhead** - Minimal metadata storage

**Use cases:** Simple environments, backwards compatibility

## Configuration

### Basic Configuration

```yaml
targets:
  - provider: vault
    kind: kv
    config:
      path: string          # Secret path (required)
      mount_point: string   # KV mount point (optional, default: "secret")
      version: integer      # KV version: 1 or 2 (optional, default: 2)
```

### Configuration Options

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `path` | string | Yes | - | Secret path in KV engine (e.g., `"myapp/config"`) |
| `mount_point` | string | No | `"secret"` | KV mount point path |
| `version` | integer | No | `2` | KV engine version: `1` or `2` |

### Path Structure

**KV v2 paths:**
```
# Store/update: mount_point/data/path
secret/data/myapp/config

# Retrieve: mount_point/data/path
secret/data/myapp/config

# Metadata: mount_point/metadata/path
secret/metadata/myapp/config
```

**Note:** SecretZero automatically handles the `/data/` and `/metadata/` prefixes for KV v2.

**KV v1 paths:**
```
# All operations: mount_point/path
secret/myapp/config
```

## Complete Examples

### Basic KV v2 Storage

Store secrets in Vault using default KV v2 engine:

```yaml
version: '1.0'

providers:
  vault:
    kind: vault
    auth:
      kind: token
      url: https://vault.example.com:8200
      token: hvs.CAESID...

secrets:
  - name: database_password
    kind: random_password
    config:
      length: 32
      special: true
      exclude_characters: '"@/\'
    targets:
      - provider: vault
        kind: kv
        config:
          path: myapp/database/password
          mount_point: secret
          version: 2
```

### KV v1 Usage

Use KV v1 for simple storage without versioning:

```yaml
version: '1.0'

providers:
  vault:
    kind: vault
    auth:
      kind: token
      url: https://vault.example.com:8200

secrets:
  - name: api_key
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      - provider: vault
        kind: kv
        config:
          path: myapp/api-key
          mount_point: kv-v1
          version: 1
```

**Enable KV v1 engine:**
```bash
vault secrets enable -path=kv-v1 -version=1 kv
```

### Custom Mount Points

Use different mount points for organizational separation:

```yaml
version: '1.0'

providers:
  vault:
    kind: vault
    auth:
      kind: approle
      url: https://vault.example.com:8200
      role_id: ${VAULT_ROLE_ID}
      secret_id: ${VAULT_SECRET_ID}

secrets:
  # Application secrets
  - name: app_secret_key
    kind: random_string
    config:
      length: 64
      charset: base64
    targets:
      - provider: vault
        kind: kv
        config:
          path: web/secret-key
          mount_point: applications

  # Infrastructure secrets
  - name: ssh_private_key
    kind: static
    config:
      value: |
        -----BEGIN RSA PRIVATE KEY-----
        ...
        -----END RSA PRIVATE KEY-----
    targets:
      - provider: vault
        kind: kv
        config:
          path: servers/prod/ssh-key
          mount_point: infrastructure

  # Database credentials
  - name: db_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: vault
        kind: kv
        config:
          path: postgres/prod/password
          mount_point: databases
```

**Setup custom mount points:**
```bash
vault secrets enable -path=applications kv-v2
vault secrets enable -path=infrastructure kv-v2
vault secrets enable -path=databases kv-v2
```

### Versioned Secrets

Leverage KV v2 versioning for change tracking:

```yaml
version: '1.0'

providers:
  vault:
    kind: vault
    auth:
      kind: token
      url: https://vault.example.com:8200

secrets:
  - name: rotating_api_key
    kind: random_string
    config:
      length: 32
    targets:
      - provider: vault
        kind: kv
        config:
          path: services/external-api/key
          version: 2
```

**Access secret versions:**
```bash
# Get current version
vault kv get secret/services/external-api/key

# Get specific version
vault kv get -version=2 secret/services/external-api/key

# View version history
vault kv metadata get secret/services/external-api/key

# Rollback to previous version
vault kv rollback -version=2 secret/services/external-api/key

# Undelete a version
vault kv undelete -versions=3 secret/services/external-api/key
```

### Hierarchical Secret Organization

Organize secrets using path hierarchies:

```yaml
version: '1.0'

providers:
  vault:
    kind: vault
    auth:
      kind: token
      url: https://vault.example.com:8200

secrets:
  # Production environment
  - name: prod_db_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: vault
        kind: kv
        config:
          path: myapp/prod/database/password

  - name: prod_redis_password
    kind: random_password
    config:
      length: 24
    targets:
      - provider: vault
        kind: kv
        config:
          path: myapp/prod/cache/redis/password

  - name: prod_api_key
    kind: random_string
    config:
      length: 32
    targets:
      - provider: vault
        kind: kv
        config:
          path: myapp/prod/api/external-service/key

  # Staging environment
  - name: staging_db_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: vault
        kind: kv
        config:
          path: myapp/staging/database/password

  - name: staging_api_key
    kind: random_string
    config:
      length: 32
    targets:
      - provider: vault
        kind: kv
        config:
          path: myapp/staging/api/external-service/key

  # Shared secrets
  - name: shared_encryption_key
    kind: random_string
    config:
      length: 64
      charset: hex
    targets:
      - provider: vault
        kind: kv
        config:
          path: myapp/shared/encryption/master-key
```

**Path structure:**
```
secret/data/myapp/
├── prod/
│   ├── database/
│   │   └── password
│   ├── cache/
│   │   └── redis/
│   │       └── password
│   └── api/
│       └── external-service/
│           └── key
├── staging/
│   ├── database/
│   │   └── password
│   └── api/
│       └── external-service/
│           └── key
└── shared/
    └── encryption/
        └── master-key
```

### Multi-Environment with Namespaces

Use Vault Enterprise namespaces for multi-tenancy:

```yaml
version: '1.0'

providers:
  vault_prod:
    kind: vault
    auth:
      kind: token
      url: https://vault.example.com:8200
      token: ${VAULT_TOKEN_PROD}
      namespace: production  # Vault Enterprise feature

  vault_dev:
    kind: vault
    auth:
      kind: token
      url: https://vault.example.com:8200
      token: ${VAULT_TOKEN_DEV}
      namespace: development

secrets:
  # Production namespace
  - name: prod_secret
    kind: random_password
    config:
      length: 32
    targets:
      - provider: vault_prod
        kind: kv
        config:
          path: myapp/database/password

  # Development namespace
  - name: dev_secret
    kind: random_password
    config:
      length: 32
    targets:
      - provider: vault_dev
        kind: kv
        config:
          path: myapp/database/password
```

**Namespace hierarchy:**
```
/
├── production/
│   └── secret/data/myapp/database/password
└── development/
    └── secret/data/myapp/database/password
```

### Microservices Architecture

Organize secrets for microservices:

```yaml
version: '1.0'

providers:
  vault:
    kind: vault
    auth:
      kind: kubernetes
      url: https://vault.example.com:8200
      role: microservices-role

secrets:
  # Shared service mesh certificates
  - name: service_mesh_ca
    kind: static
    config:
      value: |
        -----BEGIN CERTIFICATE-----
        ...
        -----END CERTIFICATE-----
    targets:
      - provider: vault
        kind: kv
        config:
          path: shared/service-mesh/ca-cert

  # Auth service
  - name: auth_db_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: vault
        kind: kv
        config:
          path: services/auth/database/password

  - name: auth_jwt_secret
    kind: random_string
    config:
      length: 64
      charset: base64
    targets:
      - provider: vault
        kind: kv
        config:
          path: services/auth/jwt/signing-key

  # Payment service
  - name: payment_stripe_key
    kind: static
    config:
      value: sk_live_...
    targets:
      - provider: vault
        kind: kv
        config:
          path: services/payment/stripe/api-key

  - name: payment_db_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: vault
        kind: kv
        config:
          path: services/payment/database/password

  # Notification service
  - name: notification_smtp_password
    kind: random_password
    config:
      length: 24
    targets:
      - provider: vault
        kind: kv
        config:
          path: services/notification/smtp/password

  - name: notification_twilio_token
    kind: static
    config:
      value: ${TWILIO_AUTH_TOKEN}
    targets:
      - provider: vault
        kind: kv
        config:
          path: services/notification/twilio/auth-token
```

### Structured Secrets

Store complex credentials as structured data:

```yaml
version: '1.0'

providers:
  vault:
    kind: vault
    auth:
      kind: token
      url: https://vault.example.com:8200

secrets:
  - name: database_credentials
    kind: templates.db_config

templates:
  db_config:
    fields:
      host:
        generator:
          kind: static
          config:
            default: postgres.example.com
      port:
        generator:
          kind: static
          config:
            default: "5432"
      database:
        generator:
          kind: static
          config:
            default: production
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
            special: true
      ssl_mode:
        generator:
          kind: static
          config:
            default: require
    targets:
      - provider: vault
        kind: kv
        config:
          path: myapp/database/config
```

**Retrieved as:**
```bash
vault kv get secret/myapp/database/config
```

```json
{
  "host": "postgres.example.com",
  "port": "5432",
  "database": "production",
  "username": "app_user",
  "password": "randompassword123456789012345678901",
  "ssl_mode": "require"
}
```

### Multi-Cloud Deployment

Deploy secrets across multiple cloud providers:

```yaml
version: '1.0'

providers:
  vault_aws:
    kind: vault
    auth:
      kind: aws
      url: https://vault-aws.example.com:8200
      role: secretzero-role

  vault_azure:
    kind: vault
    auth:
      kind: azure
      url: https://vault-azure.example.com:8200
      role: secretzero-role

  vault_gcp:
    kind: vault
    auth:
      kind: gcp
      url: https://vault-gcp.example.com:8200
      role: secretzero-role

secrets:
  # Global secrets replicated across clouds
  - name: global_api_key
    kind: random_string
    config:
      length: 32
    targets:
      - provider: vault_aws
        kind: kv
        config:
          path: global/api-key
      
      - provider: vault_azure
        kind: kv
        config:
          path: global/api-key
      
      - provider: vault_gcp
        kind: kv
        config:
          path: global/api-key

  # Cloud-specific secrets
  - name: aws_secrets
    kind: templates.aws_creds

  - name: azure_secrets
    kind: templates.azure_creds

  - name: gcp_secrets
    kind: templates.gcp_creds
```

## Differences Between KV v1 and KV v2

### Feature Comparison

| Feature | KV v1 | KV v2 |
|---------|-------|-------|
| **Versioning** | No | Yes - automatic versioning |
| **Rollback** | No | Yes - restore previous versions |
| **Soft Delete** | No | Yes - deleted versions can be undeleted |
| **Metadata** | Limited | Rich metadata with timestamps |
| **Check-and-Set** | No | Yes - prevent concurrent updates |
| **API Path** | `mount/path` | `mount/data/path` and `mount/metadata/path` |
| **Performance** | Faster (less overhead) | Slightly slower (metadata storage) |
| **Storage** | Minimal overhead | Higher overhead (versions + metadata) |

### Migration from KV v1 to KV v2

**1. Upgrade existing mount:**
```bash
# Check current version
vault secrets list -detailed

# Upgrade KV v1 to v2 (preserves data)
vault kv enable-versioning secret/
```

**2. Update SecretZero configuration:**
```yaml
# Before (KV v1)
config:
  path: myapp/secret
  version: 1

# After (KV v2)
config:
  path: myapp/secret
  version: 2
```

**3. Verify migration:**
```bash
# Check secret versions
vault kv metadata get secret/myapp/secret
```

## Integration with Vault Features

### Dynamic Secrets

Vault can generate dynamic credentials on-demand. While SecretZero focuses on static secrets, you can reference Vault's dynamic secrets:

```bash
# Enable database secrets engine
vault secrets enable database

# Configure PostgreSQL
vault write database/config/postgresql \
  plugin_name=postgresql-database-plugin \
  connection_url="postgresql://{{username}}:{{password}}@postgres:5432/mydb" \
  allowed_roles="app-role" \
  username="vault" \
  password="vault-password"

# Create role
vault write database/roles/app-role \
  db_name=postgresql \
  creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}';" \
  default_ttl="1h" \
  max_ttl="24h"

# Generate credentials (outside SecretZero)
vault read database/creds/app-role
```

### Encryption as a Service (Transit)

Use Vault's transit engine for encryption operations:

```bash
# Enable transit engine
vault secrets enable transit

# Create encryption key
vault write -f transit/keys/myapp

# Encrypt data
vault write transit/encrypt/myapp \
  plaintext=$(echo "sensitive data" | base64)

# Decrypt data
vault write transit/decrypt/myapp \
  ciphertext=vault:v1:8SDd3WHDOjf7mq69CyCqYjBXAiQQAVZRkFM13ok481zoCmHnSeDX9vyf7w==
```

### Secret Rotation

Implement secret rotation workflows:

```yaml
version: '1.0'

providers:
  vault:
    kind: vault
    auth:
      kind: token
      url: https://vault.example.com:8200

secrets:
  - name: rotating_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: vault
        kind: kv
        config:
          path: myapp/rotating/password
          version: 2  # Enables version history
```

**Rotation workflow:**
```bash
# 1. SecretZero updates secret (creates new version)
secretzero sync

# 2. Application reads new version
vault kv get -version=2 secret/myapp/rotating/password

# 3. If needed, rollback to previous version
vault kv rollback -version=1 secret/myapp/rotating/password

# 4. View rotation history
vault kv metadata get secret/myapp/rotating/password
```

### Response Wrapping

Secure secret delivery using response wrapping:

```bash
# Wrap secret response (1-time use token)
vault kv get -wrap-ttl=5m secret/myapp/password

# Client unwraps with single-use token
vault unwrap <wrapping-token>
```

## Best Practices

### 1. Secret Path Organization

Use consistent, hierarchical paths:

```yaml
# Good: Clear hierarchy
secrets/
  myapp/
    prod/
      database/
        password
      api/
        key
    staging/
      database/
        password

# Avoid: Flat structure
secrets/
  myapp-prod-db-pass
  myapp-prod-api-key
  myapp-staging-db-pass
```

### 2. Use KV v2 for Production

Enable versioning for better change tracking and recovery:

```yaml
config:
  version: 2  # Always use v2 for production
```

**Benefits:**
- Roll back mistakes
- Track change history
- Implement check-and-set for safety
- Enable secret rotation workflows

### 3. Implement Vault Policies

Create least-privilege policies:

```hcl
# Application read-only policy
path "secret/data/myapp/prod/*" {
  capabilities = ["read", "list"]
}

# SecretZero write policy
path "secret/data/myapp/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

path "secret/metadata/myapp/*" {
  capabilities = ["read", "list", "delete"]
}

# Admin policy
path "secret/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
```

**Apply policy:**
```bash
vault policy write secretzero-policy secretzero-policy.hcl
vault token create -policy=secretzero-policy
```

### 4. Enable Audit Logging

Monitor all secret access:

```bash
# Enable file audit device
vault audit enable file file_path=/var/log/vault/audit.log

# Enable syslog audit device
vault audit enable syslog tag="vault" facility="AUTH"

# View audit logs
tail -f /var/log/vault/audit.log | jq
```

**Audit log example:**
```json
{
  "time": "2024-01-15T10:30:00Z",
  "type": "response",
  "auth": {
    "token_type": "service",
    "policies": ["default", "secretzero-policy"]
  },
  "request": {
    "operation": "read",
    "path": "secret/data/myapp/prod/database/password"
  },
  "response": {
    "data": {
      "data": {},
      "metadata": {
        "version": 3
      }
    }
  }
}
```

### 5. Use Namespaces for Multi-Tenancy

Isolate environments or teams (Vault Enterprise):

```yaml
# Production namespace
providers:
  vault_prod:
    kind: vault
    auth:
      namespace: prod
      
# Development namespace
providers:
  vault_dev:
    kind: vault
    auth:
      namespace: dev
```

### 6. Implement Secret Versioning Strategy

Define version retention policies:

```bash
# Configure version retention
vault kv metadata put -max-versions=10 secret/myapp/password

# Configure check-and-set requirement
vault kv metadata put -cas-required=true secret/myapp/sensitive

# View metadata
vault kv metadata get secret/myapp/password
```

### 7. Use Token Policies

Create service-specific tokens:

```bash
# Short-lived token for CI/CD
vault token create \
  -policy=secretzero-policy \
  -ttl=1h \
  -use-limit=10

# Periodic token for services
vault token create \
  -policy=app-read-policy \
  -period=24h \
  -renewable
```

### 8. Secure Token Storage

Never commit tokens to version control:

```yaml
# Use environment variables
providers:
  vault:
    kind: vault
    auth:
      kind: token
      url: ${VAULT_ADDR}
      token: ${VAULT_TOKEN}  # From environment
```

```bash
# Set in CI/CD
export VAULT_ADDR=https://vault.example.com:8200
export VAULT_TOKEN=hvs.CAESID...

# Or use auth methods without tokens
# AppRole, Kubernetes, AWS IAM, Azure, etc.
```

### 9. High Availability Setup

Deploy Vault with HA for production:

```hcl
# vault-config.hcl
storage "raft" {
  path = "/vault/data"
  node_id = "node1"
  
  retry_join {
    leader_api_addr = "https://vault-1:8200"
  }
  retry_join {
    leader_api_addr = "https://vault-2:8200"
  }
}

listener "tcp" {
  address = "0.0.0.0:8200"
  tls_cert_file = "/vault/tls/cert.pem"
  tls_key_file = "/vault/tls/key.pem"
}

api_addr = "https://vault-node:8200"
cluster_addr = "https://vault-node:8201"
ui = true
```

### 10. Disaster Recovery

Implement backup and recovery:

```bash
# Take Raft snapshot
vault operator raft snapshot save backup.snap

# Restore from snapshot
vault operator raft snapshot restore backup.snap

# List snapshots
vault operator raft snapshot inspect backup.snap
```

## Troubleshooting

### Connection Failures

**Problem:** `VaultConnectionError` or connection timeouts.

**Solutions:**

1. **Verify Vault server is running:**
   ```bash
   vault status
   ```

2. **Check network connectivity:**
   ```bash
   curl https://vault.example.com:8200/v1/sys/health
   ```

3. **Verify TLS certificates:**
   ```bash
   openssl s_client -connect vault.example.com:8200
   ```

4. **Check firewall rules:**
   ```bash
   telnet vault.example.com 8200
   ```

### Authentication Failures

**Problem:** `VaultAuthError` or `permission denied`.

**Solutions:**

1. **Verify token is valid:**
   ```bash
   vault token lookup
   ```

2. **Check token policies:**
   ```bash
   vault token lookup -format=json | jq .data.policies
   ```

3. **Test authentication:**
   ```bash
   # Token auth
   vault login <token>
   
   # AppRole auth
   vault write auth/approle/login role_id=<role-id> secret_id=<secret-id>
   ```

4. **Verify auth method is enabled:**
   ```bash
   vault auth list
   ```

### Permission Denied

**Problem:** `403 permission denied` when accessing secrets.

**Solutions:**

1. **Check policy permissions:**
   ```bash
   vault policy read secretzero-policy
   ```

2. **Verify path capabilities:**
   ```bash
   vault token capabilities secret/data/myapp/password
   ```

3. **Test access:**
   ```bash
   vault kv get secret/myapp/password
   ```

4. **Update policy if needed:**
   ```hcl
   # Add required capabilities
   path "secret/data/myapp/*" {
     capabilities = ["create", "read", "update", "delete", "list"]
   }
   ```

### Secret Not Found

**Problem:** `404 secret not found` when retrieving secrets.

**Solutions:**

1. **Verify secret exists:**
   ```bash
   vault kv list secret/myapp
   ```

2. **Check path is correct:**
   ```bash
   # KV v2: Don't include /data/ in config path
   # SecretZero handles this automatically
   
   # Wrong:
   path: secret/data/myapp/password
   
   # Correct:
   path: myapp/password
   mount_point: secret
   ```

3. **Verify mount point:**
   ```bash
   vault secrets list
   ```

4. **Check secret version:**
   ```bash
   vault kv get -version=1 secret/myapp/password
   ```

### KV Version Mismatch

**Problem:** API errors due to incorrect KV version.

**Solutions:**

1. **Check KV version:**
   ```bash
   vault secrets list -detailed | grep secret
   ```

2. **Update configuration:**
   ```yaml
   # Match KV version in Vault
   config:
     path: myapp/password
     version: 2  # or 1
   ```

3. **Upgrade KV v1 to v2:**
   ```bash
   vault kv enable-versioning secret/
   ```

### Sealed Vault

**Problem:** `Vault is sealed` error.

**Solutions:**

1. **Check seal status:**
   ```bash
   vault status
   ```

2. **Unseal Vault:**
   ```bash
   vault operator unseal <unseal-key-1>
   vault operator unseal <unseal-key-2>
   vault operator unseal <unseal-key-3>
   ```

3. **Use auto-unseal (production):**
   ```hcl
   # AWS KMS auto-unseal
   seal "awskms" {
     region     = "us-east-1"
     kms_key_id = "alias/vault-unseal"
   }
   ```

### HVAC Library Issues

**Problem:** `ImportError: No module named 'hvac'`.

**Solution:**
```bash
pip install secretzero[vault]
# or
pip install hvac
```

## Security Considerations

### Encryption at Rest

Vault encrypts all data using AES-256-GCM:

```hcl
# Storage backend configuration
storage "raft" {
  path = "/vault/data"
}

# All data encrypted with master key
# Master key protected by seal mechanism
```

### Encryption in Transit

Always use TLS for Vault communication:

```hcl
listener "tcp" {
  address = "0.0.0.0:8200"
  tls_cert_file = "/vault/tls/cert.pem"
  tls_key_file = "/vault/tls/key.pem"
  tls_min_version = "tls12"
}
```

```yaml
# Use HTTPS URLs
providers:
  vault:
    auth:
      url: https://vault.example.com:8200  # Not http://
```

### Access Control

Implement fine-grained policies:

```hcl
# Read-only access to specific paths
path "secret/data/myapp/prod/*" {
  capabilities = ["read", "list"]
}

# Write access to specific paths
path "secret/data/myapp/staging/*" {
  capabilities = ["create", "read", "update", "delete"]
}

# Deny access to sensitive paths
path "secret/data/admin/*" {
  capabilities = ["deny"]
}
```

### Token Security

**Best practices:**

1. **Use short TTLs:**
   ```bash
   vault token create -ttl=1h
   ```

2. **Implement token renewal:**
   ```bash
   vault token renew
   ```

3. **Use periodic tokens for services:**
   ```bash
   vault token create -period=24h
   ```

4. **Revoke unused tokens:**
   ```bash
   vault token revoke <token>
   ```

5. **Use token accessors for management:**
   ```bash
   vault list auth/token/accessors
   vault token revoke -accessor <accessor>
   ```

### Audit Logging

Enable comprehensive audit logging:

```bash
# File-based audit log
vault audit enable file file_path=/var/log/vault/audit.log

# Syslog audit log
vault audit enable syslog

# Socket audit log
vault audit enable socket address=127.0.0.1:9090 socket_type=tcp
```

**Monitor audit logs:**
```bash
# Watch audit events
tail -f /var/log/vault/audit.log | jq 'select(.request.operation=="read")'

# Track failed authentication
tail -f /var/log/vault/audit.log | jq 'select(.error != null)'
```

### Secret Rotation

Implement regular rotation:

```yaml
# Use KV v2 for version history
secrets:
  - name: rotated_secret
    kind: random_password
    config:
      length: 32
    targets:
      - provider: vault
        kind: kv
        config:
          path: myapp/rotating-secret
          version: 2
```

**Rotation process:**
```bash
# 1. Generate new secret version
secretzero sync

# 2. Update applications to use new version
vault kv get -version=latest secret/myapp/rotating-secret

# 3. Verify applications are using new version
# 4. Delete old versions
vault kv delete -versions=1,2,3 secret/myapp/rotating-secret

# Or destroy permanently
vault kv destroy -versions=1,2,3 secret/myapp/rotating-secret
```

### Namespace Isolation

Use namespaces for multi-tenancy (Enterprise):

```yaml
# Isolate production from development
providers:
  vault_prod:
    kind: vault
    auth:
      namespace: production
      
  vault_dev:
    kind: vault
    auth:
      namespace: development
```

### Disaster Recovery

Implement DR strategy:

1. **Regular backups:**
   ```bash
   # Automated snapshot
   vault operator raft snapshot save /backups/vault-$(date +%Y%m%d).snap
   ```

2. **Test recovery:**
   ```bash
   # Test restore in separate environment
   vault operator raft snapshot restore /backups/vault-20240115.snap
   ```

3. **Replication (Enterprise):**
   ```bash
   # Enable DR replication
   vault write -f sys/replication/dr/primary/enable
   
   # Generate secondary token
   vault write sys/replication/dr/primary/secondary-token id=secondary1
   ```

## Vault Service Integration

### Kubernetes

**Vault Agent Injector:**

```yaml
# pod-with-secrets.yaml
apiVersion: v1
kind: Pod
metadata:
  name: myapp
  annotations:
    vault.hashicorp.com/agent-inject: "true"
    vault.hashicorp.com/role: "myapp-role"
    vault.hashicorp.com/agent-inject-secret-database: "secret/data/myapp/database"
spec:
  serviceAccountName: myapp
  containers:
  - name: app
    image: myapp:latest
```

**Vault CSI Provider:**

```yaml
# secretproviderclass.yaml
apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata:
  name: vault-secrets
spec:
  provider: vault
  parameters:
    vaultAddress: "https://vault.example.com:8200"
    roleName: "myapp-role"
    objects: |
      - objectName: "database-password"
        secretPath: "secret/data/myapp/database"
        secretKey: "password"
```

### Docker

```bash
# Run app with Vault secrets
docker run -e VAULT_ADDR=https://vault.example.com:8200 \
  -e VAULT_TOKEN=hvs.CAESID... \
  myapp:latest
```

### AWS Lambda

```python
import hvac
import os

def lambda_handler(event, context):
    # Use AWS IAM auth
    client = hvac.Client(url=os.environ['VAULT_ADDR'])
    client.auth.aws.iam_login(
        role='lambda-role',
        use_token=True,
        region='us-east-1'
    )
    
    # Read secret
    secret = client.secrets.kv.v2.read_secret_version(
        path='myapp/database',
        mount_point='secret'
    )
    
    password = secret['data']['data']['password']
    return {'statusCode': 200}
```

### Azure Functions

```python
import hvac
import os

def main(req):
    # Use Azure auth
    client = hvac.Client(url=os.environ['VAULT_ADDR'])
    client.auth.azure.login(
        role='function-role',
        jwt=get_azure_jwt()
    )
    
    # Read secret
    secret = client.secrets.kv.v2.read_secret_version(
        path='myapp/config',
        mount_point='secret'
    )
    
    return secret['data']['data']
```

## Next Steps

- Explore [AWS Secrets Manager](aws.md) for native AWS integration
- Learn about [Azure Key Vault](azure.md) for Azure environments
- Review [Kubernetes Secrets](kubernetes.md) for container workloads
- Check [examples](../../examples/index.md) for complete configurations
- Read [Vault documentation](https://developer.hashicorp.com/vault/docs) for advanced features
