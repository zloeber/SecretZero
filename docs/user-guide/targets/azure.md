# Azure Key Vault Target

SecretZero supports **Azure Key Vault** for secure secret storage in Microsoft Azure. Azure Key Vault provides hardware-backed security, centralized secret management, and seamless integration with Azure services.

## Overview

Azure Key Vault targets allow you to:

- Store secrets in Azure cloud infrastructure
- Leverage hardware security modules (HSMs) for encryption
- Integrate with Azure Active Directory for access control
- Enable managed identities for secure authentication
- Audit access with Azure Monitor and Log Analytics
- Scale globally with geo-replication
- Implement soft delete and purge protection
- Integrate seamlessly with Azure services (App Service, AKS, Container Apps)

## Prerequisites

### Installation

Azure Key Vault support requires the Azure SDK libraries:

```bash
# Install with Azure support
pip install secretzero[azure]

# Or install Azure SDK directly
pip install azure-identity azure-keyvault-secrets
```

### Authentication

Azure Key Vault targets use the Azure credential chain through `DefaultAzureCredential`:

1. **Environment variables** (`AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`)
2. **Managed Identity** (Azure VM, App Service, Container Apps, AKS)
3. **Azure CLI** (`az login`)
4. **Visual Studio Code** authentication
5. **Azure PowerShell** authentication
6. **Interactive browser** authentication

```yaml
providers:
  azure:
    kind: azure
    auth:
      kind: default  # Uses Azure credential chain
```

### Authentication Methods

#### Default Credential Chain

The recommended approach for most scenarios:

```yaml
providers:
  azure:
    kind: azure
    auth:
      kind: default  # Tries all authentication methods
```

#### Managed Identity

For Azure resources with managed identities:

```yaml
providers:
  azure:
    kind: azure
    auth:
      kind: managed_identity
      # Optional: specify client ID for user-assigned identity
      client_id: 00000000-0000-0000-0000-000000000000
```

#### Azure CLI

For local development using Azure CLI:

```yaml
providers:
  azure:
    kind: azure
    auth:
      kind: cli  # Uses `az login` credentials
```

### Required Azure Permissions

Your Azure identity (service principal, managed identity, or user) needs the following Key Vault access:

#### Using Access Policies (Classic)

```bash
# Grant secret permissions using Azure CLI
az keyvault set-policy \
  --name <vault-name> \
  --object-id <identity-object-id> \
  --secret-permissions get set delete list purge
```

Required permissions:
- **Get** - Read secret values
- **Set** - Create and update secrets
- **Delete** - Delete secrets (soft delete)
- **List** - List secrets in vault
- **Purge** - Permanently delete soft-deleted secrets

#### Using Azure RBAC (Recommended)

```bash
# Assign Key Vault Secrets Officer role
az role assignment create \
  --role "Key Vault Secrets Officer" \
  --assignee <identity-object-id> \
  --scope /subscriptions/<subscription-id>/resourceGroups/<rg>/providers/Microsoft.KeyVault/vaults/<vault-name>
```

Built-in roles:
- **Key Vault Secrets Officer** - Full secret management (recommended for SecretZero)
- **Key Vault Secrets User** - Read-only access
- **Key Vault Administrator** - Full vault access including access policies

## Configuration

### Basic Configuration

```yaml
targets:
  - provider: azure
    kind: key_vault
    config:
      vault_url: string       # Key Vault URL (required)
      secret_name: string     # Secret name (optional)
```

### Configuration Options

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `vault_url` | string | Yes | - | Full Key Vault URL (e.g., `https://myvault.vault.azure.net`) |
| `secret_name` | string | No | Secret name from config | Name to store secret under in Key Vault |

### Vault URL Format

Azure Key Vault URLs follow this format:

```
https://<vault-name>.vault.azure.net
```

Where `<vault-name>` must be:
- Globally unique across Azure
- 3-24 characters long
- Alphanumeric and hyphens only
- Start with a letter
- End with letter or digit

## Complete Examples

### Basic Key Vault Storage

Store a simple secret in Azure Key Vault:

```yaml
version: '1.0'

providers:
  azure:
    kind: azure
    auth:
      kind: default

secrets:
  - name: database_password
    kind: random_password
    config:
      length: 32
      special: true
      exclude_characters: '"@/\'
    targets:
      - provider: azure
        kind: key_vault
        config:
          vault_url: https://myapp-secrets.vault.azure.net
          secret_name: database-password
```

### Multi-Environment Setup

Manage secrets across different environments:

