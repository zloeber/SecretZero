# Multi-Cloud Secret Management

## Problem Statement

Managing secrets across multiple cloud providers creates significant operational challenges:

- Secrets scattered across AWS, Azure, GCP, and HashiCorp Vault with no unified management
- Difficult to maintain consistency across different secret storage systems
- Manual synchronization between cloud providers is error-prone and time-consuming
- No standardized way to handle cloud provider-specific secret formats and APIs
- Cross-cloud disaster recovery and backup strategies are complex
- Auditing and compliance tracking across multiple platforms is challenging
- Different authentication mechanisms and permission models for each provider

**SecretZero solves this** by providing a unified interface for managing secrets across all major cloud providers with consistent configuration, automated synchronization, and comprehensive audit trails.

## Prerequisites

- SecretZero installed with cloud provider support: `pip install secretzero[aws,azure,vault]`
- AWS credentials configured (IAM role, environment variables, or AWS CLI profile)
- Azure credentials configured (managed identity, service principal, or Azure CLI)
- HashiCorp Vault access token and endpoint URL
- Appropriate permissions in each cloud provider for secret management
- Optional: Google Cloud credentials for GCP Secret Manager

## Authentication Setup

### AWS Authentication

SecretZero uses the standard AWS credential chain:

```bash
# Option 1: Environment variables
export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
export AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
export AWS_DEFAULT_REGION=us-east-1

# Option 2: AWS CLI profile
aws configure --profile production
export AWS_PROFILE=production

# Option 3: IAM role (recommended for EC2/ECS/Lambda)
# No configuration needed - uses instance metadata

# Verify AWS credentials
aws sts get-caller-identity
```

Configure in Secretfile.yml:

```yaml
providers:
  aws:
    kind: aws
    auth:
      kind: ambient  # Uses AWS credential chain
      config:
        region: us-east-1
        # Optional: specific profile
        # profile: production
```

### Azure Authentication

SecretZero uses Azure's DefaultAzureCredential chain:

```bash
# Option 1: Azure CLI (for local development)
az login
az account set --subscription "Production Subscription"

# Option 2: Service Principal (for automation)
export AZURE_CLIENT_ID=your-client-id
export AZURE_CLIENT_SECRET=your-client-secret
export AZURE_TENANT_ID=your-tenant-id

# Option 3: Managed Identity (for Azure VMs/Functions)
# No configuration needed - uses instance metadata

# Verify Azure credentials
az account show
```

Configure in Secretfile.yml:

```yaml
providers:
  azure:
    kind: azure
    auth:
      kind: default  # Uses DefaultAzureCredential chain
      config:
        # Optional: specific tenant
        # tenant_id: your-tenant-id
```

### HashiCorp Vault Authentication

```bash
# Set Vault address and token
export VAULT_ADDR=https://vault.example.com:8200
export VAULT_TOKEN=hvs.CAESIJ1...

# Verify Vault connectivity
vault status
vault token lookup
```

Configure in Secretfile.yml:

```yaml
providers:
  vault:
    kind: vault
    auth:
      kind: token
      config:
        token: ${VAULT_TOKEN}
        url: ${VAULT_ADDR}
        # Optional: TLS configuration
        # ca_cert: /path/to/ca.pem
        # client_cert: /path/to/client.pem
        # client_key: /path/to/client-key.pem
```

### Google Cloud Authentication

```bash
# Authenticate with gcloud
gcloud auth application-default login

# Or use service account
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# Verify credentials
gcloud auth list
gcloud projects list
```

Configure in Secretfile.yml:

```yaml
providers:
  gcp:
    kind: gcp
    auth:
      kind: ambient
      config:
        project_id: my-production-project
        # Optional: service account key file
        # credentials_file: /path/to/service-account-key.json
```

## Configuration

### Basic Multi-Cloud Setup

Create `Secretfile.yml`:

```yaml
version: '1.0'

metadata:
  project: multi-cloud-app
  owner: platform-team
  description: Multi-cloud secret distribution

variables:
  environment: production
  aws_region: us-east-1
  app_name: myapp

providers:
  # AWS Secrets Manager & SSM Parameter Store
  aws:
    kind: aws
    auth:
      kind: ambient
      config:
        region: ${aws_region}
  
  # Azure Key Vault
  azure:
    kind: azure
    auth:
      kind: default
  
  # HashiCorp Vault
  vault:
    kind: vault
    auth:
      kind: token
      config:
        token: ${VAULT_TOKEN}
        url: ${VAULT_ADDR}
  
  # Local development
  local:
    kind: local

secrets:
  # Database password distributed to all providers
  - name: database_password
    kind: random_password
    one_time: true  # Generate once, sync everywhere
    rotation_period: 90d
    config:
      length: 32
      special: true
      exclude_characters: '"@/\`'
    targets:
      # Local development
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true
      
      # AWS Secrets Manager (primary)
      - provider: aws
        kind: secrets_manager
        config:
          name: ${environment}/${app_name}/database/password
          description: Database password for ${app_name}
          tags:
            Environment: ${environment}
            Application: ${app_name}
            ManagedBy: secretzero
      
      # AWS SSM Parameter Store (backup)
      - provider: aws
        kind: ssm_parameter
        config:
          name: /${environment}/${app_name}/database/password
          type: SecureString
          description: Database password for ${app_name}
          tags:
            Environment: ${environment}
            Application: ${app_name}
      
      # Azure Key Vault (DR region)
      - provider: azure
        kind: key_vault
        config:
          vault_url: https://myapp-prod-secrets.vault.azure.net
          secret_name: ${app_name}-database-password
          tags:
            environment: ${environment}
            application: ${app_name}
      
      # HashiCorp Vault (multi-cloud reference)
      - provider: vault
        kind: kv
        config:
          path: ${environment}/${app_name}/database/password
          mount_point: secret
          version: 2  # KV v2
          metadata:
            application: ${app_name}
            environment: ${environment}

  # API Key distributed across clouds
  - name: external_api_key
    kind: random_string
    rotation_period: 90d
    config:
      length: 32
      charset: alphanumeric
    targets:
      # AWS Secrets Manager
      - provider: aws
        kind: secrets_manager
        config:
          name: ${environment}/${app_name}/api-key
          description: External API key
      
      # Azure Key Vault
      - provider: azure
        kind: key_vault
        config:
          vault_url: https://myapp-prod-secrets.vault.azure.net
          secret_name: ${app_name}-api-key
      
      # Vault KV
      - provider: vault
        kind: kv
        config:
          path: ${environment}/${app_name}/api-key
          mount_point: secret
          version: 2

  # Service account credentials with multiple fields
  - name: service_account
    kind: templates.service_credentials

templates:
  service_credentials:
    description: Service account credentials
    fields:
      username:
        description: Service account username
        generator:
          kind: static
          config:
            default: svc_${app_name}_${environment}
      password:
        description: Service account password
        generator:
          kind: random_password
          config:
            length: 32
            special: true
      api_endpoint:
        description: API endpoint URL
        generator:
          kind: static
          config:
            default: https://api.example.com
      api_version:
        description: API version
        generator:
          kind: static
          config:
            default: v1
    targets:
      # Store as JSON in AWS Secrets Manager
      - provider: aws
        kind: secrets_manager
        config:
          name: ${environment}/${app_name}/service-account
          description: Service account credentials
      
      # Store in Azure Key Vault (as JSON string)
      - provider: azure
        kind: key_vault
        config:
          vault_url: https://myapp-prod-secrets.vault.azure.net
          secret_name: ${app_name}-service-account
      
      # Store as separate fields in Vault
      - provider: vault
        kind: kv
        config:
          path: ${environment}/${app_name}/service-account
          mount_point: secret
          version: 2
      
      # Store locally as JSON file
      - provider: local
        kind: file
        config:
          path: .service-account.json
          format: json
```

