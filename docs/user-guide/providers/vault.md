# HashiCorp Vault Provider

The HashiCorp Vault provider enables SecretZero to store and manage secrets in Vault's KV (Key-Value) secrets engine. It supports multiple authentication methods including token and AppRole authentication.

## Overview

The HashiCorp Vault provider is ideal for:

- **Multi-cloud deployments** requiring vendor-neutral secret management
- **Dynamic secret generation** with Vault's secrets engines
- **Production environments** with strict audit and compliance requirements
- **Kubernetes deployments** using Vault Agent or CSI driver integration
- **Organizations standardized on HashiCorp stack** (Terraform, Consul, Nomad)
- **Zero-trust architectures** requiring fine-grained access control

### Supported Target Types

| Target Type | Description | Use Case |
|-------------|-------------|----------|
| `kv` | Key-Value v2 secrets engine | Application secrets, configuration data, API keys, credentials |

## Authentication Methods

### Token Authentication

Use a Vault token for authentication. Best for development and testing.

```yaml
providers:
  vault:
    kind: vault
    auth:
      kind: token
      url: https://vault.example.com:8200
      token: s.xyz123abc456def789
```

**When to use**: Local development, testing, one-time operations, CI/CD with short-lived tokens.

#### Using Environment Variables

```yaml
providers:
  vault:
    kind: vault
    auth:
      kind: token
      url: https://vault.example.com:8200
      # token read from VAULT_TOKEN environment variable

# Set environment variable:
# export VAULT_TOKEN=s.xyz123abc456def789
# export VAULT_ADDR=https://vault.example.com:8200
```

### AppRole Authentication

Use AppRole for machine-to-machine authentication. Recommended for production applications.

```yaml
providers:
  vault:
    kind: vault
    auth:
      kind: approle
      url: https://vault.example.com:8200
      role_id: 12345678-1234-1234-1234-123456789012
      secret_id: 98765432-9876-5432-9876-543210987654
```

**When to use**: Production applications, automated systems, CI/CD pipelines, container deployments.

#### With Namespace

For Vault Enterprise with namespaces:

```yaml
providers:
  vault:
    kind: vault
    auth:
      kind: approle
      url: https://vault.example.com:8200
      role_id: 12345678-1234-1234-1234-123456789012
      secret_id: 98765432-9876-5432-9876-543210987654
      namespace: engineering/myapp
```

## Configuration

### Basic Configuration

```yaml
version: '1.0'

providers:
  vault:
    kind: vault
    auth:
      kind: token
      url: https://vault.example.com:8200
      token: s.xyz123abc456def789

secrets:
  - name: database_password
    kind: random_password
    config:
      length: 32
      special: true
    targets:
      - provider: vault
        kind: kv
        config:
          path: secret/data/myapp/db/password
```

### Multi-Namespace Configuration

Separate secrets by namespace (Vault Enterprise):

```yaml
providers:
  vault_dev:
    kind: vault
    auth:
      kind: token
      url: https://vault.example.com:8200
      namespace: dev
  
  vault_prod:
    kind: vault
    auth:
      kind: approle
      url: https://vault.example.com:8200
      role_id: prod-role-id
      secret_id: prod-secret-id
      namespace: production

secrets:
  - name: api_key
    kind: random_string
    config:
      length: 32
    targets:
      # Development namespace
      - provider: vault_dev
        kind: kv
        config:
          path: secret/data/myapp/api-key
      
      # Production namespace
      - provider: vault_prod
        kind: kv
        config:
          path: secret/data/myapp/api-key
```

### High Availability Configuration

Connect to Vault cluster:

```yaml
providers:
  vault:
    kind: vault
    auth:
      kind: approle
      url: https://vault.example.com:8200  # Load balancer or active node
      role_id: 12345678-1234-1234-1234-123456789012
      secret_id: 98765432-9876-5432-9876-543210987654

secrets:
  - name: critical_secret
    kind: random_password
    config:
      length: 32
    targets:
      - provider: vault
        kind: kv
        config:
          path: secret/data/critical/secret
```