```yaml
version: '1.0'

variables:
  environment: production
  app_name: myapp

providers:
  azure_prod:
    kind: azure
    auth:
      kind: default

  azure_staging:
    kind: azure
    auth:
      kind: default

secrets:
  # Production secrets
  - name: prod_api_key
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      - provider: azure_prod
        kind: key_vault
        config:
          vault_url: https://myapp-prod-kv.vault.azure.net
          secret_name: api-key

  # Staging secrets
  - name: staging_api_key
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      - provider: azure_staging
        kind: key_vault
        config:
          vault_url: https://myapp-staging-kv.vault.azure.net
          secret_name: api-key

  # Shared secrets across environments
  - name: shared_encryption_key
    kind: random_string
    config:
      length: 64
      charset: hex
    targets:
      - provider: azure_prod
        kind: key_vault
        config:
          vault_url: https://myapp-prod-kv.vault.azure.net
          secret_name: shared-encryption-key
      
      - provider: azure_staging
        kind: key_vault
        config:
          vault_url: https://myapp-staging-kv.vault.azure.net
          secret_name: shared-encryption-key
```

### Managed Identity Usage

Deploy secrets using Azure managed identity:

```yaml
version: '1.0'

providers:
  azure:
    kind: azure
    auth:
      kind: managed_identity
      # Optional: for user-assigned managed identity
      # client_id: 00000000-0000-0000-0000-000000000000

secrets:
  - name: app_secret_key
    kind: random_string
    config:
      length: 64
      charset: base64
    targets:
      - provider: azure
        kind: key_vault
        config:
          vault_url: https://webapp-secrets.vault.azure.net
          secret_name: app-secret-key

  - name: storage_connection_string
    kind: static
    config:
      value: DefaultEndpointsProtocol=https;AccountName=myaccount;AccountKey=...
    targets:
      - provider: azure
        kind: key_vault
        config:
          vault_url: https://webapp-secrets.vault.azure.net
          secret_name: storage-connection-string
```

### Complex Secret Templates

Store structured credentials as JSON:

```yaml
version: '1.0'

providers:
  azure:
    kind: azure
    auth:
      kind: default

secrets:
  - name: database_config
    kind: templates.db_credentials

  - name: service_account
    kind: templates.service_principal

templates:
  db_credentials:
    description: Complete database configuration
    fields:
      host:
        generator:
          kind: static
          config:
            default: myserver.database.azure.com
      port:
        generator:
          kind: static
          config:
            default: "5432"
      database:
        generator:
          kind: static
          config:
            default: production_db
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
      ssl_mode:
        generator:
          kind: static
          config:
            default: require
    targets:
      - provider: azure
        kind: key_vault
        config:
          vault_url: https://myapp-prod-kv.vault.azure.net
          secret_name: database-credentials

  service_principal:
    description: Azure service principal credentials
    fields:
      tenant_id:
        generator:
          kind: static
          config:
            default: 00000000-0000-0000-0000-000000000000
      client_id:
        generator:
          kind: static
          config:
            default: 11111111-1111-1111-1111-111111111111
      client_secret:
        generator:
          kind: random_password
          config:
            length: 40
            special: true
      subscription_id:
        generator:
          kind: static
          config:
            default: 22222222-2222-2222-2222-222222222222
    targets:
      - provider: azure
        kind: key_vault
        config:
          vault_url: https://myapp-prod-kv.vault.azure.net
          secret_name: service-principal-credentials
```

**Retrieved from Key Vault as JSON:**

```json
{
  "host": "myserver.database.azure.com",
  "port": "5432",
  "database": "production_db",
  "username": "dbadmin",
  "password": "secureRandomPassword123!@#",
  "ssl_mode": "require"
}
```

### Multi-Region Deployment

Replicate secrets across multiple Azure regions:

```yaml
version: '1.0'

variables:
  app_name: globalapp
  regions:
    - eastus
    - westus
    - westeurope

providers:
  azure_eastus:
    kind: azure
    auth:
      kind: default

  azure_westus:
    kind: azure
    auth:
      kind: default

  azure_westeurope:
    kind: azure
    auth:
      kind: default

secrets:
  - name: global_api_key
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      # East US region
      - provider: azure_eastus
        kind: key_vault
        config:
          vault_url: https://globalapp-eastus-kv.vault.azure.net
          secret_name: api-key

      # West US region
      - provider: azure_westus
        kind: key_vault
        config:
          vault_url: https://globalapp-westus-kv.vault.azure.net
          secret_name: api-key

      # West Europe region
      - provider: azure_westeurope
        kind: key_vault
        config:
          vault_url: https://globalapp-westeurope-kv.vault.azure.net
          secret_name: api-key
```

