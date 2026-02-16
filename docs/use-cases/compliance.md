# Compliance and Auditing

## Problem Statement

Meeting compliance requirements (SOC2, ISO27001, PCI-DSS, HIPAA) for secret management presents significant challenges:

- No standardized way to enforce rotation policies across all secrets
- Difficult to track secret access and modifications for audit trails
- Manual compliance checks are time-consuming and error-prone
- Inconsistent secret management practices across teams and environments
- Lack of automated controls for data classification and access restrictions
- No centralized visibility into secret lifecycle (creation, rotation, access, deletion)
- Meeting auditor requirements for documentation and evidence is complex
- Proving compliance across multiple secret storage systems is challenging

**SecretZero solves this** by providing built-in compliance policies, automated rotation enforcement, comprehensive audit trails, and compliance-ready reporting for SOC2, ISO27001, PCI-DSS, and HIPAA requirements.

## Prerequisites

- SecretZero installed: `pip install secretzero`
- Cloud provider credentials configured (AWS, Azure, Vault, etc.)
- Understanding of your organization's compliance requirements
- Access to compliance documentation and audit requirements
- Defined data classification levels for your organization
- RBAC permissions configured for secret management

## Authentication Setup

Authentication follows standard provider patterns. See [Multi-Cloud Setup](multi-cloud.md) for detailed authentication configuration for each provider.

```bash
# AWS
export AWS_PROFILE=production

# Azure
az login

# Vault
export VAULT_ADDR=https://vault.example.com:8200
export VAULT_TOKEN=hvs.CAESIJ1...
```

## Configuration

### SOC2 Compliance

SOC2 requires strict access controls, audit logging, and regular secret rotation:

```yaml
version: '1.0'

metadata:
  project: soc2-compliant-app
  owner: security-team
  compliance:
    - soc2  # Automatically applies SOC2 policies
  classification: sensitive
  description: SOC2-compliant secret management

variables:
  environment: production
  app_name: myapp

providers:
  aws:
    kind: aws
    auth:
      kind: ambient
      config:
        region: us-east-1

policies:
  # SOC2 requires secrets to be rotated regularly
  soc2_rotation:
    kind: rotation
    require_rotation_period: true
    max_age: 90d  # SOC2 recommendation: 90 days maximum
    severity: error
    enabled: true
  
  # Access control requirements
  soc2_access_control:
    kind: access
    allowed_targets:
      - secrets_manager  # Only encrypted storage
      - ssm_parameter
      - key_vault
      - vault_kv
    denied_targets:
      - file  # No local files in production
    severity: error
    enabled: true
  
  # Audit trail requirements
  soc2_audit:
    kind: audit
    require_tags: true
    required_tags:
      - Owner
      - DataClassification
      - Environment
      - Application
    require_encryption: true
    severity: error
    enabled: true

secrets:
  # Database credentials with SOC2 compliance
  - name: database_password
    kind: random_password
    rotation_period: 90d  # Required by policy
    config:
      length: 32
      special: true
      exclude_characters: '"@/\`'
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: ${environment}/${app_name}/database/password
          description: Database password (SOC2 compliant)
          kms_key_id: arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012
          tags:
            Owner: database-team
            DataClassification: sensitive
            Environment: ${environment}
            Application: ${app_name}
            Compliance: soc2
            RotationPeriod: 90d
            LastRotated: "{{ timestamp }}"

  # API keys with rotation tracking
  - name: api_key
    kind: random_string
    rotation_period: 90d
    config:
      length: 32
      charset: hex
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: ${environment}/${app_name}/api-key
          description: API key (SOC2 compliant)
          kms_key_id: arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012
          tags:
            Owner: api-team
            DataClassification: sensitive
            Environment: ${environment}
            Application: ${app_name}
            Compliance: soc2
            RotationPeriod: 90d

  # Service account with audit trail
  - name: service_account
    kind: templates.service_account_soc2

templates:
  service_account_soc2:
    description: SOC2-compliant service account credentials
    fields:
      username:
        generator:
          kind: static
          config:
            default: svc_${app_name}_${environment}
      password:
        generator:
          kind: random_password
          config:
            length: 32
            special: true
      created_at:
        generator:
          kind: static
          config:
            default: "{{ timestamp }}"
      created_by:
        generator:
          kind: static
          config:
            default: ${USER}
      compliance_version:
        generator:
          kind: static
          config:
            default: "SOC2-2017"
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: ${environment}/${app_name}/service-account
          description: Service account (SOC2 compliant)
          kms_key_id: arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012
          tags:
            Owner: automation-team
            DataClassification: sensitive
            Environment: ${environment}
            Application: ${app_name}
            Compliance: soc2
            RotationPeriod: 180d
```

### ISO27001 Compliance

ISO27001 requires documented controls, risk management, and security monitoring:

```yaml
version: '1.0'

metadata:
  project: iso27001-compliant-app
  owner: information-security-team
  compliance:
    - iso27001
  classification: confidential
  iso27001_controls:
    - A.9.4.1  # Information access restriction
    - A.10.1.1  # Cryptographic controls
    - A.12.1.3  # Capacity management
    - A.12.4.1  # Event logging
    - A.14.1.2  # Securing application services

variables:
  environment: production
  app_name: myapp

providers:
  aws:
    kind: aws
    auth:
      kind: ambient
  
  azure:
    kind: azure
    auth:
      kind: default

policies:
  # ISO27001 rotation requirements (Control A.9.2.4)
  iso27001_rotation:
    kind: rotation
    require_rotation_period: true
    max_age: 90d
    severity: error
    enabled: true
    metadata:
      control: A.9.2.4
      description: Management of secret information
  
  # Encryption requirements (Control A.10.1.1)
  iso27001_encryption:
    kind: encryption
    require_kms: true
    require_encryption_at_rest: true
    severity: error
    enabled: true
    metadata:
      control: A.10.1.1
      description: Cryptographic controls
  
  # Access control (Control A.9.4.1)
  iso27001_access:
    kind: access
    allowed_targets:
      - secrets_manager
      - key_vault
      - vault_kv
    require_mfa: true
    severity: error
    enabled: true
    metadata:
      control: A.9.4.1
      description: Information access restriction

secrets:
  # Highly confidential database credentials
  - name: database_master_password
    kind: random_password
    rotation_period: 60d  # More frequent for critical systems
    config:
      length: 32
      special: true
    targets:
      # AWS with encryption and audit logging
      - provider: aws
        kind: secrets_manager
        config:
          name: ${environment}/${app_name}/database/master-password
          description: Database master password (ISO27001 compliant)
          kms_key_id: arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012
          tags:
            Owner: database-admin-team
            DataClassification: highly-confidential
            Environment: ${environment}
            ISO27001Control: A.9.2.4,A.10.1.1
            RiskLevel: critical
            RotationPeriod: 60d
            BusinessImpact: high
            BackupRequired: "true"
      
      # Azure Key Vault for geographic redundancy
      - provider: azure
        kind: key_vault
        config:
          vault_url: https://myapp-prod-iso27001.vault.azure.net
          secret_name: ${app_name}-database-master-password
          content_type: password
          enabled: true
          expires_on: "{{ 60 days from now }}"
          tags:
            owner: database-admin-team
            data-classification: highly-confidential
            iso27001-control: A.9.2.4,A.10.1.1
            risk-level: critical

  # Application encryption keys
  - name: encryption_key
    kind: random_string
    one_time: true  # Never rotate encryption keys automatically
    rotation_period: 365d  # Annual review required
    config:
      length: 32
      charset: base64
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: ${environment}/${app_name}/encryption-key
          description: Application encryption key (ISO27001 compliant)
          kms_key_id: arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012
          tags:
            Owner: security-team
            DataClassification: highly-confidential
            Environment: ${environment}
            ISO27001Control: A.10.1.1,A.10.1.2
            KeyType: symmetric
            KeyUsage: encryption
            BackupRequired: "true"
            RecoveryPointObjective: 1h
```

### PCI-DSS Compliance

PCI-DSS has strict requirements for protecting cardholder data:

```yaml
version: '1.0'

metadata:
  project: pci-dss-compliant-app
  owner: compliance-team
  compliance:
    - pci-dss
  classification: cardholder-data-environment
  pci_dss_requirements:
    - "3.4"  # Cryptography for transmission and storage
    - "3.5"  # Key management
    - "3.6"  # Key-management procedures
    - "8.2"  # User authentication
    - "8.3"  # Multi-factor authentication

variables:
  environment: production
  app_name: payment-processor

providers:
  aws:
    kind: aws
    auth:
      kind: ambient
      config:
        region: us-east-1

policies:
  # PCI-DSS requires rotation every 90 days (Requirement 8.2.4)
  pci_rotation:
    kind: rotation
    require_rotation_period: true
    max_age: 90d
    min_age: 30d  # Minimum time between rotations
    severity: error
    enabled: true
    metadata:
      requirement: "8.2.4"
      description: Password rotation policy
  
  # Strong cryptography required (Requirement 3.4)
  pci_encryption:
    kind: encryption
    require_kms: true
    require_strong_encryption: true
    min_key_length: 256
    approved_algorithms:
      - AES-256
      - RSA-2048
    severity: error
    enabled: true
    metadata:
      requirement: "3.4"
      description: Strong cryptography
  
  # Access control (Requirement 7.1)
  pci_access_control:
    kind: access
    require_mfa: true
    require_role_separation: true
    allowed_targets:
      - secrets_manager  # Must use HSM-backed storage
    severity: error
    enabled: true
    metadata:
      requirement: "7.1"
      description: Access control systems

secrets:
  # Payment gateway credentials (cardholder data)
  - name: payment_gateway_key
    kind: random_password
    rotation_period: 90d
    config:
      length: 48  # Extra length for PCI-DSS
      special: true
      upper: true
      lower: true
      number: true
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: ${environment}/${app_name}/payment-gateway-key
          description: Payment gateway API key (PCI-DSS compliant)
          kms_key_id: arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012
          tags:
            Owner: payments-team
            DataClassification: cardholder-data
            Environment: ${environment}
            PCIDSSRequirement: "3.4,3.5,8.2"
            KeyManagementProcedure: documented
            RotationPeriod: 90d
            AccessRequiresMFA: "true"
            AuditLogEnabled: "true"
            EncryptionAlgorithm: AES-256-GCM

  # Database encryption key (for cardholder data at rest)
  - name: database_encryption_key
    kind: random_string
    one_time: true
    rotation_period: 365d  # Annual key rotation per PCI-DSS
    config:
      length: 32
      charset: base64
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: ${environment}/${app_name}/database-encryption-key
          description: Database encryption key (PCI-DSS compliant)
          kms_key_id: arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012
          tags:
            Owner: database-team
            DataClassification: encryption-key
            Environment: ${environment}
            PCIDSSRequirement: "3.4,3.5,3.6"
            KeyType: data-encryption-key
            KeyRotationSchedule: annual
            BackupRequired: "true"
            RecoveryProcedure: documented

  # Administrative access credentials
  - name: admin_credentials
    kind: templates.admin_credentials_pci

templates:
  admin_credentials_pci:
    description: PCI-DSS compliant admin credentials
    fields:
      username:
        generator:
          kind: static
          config:
            default: admin_${app_name}
      password:
        generator:
          kind: random_password
          config:
            length: 16
            special: true
            min_special: 2
            min_upper: 2
            min_lower: 2
            min_number: 2
      mfa_enabled:
        generator:
          kind: static
          config:
            default: "true"
      last_password_change:
        generator:
          kind: static
          config:
            default: "{{ timestamp }}"
      password_complexity_met:
        generator:
          kind: static
          config:
            default: "true"
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: ${environment}/${app_name}/admin-credentials
          description: Admin credentials (PCI-DSS compliant)
          kms_key_id: arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012
          tags:
            Owner: admin-team
            DataClassification: administrative-access
            Environment: ${environment}
            PCIDSSRequirement: "8.2,8.3"
            MFARequired: "true"
            PasswordComplexity: strong
            RotationPeriod: 90d
```

