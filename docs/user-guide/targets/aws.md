# AWS Targets

SecretZero supports two AWS secret management services: **AWS Secrets Manager** and **AWS Systems Manager Parameter Store**. Both provide secure, scalable secret storage with native AWS integration.

## Overview

AWS targets allow you to:

- Store secrets in AWS cloud infrastructure
- Leverage AWS KMS for encryption
- Integrate with IAM for fine-grained access control
- Enable automatic rotation with AWS Lambda
- Audit access with AWS CloudTrail
- Scale globally with multi-region support

## Prerequisites

### Installation

AWS support requires the boto3 library:

```bash
# Install with AWS support
pip install secretzero[aws]

# Or install boto3 directly
pip install boto3
```

### Authentication

AWS targets use the standard AWS credential chain:

1. Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
2. AWS credentials file (`~/.aws/credentials`)
3. IAM instance profile (EC2, ECS, Lambda)
4. IAM role (EKS, Fargate)

```yaml
providers:
  aws:
    kind: aws
    auth:
      kind: ambient  # Uses AWS credential chain
      region: us-east-1
```

### Required IAM Permissions

#### For Secrets Manager:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:CreateSecret",
        "secretsmanager:UpdateSecret",
        "secretsmanager:GetSecretValue",
        "secretsmanager:DeleteSecret",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:*:*:secret:*"
    }
  ]
}
```

#### For Parameter Store:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ssm:PutParameter",
        "ssm:GetParameter",
        "ssm:DeleteParameter",
        "ssm:DescribeParameters"
      ],
      "Resource": "arn:aws:ssm:*:*:parameter/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "kms:Decrypt",
        "kms:Encrypt"
      ],
      "Resource": "arn:aws:kms:*:*:key/*"
    }
  ]
}
```

## AWS Secrets Manager Target

AWS Secrets Manager is designed for secrets like database credentials, API keys, and OAuth tokens. It supports automatic rotation and integrates seamlessly with AWS services.

### Configuration

```yaml
targets:
  - provider: aws
    kind: secrets_manager
    config:
      name: string           # Secret name or ARN (required)
      description: string    # Secret description (optional)
      kms_key_id: string    # KMS key ARN/ID (optional)
```

### Configuration Options

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `name` | string | Yes | - | Secret name or ARN |
| `description` | string | No | `"Managed by SecretZero: {secret_name}"` | Human-readable description |
| `kms_key_id` | string | No | AWS managed key | KMS key ARN or alias for encryption |

### Basic Example

```yaml
version: '1.0'

providers:
  aws:
    kind: aws
    auth:
      kind: ambient
      region: us-east-1

secrets:
  - name: database_password
    kind: random_password
    config:
      length: 32
      special: true
      exclude_characters: '"@/\'
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: myapp/prod/db/password
          description: Production database password
```

### Advanced Example with KMS

```yaml
secrets:
  - name: api_key
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: myapp/api-key
          description: External API key for service XYZ
          kms_key_id: arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012
```

### Multi-Region Secrets

```yaml
variables:
  regions:
    - us-east-1
    - us-west-2
    - eu-west-1

secrets:
  - name: global_api_key
    kind: random_string
    config:
      length: 32
    targets:
      # Deploy to multiple regions
      - provider: aws_us_east
        kind: secrets_manager
        config:
          name: global/api-key

      - provider: aws_us_west
        kind: secrets_manager
        config:
          name: global/api-key

      - provider: aws_eu_west
        kind: secrets_manager
        config:
          name: global/api-key

providers:
  aws_us_east:
    kind: aws
    auth:
      kind: ambient
      region: us-east-1

  aws_us_west:
    kind: aws
    auth:
      kind: ambient
      region: us-west-2

  aws_eu_west:
    kind: aws
    auth:
      kind: ambient
      region: eu-west-1
```

### Structured Secrets

Store complex credentials as JSON:

```yaml
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
            default: db.example.com
      port:
        generator:
          kind: static
          config:
            default: "5432"
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
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: myapp/database/credentials
```

**Retrieved as:**
```json
{
  "host": "db.example.com",
  "port": "5432",
  "username": "app_user",
  "password": "randompassword123456789012345678901"
}
```

## AWS Systems Manager Parameter Store Target

Parameter Store is ideal for configuration data, feature flags, and secrets that don't require automatic rotation. It's cost-effective and integrates with AWS Systems Manager.

### Configuration

```yaml
targets:
  - provider: aws
    kind: ssm_parameter
    config:
      name: string         # Parameter name/path (required)
      type: string         # Parameter type (optional)
      overwrite: boolean   # Overwrite existing (optional)
      description: string  # Description (optional)
      tier: string        # Parameter tier (optional)
```

### Configuration Options

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `name` | string | Yes | - | Parameter name/path (e.g., `/myapp/db/password`) |
| `type` | string | No | `SecureString` | Parameter type: `String`, `SecureString`, `StringList` |
| `overwrite` | boolean | No | `true` | Whether to overwrite existing parameters |
| `description` | string | No | `"Managed by SecretZero: {secret_name}"` | Parameter description |
| `tier` | string | No | `Standard` | Parameter tier: `Standard`, `Advanced`, `Intelligent-Tiering` |