## Target Type: KV (Key-Value v2)

Vault's KV v2 secrets engine provides versioned key-value secret storage with automatic versioning and metadata.

### Configuration Options

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `path` | string | Yes | - | Full path to secret including mount point (e.g., secret/data/myapp/db/password) |
| `mount_point` | string | No | `secret` | KV v2 mount point |
| `cas` | integer | No | - | Check-and-Set value for optimistic concurrency control |

### Example: Basic Secret

```yaml
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
          path: secret/data/myapp/api-key
```

### Example: Hierarchical Paths

Organize secrets with hierarchical paths:

```yaml
secrets:
  # Database secrets
  - name: db_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: vault
        kind: kv
        config:
          path: secret/data/myapp/prod/database/password
  
  - name: db_username
    kind: static
    config:
      default: admin
    targets:
      - provider: vault
        kind: kv
        config:
          path: secret/data/myapp/prod/database/username
  
  # API secrets
  - name: external_api_key
    kind: random_string
    config:
      length: 64
    targets:
      - provider: vault
        kind: kv
        config:
          path: secret/data/myapp/prod/api/external-key
```

### Example: Multi-Field Secret

Store multiple related values in a single secret:

```yaml
secrets:
  - name: database_config
    kind: templates.db_config

templates:
  db_config:
    description: Complete database configuration
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
            default: dbadmin
      password:
        generator:
          kind: random_password
          config:
            length: 32
            special: true
            exclude_characters: '"@\'
      ssl_mode:
        generator:
          kind: static
          config:
            default: require
    targets:
      - provider: vault
        kind: kv
        config:
          path: secret/data/myapp/database/config
```

The secret will be stored in Vault as:

```json
{
  "data": {
    "host": "postgres.example.com",
    "port": "5432",
    "database": "production",
    "username": "dbadmin",
    "password": "xyz789...",
    "ssl_mode": "require"
  },
  "metadata": {
    "created_time": "2024-01-15T10:30:00Z",
    "version": 1
  }
}
```

### Example: Custom Mount Point

Use a custom KV v2 mount:

```yaml
secrets:
  - name: app_secret
    kind: random_password
    config:
      length: 32
    targets:
      - provider: vault
        kind: kv
        config:
          mount_point: myapp-secrets
          path: myapp-secrets/data/prod/secret
```

## Complete Examples

### Example 1: Simple Application Secrets

```yaml
version: '1.0'

variables:
  environment: production
  vault_path_prefix: secret/data/myapp/{{var.environment}}
  vault_url: https://vault.example.com:8200

providers:
  vault:
    kind: vault
    auth:
      kind: approle
      url: "{{var.vault_url}}"
      role_id: "{{env.VAULT_ROLE_ID}}"
      secret_id: "{{env.VAULT_SECRET_ID}}"

secrets:
  # Database password
  - name: database_password
    kind: random_password
    rotation_period: 90d
    config:
      length: 32
      special: true
      exclude_characters: '"@/\'
    targets:
      - provider: vault
        kind: kv
        config:
          path: "{{var.vault_path_prefix}}/db/password"
  
  # API key
  - name: external_api_key
    kind: random_string
    config:
      length: 64
      charset: alphanumeric
    targets:
      - provider: vault
        kind: kv
        config:
          path: "{{var.vault_path_prefix}}/api/external-key"
  
  # JWT signing key
  - name: jwt_secret
    kind: random_string
    config:
      length: 128
      charset: alphanumeric
    targets:
      - provider: vault
        kind: kv
        config:
          path: "{{var.vault_path_prefix}}/jwt/signing-key"

metadata:
  project: myapp
  owner: backend-team
  environment: "{{var.environment}}"
```

### Example 2: Multi-Environment Setup