### AWS-Specific Configuration

```yaml
providers:
  aws:
    kind: aws
    auth:
      kind: ambient
      config:
        region: us-east-1

secrets:
  # AWS Secrets Manager secret with automatic rotation
  - name: rds_master_password
    kind: random_password
    rotation_period: 90d
    config:
      length: 32
      special: true
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: /production/rds/master-password
          description: RDS master password
          kms_key_id: alias/aws/secretsmanager  # Use custom KMS key
          replica_regions:
            - us-west-2  # Replicate to DR region
            - eu-west-1
          tags:
            Environment: production
            Compliance: soc2
            DataClassification: sensitive
  
  # SSM Parameter with tier and policies
  - name: app_config_param
    kind: random_string
    config:
      length: 64
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /production/app/config/secret-key
          type: SecureString
          tier: Advanced  # Standard or Advanced
          data_type: text
          policies: |
            {
              "Type": "Expiration",
              "Version": "1.0",
              "Attributes": {
                "Timestamp": "2025-12-31T23:59:59.000Z"
              }
            }
          tags:
            Environment: production
            Application: myapp

  # Cross-region AWS secrets
  - name: multi_region_secret
    kind: random_password
    config:
      length: 32
    targets:
      # Primary region
      - provider: aws
        kind: secrets_manager
        config:
          name: /production/multi-region-secret
          description: Multi-region secret
          replica_regions:
            - us-west-2
            - eu-west-1
            - ap-southeast-1
```

### Azure-Specific Configuration

```yaml
providers:
  azure:
    kind: azure
    auth:
      kind: default

secrets:
  # Azure Key Vault secret with expiration
  - name: azure_storage_key
    kind: random_string
    rotation_period: 90d
    config:
      length: 44
      charset: base64
    targets:
      - provider: azure
        kind: key_vault
        config:
          vault_url: https://myapp-prod-kv.vault.azure.net
          secret_name: storage-account-key
          content_type: text/plain
          enabled: true
          expires_on: "2025-12-31T23:59:59Z"
          not_before: "2024-01-01T00:00:00Z"
          tags:
            environment: production
            application: myapp
            compliance: iso27001

  # Certificate in Azure Key Vault
  - name: application_certificate
    kind: templates.azure_certificate

templates:
  azure_certificate:
    description: Application certificate
    fields:
      certificate:
        generator:
          kind: static
          config:
            # PFX/PKCS12 certificate
            default: ${CERTIFICATE_PFX_BASE64}
      password:
        generator:
          kind: static
          config:
            default: ${CERTIFICATE_PASSWORD}
    targets:
      - provider: azure
        kind: key_vault_certificate
        config:
          vault_url: https://myapp-prod-kv.vault.azure.net
          certificate_name: app-certificate
          content_type: application/x-pkcs12
          tags:
            environment: production
            type: certificate
```

### Vault-Specific Configuration

```yaml
providers:
  vault:
    kind: vault
    auth:
      kind: token
      config:
        token: ${VAULT_TOKEN}
        url: ${VAULT_ADDR}

secrets:
  # KV v2 secret with metadata
  - name: vault_app_secret
    kind: random_password
    rotation_period: 90d
    config:
      length: 32
    targets:
      - provider: vault
        kind: kv
        config:
          path: production/app/secret-key
          mount_point: secret
          version: 2  # KV v2 enables versioning
          cas: 0  # Check-and-Set for version control
          metadata:
            application: myapp
            environment: production
            owner: platform-team
            rotation_period: 90d

  # Dynamic database credentials
  - name: vault_dynamic_db
    kind: templates.vault_database

templates:
  vault_database:
    description: Vault dynamic database credentials
    fields:
      role:
        generator:
          kind: static
          config:
            default: myapp-readonly
      connection:
        generator:
          kind: static
          config:
            default: postgres-prod
    targets:
      - provider: vault
        kind: database_role
        config:
          database_mount: database
          role_name: myapp-readonly
          db_name: postgres-prod
          creation_statements:
            - "CREATE USER '{{name}}' WITH PASSWORD '{{password}}' VALID UNTIL '{{expiration}}';"
            - "GRANT SELECT ON ALL TABLES IN SCHEMA public TO '{{name}}';"
          default_ttl: 1h
          max_ttl: 24h

  # Transit encryption key
  - name: vault_encryption_key
    kind: static
    config:
      default: placeholder
    targets:
      - provider: vault
        kind: transit_key
        config:
          mount_point: transit
          key_name: myapp-encryption-key
          key_type: aes256-gcm96
          derived: false
          exportable: false
          allow_plaintext_backup: false
```

## Step-by-Step Instructions