### Parameter Types

- **`String`** - Plain text parameter (not recommended for secrets)
- **`SecureString`** - Encrypted with KMS (recommended for secrets)
- **`StringList`** - Comma-separated values

### Basic Example

```yaml
version: '1.0'

providers:
  aws:
    kind: aws
    auth:
      kind: ambient
      region: us-east-1

secrets:
  - name: app_secret_key
    kind: random_string
    config:
      length: 64
      charset: base64
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /myapp/prod/secret-key
          type: SecureString
          overwrite: true
          tier: Standard
```

### Hierarchical Organization

Use paths to organize parameters:

```yaml
secrets:
  # Database parameters
  - name: db_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /myapp/prod/database/password
          type: SecureString

  - name: db_host
    kind: static
    config:
      value: prod-db.example.com
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /myapp/prod/database/host
          type: String

  # API parameters
  - name: api_key
    kind: random_string
    config:
      length: 32
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /myapp/prod/api/key
          type: SecureString

  # Application parameters
  - name: app_debug
    kind: static
    config:
      value: "false"
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /myapp/prod/app/debug
          type: String
```

### Advanced Tier Usage

Use Advanced tier for larger values:

```yaml
secrets:
  - name: large_certificate
    kind: static
    config:
      value: |
        -----BEGIN CERTIFICATE-----
        MIIEpQIBAAKCAQEA...
        (large certificate content)
        -----END CERTIFICATE-----
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /myapp/certificates/app-cert
          type: SecureString
          tier: Advanced  # Supports up to 8KB
```

**Tier Limits:**
- **Standard**: 4 KB, free
- **Advanced**: 8 KB, charges apply
- **Intelligent-Tiering**: Automatically switches based on size

### Environment-Based Parameters

```yaml
variables:
  environment: prod
  app_name: myapp

secrets:
  - name: secret_key
    kind: random_string
    config:
      length: 64
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /{{var.app_name}}/{{var.environment}}/secret-key
          type: SecureString
          description: "Secret key for {{var.app_name}} {{var.environment}}"
```

## Comparison: Secrets Manager vs. Parameter Store

| Feature | Secrets Manager | Parameter Store (SecureString) |
|---------|----------------|-------------------------------|
| **Encryption** | KMS (required) | KMS (optional) |
| **Automatic Rotation** | Yes (built-in) | No (manual via Lambda) |
| **Cross-Region Replication** | Yes | No |
| **Versioning** | Yes (automatic) | Yes (manual) |
| **Max Size** | 65,536 bytes | 4 KB (Standard), 8 KB (Advanced) |
| **Cost** | $0.40/secret/month + API calls | Free (Standard), $0.05/param/month (Advanced) |
| **Use Case** | Sensitive credentials, rotating secrets | Configuration, non-rotating secrets |
| **AWS Service Integration** | RDS, DocumentDB, Redshift | EC2, ECS, Lambda, Systems Manager |

### When to Use Each

**Use Secrets Manager when:**
- Secrets require automatic rotation
- Managing database credentials
- Need cross-region replication
- Want built-in integration with RDS/DocumentDB
- Compliance requires secret rotation

**Use Parameter Store when:**
- Storing configuration values
- Managing application settings
- Need hierarchical organization
- Cost is a primary concern
- Secrets don't require rotation

## Complete Examples

### Multi-Tier Application

```yaml
version: '1.0'

variables:
  environment: production
  app_name: webapp

providers:
  aws:
    kind: aws
    auth:
      kind: ambient
      region: us-east-1

secrets:
  # Critical secrets → Secrets Manager
  - name: database_master_password
    kind: random_password
    config:
      length: 32
      special: true
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: "{{var.app_name}}/{{var.environment}}/db/master-password"
          description: Master database password

  - name: jwt_signing_key
    kind: random_string
    config:
      length: 64
      charset: base64
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: "{{var.app_name}}/{{var.environment}}/jwt/signing-key"

  # Configuration → Parameter Store
  - name: db_connection_pool_size
    kind: static
    config:
      value: "20"
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /{{var.app_name}}/{{var.environment}}/db/pool-size
          type: String

  - name: log_level
    kind: static
    config:
      value: INFO
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /{{var.app_name}}/{{var.environment}}/logging/level
          type: String

  - name: feature_flag_new_ui
    kind: static
    config:
      value: "true"
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /{{var.app_name}}/{{var.environment}}/features/new-ui
          type: String
```

### Microservices Architecture

```yaml
version: '1.0'

providers:
  aws:
    kind: aws
    auth:
      kind: ambient
      region: us-east-1

secrets:
  # Shared secrets
  - name: shared_encryption_key
    kind: random_string
    config:
      length: 64
      charset: hex
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: shared/encryption-key

  # Service-specific secrets
  - name: auth_service_db_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /services/auth/db/password
          type: SecureString

  - name: payment_service_api_key
    kind: random_string
    config:
      length: 32
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: services/payment/api-key

  - name: notification_service_smtp_password
    kind: random_password
    config:
      length: 24
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /services/notification/smtp/password
          type: SecureString
```