```yaml
version: '1.0'

variables:
  app_name: myapp
  vault_url: https://vault.example.com:8200

providers:
  vault_dev:
    kind: vault
    auth:
      kind: token
      url: "{{var.vault_url}}"
      # token from VAULT_TOKEN env var
  
  vault_staging:
    kind: vault
    auth:
      kind: approle
      url: "{{var.vault_url}}"
      role_id: staging-role-id
      secret_id: staging-secret-id
  
  vault_prod:
    kind: vault
    auth:
      kind: approle
      url: "{{var.vault_url}}"
      role_id: prod-role-id
      secret_id: prod-secret-id
      namespace: production

secrets:
  - name: database_password
    kind: random_password
    config:
      length: 32
      special: true
    targets:
      # Development
      - provider: vault_dev
        kind: kv
        config:
          path: secret/data/{{var.app_name}}/dev/db/password
      
      # Staging
      - provider: vault_staging
        kind: kv
        config:
          path: secret/data/{{var.app_name}}/staging/db/password
      
      # Production
      - provider: vault_prod
        kind: kv
        config:
          path: secret/data/{{var.app_name}}/prod/db/password
```

### Example 3: Microservices Architecture

```yaml
version: '1.0'

variables:
  vault_url: https://vault.example.com:8200
  environment: production

providers:
  vault:
    kind: vault
    auth:
      kind: approle
      url: "{{var.vault_url}}"
      role_id: "{{env.VAULT_ROLE_ID}}"
      secret_id: "{{env.VAULT_SECRET_ID}}"

secrets:
  # Service A secrets
  - name: service_a_db
    kind: templates.service_db
    
  # Service B secrets
  - name: service_b_api_key
    kind: random_string
    config:
      length: 64
    targets:
      - provider: vault
        kind: kv
        config:
          path: secret/data/services/service-b/api-key
  
  # Shared secrets
  - name: inter_service_token
    kind: random_string
    config:
      length: 128
    targets:
      - provider: vault
        kind: kv
        config:
          path: secret/data/shared/inter-service-token

templates:
  service_db:
    description: Service database credentials
    fields:
      host:
        generator:
          kind: static
          config:
            default: postgres-service-a.internal
      username:
        generator:
          kind: static
          config:
            default: service_a_user
      password:
        generator:
          kind: random_password
          config:
            length: 32
            special: true
      database:
        generator:
          kind: static
          config:
            default: service_a_db
    targets:
      - provider: vault
        kind: kv
        config:
          path: secret/data/services/service-a/database
```

### Example 4: PostgreSQL with Connection String

```yaml
version: '1.0'

providers:
  vault:
    kind: vault
    auth:
      kind: approle
      url: https://vault.example.com:8200
      role_id: "{{env.VAULT_ROLE_ID}}"
      secret_id: "{{env.VAULT_SECRET_ID}}"

secrets:
  - name: postgres_credentials
    kind: templates.postgres_full

templates:
  postgres_full:
    description: PostgreSQL credentials with connection string
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
            default: postgres
      password:
        generator:
          kind: random_password
          config:
            length: 32
            special: true
            exclude_characters: '"@/\`'
      connection_string:
        generator:
          kind: static
          config:
            default: "postgresql://postgres:{password}@postgres.example.com:5432/production?sslmode=require"
    targets:
      - provider: vault
        kind: kv
        config:
          path: secret/data/myapp/postgres/credentials
```

## Vault Policies and Permissions

### Required Vault Policies

For SecretZero to manage secrets, create a Vault policy with appropriate permissions.

#### Minimum Policy for KV v2

```hcl
# Policy: secretzero-kv-write
# Description: Allow SecretZero to write secrets to KV v2

# Read and write to secret paths
path "secret/data/myapp/*" {
  capabilities = ["create", "update", "read"]
}

# Read secret metadata
path "secret/metadata/myapp/*" {
  capabilities = ["read", "list"]
}

# Delete old versions (optional, for cleanup)
path "secret/delete/myapp/*" {
  capabilities = ["update"]
}

# Destroy versions (optional, for compliance)
path "secret/destroy/myapp/*" {
  capabilities = ["update"]
}
```