### Microservices Architecture

Organize secrets for multiple microservices:

```yaml
version: '1.0'

providers:
  azure:
    kind: azure
    auth:
      kind: managed_identity

secrets:
  # Auth service secrets
  - name: auth_jwt_secret
    kind: random_string
    config:
      length: 64
      charset: base64
    targets:
      - provider: azure
        kind: key_vault
        config:
          vault_url: https://microservices-kv.vault.azure.net
          secret_name: auth-service-jwt-secret

  - name: auth_db_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: azure
        kind: key_vault
        config:
          vault_url: https://microservices-kv.vault.azure.net
          secret_name: auth-service-db-password

  # Payment service secrets
  - name: payment_api_key
    kind: random_string
    config:
      length: 32
    targets:
      - provider: azure
        kind: key_vault
        config:
          vault_url: https://microservices-kv.vault.azure.net
          secret_name: payment-service-api-key

  - name: payment_webhook_secret
    kind: random_string
    config:
      length: 48
      charset: hex
    targets:
      - provider: azure
        kind: key_vault
        config:
          vault_url: https://microservices-kv.vault.azure.net
          secret_name: payment-service-webhook-secret

  # Notification service secrets
  - name: notification_sendgrid_key
    kind: static
    config:
      value: ${SENDGRID_API_KEY}
    targets:
      - provider: azure
        kind: key_vault
        config:
          vault_url: https://microservices-kv.vault.azure.net
          secret_name: notification-service-sendgrid-key
```

## Best Practices

### 1. Naming Conventions

Use consistent, descriptive naming for secrets:

```yaml
# Good: Clear, hierarchical naming
secrets:
  - name: api_gateway_key
    targets:
      - provider: azure
        kind: key_vault
        config:
          vault_url: https://prod-kv.vault.azure.net
          secret_name: api-gateway-key  # Kebab-case

  - name: db_password
    targets:
      - provider: azure
        kind: key_vault
        config:
          vault_url: https://prod-kv.vault.azure.net
          secret_name: database-password

# Avoid: Inconsistent or unclear names
# BAD-NAME, dbPWD, secret1, temp_key
```

**Recommended patterns:**
- Use kebab-case: `database-password`, `api-key`, `jwt-signing-key`
- Include context: `service-name-secret-type`
- Use descriptive names: `sendgrid-api-key` not `sg-key`
- Group related secrets: `auth-db-password`, `auth-jwt-secret`

### 2. Access Policies and Permissions

Implement least privilege access:

```bash
# Create separate Key Vaults per environment
az keyvault create \
  --name myapp-prod-kv \
  --resource-group production-rg \
  --location eastus \
  --enable-rbac-authorization

# Grant minimal permissions to application
az role assignment create \
  --role "Key Vault Secrets User" \
  --assignee <app-managed-identity-id> \
  --scope /subscriptions/<sub-id>/resourceGroups/production-rg/providers/Microsoft.KeyVault/vaults/myapp-prod-kv

# Grant management permissions to SecretZero
az role assignment create \
  --role "Key Vault Secrets Officer" \
  --assignee <secretzero-identity-id> \
  --scope /subscriptions/<sub-id>/resourceGroups/production-rg/providers/Microsoft.KeyVault/vaults/myapp-prod-kv
```

**Best practices:**
- Use Azure RBAC over access policies (modern approach)
- Create separate vaults per environment (dev, staging, prod)
- Grant applications read-only access
- Limit secret management to specific service principals
- Use managed identities instead of service principal credentials
- Enable network restrictions (firewall rules, private endpoints)

### 3. Soft Delete and Purge Protection

Enable protection against accidental deletion:

```bash
# Create vault with protection enabled
az keyvault create \
  --name myapp-kv \
  --resource-group myapp-rg \
  --location eastus \
  --enable-soft-delete true \
  --enable-purge-protection true \
  --retention-days 90

# Enable on existing vault
az keyvault update \
  --name myapp-kv \
  --enable-purge-protection true
```

**Important notes:**
- **Soft delete**: Deleted secrets retained for 7-90 days (default: 90)
- **Purge protection**: Prevents permanent deletion during retention period
- Once enabled, purge protection **cannot be disabled**
- SecretZero automatically purges secrets after soft delete
- Consider your recovery needs before enabling purge protection