### HIPAA Compliance

HIPAA requires protection of Protected Health Information (PHI):

```yaml
version: '1.0'

metadata:
  project: hipaa-compliant-healthcare-app
  owner: compliance-officer
  compliance:
    - hipaa
  classification: protected-health-information
  hipaa_safeguards:
    - technical  # 164.312
    - physical   # 164.310
    - administrative  # 164.308

variables:
  environment: production
  app_name: healthcare-portal

providers:
  aws:
    kind: aws
    auth:
      kind: ambient
      config:
        region: us-east-1

policies:
  # HIPAA Security Rule - Access Control (164.312(a)(1))
  hipaa_access_control:
    kind: access
    require_unique_user_identification: true
    require_automatic_logoff: true
    require_encryption: true
    allowed_targets:
      - secrets_manager
      - key_vault
    severity: error
    enabled: true
    metadata:
      safeguard: "164.312(a)(1)"
      description: Access Control
  
  # HIPAA Security Rule - Audit Controls (164.312(b))
  hipaa_audit_controls:
    kind: audit
    require_audit_logs: true
    require_log_retention: true
    log_retention_days: 2555  # 7 years for HIPAA
    severity: error
    enabled: true
    metadata:
      safeguard: "164.312(b)"
      description: Audit Controls
  
  # HIPAA Security Rule - Integrity (164.312(c)(1))
  hipaa_integrity:
    kind: integrity
    require_encryption: true
    require_mechanism_to_authenticate: true
    severity: error
    enabled: true
    metadata:
      safeguard: "164.312(c)(1)"
      description: Integrity Controls

secrets:
  # Database credentials for PHI access
  - name: phi_database_password
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
          name: ${environment}/${app_name}/phi-database-password
          description: PHI database password (HIPAA compliant)
          kms_key_id: arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012
          tags:
            Owner: healthcare-it-team
            DataClassification: protected-health-information
            Environment: ${environment}
            HIPAASafeguard: "164.312(a)(2)(iv)"
            EncryptionRequired: "true"
            AuditLogRetention: 2555days
            AccessRequiresBAA: "true"
            PHIAccess: "true"

  # API keys for healthcare integrations
  - name: hl7_integration_key
    kind: random_string
    rotation_period: 90d
    config:
      length: 32
      charset: hex
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: ${environment}/${app_name}/hl7-integration-key
          description: HL7 integration API key (HIPAA compliant)
          kms_key_id: arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012
          tags:
            Owner: integration-team
            DataClassification: phi-access
            Environment: ${environment}
            HIPAASafeguard: "164.312(e)(1)"
            TransmissionSecurity: "true"
            EncryptionInTransit: "true"

  # Encryption keys for PHI at rest
  - name: phi_encryption_key
    kind: random_string
    one_time: true
    rotation_period: 365d
    config:
      length: 32
      charset: base64
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: ${environment}/${app_name}/phi-encryption-key
          description: PHI encryption key (HIPAA compliant)
          kms_key_id: arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012
          tags:
            Owner: security-team
            DataClassification: encryption-key
            Environment: ${environment}
            HIPAASafeguard: "164.312(a)(2)(iv)"
            KeyType: phi-encryption
            BackupRequired: "true"
            DisasterRecovery: documented
```

## Step-by-Step Instructions

### 1. Define Compliance Requirements

```bash
# Create compliance requirements document
cat > compliance-requirements.md << 'EOF'
# Compliance Requirements

## SOC2
- Secret rotation: Maximum 90 days
- Access control: Role-based access
- Audit logging: All secret access logged
- Encryption: KMS-encrypted storage

## ISO27001
- Controls: A.9.4.1, A.10.1.1, A.12.4.1
- Risk assessment: Quarterly
- Incident response: Documented procedures
- Business continuity: DR strategy

## PCI-DSS
- Requirements: 3.4, 3.5, 8.2, 8.3
- Key rotation: 90 days maximum
- Strong cryptography: AES-256 minimum
- MFA: Required for all access

## HIPAA
- Safeguards: Technical, Physical, Administrative
- PHI protection: Encryption required
- Audit trails: 7-year retention
- BAA: Required for vendors
EOF
```

### 2. Configure Compliance Policies

```bash
# Validate compliance configuration
secretzero validate -f Secretfile.yml

# Expected output:
# ✓ Configuration is valid
# ✓ Compliance framework: soc2
# ✓ All secrets have rotation_period defined
# ✓ All targets use encrypted storage
# ✓ All secrets have required tags
# ✓ Audit logging enabled
```