#### Policy for Multiple Applications

```hcl
# Policy: secretzero-multi-app
# Description: Manage secrets for multiple applications

path "secret/data/myapp/*" {
  capabilities = ["create", "update", "read"]
}

path "secret/data/otherapp/*" {
  capabilities = ["create", "update", "read"]
}

path "secret/metadata/*" {
  capabilities = ["read", "list"]
}
```

#### Policy with Namespace (Enterprise)

```hcl
# Policy: secretzero-namespaced
# Description: Manage secrets within a namespace

# Within the 'engineering' namespace
path "secret/data/myapp/*" {
  capabilities = ["create", "update", "read"]
}

path "secret/metadata/myapp/*" {
  capabilities = ["read", "list"]
}
```

### Setting Up AppRole

Create an AppRole for SecretZero:

```bash
# Enable AppRole auth method
vault auth enable approle

# Create policy
vault policy write secretzero-policy - <<EOF
path "secret/data/myapp/*" {
  capabilities = ["create", "update", "read"]
}

path "secret/metadata/myapp/*" {
  capabilities = ["read", "list"]
}
EOF

# Create AppRole
vault write auth/approle/role/secretzero \
  token_policies="secretzero-policy" \
  token_ttl=1h \
  token_max_ttl=4h \
  secret_id_ttl=0

# Get Role ID
vault read auth/approle/role/secretzero/role-id

# Generate Secret ID
vault write -f auth/approle/role/secretzero/secret-id
```

### Token Authentication Setup

Create a token with appropriate policy:

```bash
# Create policy
vault policy write secretzero-policy - <<EOF
path "secret/data/myapp/*" {
  capabilities = ["create", "update", "read"]
}

path "secret/metadata/myapp/*" {
  capabilities = ["read", "list"]
}
EOF

# Create token
vault token create \
  -policy=secretzero-policy \
  -ttl=8h \
  -renewable=true \
  -display-name="secretzero-dev"
```

## Best Practices

### 1. Use AppRole for Applications

```yaml
# Good: AppRole authentication for production
providers:
  vault:
    kind: vault
    auth:
      kind: approle
      url: https://vault.example.com:8200
      role_id: "{{env.VAULT_ROLE_ID}}"
      secret_id: "{{env.VAULT_SECRET_ID}}"

# Avoid: Token authentication in production
providers:
  vault:
    kind: vault
    auth:
      kind: token
      token: s.hardcoded-token  # Don't hardcode tokens!
```

**Why**: AppRole provides machine-to-machine authentication with role-based access control, while tokens are better suited for development.

### 2. Use Token Auth for Development

```yaml
# Good for development
providers:
  vault:
    kind: vault
    auth:
      kind: token
      url: http://localhost:8200
      # token from VAULT_TOKEN environment variable
```

**Why**: Token authentication is simpler for local development and testing, avoiding the complexity of AppRole setup.

### 3. Enable Audit Logging

```bash
# Enable audit logging to track all Vault operations
vault audit enable file file_path=/var/log/vault/audit.log

# Or use syslog
vault audit enable syslog
```

**Why**: Audit logs provide compliance records, security monitoring, and troubleshooting information.

### 4. Use Namespaces for Isolation (Enterprise)

```yaml
# Separate by team or environment
providers:
  vault_engineering:
    kind: vault
    auth:
      kind: approle
      url: https://vault.example.com:8200
      namespace: engineering
      role_id: eng-role-id
      secret_id: eng-secret-id
  
  vault_operations:
    kind: vault
    auth:
      kind: approle
      url: https://vault.example.com:8200
      namespace: operations
      role_id: ops-role-id
      secret_id: ops-secret-id
```

**Why**: Namespaces provide logical isolation, separate policies, and multi-tenancy support.

### 5. Implement Hierarchical Path Structure

```yaml
# Good: Clear, hierarchical structure
secret/data/myapp/prod/database/password
secret/data/myapp/prod/api/external-key
secret/data/myapp/staging/database/password

# Avoid: Flat structure
secret/data/myapp-prod-db-password
secret/data/api-key
secret/data/password1
```