### 4. Resource Tagging

Tag Key Vaults for organization and cost tracking:

```bash
# Tag vault with metadata
az keyvault update \
  --name myapp-kv \
  --tags \
    Environment=production \
    Application=myapp \
    Owner=platform-team \
    CostCenter=engineering \
    ManagedBy=secretzero
```

**Recommended tags:**
- `Environment`: dev, staging, production
- `Application`: Application or service name
- `Owner`: Team or individual responsible
- `CostCenter`: For billing allocation
- `ManagedBy`: Tool managing the resource (secretzero)
- `Compliance`: Required compliance frameworks (sox, pci-dss)

### 5. Secret Versioning

Azure Key Vault automatically versions secrets:

```python
# Access specific version
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
client = SecretClient(vault_url="https://myvault.vault.azure.net", credential=credential)

# Get latest version (default)
secret = client.get_secret("database-password")

# Get specific version
secret = client.get_secret("database-password", version="abc123...")

# List all versions
versions = client.list_properties_of_secret_versions("database-password")
for version in versions:
    print(f"Version: {version.version}, Created: {version.created_on}")
```

**Version management:**
- All secret updates create new versions automatically
- Previous versions remain accessible
- Each version has a unique ID
- Versions can be disabled without deletion
- Set expiration dates on secrets
- Monitor version count to avoid clutter

### 6. Network Security

Restrict vault access to specific networks:

```bash
# Enable firewall and configure network rules
az keyvault update \
  --name myapp-kv \
  --default-action Deny

# Allow specific IP ranges
az keyvault network-rule add \
  --name myapp-kv \
  --ip-address 203.0.113.0/24

# Allow specific VNets
az keyvault network-rule add \
  --name myapp-kv \
  --vnet-name myapp-vnet \
  --subnet appservice-subnet

# Enable private endpoint
az network private-endpoint create \
  --name myapp-kv-pe \
  --resource-group myapp-rg \
  --vnet-name myapp-vnet \
  --subnet private-endpoints \
  --private-connection-resource-id /subscriptions/.../Microsoft.KeyVault/vaults/myapp-kv \
  --group-id vault \
  --connection-name myapp-kv-connection
```

## Integration with Azure Services

### Azure App Service

Reference Key Vault secrets in App Service:

```bash
# Add Key Vault reference to App Service settings
az webapp config appsettings set \
  --name myapp \
  --resource-group myapp-rg \
  --settings \
    DATABASE_PASSWORD="@Microsoft.KeyVault(SecretUri=https://myapp-kv.vault.azure.net/secrets/database-password/)" \
    API_KEY="@Microsoft.KeyVault(VaultName=myapp-kv;SecretName=api-key)"

# Grant App Service managed identity access
az keyvault set-policy \
  --name myapp-kv \
  --object-id <app-service-identity-id> \
  --secret-permissions get
```

**App Service automatically:**
- Retrieves secrets using managed identity
- Refreshes secret values periodically
- Loads secrets before application starts
- Makes secrets available as environment variables

### Azure Container Apps

Use Key Vault secrets in Container Apps:

```yaml
# container-app.yaml
properties:
  configuration:
    secrets:
      - name: database-password
        keyVaultUrl: https://myapp-kv.vault.azure.net/secrets/database-password
      - name: api-key
        keyVaultUrl: https://myapp-kv.vault.azure.net/secrets/api-key
  template:
    containers:
      - name: myapp
        image: myregistry.azurecr.io/myapp:latest
        env:
          - name: DATABASE_PASSWORD
            secretRef: database-password
          - name: API_KEY
            secretRef: api-key
```

```bash
# Deploy with Azure CLI
az containerapp create \
  --name myapp \
  --resource-group myapp-rg \
  --environment myapp-env \
  --image myregistry.azurecr.io/myapp:latest \
  --secrets \
    database-password="keyvaultref:https://myapp-kv.vault.azure.net/secrets/database-password,identityref:/subscriptions/.../managedIdentities/myapp-identity" \
  --env-vars \
    DATABASE_PASSWORD=secretref:database-password
```

### Azure Kubernetes Service (AKS)

Use the Secrets Store CSI Driver to mount secrets:

```bash
# Install CSI driver
helm repo add csi-secrets-store-provider-azure https://azure.github.io/secrets-store-csi-driver-provider-azure/charts
helm install csi csi-secrets-store-provider-azure/csi-secrets-store-provider-azure

# Enable CSI driver on AKS
az aks enable-addons \
  --addons azure-keyvault-secrets-provider \
  --name myapp-aks \
  --resource-group myapp-rg
```