### 1. Configure Cloud Provider Credentials

```bash
# AWS
export AWS_PROFILE=production
aws sts get-caller-identity

# Azure
az login
az account show

# Vault
export VAULT_ADDR=https://vault.example.com:8200
export VAULT_TOKEN=hvs.CAESIJ1...
vault status

# Verify all providers
secretzero test
```

### 2. Validate Configuration

```bash
secretzero validate -f Secretfile.yml

# Expected output:
# ✓ Configuration is valid
# ✓ 4 providers configured (aws, azure, vault, local)
# ✓ 3 secrets defined
# ✓ 12 targets configured
# ✓ All provider credentials valid
```

### 3. Preview Multi-Cloud Sync

```bash
secretzero sync --dry-run

# Expected output:
# [DRY RUN] Would create:
#   ✓ database_password → Local file (.env)
#   ✓ database_password → AWS Secrets Manager (production/myapp/database/password)
#   ✓ database_password → AWS SSM Parameter (/production/myapp/database/password)
#   ✓ database_password → Azure Key Vault (myapp-database-password)
#   ✓ database_password → Vault KV (production/myapp/database/password)
#   ✓ external_api_key → AWS Secrets Manager (production/myapp/api-key)
#   ✓ external_api_key → Azure Key Vault (myapp-api-key)
#   ✓ external_api_key → Vault KV (production/myapp/api-key)
#   ✓ service_account → AWS Secrets Manager (production/myapp/service-account)
#   ✓ service_account → Azure Key Vault (myapp-service-account)
#   ✓ service_account → Vault KV (production/myapp/service-account)
#   ✓ service_account → Local file (.service-account.json)
```

### 4. Sync Secrets Across Cloud Providers

```bash
secretzero sync

# Expected output:
# ✓ Generated database_password
# ✓ Created local file: .env
# ✓ Created AWS Secrets Manager secret: production/myapp/database/password
# ✓ Created AWS SSM Parameter: /production/myapp/database/password
# ✓ Created Azure Key Vault secret: myapp-database-password
# ✓ Created Vault KV secret: production/myapp/database/password
# ✓ Generated external_api_key
# ✓ Created AWS Secrets Manager secret: production/myapp/api-key
# ✓ Created Azure Key Vault secret: myapp-api-key
# ✓ Created Vault KV secret: production/myapp/api-key
# ✓ Generated service_account
# ✓ Created AWS Secrets Manager secret: production/myapp/service-account
# ✓ Created Azure Key Vault secret: myapp-service-account
# ✓ Created Vault KV secret: production/myapp/service-account
# ✓ Created local file: .service-account.json
# ✓ Updated .gitsecrets.lock
```

### 5. Verify Secrets in Each Provider

```bash
# AWS Secrets Manager
aws secretsmanager get-secret-value \
  --secret-id production/myapp/database/password \
  --query 'SecretString' --output text

# AWS SSM Parameter Store
aws ssm get-parameter \
  --name /production/myapp/database/password \
  --with-decryption \
  --query 'Parameter.Value' --output text

# Azure Key Vault
az keyvault secret show \
  --vault-name myapp-prod-secrets \
  --name myapp-database-password \
  --query 'value' --output tsv

# Vault KV
vault kv get -field=password secret/production/myapp/database/password

# Local files
cat .env
cat .service-account.json
```

## Using Secrets in Different Clouds

### AWS Lambda Function

```python
import boto3
import json

# Using AWS Secrets Manager
def get_secret_from_secretsmanager():
    client = boto3.client('secretsmanager', region_name='us-east-1')
    response = client.get_secret_value(SecretId='production/myapp/database/password')
    return response['SecretString']

# Using AWS SSM Parameter Store
def get_secret_from_ssm():
    client = boto3.client('ssm', region_name='us-east-1')
    response = client.get_parameter(
        Name='/production/myapp/database/password',
        WithDecryption=True
    )
    return response['Parameter']['Value']

# Using service account JSON
def get_service_account():
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId='production/myapp/service-account')
    return json.loads(response['SecretString'])

# Lambda handler
def lambda_handler(event, context):
    db_password = get_secret_from_secretsmanager()
    api_key = get_secret_from_ssm()
    svc_account = get_service_account()
    
    # Use secrets
    return {
        'statusCode': 200,
        'body': json.dumps('Secrets loaded successfully')
    }
```

### Azure Function

```python
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import json

# Initialize Key Vault client
credential = DefaultAzureCredential()
vault_url = "https://myapp-prod-secrets.vault.azure.net"
client = SecretClient(vault_url=vault_url, credential=credential)

def get_database_password():
    secret = client.get_secret("myapp-database-password")
    return secret.value

def get_api_key():
    secret = client.get_secret("myapp-api-key")
    return secret.value

def get_service_account():
    secret = client.get_secret("myapp-service-account")
    return json.loads(secret.value)

# Azure Function main
def main(req):
    db_password = get_database_password()
    api_key = get_api_key()
    svc_account = get_service_account()
    
    # Use secrets
    return {
        "statusCode": 200,
        "body": "Secrets loaded successfully"
    }
```

### HashiCorp Vault Integration

```python
import hvac
import os

# Initialize Vault client
vault_url = os.environ.get('VAULT_ADDR', 'https://vault.example.com:8200')
vault_token = os.environ['VAULT_TOKEN']

client = hvac.Client(url=vault_url, token=vault_token)

def get_database_password():
    secret = client.secrets.kv.v2.read_secret_version(
        path='production/myapp/database/password',
        mount_point='secret'
    )
    return secret['data']['data']['password']

def get_api_key():
    secret = client.secrets.kv.v2.read_secret_version(
        path='production/myapp/api-key',
        mount_point='secret'
    )
    return secret['data']['data']

def get_service_account():
    secret = client.secrets.kv.v2.read_secret_version(
        path='production/myapp/service-account',
        mount_point='secret'
    )
    return secret['data']['data']

# Use secrets
db_password = get_database_password()
api_key = get_api_key()
svc_account = get_service_account()
```

### Multi-Cloud Application (Python)