**Why**: Hierarchical paths enable easier policy management, logical organization, and path-based access control.

### 6. Use Secret Versioning

KV v2 automatically versions secrets. Retrieve specific versions:

```bash
# Read latest version
vault kv get secret/myapp/db/password

# Read specific version
vault kv get -version=2 secret/myapp/db/password

# View version history
vault kv metadata get secret/myapp/db/password
```

### 7. Set Appropriate Token TTL

```yaml
# AppRole with reasonable TTL
vault write auth/approle/role/secretzero \
  token_policies="secretzero-policy" \
  token_ttl=1h \
  token_max_ttl=4h \
  secret_id_ttl=0
```

**Why**: Short TTL limits exposure window if credentials are compromised, while renewable tokens avoid frequent re-authentication.

### 8. Rotate AppRole Secret IDs

```bash
# Generate new Secret ID
vault write -f auth/approle/role/secretzero/secret-id

# Update application configuration
# Revoke old Secret ID after transition
```

**Why**: Regular rotation follows security best practices and limits credential lifetime.

## Integration Examples

### Python Application

```python
import hvac
import os

# Initialize Vault client
client = hvac.Client(url='https://vault.example.com:8200')

# Authenticate with AppRole
client.auth.approle.login(
    role_id=os.environ['VAULT_ROLE_ID'],
    secret_id=os.environ['VAULT_SECRET_ID']
)

# Read secret
secret = client.secrets.kv.v2.read_secret_version(
    path='myapp/database/config',
    mount_point='secret'
)

# Access secret data
db_password = secret['data']['data']['password']
db_host = secret['data']['data']['host']

# Use credentials
print(f"Connecting to {db_host}")
```

### Docker Compose

```yaml
version: '3.8'

services:
  app:
    image: myapp:latest
    environment:
      - VAULT_ADDR=https://vault.example.com:8200
      - VAULT_ROLE_ID=${VAULT_ROLE_ID}
      - VAULT_SECRET_ID=${VAULT_SECRET_ID}
    command: |
      sh -c '
        # Authenticate and fetch secrets
        export VAULT_TOKEN=$$(vault write -field=token auth/approle/login \
          role_id=$${VAULT_ROLE_ID} \
          secret_id=$${VAULT_SECRET_ID})
        
        # Read secrets
        export DB_PASSWORD=$$(vault kv get -field=password secret/myapp/db/password)
        
        # Start application
        python app.py
      '
```

### Kubernetes with Vault Agent Injector

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  template:
    metadata:
      annotations:
        vault.hashicorp.com/agent-inject: "true"
        vault.hashicorp.com/role: "myapp"
        vault.hashicorp.com/agent-inject-secret-database: "secret/data/myapp/database/config"
        vault.hashicorp.com/agent-inject-template-database: |
          {{- with secret "secret/data/myapp/database/config" -}}
          export DB_HOST="{{ .Data.data.host }}"
          export DB_USER="{{ .Data.data.username }}"
          export DB_PASSWORD="{{ .Data.data.password }}"
          export DB_NAME="{{ .Data.data.database }}"
          {{- end }}
    spec:
      serviceAccountName: myapp
      containers:
        - name: myapp
          image: myapp:latest
          command:
            - /bin/sh
            - -c
            - |
              source /vault/secrets/database
              python app.py
```

### Terraform Integration

```hcl
# Configure Vault provider
provider "vault" {
  address = "https://vault.example.com:8200"
}

# Read secret from Vault
data "vault_kv_secret_v2" "database" {
  mount = "secret"
  name  = "myapp/database/config"
}