**SecretProviderClass manifest:**

```yaml
apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata:
  name: azure-keyvault-secrets
  namespace: default
spec:
  provider: azure
  parameters:
    usePodIdentity: "false"
    useVMManagedIdentity: "true"
    userAssignedIdentityID: "00000000-0000-0000-0000-000000000000"
    keyvaultName: "myapp-kv"
    objects: |
      array:
        - |
          objectName: database-password
          objectType: secret
          objectVersion: ""
        - |
          objectName: api-key
          objectType: secret
          objectVersion: ""
    tenantId: "00000000-0000-0000-0000-000000000000"
```

**Pod using secrets:**

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: myapp
spec:
  containers:
    - name: myapp
      image: myapp:latest
      volumeMounts:
        - name: secrets-store
          mountPath: "/mnt/secrets"
          readOnly: true
      env:
        - name: DATABASE_PASSWORD
          valueFrom:
            secretKeyRef:
              name: keyvault-secrets
              key: database-password
  volumes:
    - name: secrets-store
      csi:
        driver: secrets-store.csi.k8s.io
        readOnly: true
        volumeAttributes:
          secretProviderClass: "azure-keyvault-secrets"
```

### Azure Functions

Access Key Vault from Azure Functions:

```python
# function_app.py
import os
import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

def main(req: func.HttpRequest) -> func.HttpResponse:
    # Option 1: Reference from app settings
    # Set in configuration: @Microsoft.KeyVault(SecretUri=...)
    db_password = os.environ["DATABASE_PASSWORD"]
    
    # Option 2: Direct Key Vault access
    credential = DefaultAzureCredential()
    client = SecretClient(
        vault_url="https://myapp-kv.vault.azure.net",
        credential=credential
    )
    api_key = client.get_secret("api-key").value
    
    return func.HttpResponse("Success", status_code=200)
```

### Azure DevOps Pipelines

Integrate Key Vault with Azure Pipelines:

```yaml
# azure-pipelines.yml
trigger:
  - main

pool:
  vmImage: 'ubuntu-latest'

variables:
  - group: production-secrets  # Variable group linked to Key Vault

steps:
  - task: AzureKeyVault@2
    inputs:
      azureSubscription: 'MyAzureSubscription'
      KeyVaultName: 'myapp-kv'
      SecretsFilter: 'database-password,api-key'
      RunAsPreJob: true

  - script: |
      echo "Using secrets from Key Vault"
      # Secrets available as environment variables
      # DATABASE_PASSWORD and API_KEY are now accessible
      ./deploy.sh
    env:
      DATABASE_PASSWORD: $(database-password)
      API_KEY: $(api-key)
```

## Troubleshooting Common Issues

### 1. Access Denied Errors

**Problem:** `Forbidden` or `Access denied` when accessing Key Vault.

**Solutions:**

```bash
# Check current identity
az account show

# Verify vault access policies
az keyvault show --name myapp-kv --query properties.accessPolicies

# Grant necessary permissions
az keyvault set-policy \
  --name myapp-kv \
  --object-id <your-object-id> \
  --secret-permissions get set delete list purge

# Or use RBAC
az role assignment create \
  --role "Key Vault Secrets Officer" \
  --assignee <your-identity> \
  --scope /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.KeyVault/vaults/myapp-kv
```

**Common causes:**
- Missing permissions on Key Vault
- Using wrong managed identity
- Network restrictions blocking access
- Firewall rules not configured
- Private endpoint without proper DNS

### 2. Authentication Failures

**Problem:** `Azure SDK not installed` or `Authentication failed`.

**Solutions:**

```bash
# Install Azure SDK
pip install secretzero[azure]

# For managed identity, verify identity exists
az identity show --name myapp-identity --resource-group myapp-rg

# For CLI authentication, login
az login

# Test authentication
az keyvault secret list --vault-name myapp-kv
```

### 3. Vault URL Issues

**Problem:** Invalid vault URL or vault not found.

**Solutions:**

```yaml
# Correct format (must include https:// and .vault.azure.net)
config:
  vault_url: https://myapp-kv.vault.azure.net  # ✓ Correct