```python
import os
import boto3
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import hvac

class MultiCloudSecretManager:
    """Unified secret manager for multi-cloud deployments"""
    
    def __init__(self, cloud_provider=None):
        self.cloud_provider = cloud_provider or self._detect_cloud_provider()
        self._init_clients()
    
    def _detect_cloud_provider(self):
        """Auto-detect cloud provider from environment"""
        if os.environ.get('AWS_EXECUTION_ENV'):
            return 'aws'
        elif os.environ.get('AZURE_FUNCTIONS_ENVIRONMENT'):
            return 'azure'
        elif os.environ.get('VAULT_ADDR'):
            return 'vault'
        else:
            return 'local'
    
    def _init_clients(self):
        """Initialize cloud-specific clients"""
        if self.cloud_provider == 'aws':
            self.secrets_client = boto3.client('secretsmanager')
            self.ssm_client = boto3.client('ssm')
        elif self.cloud_provider == 'azure':
            credential = DefaultAzureCredential()
            vault_url = os.environ['AZURE_KEYVAULT_URL']
            self.kv_client = SecretClient(vault_url=vault_url, credential=credential)
        elif self.cloud_provider == 'vault':
            self.vault_client = hvac.Client(
                url=os.environ['VAULT_ADDR'],
                token=os.environ['VAULT_TOKEN']
            )
    
    def get_secret(self, secret_path):
        """Get secret from appropriate cloud provider"""
        if self.cloud_provider == 'aws':
            response = self.secrets_client.get_secret_value(SecretId=secret_path)
            return response['SecretString']
        
        elif self.cloud_provider == 'azure':
            secret = self.kv_client.get_secret(secret_path)
            return secret.value
        
        elif self.cloud_provider == 'vault':
            secret = self.vault_client.secrets.kv.v2.read_secret_version(
                path=secret_path,
                mount_point='secret'
            )
            return secret['data']['data']
        
        elif self.cloud_provider == 'local':
            # Read from environment or .env file
            return os.environ.get(secret_path)

# Usage
secrets = MultiCloudSecretManager()
db_password = secrets.get_secret('production/myapp/database/password')
api_key = secrets.get_secret('production/myapp/api-key')
```

## Advanced Scenarios

### Cross-Region Disaster Recovery

Replicate secrets across multiple regions for high availability:

```yaml
version: '1.0'

variables:
  environment: production
  primary_region: us-east-1
  dr_region: us-west-2

providers:
  aws_primary:
    kind: aws
    auth:
      kind: ambient
      config:
        region: ${primary_region}
  
  aws_dr:
    kind: aws
    auth:
      kind: ambient
      config:
        region: ${dr_region}
  
  azure_primary:
    kind: azure
    auth:
      kind: default
  
  azure_dr:
    kind: azure
    auth:
      kind: default

secrets:
  - name: critical_database_password
    kind: random_password
    one_time: true
    rotation_period: 90d
    config:
      length: 32
      special: true
    targets:
      # AWS primary region
      - provider: aws_primary
        kind: secrets_manager
        config:
          name: ${environment}/database/password
          description: Critical database password (primary)
          replica_regions:
            - ${dr_region}  # AWS native replication
          tags:
            Region: primary
            DR: enabled
      
      # AWS DR region (explicit)
      - provider: aws_dr
        kind: secrets_manager
        config:
          name: ${environment}/database/password
          description: Critical database password (DR)
          tags:
            Region: dr
            DR: enabled
      
      # Azure primary Key Vault
      - provider: azure_primary
        kind: key_vault
        config:
          vault_url: https://myapp-primary.vault.azure.net
          secret_name: database-password
          tags:
            region: primary
            dr: enabled
      
      # Azure DR Key Vault
      - provider: azure_dr
        kind: key_vault
        config:
          vault_url: https://myapp-dr.vault.azure.net
          secret_name: database-password
          tags:
            region: dr
            dr: enabled

metadata:
  project: multi-region-dr
  owner: platform-team
  compliance:
    - soc2
    - iso27001
```

### Hybrid Cloud with On-Premises Vault

Bridge cloud secrets with on-premises HashiCorp Vault:

```yaml
version: '1.0'

providers:
  aws:
    kind: aws
    auth:
      kind: ambient
      config:
        region: us-east-1
  
  azure:
    kind: azure
    auth:
      kind: default
  
  # On-premises Vault cluster
  vault_onprem:
    kind: vault
    auth:
      kind: token
      config:
        token: ${VAULT_TOKEN}
        url: https://vault.internal.company.com:8200
        ca_cert: /etc/vault/ca.pem
  
  # Cloud Vault cluster
  vault_cloud:
    kind: vault
    auth:
      kind: token
      config:
        token: ${VAULT_CLOUD_TOKEN}
        url: https://vault.cloud.company.com:8200

secrets:
  # Hybrid cloud application credentials
  - name: app_hybrid_credentials
    kind: templates.hybrid_credentials

templates:
  hybrid_credentials:
    description: Hybrid cloud application credentials
    fields:
      cloud_api_key:
        generator:
          kind: random_string
          config:
            length: 32
            charset: hex
      onprem_api_key:
        generator:
          kind: random_string
          config:
            length: 32
            charset: hex
      shared_secret:
        generator:
          kind: random_password
          config:
            length: 48
            special: true
    targets:
      # Cloud secrets in AWS
      - provider: aws
        kind: secrets_manager
        config:
          name: production/hybrid/credentials
      
      # Cloud secrets in Azure
      - provider: azure
        kind: key_vault
        config:
          vault_url: https://myapp-cloud.vault.azure.net
          secret_name: hybrid-credentials
      
      # On-premises Vault
      - provider: vault_onprem
        kind: kv
        config:
          path: production/hybrid/credentials
          mount_point: secret
          version: 2
      
      # Cloud Vault (for cloud-native apps)
      - provider: vault_cloud
        kind: kv
        config:
          path: production/hybrid/credentials
          mount_point: secret
          version: 2
```

### Compliance-Driven Multi-Cloud

Implement strict compliance requirements across cloud providers:

```yaml
version: '1.0'

metadata:
  project: compliance-multi-cloud
  owner: compliance-team
  compliance:
    - soc2
    - iso27001
    - pci-dss
  classification: highly-sensitive

variables:
  environment: production

providers:
  aws:
    kind: aws
    auth:
      kind: ambient
      config:
        region: us-east-1
  
  azure:
    kind: azure
    auth:
      kind: default
  
  vault:
    kind: vault
    auth:
      kind: token
      config:
        token: ${VAULT_TOKEN}
        url: ${VAULT_ADDR}

policies:
  # Strict rotation requirements
  compliance_rotation:
    kind: rotation
    require_rotation_period: true
    max_age: 60d  # PCI-DSS requires 90 days max
    severity: error
    enabled: true
  
  # Encryption at rest required
  encryption_required:
    kind: encryption
    require_kms: true
    severity: error
    enabled: true
  
  # Audit trail requirements
  audit_required:
    kind: audit
    require_tags: true
    required_tags:
      - DataClassification
      - Owner
      - Compliance
    severity: error
    enabled: true

secrets:
  # PCI-DSS compliant payment processing secret
  - name: payment_gateway_key
    kind: random_password
    rotation_period: 60d
    config:
      length: 48
      special: true
    targets:
      # AWS with KMS encryption
      - provider: aws
        kind: secrets_manager
        config:
          name: ${environment}/payment/gateway-key
          description: Payment gateway API key
          kms_key_id: arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012
          tags:
            DataClassification: highly-sensitive
            Owner: payments-team
            Compliance: pci-dss,soc2
            Environment: ${environment}
      
      # Azure with managed encryption
      - provider: azure
        kind: key_vault
        config:
          vault_url: https://myapp-compliance.vault.azure.net
          secret_name: payment-gateway-key
          tags:
            data-classification: highly-sensitive
            owner: payments-team
            compliance: pci-dss,soc2
      
      # Vault with audit enabled
      - provider: vault
        kind: kv
        config:
          path: ${environment}/payment/gateway-key
          mount_point: secret
          version: 2
          metadata:
            data_classification: highly-sensitive
            owner: payments-team
            compliance: pci-dss,soc2
            audit_required: "true"

  # SOC2 compliant database credentials
  - name: database_admin_password
    kind: random_password
    rotation_period: 90d
    config:
      length: 32
      special: true
      exclude_characters: '"@/\`'
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: ${environment}/database/admin-password
          description: Database administrator password
          kms_key_id: arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012
          replica_regions:
            - us-west-2  # DR region
          tags:
            DataClassification: sensitive
            Owner: database-team
            Compliance: soc2,iso27001
            RotationPeriod: 90d
      
      - provider: azure
        kind: key_vault
        config:
          vault_url: https://myapp-compliance.vault.azure.net
          secret_name: database-admin-password
          expires_on: "{{ 90 days from now }}"
          tags:
            data-classification: sensitive
            owner: database-team
            compliance: soc2,iso27001
      
      - provider: vault
        kind: kv
        config:
          path: ${environment}/database/admin-password
          mount_point: secret
          version: 2
          metadata:
            data_classification: sensitive
            owner: database-team
            compliance: soc2,iso27001
            rotation_period: 90d
```

### Cost Optimization Strategy

Optimize costs by using appropriate secret storage for different use cases:

```yaml
version: '1.0'

variables:
  environment: production

providers:
  aws:
    kind: aws
    auth:
      kind: ambient

secrets:
  # High-value secrets → AWS Secrets Manager ($0.40/month + $0.05/10k API calls)
  - name: database_master_password
    kind: random_password
    rotation_period: 90d
    config:
      length: 32
      special: true
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: ${environment}/database/master-password
          description: RDS master password (high-value, rotation enabled)
          tags:
            Cost-Optimization: secrets-manager
            Rotation: enabled

  # Standard secrets → SSM Parameter Store ($0.05/month for Standard tier)
  - name: api_key
    kind: random_string
    config:
      length: 32
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /${environment}/api/key
          type: SecureString
          tier: Standard  # More cost-effective than Secrets Manager
          description: API key (standard access pattern)
          tags:
            Cost-Optimization: ssm-standard

  # Configuration values → SSM Parameter Store String (Free)
  - name: app_version
    kind: static
    config:
      default: "1.0.0"
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /${environment}/app/version
          type: String  # Free tier
          tier: Standard
          description: Application version (non-sensitive)
          tags:
            Cost-Optimization: ssm-string-free

  # Large secrets → SSM Parameter Store Advanced tier ($0.05/month)
  - name: large_certificate
    kind: static
    config:
      default: ${CERTIFICATE_CONTENT}  # Up to 8KB
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /${environment}/certificates/large-cert
          type: SecureString
          tier: Advanced  # Required for >4KB parameters
          description: Large certificate (Advanced tier required)
          tags:
            Cost-Optimization: ssm-advanced
```

## Best Practices

1. **Use Provider-Native Features** - Leverage cloud-specific features like AWS Secrets Manager automatic rotation, Azure Key Vault soft delete, and Vault's dynamic secrets. Don't try to replicate provider features with custom code - use what each platform does best.

2. **Implement Geographic Redundancy** - Store critical secrets in multiple regions and cloud providers for disaster recovery. Use AWS Secrets Manager replica regions, Azure geo-replication, and Vault replication clusters. Test failover procedures regularly.

3. **Tag Everything Consistently** - Apply consistent tagging across all cloud providers for cost tracking, compliance, and automation. Use tags for: DataClassification, Owner, Environment, Application, Compliance, CostCenter, and ManagedBy. Enforce tag policies.

4. **Minimize Cross-Cloud API Calls** - Cache secrets locally when possible to reduce API calls and costs. Use AWS Secrets Manager caching, Azure Key Vault caching, or implement application-level caching with appropriate TTLs (5-60 minutes depending on sensitivity).

5. **Implement Least Privilege Access** - Grant minimum necessary permissions in each cloud provider: AWS IAM policies with specific secret ARNs, Azure RBAC with specific Key Vault permissions, and Vault policies with path-based access. Avoid wildcard permissions.

6. **Monitor and Alert on Secret Access** - Enable CloudTrail (AWS), Azure Monitor, and Vault audit logs to track secret access. Set up alerts for unusual access patterns, failed authentication attempts, and secret modifications. Integrate with SIEM systems.

7. **Use Cost-Effective Storage** - Choose appropriate secret storage based on access patterns and requirements: Secrets Manager for auto-rotation, SSM Parameter Store for simple secrets, Key Vault for Azure-native apps, and Vault for dynamic secrets. Balance cost vs. features.

