# Azure Provider

The Azure provider enables SecretZero to store and manage secrets in Azure Key Vault. It supports multiple authentication methods including Managed Identity, Default Azure Credential chain, and Azure CLI authentication.

## Overview

The Azure provider is ideal for:

- **Azure-native applications** running on Azure App Service, Azure Functions, AKS, or Azure VMs
- **Managed Identity authentication** for secure, credential-free access
- **Production applications** requiring centralized secret management with RBAC
- **Multi-cloud deployments** needing Azure integration
- **Compliance requirements** that mandate Azure-native security services

### Supported Target Types

| Target Type | Description | Use Case |
|-------------|-------------|----------|
| `key_vault` | Azure Key Vault Secrets | Application secrets, certificates, connection strings, API keys |

## Authentication Methods

### Default Credential Chain (Recommended)

The default authentication method tries multiple credential sources in order:

1. **Environment variables** (`AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`)
2. **Managed Identity** (if running on Azure infrastructure)
3. **Azure CLI** (if authenticated via `az login`)
4. **Visual Studio Code** (if authenticated)
5. **Azure PowerShell** (if authenticated)

```yaml
providers:
  azure:
    kind: azure
    auth:
      kind: default
```

**When to use**: Most scenarios, especially production environments with Managed Identity or development with Azure CLI.

### Managed Identity Authentication

Use the system-assigned or user-assigned managed identity of Azure resources:

```yaml
# System-assigned managed identity
providers:
  azure:
    kind: azure
    auth:
      kind: managed_identity

# User-assigned managed identity
providers:
  azure:
    kind: azure
    auth:
      kind: managed_identity
      client_id: 12345678-1234-1234-1234-123456789012
```

**When to use**: Production deployments on Azure App Service, Azure Functions, AKS, Azure VMs, or Azure Container Instances.

### Azure CLI Authentication

Use credentials from the Azure CLI (`az login`):

```yaml
providers:
  azure:
    kind: azure
    auth:
      kind: cli
```

**When to use**: Local development, testing, CI/CD pipelines with Azure CLI pre-authenticated.

## Configuration

### Basic Configuration

```yaml
version: '1.0'

providers:
  azure:
    kind: azure
    auth:
      kind: default

secrets:
  - name: database-password
    kind: random_password
    config:
      length: 32
      special: true
    targets:
      - provider: azure
        kind: key_vault
        config:
          vault_url: https://myapp-secrets.vault.azure.net
          secret_name: database-password
```

### Multi-Vault Configuration

Store secrets in multiple Key Vaults:

```yaml
providers:
  azure_prod:
    kind: azure
    auth:
      kind: default
  
  azure_dr:
    kind: azure
    auth:
      kind: default

secrets:
  - name: api-key
    kind: random_string
    config:
      length: 32
    targets:
      # Primary vault
      - provider: azure_prod
        kind: key_vault
        config:
          vault_url: https://prod-secrets.vault.azure.net
          secret_name: api-key
      
      # DR vault
      - provider: azure_dr
        kind: key_vault
        config:
          vault_url: https://dr-secrets.vault.azure.net
          secret_name: api-key
```

### Service Principal Authentication

For CI/CD or cross-tenant scenarios:

```yaml
providers:
  azure:
    kind: azure
    auth:
      kind: default  # Uses environment variables
      
# Set these environment variables:
# export AZURE_CLIENT_ID=<service-principal-app-id>
# export AZURE_CLIENT_SECRET=<service-principal-password>
# export AZURE_TENANT_ID=<azure-tenant-id>
```

## Target Type: Key Vault

Azure Key Vault provides secure storage for secrets, keys, and certificates with comprehensive access control and audit logging.