# Common mistakes to avoid:
# vault_url: myapp-kv                           # ✗ Missing protocol and domain
# vault_url: https://myapp-kv.com              # ✗ Wrong domain
# vault_url: myapp-kv.vault.azure.net          # ✗ Missing protocol
```

```bash
# Verify vault exists and get URL
az keyvault show --name myapp-kv --query properties.vaultUri -o tsv
```

### 4. Secret Name Restrictions

**Problem:** Invalid secret name errors.

**Azure Key Vault secret name rules:**
- Must be 1-127 characters
- Alphanumeric characters and hyphens only
- Must start with a letter or number
- Cannot end with a hyphen
- No consecutive hyphens

```yaml
# Valid secret names
secret_name: database-password      # ✓
secret_name: api-key-2024          # ✓
secret_name: jwt-signing-key-v2    # ✓

# Invalid secret names
secret_name: database_password      # ✗ Underscore not allowed
secret_name: api-key-              # ✗ Ends with hyphen
secret_name: -database-password    # ✗ Starts with hyphen
secret_name: api--key              # ✗ Consecutive hyphens
```

### 5. Soft Delete and Purge Issues

**Problem:** Cannot create secret because it's soft-deleted.

**Solutions:**

```bash
# List deleted secrets
az keyvault secret list-deleted --vault-name myapp-kv

# Recover deleted secret
az keyvault secret recover \
  --vault-name myapp-kv \
  --name database-password

# Or permanently purge (if purge protection not enabled)
az keyvault secret purge \
  --vault-name myapp-kv \
  --name database-password

# Wait for purge to complete before recreating
```

**Note:** SecretZero's delete operation performs both soft delete and purge automatically.

### 6. Network Connectivity Issues

**Problem:** Cannot connect to Key Vault from restricted network.

**Solutions:**

```bash
# Check network rules
az keyvault network-rule list --name myapp-kv

# Add your IP to allowed list
az keyvault network-rule add \
  --name myapp-kv \
  --ip-address <your-public-ip>/32

# Or temporarily disable network restrictions
az keyvault update \
  --name myapp-kv \
  --default-action Allow
```

### 7. Managed Identity Issues

**Problem:** Managed identity not working.

**Solutions:**

```bash
# Verify system-assigned identity is enabled
az webapp identity show --name myapp --resource-group myapp-rg

# Enable system-assigned identity
az webapp identity assign --name myapp --resource-group myapp-rg

# For user-assigned identity
az webapp identity assign \
  --name myapp \
  --resource-group myapp-rg \
  --identities /subscriptions/.../managedIdentities/myapp-identity

# Grant Key Vault access to the identity
IDENTITY_ID=$(az webapp identity show --name myapp --resource-group myapp-rg --query principalId -o tsv)
az keyvault set-policy \
  --name myapp-kv \
  --object-id $IDENTITY_ID \
  --secret-permissions get list
```

## Security Considerations

### Encryption at Rest

Azure Key Vault provides multiple layers of encryption:

**1. Hardware Security Modules (HSMs)**

```bash
# Standard tier (software-protected)
az keyvault create \
  --name myapp-kv \
  --resource-group myapp-rg \
  --sku standard

# Premium tier (HSM-backed)
az keyvault create \
  --name myapp-kv \
  --resource-group myapp-rg \
  --sku premium
```

**Key differences:**
- **Standard**: Software-protected keys, $0.03/10,000 operations
- **Premium**: HSM-backed keys (FIPS 140-2 Level 2), $1/key/month

**2. Encryption Keys**

All secrets are encrypted using:
- Azure Storage Service Encryption (SSE)
- 256-bit AES encryption
- Microsoft-managed keys (automatic)
- Customer-managed keys (optional, requires Premium tier)

### Role-Based Access Control (RBAC)

Implement fine-grained access control:

```bash
# Recommended: Use Azure RBAC
az keyvault create \
  --name myapp-kv \
  --enable-rbac-authorization true

# Built-in roles for secret management:
# - Key Vault Administrator: Full control
# - Key Vault Secrets Officer: Manage secrets (create, read, update, delete)
# - Key Vault Secrets User: Read secrets only
# - Key Vault Reader: Read metadata only (not secret values)

# Grant read-only access to application
az role assignment create \
  --role "Key Vault Secrets User" \
  --assignee <app-identity> \
  --scope /subscriptions/.../vaults/myapp-kv

# Grant management access to CI/CD
az role assignment create \
  --role "Key Vault Secrets Officer" \
  --assignee <cicd-identity> \
  --scope /subscriptions/.../vaults/myapp-kv