# Use in AWS RDS instance
resource "aws_db_instance" "main" {
  username = data.vault_kv_secret_v2.database.data["username"]
  password = data.vault_kv_secret_v2.database.data["password"]
  # ... other configuration
}
```

### CI/CD Pipeline (GitHub Actions)

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
      
      - name: Import Secrets from Vault
        uses: hashicorp/vault-action@v2
        with:
          url: https://vault.example.com:8200
          method: approle
          roleId: ${{ secrets.VAULT_ROLE_ID }}
          secretId: ${{ secrets.VAULT_SECRET_ID }}
          secrets: |
            secret/data/myapp/prod/database password | DB_PASSWORD ;
            secret/data/myapp/prod/api external-key | API_KEY
      
      - name: Deploy Application
        run: |
          echo "Deploying with secrets from Vault"
          ./deploy.sh
        env:
          DB_PASSWORD: ${{ env.DB_PASSWORD }}
          API_KEY: ${{ env.API_KEY }}
```

## Troubleshooting

### Authentication Errors

**Error**: `Vault authentication failed. Check credentials and configuration.`

**Solutions**:

1. **Verify Vault is accessible**:
   ```bash
   curl -k https://vault.example.com:8200/v1/sys/health
   ```

2. **Test token authentication**:
   ```bash
   export VAULT_ADDR=https://vault.example.com:8200
   export VAULT_TOKEN=s.xyz123
   vault token lookup
   ```

3. **Test AppRole authentication**:
   ```bash
   vault write auth/approle/login \
     role_id=12345678-1234-1234-1234-123456789012 \
     secret_id=98765432-9876-5432-9876-543210987654
   ```

4. **Check namespace** (Enterprise):
   ```bash
   export VAULT_NAMESPACE=engineering
   vault token lookup
   ```

### Permission Denied Errors

**Error**: `permission denied`

**Solutions**:

1. **Check token capabilities**:
   ```bash
   vault token capabilities secret/data/myapp/db/password
   ```

2. **Review attached policies**:
   ```bash
   vault token lookup
   # Check 'policies' field in output
   ```

3. **Verify policy allows operation**:
   ```bash
   vault policy read secretzero-policy
   ```

4. **Test with root token** (temporarily):
   ```bash
   vault login <root-token>
   vault kv put secret/myapp/test value=test
   # If this works, it's a policy issue
   ```

### Namespace Errors

**Error**: `namespace not found` or secrets not accessible

**Solutions**:

1. **List available namespaces** (Enterprise):
   ```bash
   vault namespace list
   ```

2. **Set correct namespace**:
   ```bash
   export VAULT_NAMESPACE=engineering
   vault kv list secret/
   ```

3. **Verify namespace in configuration**:
   ```yaml
   providers:
     vault:
       kind: vault
       auth:
         kind: approle
         url: https://vault.example.com:8200
         namespace: engineering  # Must match Vault namespace
         role_id: role-id
         secret_id: secret-id
   ```

### Sealed Vault

**Error**: `Vault is sealed`

**Solutions**:

1. **Check Vault status**:
   ```bash
   vault status
   ```

2. **Unseal Vault**:
   ```bash
   vault operator unseal <unseal-key-1>
   vault operator unseal <unseal-key-2>
   vault operator unseal <unseal-key-3>
   ```

3. **Auto-unseal configuration** (production):
   ```hcl
   # Vault configuration with auto-unseal
   seal "awskms" {
     region     = "us-east-1"
     kms_key_id = "alias/vault-unseal-key"
   }
   ```

### Path Not Found

**Error**: `secret not found at path`

**Solutions**:

1. **Verify KV v2 path format**:
   ```bash
   # Correct KV v2 path includes /data/
   vault kv get secret/myapp/db/password
   # API path: secret/data/myapp/db/password
   ```

2. **Check mount point**:
   ```bash
   vault secrets list
   # Verify mount point (usually 'secret/')
   ```

3. **List available secrets**:
   ```bash
   vault kv list secret/myapp/
   ```

### Connection Errors

**Error**: `connection refused` or `timeout`

**Solutions**:

1. **Check Vault server is running**:
   ```bash
   systemctl status vault  # On Linux
   ps aux | grep vault     # Process check
   ```