8. **Encrypt with Customer-Managed Keys** - Use AWS KMS customer-managed keys (CMK), Azure Key Vault keys, or Vault transit encryption for additional control. Enable key rotation policies. Separate keys by environment and data classification level.

9. **Implement Secret Versioning** - Enable versioning in AWS Secrets Manager, Azure Key Vault, and Vault KV v2 to support rollback during incidents. Retain previous versions for audit and recovery purposes (typically 90 days minimum for compliance).

10. **Automate Compliance Validation** - Use SecretZero policies to enforce rotation requirements, tagging standards, and access controls across all cloud providers. Run compliance checks in CI/CD pipelines. Generate compliance reports for auditors showing consistent controls across clouds.

## Troubleshooting

### AWS Authentication Failed

**Problem**: `Error: Unable to authenticate with AWS`

**Solutions**:

```bash
# Verify AWS credentials
aws sts get-caller-identity

# Check IAM permissions
aws iam get-user
aws iam list-attached-user-policies --user-name your-username

# Verify required permissions
aws secretsmanager list-secrets --max-items 1
aws ssm describe-parameters --max-items 1

# Check region configuration
echo $AWS_DEFAULT_REGION
aws configure get region

# Use specific profile
export AWS_PROFILE=production
secretzero sync

# Check credential chain
aws configure list

# For EC2/ECS, verify IAM role
curl http://169.254.169.254/latest/meta-data/iam/security-credentials/
```

Required AWS IAM permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:CreateSecret",
        "secretsmanager:GetSecretValue",
        "secretsmanager:PutSecretValue",
        "secretsmanager:UpdateSecret",
        "secretsmanager:TagResource"
      ],
      "Resource": "arn:aws:secretsmanager:*:*:secret:production/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ssm:PutParameter",
        "ssm:GetParameter",
        "ssm:AddTagsToResource"
      ],
      "Resource": "arn:aws:ssm:*:*:parameter/production/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "kms:Decrypt",
        "kms:Encrypt",
        "kms:GenerateDataKey"
      ],
      "Resource": "arn:aws:kms:*:*:key/*"
    }
  ]
}
```

### Azure Authentication Failed

**Problem**: `Error: Azure authentication failed`

**Solutions**:

```bash
# Verify Azure login
az account show

# Check subscription
az account list --output table

# Set correct subscription
az account set --subscription "Production Subscription"

# Verify Key Vault access
az keyvault list --output table
az keyvault secret list --vault-name myapp-prod-secrets

# Check service principal (if using)
az ad sp show --id $AZURE_CLIENT_ID

# Verify Key Vault permissions
az keyvault set-policy \
  --name myapp-prod-secrets \
  --object-id $(az ad signed-in-user show --query objectId -o tsv) \
  --secret-permissions get list set delete

# For managed identity (in Azure VM/Functions)
curl 'http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://vault.azure.net' -H Metadata:true

# Check environment variables
echo $AZURE_CLIENT_ID
echo $AZURE_TENANT_ID
```

Required Azure Key Vault permissions:

- Secret: Get, List, Set, Delete
- Certificate: Get, List, Import (if using certificates)
- Storage: Get, List, Set (if using storage account keys)

### Vault Connection Failed

**Problem**: `Error: Unable to connect to Vault`

**Solutions**:

```bash
# Verify Vault address
echo $VAULT_ADDR
curl -k $VAULT_ADDR/v1/sys/health

# Check Vault token
echo $VAULT_TOKEN
vault token lookup

# Verify token permissions
vault token capabilities secret/production/myapp

# Check Vault status
vault status

# Test authentication
vault auth list
vault login $VAULT_TOKEN

# Verify KV mount
vault secrets list
vault kv list secret/

# Check network connectivity
nc -zv vault.example.com 8200
curl -v https://vault.example.com:8200/v1/sys/health

# TLS certificate issues
vault status -tls-skip-verify
# Or configure CA certificate
export VAULT_CACERT=/path/to/ca.pem

# Check Vault policies
vault policy read myapp-policy
vault token lookup -format=json | jq -r .data.policies
```

### Secret Not Syncing to All Providers

**Problem**: Secret syncs to some providers but not others

**Solutions**:

```bash
# Enable verbose logging
secretzero sync --verbose

# Test each provider individually
secretzero test

# Check provider configuration
secretzero validate

# Force sync to specific provider
secretzero sync --provider aws
secretzero sync --provider azure
secretzero sync --provider vault

# Check lockfile for sync status
cat .gitsecrets.lock | jq '.secrets[] | select(.name=="database_password")'

# Verify permissions for each provider
# AWS
aws secretsmanager describe-secret --secret-id production/myapp/database/password

# Azure
az keyvault secret show --vault-name myapp-prod-secrets --name myapp-database-password

# Vault
vault kv get secret/production/myapp/database/password

# Check for provider-specific errors in logs
secretzero sync 2>&1 | grep ERROR
```

### Cross-Region Replication Issues

**Problem**: AWS Secrets Manager replication not working

**Solutions**:

```bash
# Verify replica regions configuration
aws secretsmanager describe-secret \
  --secret-id production/myapp/database/password \
  --query 'ReplicationStatus' --output json

# Check KMS key permissions in replica regions
aws kms describe-key \
  --key-id alias/aws/secretsmanager \
  --region us-west-2

# Enable replication manually
aws secretsmanager replicate-secret-to-regions \
  --secret-id production/myapp/database/password \
  --add-replica-regions Region=us-west-2 \
  --region us-east-1

# Verify replication status
aws secretsmanager describe-secret \
  --secret-id production/myapp/database/password \
  --region us-west-2

# Check for replication errors
aws secretsmanager list-secrets \
  --filter Key=name,Values=production/myapp/database/password \
  --region us-east-1

# Remove and re-add replica if stuck
aws secretsmanager remove-regions-from-replication \
  --secret-id production/myapp/database/password \
  --remove-replica-regions us-west-2 \
  --region us-east-1

# Wait a few seconds, then re-add
aws secretsmanager replicate-secret-to-regions \
  --secret-id production/myapp/database/password \
  --add-replica-regions Region=us-west-2 \
  --region us-east-1