### 3. Run Compliance Checks

```bash
# Check all compliance policies
secretzero policy -f Secretfile.yml

# Expected output:
# ✓ Policy: soc2_rotation (PASS)
#   - All secrets have rotation_period ≤ 90 days
#   - 5 secrets compliant
# 
# ✓ Policy: soc2_access_control (PASS)
#   - All targets use encrypted storage
#   - No file targets in production
# 
# ✓ Policy: soc2_audit (PASS)
#   - All secrets have required tags
#   - Owner, DataClassification, Environment present
# 
# ✓ Overall: 3/3 policies PASSED

# Fail on warnings (strict mode)
secretzero policy --fail-on-warning

# Generate compliance report
secretzero policy --format json > compliance-report.json
```

### 4. Generate Audit Trail

```bash
# Sync secrets with audit trail
secretzero sync

# View audit trail in lockfile
cat .gitsecrets.lock | jq '.audit_trail'

# Expected output:
# {
#   "database_password": {
#     "created_at": "2024-01-15T10:30:00Z",
#     "created_by": "security-team",
#     "last_rotated": "2024-01-15T10:30:00Z",
#     "rotation_count": 0,
#     "next_rotation": "2024-04-15T10:30:00Z",
#     "compliance": ["soc2"],
#     "targets": [
#       {
#         "provider": "aws",
#         "type": "secrets_manager",
#         "name": "production/myapp/database/password",
#         "encrypted": true
#       }
#     ]
#   }
# }
```

### 5. Set Up Rotation Monitoring

```bash
# Check rotation status
secretzero rotate --dry-run

# Expected output:
# Rotation Status:
# ✓ database_password: Up to date (45 days until rotation)
# ✓ api_key: Up to date (30 days until rotation)
# ⚠ service_account: Due for rotation in 5 days
# ✗ admin_password: OVERDUE by 15 days

# Rotate overdue secrets
secretzero rotate

# Schedule automated rotation check
# Add to cron or CI/CD pipeline
0 0 * * * cd /path/to/project && secretzero rotate
```

### 6. Generate Compliance Reports

```bash
# Generate SOC2 compliance report
secretzero compliance-report --framework soc2 --output soc2-report.pdf

# Generate ISO27001 compliance report
secretzero compliance-report --framework iso27001 --output iso27001-report.pdf

# Generate audit evidence for specific date range
secretzero audit --from 2024-01-01 --to 2024-01-31 --output january-audit.json
```

## Using Secrets with Compliance

### SOC2 Audit Trail Example

```python
import boto3
import json
from datetime import datetime

def get_secret_with_audit(secret_name, user_id, purpose):
    """Retrieve secret with audit logging for SOC2 compliance"""
    
    # Create AWS clients
    secrets_client = boto3.client('secretsmanager')
    cloudtrail_client = boto3.client('cloudtrail')
    
    # Log access attempt
    print(f"[AUDIT] {datetime.utcnow().isoformat()}Z - User: {user_id} - Secret: {secret_name} - Purpose: {purpose}")
    
    try:
        # Retrieve secret
        response = secrets_client.get_secret_value(SecretId=secret_name)
        
        # Log successful access
        audit_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "user_id": user_id,
            "secret_name": secret_name,
            "action": "secret_accessed",
            "purpose": purpose,
            "status": "success",
            "source_ip": get_source_ip(),
            "compliance": "soc2"
        }
        log_audit_entry(audit_entry)
        
        return response['SecretString']
    
    except Exception as e:
        # Log failed access
        audit_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "user_id": user_id,
            "secret_name": secret_name,
            "action": "secret_access_failed",
            "purpose": purpose,
            "status": "failed",
            "error": str(e),
            "compliance": "soc2"
        }
        log_audit_entry(audit_entry)
        raise

def log_audit_entry(entry):
    """Log audit entry to CloudWatch Logs for SOC2 compliance"""
    logs_client = boto3.client('logs')
    
    logs_client.put_log_events(
        logGroupName='/compliance/secret-access',
        logStreamName='soc2-audit',
        logEvents=[
            {
                'timestamp': int(datetime.utcnow().timestamp() * 1000),
                'message': json.dumps(entry)
            }
        ]
    )

# Usage
db_password = get_secret_with_audit(
    secret_name='production/myapp/database/password',
    user_id='john.doe@example.com',
    purpose='database_connection'
)
```

### PCI-DSS Cardholder Data Protection

```python
import boto3
import hashlib
import hmac
from cryptography.fernet import Fernet

def handle_payment_with_pci_compliance(card_data):
    """Handle payment processing with PCI-DSS compliance"""
    
    # Get encryption key from AWS Secrets Manager
    secrets_client = boto3.client('secretsmanager')
    
    # Retrieve data encryption key (PCI-DSS Requirement 3.4)
    response = secrets_client.get_secret_value(
        SecretId='production/payment-processor/database-encryption-key'
    )
    encryption_key = response['SecretString']
    
    # Encrypt cardholder data before storage (PCI-DSS Requirement 3.4)
    fernet = Fernet(encryption_key.encode())
    encrypted_card = fernet.encrypt(card_data.encode())
    
    # Get payment gateway credentials (PCI-DSS Requirement 8.2)
    gateway_response = secrets_client.get_secret_value(
        SecretId='production/payment-processor/payment-gateway-key'
    )
    gateway_key = gateway_response['SecretString']
    
    # Process payment with encrypted connection (PCI-DSS Requirement 4.1)
    payment_result = process_payment_encrypted(encrypted_card, gateway_key)
    
    # Log access with timestamp (PCI-DSS Requirement 10.2)
    log_pci_access(
        action='payment_processed',
        user='payment-service',
        timestamp=datetime.utcnow().isoformat() + 'Z',
        result='success'
    )
    
    return payment_result

def log_pci_access(action, user, timestamp, result):
    """Log access for PCI-DSS audit trail (Requirement 10)"""
    logs_client = boto3.client('logs')
    
    log_entry = {
        'timestamp': timestamp,
        'action': action,
        'user': user,
        'result': result,
        'compliance': 'pci-dss',
        'requirement': '10.2'
    }
    
    logs_client.put_log_events(
        logGroupName='/compliance/pci-dss',
        logStreamName='payment-access',
        logEvents=[{
            'timestamp': int(datetime.utcnow().timestamp() * 1000),
            'message': json.dumps(log_entry)
        }]
    )
```