```

**RBAC best practices:**
- Enable RBAC on all new vaults
- Use built-in roles when possible
- Scope permissions to specific secrets when needed
- Review and audit role assignments regularly
- Use Privileged Identity Management (PIM) for elevated access

### Audit Logs and Monitoring

Enable comprehensive logging:

```bash
# Enable diagnostic settings
az monitor diagnostic-settings create \
  --name keyvault-diagnostics \
  --resource /subscriptions/.../vaults/myapp-kv \
  --logs '[{"category": "AuditEvent", "enabled": true}]' \
  --metrics '[{"category": "AllMetrics", "enabled": true}]' \
  --workspace /subscriptions/.../workspaces/myapp-logs

# Query audit logs with KQL
# Go to Log Analytics workspace
```

**Key audit log queries:**

```kql
// All Key Vault operations
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.KEYVAULT"
| project TimeGenerated, OperationName, ResultSignature, CallerIPAddress, identity_claim_http_schemas_microsoft_com_identity_claims_objectidentifier_g

// Failed access attempts
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.KEYVAULT"
| where ResultSignature == "Unauthorized"
| project TimeGenerated, OperationName, CallerIPAddress, identity_claim_oid_g

// Secret access by specific identity
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.KEYVAULT"
| where OperationName == "SecretGet"
| where identity_claim_oid_g == "<identity-object-id>"
| project TimeGenerated, id_s, CallerIPAddress
```

**Monitored events:**
- Secret read operations (SecretGet)
- Secret write operations (SecretSet)
- Secret deletion (SecretDelete, SecretPurge)
- Access policy changes
- Failed authentication attempts
- Network rule changes

### Azure Policy and Compliance

Enforce security standards:

```bash
# Assign built-in policies

# 1. Key vaults should have soft delete enabled
az policy assignment create \
  --name require-soft-delete \
  --policy "/providers/Microsoft.Authorization/policyDefinitions/1e66c121-a66a-4b1f-9b83-0fd99bf0fc2d" \
  --scope /subscriptions/<subscription-id>

# 2. Key vaults should have purge protection enabled
az policy assignment create \
  --name require-purge-protection \
  --policy "/providers/Microsoft.Authorization/policyDefinitions/0b60c0b2-2dc2-4e1c-b5c9-abbed971de53" \
  --scope /subscriptions/<subscription-id>

# 3. Azure Key Vault should have firewall enabled
az policy assignment create \
  --name require-firewall \
  --policy "/providers/Microsoft.Authorization/policyDefinitions/55615ac9-af46-4a59-874e-391cc3dfb490" \
  --scope /subscriptions/<subscription-id>
```

**Compliance frameworks:**
- SOC 2 Type II
- ISO 27001
- PCI DSS
- HIPAA
- FedRAMP
- GDPR compliant

### Secret Rotation Strategy

Implement regular secret rotation:

```yaml
# Automated rotation with SecretZero
secrets:
  - name: database_password
    kind: random_password
    rotation_period: 90d  # Rotate every 90 days
    config:
      length: 32
      special: true
    targets:
      - provider: azure
        kind: key_vault
        config:
          vault_url: https://myapp-kv.vault.azure.net
          secret_name: database-password
```

**Manual rotation with Azure:**

```bash
# Create rotation function (Python example)
# Deploy as Azure Function with timer trigger
```

```python
import azure.functions as func
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential
import secrets
import string

def main(mytimer: func.TimerRequest) -> None:
    credential = DefaultAzureCredential()
    client = SecretClient(
        vault_url="https://myapp-kv.vault.azure.net",
        credential=credential
    )
    
    # Generate new password
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()"
    new_password = ''.join(secrets.choice(alphabet) for i in range(32))
    
    # Update in Key Vault
    client.set_secret("database-password", new_password)
    
    # Update database (implementation-specific)
    # update_database_password(new_password)
```

### Private Endpoints

Isolate Key Vault access to private network:

```bash
# Create private endpoint
az network private-endpoint create \
  --name myapp-kv-pe \
  --resource-group myapp-rg \
  --vnet-name myapp-vnet \
  --subnet private-endpoints \
  --private-connection-resource-id /subscriptions/.../Microsoft.KeyVault/vaults/myapp-kv \
  --group-id vault \
  --connection-name myapp-kv-connection

# Create private DNS zone
az network private-dns zone create \
  --resource-group myapp-rg \
  --name privatelink.vaultcore.azure.net

# Link DNS zone to VNet
az network private-dns link vnet create \
  --resource-group myapp-rg \
  --zone-name privatelink.vaultcore.azure.net \
  --name myapp-dns-link \
  --virtual-network myapp-vnet \
  --registration-enabled false