2. **Verify network connectivity**:
   ```bash
   nc -zv vault.example.com 8200
   telnet vault.example.com 8200
   ```

3. **Check firewall rules**:
   ```bash
   # On Vault server
   sudo iptables -L -n | grep 8200
   ```

4. **Verify TLS certificate** (if using HTTPS):
   ```bash
   openssl s_client -connect vault.example.com:8200
   ```

## Cost Optimization and Performance

### Vault deployment options

HashiCorp publishes multiple Vault distribution and hosting options; features such as namespaces, replication, and HSM support depend on the edition and how you deploy. Refer to [HashiCorp Vault](https://www.vaultproject.io/) documentation for current capabilities and deployment models.

### Performance Tips

#### 1. Use Local Caching

Cache secrets in application memory:

```python
import hvac
import time
from threading import Lock

class VaultCache:
    def __init__(self, vault_client, ttl=3600):
        self.client = vault_client
        self.cache = {}
        self.ttl = ttl
        self.lock = Lock()
    
    def get_secret(self, path):
        with self.lock:
            if path in self.cache:
                value, timestamp = self.cache[path]
                if time.time() - timestamp < self.ttl:
                    return value
            
            # Fetch from Vault
            secret = self.client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point='secret'
            )
            value = secret['data']['data']
            self.cache[path] = (value, time.time())
            return value

# Usage
client = hvac.Client(url='https://vault.example.com:8200')
cache = VaultCache(client, ttl=3600)
db_config = cache.get_secret('myapp/database/config')
```

#### 2. Use Vault Agent for Caching

Deploy Vault Agent as a sidecar:

```hcl
# vault-agent.hcl
pid_file = "./pidfile"

vault {
  address = "https://vault.example.com:8200"
}

auto_auth {
  method "approle" {
    mount_path = "auth/approle"
    config = {
      role_id_file_path   = "/etc/vault/role-id"
      secret_id_file_path = "/etc/vault/secret-id"
    }
  }

  sink "file" {
    config = {
      path = "/tmp/vault-token"
    }
  }
}

cache {
  use_auto_auth_token = true
}

listener "tcp" {
  address     = "127.0.0.1:8200"
  tls_disable = true
}
```

#### 3. Batch Operations

Minimize API calls by batching:

```python
# Read multiple secrets efficiently
secrets_to_read = [
    'myapp/database/config',
    'myapp/api/external-key',
    'myapp/jwt/signing-key'
]

secrets = {}
for path in secrets_to_read:
    secret = client.secrets.kv.v2.read_secret_version(
        path=path,
        mount_point='secret'
    )
    secrets[path] = secret['data']['data']
```

#### 4. Use Connection Pooling

```python
import hvac
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Configure retry strategy
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504]
)

adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=10)

client = hvac.Client(url='https://vault.example.com:8200')
client.session.mount('https://', adapter)
```

### High Availability Setup

Deploy Vault in HA mode with integrated storage (Raft):

```hcl
# vault.hcl
storage "raft" {
  path    = "/opt/vault/data"
  node_id = "vault-1"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = false
  tls_cert_file = "/etc/vault/tls/vault.crt"
  tls_key_file  = "/etc/vault/tls/vault.key"
}

api_addr = "https://vault-1.example.com:8200"
cluster_addr = "https://vault-1.example.com:8201"
ui = true
```

### Monitoring and Metrics

Enable telemetry for monitoring:

```hcl
# vault.hcl
telemetry {
  prometheus_retention_time = "30s"
  disable_hostname = false
}
```

Monitor key metrics:
- Token creation/revocation rate
- Secret read/write latency
- Authentication success/failure rate
- Storage backend performance

## See Also

- [Providers Overview](index.md)
- [AWS Provider](aws.md)
- [Azure Provider](azure.md)
- [HashiCorp Vault Documentation](https://www.vaultproject.io/docs)
- [Vault API Documentation](https://www.vaultproject.io/api-docs)
- [HVAC Python Client](https://hvac.readthedocs.io/)