## Advanced Scenarios

### Multi-Framework Compliance

Support multiple compliance frameworks simultaneously:

```yaml
version: '1.0'

metadata:
  project: multi-compliance-app
  owner: compliance-team
  compliance:
    - soc2
    - iso27001
    - pci-dss
    - hipaa
  classification: highly-sensitive

providers:
  aws:
    kind: aws
    auth:
      kind: ambient

policies:
  # Strictest rotation policy (satisfies all frameworks)
  multi_compliance_rotation:
    kind: rotation
    require_rotation_period: true
    max_age: 60d  # Strictest: PCI-DSS for cardholder data
    severity: error
    enabled: true
    metadata:
      soc2: CC6.1
      iso27001: A.9.2.4
      pci_dss: "8.2.4"
      hipaa: "164.312(a)"
  
  # Combined encryption requirements
  multi_compliance_encryption:
    kind: encryption
    require_kms: true
    require_encryption_at_rest: true
    require_encryption_in_transit: true
    min_key_length: 256
    approved_algorithms:
      - AES-256-GCM
    severity: error
    enabled: true
    metadata:
      soc2: CC6.7
      iso27001: A.10.1.1
      pci_dss: "3.4"
      hipaa: "164.312(a)(2)(iv)"

secrets:
  - name: critical_system_password
    kind: random_password
    rotation_period: 60d  # Meets all frameworks
    config:
      length: 32
      special: true
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: production/critical/password
          description: Multi-compliance critical password
          kms_key_id: arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012
          tags:
            Compliance: soc2,iso27001,pci-dss,hipaa
            SOC2Control: CC6.1
            ISO27001Control: A.9.2.4
            PCIDSSRequirement: "8.2.4"
            HIPAASafeguard: "164.312(a)"
            RotationPeriod: 60d
```

### Automated Compliance Monitoring

Set up continuous compliance monitoring:

```yaml
# .github/workflows/compliance-check.yml
name: Compliance Monitoring

on:
  schedule:
    - cron: '0 0 * * *'  # Daily
  push:
    paths:
      - 'Secretfile.yml'
  workflow_dispatch:

jobs:
  compliance-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install SecretZero
        run: pip install secretzero
      
      - name: Validate Configuration
        run: secretzero validate -f Secretfile.yml
      
      - name: Run Policy Checks
        run: |
          secretzero policy -f Secretfile.yml --fail-on-warning --format json > policy-results.json
      
      - name: Check Rotation Status
        run: |
          secretzero rotate --dry-run --format json > rotation-status.json
      
      - name: Generate Compliance Report
        run: |
          secretzero compliance-report --framework soc2 --output soc2-report.pdf
          secretzero compliance-report --framework iso27001 --output iso27001-report.pdf
      
      - name: Upload Reports
        uses: actions/upload-artifact@v3
        with:
          name: compliance-reports
          path: |
            policy-results.json
            rotation-status.json
            soc2-report.pdf
            iso27001-report.pdf
      
      - name: Notify Compliance Team
        if: failure()
        run: |
          # Send notification to compliance team
          echo "Compliance check failed. Alerting team..."
          # Integration with Slack, email, or ticketing system
```

### Compliance Evidence Collection

Automate evidence collection for auditors:

```bash
#!/bin/bash
# collect-compliance-evidence.sh

set -e

EVIDENCE_DIR="compliance-evidence-$(date +%Y-%m-%d)"
mkdir -p "$EVIDENCE_DIR"

echo "Collecting compliance evidence..."

# 1. Current secret inventory
echo "1. Collecting secret inventory..."
secretzero list --format json > "$EVIDENCE_DIR/secret-inventory.json"

# 2. Rotation status report
echo "2. Collecting rotation status..."
secretzero rotate --dry-run --format json > "$EVIDENCE_DIR/rotation-status.json"

# 3. Policy compliance report
echo "3. Running policy checks..."
secretzero policy --format json > "$EVIDENCE_DIR/policy-compliance.json"

# 4. Audit trail for last 90 days
echo "4. Collecting audit trail..."
secretzero audit \
  --from "$(date -d '90 days ago' +%Y-%m-%d)" \
  --to "$(date +%Y-%m-%d)" \
  --output "$EVIDENCE_DIR/audit-trail-90days.json"

# 5. AWS CloudTrail logs (secret access)
echo "5. Collecting AWS CloudTrail logs..."
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=ResourceType,AttributeValue=AWS::SecretsManager::Secret \
  --start-time "$(date -d '90 days ago' +%Y-%m-%d)" \
  --max-results 1000 \
  > "$EVIDENCE_DIR/cloudtrail-secret-access.json"

# 6. Azure Activity Logs (Key Vault)
echo "6. Collecting Azure activity logs..."
az monitor activity-log list \
  --resource-group production \
  --start-time "$(date -d '90 days ago' +%Y-%m-%d)" \
  --offset 90d \
  --query "[?contains(resourceType, 'Microsoft.KeyVault')]" \
  > "$EVIDENCE_DIR/azure-keyvault-activity.json"

# 7. Generate compliance reports
echo "7. Generating compliance reports..."
secretzero compliance-report --framework soc2 --output "$EVIDENCE_DIR/soc2-report.pdf"
secretzero compliance-report --framework iso27001 --output "$EVIDENCE_DIR/iso27001-report.pdf"

# 8. Configuration snapshot
echo "8. Capturing configuration..."
cp Secretfile.yml "$EVIDENCE_DIR/"
cp .gitsecrets.lock "$EVIDENCE_DIR/"

# 9. RBAC policies
echo "9. Collecting RBAC policies..."
aws iam get-policy --policy-arn "arn:aws:iam::123456789012:policy/SecretZeroAccess" \
  > "$EVIDENCE_DIR/aws-iam-policy.json"

# 10. Create evidence package
echo "10. Creating evidence package..."
tar -czf "$EVIDENCE_DIR.tar.gz" "$EVIDENCE_DIR"

echo "Evidence collection complete: $EVIDENCE_DIR.tar.gz"
```

## Best Practices

1. **Implement Defense in Depth** - Use multiple layers of security controls: encryption at rest, encryption in transit, access controls, audit logging, and monitoring. Don't rely on a single control - combine provider-native features (AWS KMS, Azure RBAC, Vault policies) with SecretZero policies for comprehensive protection.

2. **Document Everything** - Maintain comprehensive documentation of secret management procedures, rotation policies, incident response plans, and business continuity procedures. Include runbooks for common scenarios, escalation paths, and contact information. Documentation is critical for audit success.

3. **Automate Compliance Checks** - Run compliance policy checks in CI/CD pipelines before deploying secret changes. Use `secretzero policy --fail-on-warning` to prevent non-compliant configurations from reaching production. Schedule daily compliance scans and alert on violations.

4. **Maintain Audit Trails** - Enable comprehensive logging at all levels: SecretZero lockfile, AWS CloudTrail, Azure Activity Logs, Vault audit logs, and application logs. Retain logs for required periods (7 years for HIPAA, 6+ years for SOC2). Use immutable storage for audit logs.

5. **Separate Environments** - Use separate secret storage per environment (dev, staging, production) with strict access controls. Never share secrets between environments. Use different AWS accounts, Azure subscriptions, or Vault namespaces for each environment. Implement network isolation.

6. **Regular Rotation Testing** - Test secret rotation procedures regularly (at least quarterly) to ensure they work during actual rotation events. Include rotation testing in disaster recovery drills. Document rotation procedures and maintain runbooks for emergency rotation.

7. **Implement Least Privilege** - Grant minimum necessary permissions for secret access. Use role-based access control (RBAC) with specific secret paths. Regularly review and audit access permissions. Remove access promptly when no longer needed. Require approval for privilege escalation.

8. **Monitor and Alert** - Set up real-time alerts for compliance violations: rotation overdue, unauthorized access attempts, policy violations, and encryption failures. Integrate with SIEM systems for correlation. Define response procedures and escalation paths for each alert type.

9. **Third-Party Vendor Management** - Require Business Associate Agreements (BAA) for HIPAA, service organization controls for SOC2, and documented security controls for all vendors. Audit vendor compliance regularly. Maintain vendor risk assessments and review them annually.

10. **Incident Response Planning** - Develop and document incident response procedures for secret compromise: immediate rotation, access revocation, impact assessment, notification requirements, and remediation steps. Conduct tabletop exercises annually. Maintain 24/7 contact information for security team.

## Troubleshooting

### Policy Validation Failed

**Problem**: `Error: Policy validation failed - rotation_period exceeds max_age`

**Solutions**:

```bash
# View policy details
secretzero policy --verbose

# Check which secrets violate policies
secretzero policy --show-violations

# Expected output:
# ✗ Policy: compliance_rotation (FAILED)
#   Violations:
#   - Secret 'old_api_key': rotation_period=120d exceeds max_age=90d
#   - Secret 'legacy_password': no rotation_period defined
# 
# Fix: Update Secretfile.yml with compliant values

# Update secret configuration
# Change: rotation_period: 120d
# To: rotation_period: 90d

# Re-validate
secretzero policy
```

### Missing Required Tags

**Problem**: `Error: Secret missing required compliance tags`

**Solutions**:

```bash
# Check tag requirements
secretzero policy --verbose

# Add required tags to all secrets
# In Secretfile.yml:
targets:
  - provider: aws
    kind: secrets_manager
    config:
      name: production/myapp/secret
      tags:
        Owner: team-name
        DataClassification: sensitive
        Environment: production
        Application: myapp
        Compliance: soc2

# Validate tags
secretzero validate
```

### Rotation Overdue

**Problem**: `Warning: 5 secrets overdue for rotation`

**Solutions**:

```bash
# Check rotation status
secretzero rotate --dry-run

# Expected output:
# Rotation Status:
# ✗ database_password: OVERDUE by 15 days (last rotated: 2023-10-01)
# ✗ api_key: OVERDUE by 7 days (last rotated: 2023-10-24)
# ⚠ service_account: Due in 2 days (last rotated: 2023-10-01)

# Rotate overdue secrets
secretzero rotate

# For specific secret
secretzero rotate --secret database_password

# Force rotation (even if not due)
secretzero rotate --force --secret api_key

# Update applications with new secrets
# Verify applications work with new secrets
# Document rotation in audit log
```