### Configuration Options

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `vault_url` | string | Yes | - | Key Vault URL (e.g., https://myvault.vault.azure.net) |
| `secret_name` | string | Yes | - | Name of the secret in Key Vault |
| `content_type` | string | No | - | Content type metadata (e.g., "application/json") |
| `tags` | object | No | - | Key-value tags for the secret |
| `enabled` | boolean | No | `true` | Whether the secret is enabled |

### Example: Basic Secret

```yaml
secrets:
  - name: api-key
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      - provider: azure
        kind: key_vault
        config:
          vault_url: https://myapp-kv.vault.azure.net
          secret_name: api-key
          content_type: text/plain
          tags:
            Environment: production
            Application: myapp
            ManagedBy: secretzero
```

### Example: JSON Secret

```yaml
secrets:
  - name: database-connection
    kind: templates.db_config

templates:
  db_config:
    description: Database connection configuration
    fields:
      host:
        generator:
          kind: static
          config:
            default: myserver.database.azure.com
      username:
        generator:
          kind: static
          config:
            default: adminuser
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
            default: production
    targets:
      - provider: azure
        kind: key_vault
        config:
          vault_url: https://myapp-kv.vault.azure.net
          secret_name: database-connection
          content_type: application/json
          tags:
            Type: database-config
            Rotation: 90days
```

The secret will be stored as JSON in Key Vault:
```json
{
  "host": "myserver.database.azure.com",
  "username": "adminuser",
  "password": "xyz789...",
  "database": "production"
}
```

### Example: Connection String

```yaml
secrets:
  - name: storage-connection-string
    kind: static
    config:
      default: ${AZURE_STORAGE_CONNECTION_STRING}
    targets:
      - provider: azure
        kind: key_vault
        config:
          vault_url: https://myapp-kv.vault.azure.net
          secret_name: storage-connection-string
          content_type: text/plain
          tags:
            Service: azure-storage
            Type: connection-string
```

### Example: Certificate

```yaml
secrets:
  - name: ssl-certificate
    kind: static
    config:
      default: |
        -----BEGIN CERTIFICATE-----
        MIICljCCAX4CCQCKz...
        -----END CERTIFICATE-----
    targets:
      - provider: azure
        kind: key_vault
        config:
          vault_url: https://myapp-kv.vault.azure.net
          secret_name: ssl-certificate
          content_type: application/x-pem-file
          tags:
            Type: certificate
            Expiry: "2025-12-31"
```

## Complete Examples

### Example 1: Application Secrets

```yaml
version: '1.0'

variables:
  environment: production
  vault_url: https://myapp-prod.vault.azure.net
  app_name: myapp

providers:
  azure:
    kind: azure
    auth:
      kind: managed_identity

secrets:
  # Database password
  - name: db-password
    kind: random_password
    rotation_period: 90d
    config:
      length: 32
      special: true
      exclude_characters: '"@\'
    targets:
      - provider: azure
        kind: key_vault
        config:
          vault_url: "{{var.vault_url}}"
          secret_name: "{{var.app_name}}-db-password"
          tags:
            Environment: "{{var.environment}}"
            Type: database
            Rotation: enabled
  
  # API Key
  - name: external-api-key
    kind: random_string
    config:
      length: 64
      charset: alphanumeric
    targets:
      - provider: azure
        kind: key_vault
        config:
          vault_url: "{{var.vault_url}}"
          secret_name: external-api-key
          content_type: text/plain
          tags:
            Service: external-api
            Environment: "{{var.environment}}"
  
  # JWT Signing Key
  - name: jwt-secret
    kind: random_string
    config:
      length: 128
      charset: alphanumeric
    targets:
      - provider: azure
        kind: key_vault
        config:
          vault_url: "{{var.vault_url}}"
          secret_name: jwt-signing-key
          content_type: text/plain
          tags:
            Type: jwt
            Algorithm: HS256

metadata:
  project: "{{var.app_name}}"
  owner: backend-team
  environment: "{{var.environment}}"
```

### Example 2: Multi-Environment Setup

```yaml
version: '1.0'

variables:
  app_name: myapp

providers:
  azure_dev:
    kind: azure
    auth:
      kind: cli  # Local development
  
  azure_staging:
    kind: azure
    auth:
      kind: managed_identity
      client_id: dev-managed-identity-id
  
  azure_prod:
    kind: azure
    auth:
      kind: managed_identity
      client_id: prod-managed-identity-id

secrets:
  - name: database-password
    kind: random_password
    config:
      length: 32
      special: true
    targets:
      # Development
      - provider: azure_dev
        kind: key_vault
        config:
          vault_url: https://myapp-dev.vault.azure.net
          secret_name: database-password
          tags:
            Environment: development
      
      # Staging
      - provider: azure_staging
        kind: key_vault
        config:
          vault_url: https://myapp-staging.vault.azure.net
          secret_name: database-password
          tags:
            Environment: staging
      
      # Production
      - provider: azure_prod
        kind: key_vault
        config:
          vault_url: https://myapp-prod.vault.azure.net
          secret_name: database-password
          tags:
            Environment: production
            Critical: "true"
```

### Example 3: Azure SQL Database Credentials

```yaml
version: '1.0'

providers:
  azure:
    kind: azure
    auth:
      kind: default

secrets:
  - name: azure-sql-credentials
    kind: templates.sql_credentials

templates:
  sql_credentials:
    description: Azure SQL Database credentials
    fields:
      server:
        generator:
          kind: static
          config:
            default: myserver.database.windows.net
      database:
        generator:
          kind: static
          config:
            default: production
      username:
        generator:
          kind: static
          config:
            default: sqladmin
      password:
        generator:
          kind: random_password
          config:
            length: 32
            special: true
            exclude_characters: '"@\'
      connection_string:
        generator:
          kind: static
          config:
            default: "Server=tcp:myserver.database.windows.net,1433;Database=production;User ID=sqladmin;Password={password};Encrypt=true;Connection Timeout=30;"
    targets:
      - provider: azure
        kind: key_vault
        config:
          vault_url: https://myapp-kv.vault.azure.net
          secret_name: azure-sql-credentials
          content_type: application/json
          tags:
            Service: azure-sql
            Database: production
```

## Azure RBAC Permissions

### Required Permissions

Grant the following Azure RBAC roles or permissions:

#### Option 1: Use Built-in Roles

Assign the **Key Vault Secrets Officer** role:

```bash
# For a user
az role assignment create \
  --role "Key Vault Secrets Officer" \
  --assignee user@example.com \
  --scope /subscriptions/{subscription-id}/resourceGroups/{resource-group}/providers/Microsoft.KeyVault/vaults/{vault-name}

# For a managed identity
az role assignment create \
  --role "Key Vault Secrets Officer" \
  --assignee {managed-identity-client-id} \
  --scope /subscriptions/{subscription-id}/resourceGroups/{resource-group}/providers/Microsoft.KeyVault/vaults/{vault-name}

# For a service principal
az role assignment create \
  --role "Key Vault Secrets Officer" \
  --assignee {service-principal-app-id} \
  --scope /subscriptions/{subscription-id}/resourceGroups/{resource-group}/providers/Microsoft.KeyVault/vaults/{vault-name}
```

#### Option 2: Use Key Vault Access Policies (Classic)

If using access policies instead of RBAC:

```bash
az keyvault set-policy \
  --name {vault-name} \
  --object-id {object-id} \
  --secret-permissions get list set delete
```

### Minimum Required Permissions

For fine-grained RBAC control:

```json
{
  "permissions": [
    {
      "actions": [
        "Microsoft.KeyVault/vaults/secrets/read",
        "Microsoft.KeyVault/vaults/secrets/write",
        "Microsoft.KeyVault/vaults/secrets/delete"
      ],
      "notActions": [],
      "dataActions": [
        "Microsoft.KeyVault/vaults/secrets/getSecret/action",
        "Microsoft.KeyVault/vaults/secrets/setSecret/action",
        "Microsoft.KeyVault/vaults/secrets/readMetadata/action"
      ],
      "notDataActions": []
    }
  ]
}
```

## Best Practices

### 1. Use Managed Identity in Production

```yaml
# Good: Managed Identity (no credentials to manage)
providers:
  azure:
    kind: azure
    auth:
      kind: managed_identity

# Avoid: Service principal with secrets in code
providers:
  azure:
    kind: azure
    auth:
      kind: default
      # Don't put credentials in the config file
```

### 2. Implement Naming Conventions

```yaml
# Good: Clear, hierarchical naming
database-password
api-external-key
jwt-signing-key-prod
storage-connection-string

# Avoid: Ambiguous names
secret1
mykey
password
```

### 3. Use Tags Consistently

```yaml
targets:
  - provider: azure
    kind: key_vault
    config:
      vault_url: https://myapp-kv.vault.azure.net
      secret_name: api-key
      tags:
        Environment: production
        Application: myapp
        ManagedBy: secretzero
        Owner: backend-team
        CostCenter: engineering
        Compliance: pci-dss
```

### 4. Separate Key Vaults by Environment

```yaml
# Development
vault_url: https://myapp-dev.vault.azure.net

# Staging
vault_url: https://myapp-staging.vault.azure.net

# Production
vault_url: https://myapp-prod.vault.azure.net
```

Benefits:
- Isolation between environments
- Separate RBAC policies
- Different compliance requirements
- Independent disaster recovery

### 5. Enable Soft Delete and Purge Protection

```bash
# Enable soft delete (retention period: 90 days)
az keyvault update \
  --name myapp-kv \
  --enable-soft-delete true \
  --retention-days 90

# Enable purge protection (prevents permanent deletion)
az keyvault update \
  --name myapp-kv \
  --enable-purge-protection true
```

## Integration with Azure Services

### Azure App Service

Access Key Vault secrets in App Service:

```bash
# Using App Service configuration
az webapp config appsettings set \
  --resource-group myapp-rg \
  --name myapp \
  --settings \
    "DB_PASSWORD=@Microsoft.KeyVault(SecretUri=https://myapp-kv.vault.azure.net/secrets/database-password/)" \
    "API_KEY=@Microsoft.KeyVault(SecretUri=https://myapp-kv.vault.azure.net/secrets/api-key/)"
```

In application code:

```python
import os

# Secrets automatically injected as environment variables
db_password = os.environ.get('DB_PASSWORD')
api_key = os.environ.get('API_KEY')
```

### Azure Functions

Access secrets in Azure Functions:

```python
import os
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

def main(req):
    # Using environment variables (App Settings reference Key Vault)
    db_password = os.environ.get('DB_PASSWORD')
    
    # Or direct SDK access
    credential = DefaultAzureCredential()
    client = SecretClient(
        vault_url="https://myapp-kv.vault.azure.net",
        credential=credential
    )
    secret = client.get_secret("database-password")
    db_password = secret.value
```

### Azure Kubernetes Service (AKS)

Use Azure Key Vault Provider for Secrets Store CSI Driver:

```yaml
apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata:
  name: azure-keyvault
spec:
  provider: azure
  parameters:
    usePodIdentity: "false"
    useVMManagedIdentity: "true"
    userAssignedIdentityID: "client-id-of-managed-identity"
    keyvaultName: "myapp-kv"
    objects: |
      array:
        - |
          objectName: database-password
          objectType: secret
          objectVersion: ""
    tenantId: "your-tenant-id"
---
apiVersion: v1
kind: Pod
metadata:
  name: myapp
spec:
  serviceAccountName: myapp-sa
  containers:
    - name: myapp
      image: myapp:latest
      volumeMounts:
        - name: secrets-store
          mountPath: "/mnt/secrets"
          readOnly: true
      env:
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: database-password
              key: password
  volumes:
    - name: secrets-store
      csi:
        driver: secrets-store.csi.k8s.io
        readOnly: true
        volumeAttributes:
          secretProviderClass: "azure-keyvault"
```

### Azure DevOps Pipelines

Access Key Vault secrets in Azure Pipelines:

```yaml
trigger:
  - main

pool:
  vmImage: 'ubuntu-latest'

variables:
  - group: myapp-keyvault  # Variable group linked to Key Vault

steps:
  - task: AzureKeyVault@2
    inputs:
      azureSubscription: 'my-service-connection'
      KeyVaultName: 'myapp-kv'
      SecretsFilter: '*'
      RunAsPreJob: true
  
  - script: |
      echo "Using secrets from Key Vault"
      echo "API Key: $(api-key)"
    displayName: 'Use secrets'
```

## Troubleshooting

### Authentication Errors

**Error**: `Azure authentication failed. Check credentials and configuration.`

**Solutions**:

1. **For Managed Identity**:
   ```bash
   # Verify managed identity is enabled
   az webapp identity show --name myapp --resource-group myapp-rg
   
   # Check if identity has Key Vault access
   az role assignment list --assignee {identity-object-id} --scope {key-vault-id}
   ```

2. **For Azure CLI**:
   ```bash
   # Verify CLI authentication
   az account show
   
   # Re-authenticate if needed
   az login
   ```

3. **For Service Principal**:
   ```bash
   # Test service principal authentication
   az login --service-principal \
     --username {client-id} \
     --password {client-secret} \
     --tenant {tenant-id}
   ```

### Permission Denied

**Error**: `Forbidden: The user, group or application does not have secrets get permission`

**Solutions**:

1. Check RBAC role assignments:
   ```bash
   az role assignment list \
     --assignee {object-id} \
     --scope /subscriptions/{sub-id}/resourceGroups/{rg}/providers/Microsoft.KeyVault/vaults/{vault}
   ```

2. Grant appropriate role:
   ```bash
   az role assignment create \
     --role "Key Vault Secrets Officer" \
     --assignee {object-id} \
     --scope {key-vault-resource-id}
   ```

3. For access policies (classic model):
   ```bash
   az keyvault set-policy \
     --name myapp-kv \
     --object-id {object-id} \
     --secret-permissions get list set
   ```

### Key Vault Not Found

**Error**: `VaultNotFound: Vault not found`

**Solutions**:

1. Verify vault URL is correct:
   ```bash
   az keyvault show --name myapp-kv
   ```

2. Check DNS resolution:
   ```bash
   nslookup myapp-kv.vault.azure.net
   ```

3. Ensure vault is not soft-deleted:
   ```bash
   az keyvault list-deleted
   
   # Recover if needed
   az keyvault recover --name myapp-kv
   ```

### Network Access Issues

**Error**: `Network access denied`

**Solutions**:

1. Check Key Vault firewall settings:
   ```bash
   az keyvault network-rule list --name myapp-kv
   ```

2. Add IP or VNet rule:
   ```bash
   # Allow specific IP
   az keyvault network-rule add \
     --name myapp-kv \
     --ip-address 1.2.3.4
   
   # Allow VNet subnet
   az keyvault network-rule add \
     --name myapp-kv \
     --vnet-name myapp-vnet \
     --subnet myapp-subnet
   ```

3. Allow trusted Azure services:
   ```bash
   az keyvault update \
     --name myapp-kv \
     --bypass AzureServices
   ```

## Cost optimization

Azure Key Vault transaction and certificate pricing is published by Microsoft and changes over time. See [Azure Key Vault pricing](https://azure.microsoft.com/pricing/details/key-vault/) for current rates and tier differences (including HSM-backed keys on Premium SKUs).

**Practical tips**:

1. Cache secrets in application memory
2. Use managed identities (no additional cost)
3. Consolidate secrets in fewer vaults
4. Use standard tier unless HSM keys required
5. Monitor transactions with Azure Monitor

### Transaction Optimization

```python
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential
import time

# Bad: Fetch secret on every request
def get_config_bad():
    client = SecretClient(vault_url="https://myapp-kv.vault.azure.net", 
                          credential=DefaultAzureCredential())
    return client.get_secret("api-key").value

# Good: Cache secret with refresh
class SecretCache:
    def __init__(self, vault_url):
        self.client = SecretClient(vault_url=vault_url, 
                                   credential=DefaultAzureCredential())
        self.cache = {}
        self.ttl = 3600  # 1 hour
    
    def get_secret(self, name):
        if name in self.cache:
            value, timestamp = self.cache[name]
            if time.time() - timestamp < self.ttl:
                return value
        
        # Fetch from Key Vault
        secret = self.client.get_secret(name)
        self.cache[name] = (secret.value, time.time())
        return secret.value

cache = SecretCache("https://myapp-kv.vault.azure.net")
api_key = cache.get_secret("api-key")
```

## See Also

- [Providers Overview](index.md)
- [AWS Provider](aws.md)
- [HashiCorp Vault Provider](vault.md)
- [Azure Key Vault Documentation](https://docs.microsoft.com/en-us/azure/key-vault/)
- [Azure Identity SDK](https://docs.microsoft.com/en-us/python/api/overview/azure/identity-readme)