## Best Practices

### 1. Use Consistent Naming Conventions

```yaml
# Good: hierarchical structure
/myapp/prod/database/password
/myapp/prod/api/key
/myapp/staging/database/password

# Avoid: inconsistent naming
myapp-db-pass
MYAPP_API_KEY
app.secret
```

### 2. Leverage Tags for Organization

```yaml
# Note: Tagging requires AWS API calls beyond SecretZero
# Use external tools or scripts to add tags:

# AWS CLI example:
# aws secretsmanager tag-resource \
#   --secret-id myapp/api-key \
#   --tags Key=Environment,Value=production Key=Owner,Value=platform-team
```

### 3. Enable CloudTrail Logging

Monitor secret access:

```bash
# Enable CloudTrail for Secrets Manager
aws cloudtrail create-trail \
  --name secrets-audit \
  --s3-bucket-name my-audit-bucket

# Enable logging
aws cloudtrail start-logging --name secrets-audit
```

### 4. Use Least Privilege IAM

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:123456789012:secret:myapp/prod/*"
    }
  ]
}
```

### 5. Implement Secret Rotation

```yaml
# Generate rotatable secrets
secrets:
  - name: db_password
    kind: random_password
    rotation_period: 90d  # Rotate every 90 days
    config:
      length: 32
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: myapp/db/password
```

## Troubleshooting

### Access Denied Errors

**Problem:** `AccessDeniedException` when storing/retrieving secrets.

**Solutions:**
1. Verify IAM permissions
   ```bash
   aws secretsmanager get-secret-value --secret-id test-secret
   ```
2. Check resource-based policies
3. Ensure KMS key permissions if using custom keys

### Secret Already Exists

**Problem:** `ResourceExistsException` when creating secrets.

**Solution:** SecretZero automatically updates existing secrets. If you see this error:
1. Verify the secret name is correct
2. Check if another process is creating secrets
3. Use `overwrite: true` for Parameter Store

### KMS Key Not Found

**Problem:** `KMSKeyNotFoundException` when using custom KMS keys.

**Solutions:**
1. Verify KMS key ARN/alias is correct
2. Ensure KMS key is in the same region
3. Check KMS key permissions:
   ```bash
   aws kms describe-key --key-id <key-arn>
   ```

### Parameter Size Exceeded

**Problem:** `ParameterMaxLength` error for Parameter Store.

**Solutions:**
1. Use Advanced tier for larger parameters:
   ```yaml
   config:
     tier: Advanced
   ```
2. Switch to Secrets Manager (65KB limit)
3. Split large values into multiple parameters

## Security Considerations

### Encryption

Both services encrypt secrets at rest:

- **Secrets Manager**: Mandatory KMS encryption
- **Parameter Store SecureString**: KMS encryption (AWS managed or custom key)

```yaml
# Use custom KMS key
secrets:
  - name: sensitive_key
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: sensitive-key
          kms_key_id: alias/myapp-secrets
```

### Access Control

Use IAM policies and resource tags:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "secretsmanager:ResourceTag/Environment": "production"
        }
      }
    }
  ]
}
```

### Audit Logging

Enable CloudTrail for complete audit trail:

- Secret creation/updates
- Secret access (GetSecretValue, GetParameter)
- Secret deletion
- KMS key usage

### Secret Deletion

```yaml
# Secrets Manager: 7-30 day recovery window
# Force immediate deletion in code (use with caution):
# sm.delete_secret(SecretId=secret_id, ForceDeleteWithoutRecovery=True)

# Parameter Store: Immediate deletion
# No recovery period
```

## AWS Service Integration

### ECS Task Definitions

```json
{
  "containerDefinitions": [
    {
      "name": "app",
      "secrets": [
        {
          "name": "DB_PASSWORD",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789012:secret:myapp/db/password"
        },
        {
          "name": "API_KEY",
          "valueFrom": "arn:aws:ssm:us-east-1:123456789012:parameter/myapp/api-key"
        }
      ]
    }
  ]
}
```

### Lambda Functions

```python
import boto3
import json

# Secrets Manager
secrets_client = boto3.client('secretsmanager')
response = secrets_client.get_secret_value(SecretId='myapp/db/password')
secret = json.loads(response['SecretString'])

# Parameter Store
ssm_client = boto3.client('ssm')
response = ssm_client.get_parameter(Name='/myapp/api-key', WithDecryption=True)
api_key = response['Parameter']['Value']
```

### RDS Integration

```yaml
# Create RDS master password
secrets:
  - name: rds_master_password
    kind: random_password
    config:
      length: 32
      special: true
      exclude_characters: '"@/\`'
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: rds/master-password
```

Then reference in RDS:
```bash
aws rds create-db-instance \
  --db-instance-identifier mydb \
  --manage-master-user-password \
  --master-username admin \
  --engine postgres
```

## Next Steps

- Explore [Azure Key Vault](azure.md) for multi-cloud deployments
- Learn about [HashiCorp Vault](vault.md) for hybrid environments
- Review [Kubernetes secrets](kubernetes.md) for container workloads
- Check [examples](../../examples/) for complete configurations