# Create DNS zone group
az network private-endpoint dns-zone-group create \
  --resource-group myapp-rg \
  --endpoint-name myapp-kv-pe \
  --name default \
  --private-dns-zone /subscriptions/.../privateDnsZones/privatelink.vaultcore.azure.net \
  --zone-name vault
```

## Complete Production Example

Comprehensive configuration for production deployment:

```yaml
version: '1.0'

variables:
  environment: production
  app_name: enterprise-app
  azure_region: eastus
  compliance_frameworks:
    - soc2
    - iso27001
    - pci-dss

providers:
  azure_prod:
    kind: azure
    auth:
      kind: managed_identity
      # Uses system-assigned managed identity from Azure App Service

secrets:
  # Database credentials (structured)
  - name: postgres_master_credentials
    kind: templates.postgres_config
    rotation_period: 90d

  # Application secrets
  - name: jwt_signing_key
    kind: random_string
    config:
      length: 64
      charset: base64
    targets:
      - provider: azure_prod
        kind: key_vault
        config:
          vault_url: https://{{var.app_name}}-{{var.environment}}-kv.vault.azure.net
          secret_name: jwt-signing-key

  - name: session_encryption_key
    kind: random_string
    config:
      length: 32
      charset: hex
    targets:
      - provider: azure_prod
        kind: key_vault
        config:
          vault_url: https://{{var.app_name}}-{{var.environment}}-kv.vault.azure.net
          secret_name: session-encryption-key

  # External service credentials
  - name: sendgrid_api_key
    kind: static
    config:
      value: ${SENDGRID_API_KEY}
    targets:
      - provider: azure_prod
        kind: key_vault
        config:
          vault_url: https://{{var.app_name}}-{{var.environment}}-kv.vault.azure.net
          secret_name: sendgrid-api-key

  - name: stripe_secret_key
    kind: static
    config:
      value: ${STRIPE_SECRET_KEY}
    targets:
      - provider: azure_prod
        kind: key_vault
        config:
          vault_url: https://{{var.app_name}}-{{var.environment}}-kv.vault.azure.net
          secret_name: stripe-secret-key

  # Service principal credentials
  - name: monitoring_service_principal
    kind: templates.azure_sp_credentials

templates:
  postgres_config:
    description: PostgreSQL master credentials
    fields:
      host:
        generator:
          kind: static
          config:
            default: {{var.app_name}}-{{var.environment}}-pg.postgres.database.azure.com
      port:
        generator:
          kind: static
          config:
            default: "5432"
      database:
        generator:
          kind: static
          config:
            default: production_db
      username:
        generator:
          kind: static
          config:
            default: pgadmin
      password:
        generator:
          kind: random_password
          config:
            length: 32
            special: true
            exclude_characters: '"@/\`'
      ssl_mode:
        generator:
          kind: static
          config:
            default: require
    targets:
      - provider: azure_prod
        kind: key_vault
        config:
          vault_url: https://{{var.app_name}}-{{var.environment}}-kv.vault.azure.net
          secret_name: postgres-master-credentials

  azure_sp_credentials:
    description: Azure Service Principal credentials for monitoring
    fields:
      tenant_id:
        generator:
          kind: static
          config:
            default: ${AZURE_TENANT_ID}
      client_id:
        generator:
          kind: static
          config:
            default: ${AZURE_MONITORING_CLIENT_ID}
      client_secret:
        generator:
          kind: random_password
          config:
            length: 40
      subscription_id:
        generator:
          kind: static
          config:
            default: ${AZURE_SUBSCRIPTION_ID}
    targets:
      - provider: azure_prod
        kind: key_vault
        config:
          vault_url: https://{{var.app_name}}-{{var.environment}}-kv.vault.azure.net
          secret_name: monitoring-service-principal

metadata:
  owner: platform-security-team
  contact: security@example.com
  project: {{var.app_name}}
  environment: {{var.environment}}
  compliance: {{var.compliance_frameworks}}
  cost_center: engineering
  documentation: https://wiki.example.com/secrets-management
```

## Next Steps

- Explore [AWS Secrets Manager](aws.md) for multi-cloud deployments
- Learn about [HashiCorp Vault](vault.md) for hybrid environments
- Review [Kubernetes secrets](kubernetes.md) for container workloads
- Check [examples](../../examples/) for complete configurations
- Read about [Secret Templates](../templates.md) for structured secrets
- Understand [Secret Rotation](../rotation.md) strategies