### Audit Trail Missing

**Problem**: `Error: No audit trail found for secret access`

**Solutions**:

```bash
# Enable audit logging in AWS
aws secretsmanager update-secret \
  --secret-id production/myapp/secret \
  --description "Audit logging enabled" \
  --tags Key=AuditLogEnabled,Value=true

# Verify CloudTrail is enabled
aws cloudtrail describe-trails
aws cloudtrail get-trail-status --name mytrail

# Check CloudWatch Logs
aws logs describe-log-groups --log-group-name-prefix /compliance

# Query audit events
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=ResourceName,AttributeValue=production/myapp/secret \
  --max-results 50

# Export audit trail
secretzero audit --from 2024-01-01 --to 2024-12-31 --output audit-2024.json
```

### Encryption Key Access Denied

**Problem**: `Error: Access denied to KMS key`

**Solutions**:

```bash
# Check KMS key policy
aws kms get-key-policy \
  --key-id 12345678-1234-1234-1234-123456789012 \
  --policy-name default \
  --output text

# Verify IAM permissions
aws iam get-policy-version \
  --policy-arn arn:aws:iam::123456789012:policy/SecretZeroAccess \
  --version-id v1

# Test KMS permissions
aws kms describe-key \
  --key-id 12345678-1234-1234-1234-123456789012

# Add required KMS permissions to IAM policy
{
  "Effect": "Allow",
  "Action": [
    "kms:Decrypt",
    "kms:Encrypt",
    "kms:GenerateDataKey",
    "kms:DescribeKey"
  ],
  "Resource": "arn:aws:kms:us-east-1:123456789012:key/*"
}

# Update IAM policy
aws iam create-policy-version \
  --policy-arn arn:aws:iam::123456789012:policy/SecretZeroAccess \
  --policy-document file://updated-policy.json \
  --set-as-default
```

### Compliance Report Generation Failed

**Problem**: `Error: Failed to generate compliance report`

**Solutions**:

```bash
# Verify all secrets have required metadata
secretzero validate

# Check for missing compliance tags
secretzero policy --show-violations

# Ensure audit trail exists
cat .gitsecrets.lock | jq '.audit_trail'

# Generate report with verbose logging
secretzero compliance-report --framework soc2 --verbose

# Check for missing dependencies
pip install secretzero[compliance,reporting]

# Generate simpler report format
secretzero compliance-report --framework soc2 --format json > report.json

# Convert JSON to PDF manually
# Use tools like wkhtmltopdf or pandoc
```

### Multi-Framework Conflicts

**Problem**: Different compliance frameworks have conflicting requirements

**Solutions**:

```bash
# Use strictest requirements across all frameworks
# Example: PCI-DSS requires 90-day rotation, SOC2 recommends 90 days
# Solution: Use 60-day rotation to exceed all requirements

# In Secretfile.yml:
policies:
  strictest_rotation:
    kind: rotation
    max_age: 60d  # More frequent than any framework requires
    severity: error

  strictest_encryption:
    kind: encryption
    min_key_length: 256  # Highest security level
    approved_algorithms:
      - AES-256-GCM  # Strongest algorithm
    severity: error

# Document why you exceed requirements
# In metadata:
metadata:
  compliance_approach: strictest
  rationale: |
    We use 60-day rotation even though frameworks require 90 days
    to demonstrate security-first approach and reduce risk window.
```

### Third-Party Audit Evidence

**Problem**: Auditor requests evidence of secret rotation

**Solutions**:

```bash
# Generate comprehensive evidence package
./collect-compliance-evidence.sh

# Export specific secret history
secretzero audit --secret database_password --format json > database_password_history.json

# Show rotation timeline
secretzero rotate --dry-run --secret database_password --show-history

# Generate rotation certificate
secretzero certificate --secret database_password --output rotation-cert.pdf

# Include in evidence:
# 1. Secretfile.yml configuration
# 2. .gitsecrets.lock with timestamps
# 3. CloudTrail logs showing rotation events
# 4. Policy compliance reports
# 5. Rotation status reports
# 6. Access logs for the secret
# 7. Incident response procedures
# 8. Documentation of rotation process
```

## Complete Example

Full production compliance-ready configuration:

```yaml
version: '1.0'

metadata:
  project: production-compliance-app
  owner: compliance-team
  created_at: "2024-01-01T00:00:00Z"
  compliance:
    - soc2
    - iso27001
    - pci-dss
  classification: highly-sensitive
  audit_requirements:
    log_retention_days: 2555  # 7 years
    rotation_evidence: required
    access_logging: required
    encryption: required

variables:
  environment: production
  app_name: secure-app
  aws_region: us-east-1

providers:
  aws:
    kind: aws
    auth:
      kind: ambient
      config:
        region: ${aws_region}

policies:
  # Combined rotation policy (strictest requirements)
  compliance_rotation:
    kind: rotation
    require_rotation_period: true
    max_age: 60d
    warn_days_before: 14
    severity: error
    enabled: true
    metadata:
      frameworks: soc2,iso27001,pci-dss
      requirement: "Secrets must rotate at least every 60 days"
  
  # Encryption requirements
  compliance_encryption:
    kind: encryption
    require_kms: true
    require_encryption_at_rest: true
    require_encryption_in_transit: true
    min_key_length: 256
    approved_algorithms:
      - AES-256-GCM
    severity: error
    enabled: true
    metadata:
      frameworks: soc2,iso27001,pci-dss
      requirement: "All secrets must use strong encryption"
  
  # Access control requirements
  compliance_access:
    kind: access
    allowed_targets:
      - secrets_manager
      - key_vault
      - vault_kv
    denied_targets:
      - file
    require_mfa: true
    require_audit_logs: true
    severity: error
    enabled: true
    metadata:
      frameworks: soc2,iso27001
      requirement: "Access control and audit logging required"
  
  # Tagging requirements
  compliance_tagging:
    kind: audit
    require_tags: true
    required_tags:
      - Owner
      - DataClassification
      - Environment
      - Application
      - Compliance
    severity: error
    enabled: true
    metadata:
      frameworks: soc2,iso27001
      requirement: "All secrets must be properly tagged"

secrets:
  # 1. Database credentials
  - name: database_master_password
    kind: random_password
    rotation_period: 60d
    config:
      length: 32
      special: true
      exclude_characters: '"@/\`'
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: ${environment}/${app_name}/database/master-password
          description: Database master password (multi-compliance)
          kms_key_id: arn:aws:kms:${aws_region}:123456789012:key/12345678-1234-1234-1234-123456789012
          replica_regions:
            - us-west-2
          tags:
            Owner: database-team
            DataClassification: highly-sensitive
            Environment: ${environment}
            Application: ${app_name}
            Compliance: soc2,iso27001,pci-dss
            SOC2Control: CC6.1
            ISO27001Control: A.9.2.4
            PCIDSSRequirement: "8.2.4"
            RotationPeriod: 60d
            AuditLogEnabled: "true"

  # 2. API credentials
  - name: api_credentials
    kind: templates.api_creds_compliance
    rotation_period: 60d

  # 3. Encryption keys
  - name: application_encryption_key
    kind: random_string
    one_time: true
    rotation_period: 365d
    config:
      length: 32
      charset: base64
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: ${environment}/${app_name}/encryption-key
          description: Application encryption key (multi-compliance)
          kms_key_id: arn:aws:kms:${aws_region}:123456789012:key/12345678-1234-1234-1234-123456789012
          tags:
            Owner: security-team
            DataClassification: encryption-key
            Environment: ${environment}
            Application: ${app_name}
            Compliance: soc2,iso27001,pci-dss
            KeyType: data-encryption-key
            BackupRequired: "true"

  # 4. Service account
  - name: service_account
    kind: templates.service_account_compliance
    rotation_period: 90d

templates:
  api_creds_compliance:
    description: API credentials with compliance controls
    fields:
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
            default: "{{ timestamp }}"
      compliance_version:
        generator:
          kind: static
          config:
            default: "2024.1"
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: ${environment}/${app_name}/api-credentials
          description: API credentials (multi-compliance)
          kms_key_id: arn:aws:kms:${aws_region}:123456789012:key/12345678-1234-1234-1234-123456789012
          tags:
            Owner: api-team
            DataClassification: sensitive
            Environment: ${environment}
            Application: ${app_name}
            Compliance: soc2,iso27001

  service_account_compliance:
    description: Service account with full compliance
    fields:
      account_id:
        generator:
          kind: static
          config:
            default: svc_${app_name}_${environment}
      password:
        generator:
          kind: random_password
          config:
            length: 32
            special: true
      mfa_enabled:
        generator:
          kind: static
          config:
            default: "true"
      created_at:
        generator:
          kind: static
          config:
            default: "{{ timestamp }}"
      compliance_frameworks:
        generator:
          kind: static
          config:
            default: "soc2,iso27001,pci-dss"
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: ${environment}/${app_name}/service-account
          description: Service account (multi-compliance)
          kms_key_id: arn:aws:kms:${aws_region}:123456789012:key/12345678-1234-1234-1234-123456789012
          tags:
            Owner: automation-team
            DataClassification: sensitive
            Environment: ${environment}
            Application: ${app_name}
            Compliance: soc2,iso27001,pci-dss
            MFARequired: "true"
```

Deploy with compliance validation:

```bash
# 1. Validate configuration
secretzero validate

# 2. Run all compliance checks
secretzero policy --fail-on-warning

# 3. Preview changes
secretzero sync --dry-run

# 4. Deploy secrets
secretzero sync

# 5. Verify compliance
secretzero policy
secretzero rotate --dry-run

# 6. Generate compliance reports
secretzero compliance-report --framework soc2 --output soc2-report.pdf
secretzero compliance-report --framework iso27001 --output iso27001-report.pdf

# 7. Collect audit evidence
./collect-compliance-evidence.sh

# 8. Schedule automated monitoring
# Add to cron:
# 0 0 * * * cd /path/to/project && secretzero policy --fail-on-warning
# 0 0 * * 0 cd /path/to/project && secretzero rotate
```

## Next Steps

- **[Multi-Cloud Setup](multi-cloud.md)** - Extend compliance across cloud providers
- **[Kubernetes Integration](kubernetes.md)** - Compliance in Kubernetes environments
- **[Migration Guide](migration.md)** - Migrate to compliance-ready configuration
- **[SOC2 Resources](https://www.aicpa.org/soc)** - Official SOC2 documentation
- **[ISO27001 Standards](https://www.iso.org/isoiec-27001-information-security.html)** - ISO27001 requirements
- **[PCI-DSS](https://www.pcisecuritystandards.org/)** - PCI-DSS standards
- **[HIPAA Guidance](https://www.hhs.gov/hipaa/)** - HIPAA compliance resources