```

### Cost Overruns

**Problem**: Unexpected high costs from secret storage

**Solutions**:

```bash
# Analyze AWS costs
# Secrets Manager: $0.40/month per secret + $0.05/10k API calls
aws secretsmanager list-secrets --query 'SecretList | length'

# SSM Parameter Store: $0.05/month (Standard), $0.05/month (Advanced)
aws ssm describe-parameters --query 'Parameters | length'

# Check API call metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/SecretsManager \
  --metric-name SecretAccessed \
  --dimensions Name=SecretName,Value=production/myapp/database/password \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-31T23:59:59Z \
  --period 86400 \
  --statistics Sum

# Optimize by migrating to SSM Parameter Store
# For secrets without rotation needs
secretzero sync --target-type ssm_parameter

# Implement caching to reduce API calls
# Use AWS Secrets Manager caching client
pip install aws-secretsmanager-caching

# Azure Key Vault costs
# $0.03 per 10,000 operations
az monitor metrics list \
  --resource /subscriptions/{subscription-id}/resourceGroups/{rg}/providers/Microsoft.KeyVault/vaults/{vault-name} \
  --metric ServiceApiHit \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-31T23:59:59Z

# Vault costs depend on deployment model
# Self-hosted: infrastructure costs
# HCP Vault: per-client pricing
```

### Provider API Rate Limiting

**Problem**: `Error: Rate limit exceeded`

**Solutions**:

```bash
# AWS rate limits
# Secrets Manager: 1,500 TPS per account per region
# SSM: 3,000 TPS for GetParameter

# Implement exponential backoff
secretzero sync --retry-max-attempts 5 --retry-backoff exponential

# Batch operations when possible
# Use AWS SDK batch operations

# Azure rate limits
# Key Vault: 2,000 GET requests per 10 seconds per vault
# Spread across multiple Key Vaults if needed

# Vault rate limits
# Configured via rate limit quotas
vault read sys/quotas/rate-limit

# Implement client-side caching
# Cache secrets for 5-60 minutes depending on sensitivity
export SECRETZERO_CACHE_TTL=300  # 5 minutes

# Monitor rate limit metrics
# AWS CloudWatch
aws cloudwatch get-metric-statistics \
  --namespace AWS/SecretsManager \
  --metric-name ThrottledRequests \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum

# Use provider SDKs with built-in retry logic
```

### Secret Value Corruption

**Problem**: Secret value appears corrupted or unreadable

**Solutions**:

```bash
# Check encoding
# AWS and Azure use UTF-8, Vault uses bytes

# Verify secret value
# AWS
aws secretsmanager get-secret-value \
  --secret-id production/myapp/database/password \
  --query 'SecretString' --output text | od -c

# Azure
az keyvault secret show \
  --vault-name myapp-prod-secrets \
  --name myapp-database-password \
  --query 'value' --output tsv | od -c

# Vault
vault kv get -field=password secret/production/myapp/database/password | od -c

# Check for base64 encoding issues
# SecretZero handles base64 encoding automatically
# Don't manually encode values

# Verify character set
secretzero validate

# Check special characters in secret
# Some providers have restrictions on special characters

# Re-generate and sync
secretzero sync --force --secret database_password

# Check lockfile for original value hash
cat .gitsecrets.lock | jq '.secrets[] | select(.name=="database_password")'
```

## Complete Example

Full production multi-cloud secret management:

```yaml
version: '1.0'

metadata:
  project: multi-cloud-production
  owner: platform-team
  compliance:
    - soc2
    - iso27001
  classification: sensitive
  description: |
    Production multi-cloud secret management across AWS, Azure, and Vault.
    Implements geographic redundancy, compliance requirements, and cost optimization.

variables:
  environment: production
  app_name: myapp
  aws_primary_region: us-east-1
  aws_dr_region: us-west-2
  azure_primary_region: eastus
  azure_dr_region: westus2

providers:
  # AWS Primary Region
  aws_primary:
    kind: aws
    auth:
      kind: ambient
      config:
        region: ${aws_primary_region}
  
  # AWS DR Region
  aws_dr:
    kind: aws
    auth:
      kind: ambient
      config:
        region: ${aws_dr_region}
  
  # Azure Primary
  azure_primary:
    kind: azure
    auth:
      kind: default
  
  # HashiCorp Vault
  vault:
    kind: vault
    auth:
      kind: token
      config:
        token: ${VAULT_TOKEN}
        url: ${VAULT_ADDR}
  
  # Local development
  local:
    kind: local

policies:
  # Rotation requirements
  compliance_rotation:
    kind: rotation
    require_rotation_period: true
    max_age: 90d
    severity: error
    enabled: true
  
  # Tagging requirements
  audit_trail:
    kind: audit
    require_tags: true
    required_tags:
      - DataClassification
      - Owner
      - Environment
      - Application
    severity: warning
    enabled: true

secrets:
  # 1. Database credentials (multi-cloud, auto-rotating)
  - name: database_credentials
    kind: templates.database_full
    rotation_period: 90d

  # 2. API keys (distributed across providers)
  - name: external_api_keys
    kind: templates.api_credentials
    rotation_period: 90d

  # 3. Service account (JSON format)
  - name: service_account_credentials
    kind: templates.service_account
    rotation_period: 180d

  # 4. Encryption keys
  - name: application_encryption_key
    kind: random_string
    one_time: true
    rotation_period: 365d
    config:
      length: 32
      charset: base64
    targets:
      # AWS with KMS encryption
      - provider: aws_primary
        kind: secrets_manager
        config:
          name: ${environment}/${app_name}/encryption-key
          description: Application encryption key
          kms_key_id: alias/myapp-encryption
          replica_regions:
            - ${aws_dr_region}
          tags:
            DataClassification: highly-sensitive
            Owner: security-team
            Environment: ${environment}
            Application: ${app_name}
            Compliance: soc2,iso27001
      
      # Azure Key Vault
      - provider: azure_primary
        kind: key_vault
        config:
          vault_url: https://myapp-prod-primary.vault.azure.net
          secret_name: ${app_name}-encryption-key
          tags:
            data-classification: highly-sensitive
            owner: security-team
            environment: ${environment}
      
      # Vault
      - provider: vault
        kind: kv
        config:
          path: ${environment}/${app_name}/encryption-key
          mount_point: secret
          version: 2
          metadata:
            data_classification: highly-sensitive
            owner: security-team

templates:
  # Complete database credentials
  database_full:
    description: Complete database credentials with connection strings
    fields:
      host:
        generator:
          kind: static
          config:
            default: ${DB_HOST}
      port:
        generator:
          kind: static
          config:
            default: "5432"
      database:
        generator:
          kind: static
          config:
            default: ${app_name}
      username:
        generator:
          kind: static
          config:
            default: ${app_name}_user
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
            default: postgresql://${app_name}_user:{{password}}@${DB_HOST}:5432/${app_name}
    targets:
      # AWS Secrets Manager (primary)
      - provider: aws_primary
        kind: secrets_manager
        config:
          name: ${environment}/${app_name}/database/credentials
          description: Database credentials with auto-rotation
          replica_regions:
            - ${aws_dr_region}
          tags:
            DataClassification: sensitive
            Owner: database-team
            Environment: ${environment}
            Application: ${app_name}
            RotationEnabled: "true"
      
      # Azure Key Vault (DR)
      - provider: azure_primary
        kind: key_vault
        config:
          vault_url: https://myapp-prod-primary.vault.azure.net
          secret_name: ${app_name}-database-credentials
          content_type: application/json
          tags:
            data-classification: sensitive
            owner: database-team
            environment: ${environment}
      
      # Vault (multi-cloud reference)
      - provider: vault
        kind: kv
        config:
          path: ${environment}/${app_name}/database/credentials
          mount_point: secret
          version: 2
          metadata:
            data_classification: sensitive
            owner: database-team
            rotation_period: 90d
      
      # Local development
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true

  # API credentials
  api_credentials:
    description: External API credentials
    fields:
      stripe_api_key:
        generator:
          kind: static
          config:
            default: ${STRIPE_API_KEY}
      sendgrid_api_key:
        generator:
          kind: static
          config:
            default: ${SENDGRID_API_KEY}
      twilio_auth_token:
        generator:
          kind: static
          config:
            default: ${TWILIO_AUTH_TOKEN}
    targets:
      # AWS Secrets Manager
      - provider: aws_primary
        kind: secrets_manager
        config:
          name: ${environment}/${app_name}/api-keys
          description: Third-party API keys
          tags:
            DataClassification: sensitive
            Owner: platform-team
            Environment: ${environment}
            Application: ${app_name}
      
      # Azure Key Vault
      - provider: azure_primary
        kind: key_vault
        config:
          vault_url: https://myapp-prod-primary.vault.azure.net
          secret_name: ${app_name}-api-keys
          content_type: application/json
          tags:
            data-classification: sensitive
            owner: platform-team
      
      # Vault
      - provider: vault
        kind: kv
        config:
          path: ${environment}/${app_name}/api-keys
          mount_point: secret
          version: 2

  # Service account
  service_account:
    description: Service account credentials for automation
    fields:
      account_id:
        generator:
          kind: static
          config:
            default: svc_${app_name}_${environment}
      api_key:
        generator:
          kind: random_string
          config:
            length: 32
            charset: hex
      api_secret:
        generator:
          kind: random_password
          config:
            length: 48
            special: true
      created_at:
        generator:
          kind: static
          config:
            default: "2024-01-15T10:30:00Z"  # ISO 8601 timestamp
    targets:
      # AWS Secrets Manager
      - provider: aws_primary
        kind: secrets_manager
        config:
          name: ${environment}/${app_name}/service-account
          description: Service account credentials
          tags:
            DataClassification: sensitive
            Owner: automation-team
            Environment: ${environment}
      
      # Azure Key Vault
      - provider: azure_primary
        kind: key_vault
        config:
          vault_url: https://myapp-prod-primary.vault.azure.net
          secret_name: ${app_name}-service-account
          content_type: application/json
      
      # Vault
      - provider: vault
        kind: kv
        config:
          path: ${environment}/${app_name}/service-account
          mount_point: secret
          version: 2
      
      # Local file
      - provider: local
        kind: file
        config:
          path: .service-account.json
          format: json
```

Deploy:

```bash
# 1. Set environment variables
export AWS_PROFILE=production
export AZURE_SUBSCRIPTION_ID=your-subscription-id
export VAULT_ADDR=https://vault.example.com:8200
export VAULT_TOKEN=hvs.CAESIJ1...
export DB_HOST=postgres.prod.example.com
export STRIPE_API_KEY=sk_live_...
export SENDGRID_API_KEY=SG....
export TWILIO_AUTH_TOKEN=your-token

# 2. Validate configuration
secretzero validate

# 3. Test all provider connections
secretzero test

# 4. Check compliance policies
secretzero policy --fail-on-warning

# 5. Preview multi-cloud sync
secretzero sync --dry-run

# 6. Sync secrets to all providers
secretzero sync

# 7. Verify in each provider
# AWS
aws secretsmanager list-secrets --query 'SecretList[?starts_with(Name, `production/myapp/`)].Name'

# Azure
az keyvault secret list --vault-name myapp-prod-primary --query '[].name'

# Vault
vault kv list secret/production/myapp/

# Local
ls -la .env .service-account.json

# 8. Test secret retrieval
# AWS
aws secretsmanager get-secret-value --secret-id production/myapp/database/credentials

# Azure
az keyvault secret show --vault-name myapp-prod-primary --name myapp-database-credentials

# Vault
vault kv get secret/production/myapp/database/credentials

# 9. Set up automated rotation
# Add to CI/CD pipeline or scheduled job
secretzero rotate --dry-run
secretzero rotate
```

## Next Steps

- **[Kubernetes Integration](kubernetes.md)** - Sync multi-cloud secrets to Kubernetes
- **[Compliance Scenarios](compliance.md)** - Implement SOC2/ISO27001 across clouds
- **[Augmentation Guide](augmenting.md)** - Augment your current secrets manager
- **[AWS Secrets Manager](https://aws.amazon.com/secrets-manager/)** - AWS-specific features
- **[Azure Key Vault](https://azure.microsoft.com/en-us/products/key-vault)** - Azure-specific features
- **[HashiCorp Vault](https://www.vaultproject.io/)** - Vault-specific features
