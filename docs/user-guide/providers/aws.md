# AWS Provider

The AWS provider enables SecretZero to store and manage secrets in AWS Secrets Manager and AWS Systems Manager Parameter Store. It supports multiple authentication methods including ambient authentication, AWS profiles, and IAM role assumption.

## Overview

The AWS provider is ideal for:

- **Cloud-native applications** running on AWS infrastructure (EC2, ECS, Lambda, EKS)
- **Serverless architectures** that need automatic secret rotation
- **Multi-region deployments** requiring secret replication
- **Applications using AWS SDK** that can directly access AWS services
- **Organizations with existing AWS IAM policies** and role-based access control

### Supported Target Types

| Target Type | Description | Use Case |
|-------------|-------------|----------|
| `ssm_parameter` | AWS Systems Manager Parameter Store | Simple key-value secrets, configuration parameters, cost-effective storage |
| `secrets_manager` | AWS Secrets Manager | Database credentials, API keys, automatic rotation, cross-region replication |

## Authentication Methods

### Ambient Authentication (Recommended)

Ambient authentication automatically discovers credentials from the environment, following the [AWS credential provider chain](https://docs.aws.amazon.com/sdkref/latest/guide/standardized-credentials.html):

1. Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
2. AWS credentials file (`~/.aws/credentials`)
3. ECS container credentials (IAM role for ECS tasks)
4. EC2 instance metadata (IAM role for EC2 instances)

```yaml
providers:
  aws:
    kind: aws
    auth:
      kind: ambient
      region: us-east-1
```

**When to use**: Production environments with IAM roles, local development with AWS CLI configured, CI/CD pipelines with AWS credentials.

### AWS Profile Authentication

Use a named AWS profile from `~/.aws/credentials` or `~/.aws/config`:

```yaml
providers:
  aws:
    kind: aws
    auth:
      kind: profile
      profile: my-profile-name
      region: us-west-2
```

**When to use**: Local development with multiple AWS accounts, testing with different credentials, separating environments by profile.

### Assume Role Authentication

Assume an IAM role for cross-account access or elevated permissions:

```yaml
providers:
  aws:
    kind: aws
    auth:
      kind: assume_role
      role_arn: arn:aws:iam::123456789012:role/SecretZeroRole
      region: us-east-1
```

**When to use**: Cross-account secret management, temporary elevated permissions, CI/CD pipelines assuming deployment roles.

## Configuration

### Basic Configuration

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
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: prod/db/password
          description: Production database password
```

### Multi-Region Configuration

Store secrets in multiple AWS regions:

```yaml
providers:
  aws_primary:
    kind: aws
    auth:
      kind: ambient
      region: us-east-1
  
  aws_secondary:
    kind: aws
    auth:
      kind: ambient
      region: eu-west-1

secrets:
  - name: api_key
    kind: random_string
    config:
      length: 32
    targets:
      - provider: aws_primary
        kind: secrets_manager
        config:
          name: prod/api-key
      
      - provider: aws_secondary
        kind: secrets_manager
        config:
          name: prod/api-key
```

### Cross-Account Configuration

Access secrets in different AWS accounts:

```yaml
providers:
  aws_account_a:
    kind: aws
    auth:
      kind: profile
      profile: account-a
      region: us-east-1
  
  aws_account_b:
    kind: aws
    auth:
      kind: assume_role
      role_arn: arn:aws:iam::987654321098:role/SecretZeroRole
      region: us-east-1

secrets:
  - name: shared_secret
    kind: random_password
    config:
      length: 32
    targets:
      - provider: aws_account_a
        kind: secrets_manager
        config:
          name: shared/secret
      
      - provider: aws_account_b
        kind: secrets_manager
        config:
          name: shared/secret
```

## Target Types

### SSM Parameter Store

AWS Systems Manager Parameter Store provides hierarchical storage for configuration data and secrets.

#### Configuration Options

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `name` | string | Yes | - | Parameter name (supports hierarchical paths) |
| `type` | string | No | `SecureString` | Parameter type: `String`, `StringList`, or `SecureString` |
| `description` | string | No | - | Parameter description |
| `overwrite` | boolean | No | `true` | Overwrite existing parameter |
| `tier` | string | No | `Standard` | Parameter tier: `Standard` or `Advanced` |
| `kms_key_id` | string | No | AWS managed | KMS key ID for encryption |
| `tags` | object | No | - | Key-value tags |

#### Example: Basic SSM Parameter

```yaml
secrets:
  - name: database_host
    kind: static
    config:
      default: db.example.com
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /myapp/prod/db/host
          type: String
          description: Production database hostname
          tags:
            Environment: production
            Application: myapp
```

#### Example: Hierarchical Parameters

```yaml
secrets:
  - name: database_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /myapp/prod/db/password
          type: SecureString
          tier: Standard
  
  - name: database_username
    kind: static
    config:
      default: admin
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /myapp/prod/db/username
          type: String
```

#### Example: Advanced Tier with Custom KMS Key

```yaml
secrets:
  - name: encryption_key
    kind: random_string
    config:
      length: 64
      charset: alphanumeric
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /myapp/prod/encryption-key
          type: SecureString
          tier: Advanced  # Required for large values (>4KB)
          kms_key_id: arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012
          description: Application encryption key
```

### Secrets Manager

AWS Secrets Manager provides automatic secret rotation, built-in integration with RDS, and cross-region replication.

#### Configuration Options

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `name` | string | Yes | - | Secret name or ARN |
| `description` | string | No | - | Secret description |
| `kms_key_id` | string | No | AWS managed | KMS key ID for encryption |
| `tags` | list | No | - | List of tag dictionaries |
| `replica_regions` | list | No | - | List of regions for replication |

#### Example: Database Credentials

```yaml
secrets:
  - name: postgres_password
    kind: random_password
    one_time: true
    rotation_period: 90d
    config:
      length: 32
      special: true
      exclude_characters: '"@/\`'
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: prod/postgres/master-password
          description: PostgreSQL master password
          tags:
            - Key: Environment
              Value: production
            - Key: Database
              Value: postgres
            - Key: Rotation
              Value: "90days"
```

#### Example: JSON Secret

```yaml
secrets:
  - name: api_credentials
    kind: templates.api_creds
    
templates:
  api_creds:
    description: API credentials with multiple fields
    fields:
      api_key:
        generator:
          kind: random_string
          config:
            length: 32
      api_secret:
        generator:
          kind: random_password
          config:
            length: 48
      endpoint:
        generator:
          kind: static
          config:
            default: https://api.example.com
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: prod/api/credentials
          description: API service credentials
```

The secret will be stored as JSON:
```json
{
  "api_key": "abc123...",
  "api_secret": "xyz789...",
  "endpoint": "https://api.example.com"
}
```

#### Example: Cross-Region Replication

```yaml
secrets:
  - name: global_api_key
    kind: random_string
    config:
      length: 32
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: global/api-key
          description: Global API key replicated across regions
          replica_regions:
            - region: eu-west-1
              kms_key_id: arn:aws:kms:eu-west-1:123456789012:key/replica-key-id
            - region: ap-southeast-1
```

## Complete Examples

### Example 1: Simple Application Secrets

```yaml
version: '1.0'

variables:
  environment: production
  app_name: myapp
  aws_region: us-east-1

providers:
  aws:
    kind: aws
    auth:
      kind: ambient
      region: "{{var.aws_region}}"

secrets:
  # Database password in Secrets Manager
  - name: database_password
    kind: random_password
    rotation_period: 90d
    config:
      length: 32
      special: true
      exclude_characters: '"@/\'
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: "{{var.app_name}}/{{var.environment}}/db/password"
          description: "Database password for {{var.app_name}}"
  
  # API key in Parameter Store
  - name: external_api_key
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: "/{{var.app_name}}/{{var.environment}}/external-api-key"
          type: SecureString
          description: "External API key"

metadata:
  project: "{{var.app_name}}"
  owner: backend-team
```

### Example 2: Multi-Environment Setup

```yaml
version: '1.0'

variables:
  app_name: myapp

providers:
  aws_dev:
    kind: aws
    auth:
      kind: profile
      profile: dev-account
      region: us-west-2
  
  aws_staging:
    kind: aws
    auth:
      kind: profile
      profile: staging-account
      region: us-east-1
  
  aws_prod:
    kind: aws
    auth:
      kind: assume_role
      role_arn: arn:aws:iam::123456789012:role/SecretZeroRole
      region: us-east-1

secrets:
  - name: database_password
    kind: random_password
    config:
      length: 32
      special: true
    targets:
      # Development
      - provider: aws_dev
        kind: ssm_parameter
        config:
          name: /{{var.app_name}}/dev/db/password
          type: SecureString
      
      # Staging
      - provider: aws_staging
        kind: secrets_manager
        config:
          name: {{var.app_name}}/staging/db/password
      
      # Production
      - provider: aws_prod
        kind: secrets_manager
        config:
          name: {{var.app_name}}/prod/db/password
          replica_regions:
            - region: eu-west-1
```

### Example 3: RDS Database Credentials

```yaml
version: '1.0'

providers:
  aws:
    kind: aws
    auth:
      kind: ambient
      region: us-east-1

secrets:
  - name: rds_master_credentials
    kind: templates.rds_creds

templates:
  rds_creds:
    description: RDS master credentials
    fields:
      username:
        generator:
          kind: static
          config:
            default: admin
      password:
        generator:
          kind: random_password
          config:
            length: 32
            special: true
            exclude_characters: '"@/\`'
      engine:
        generator:
          kind: static
          config:
            default: postgres
      host:
        generator:
          kind: static
          config:
            default: mydb.cluster-abc123.us-east-1.rds.amazonaws.com
      port:
        generator:
          kind: static
          config:
            default: "5432"
      dbname:
        generator:
          kind: static
          config:
            default: production
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: prod/rds/master
          description: RDS master credentials
          tags:
            - Key: Database
              Value: RDS
            - Key: Engine
              Value: PostgreSQL
```

## IAM Permissions

### Minimum Required Permissions

For SSM Parameter Store:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ssm:PutParameter",
        "ssm:GetParameter",
        "ssm:GetParameters",
        "ssm:DescribeParameters",
        "ssm:AddTagsToResource"
      ],
      "Resource": "arn:aws:ssm:*:*:parameter/*"
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

For Secrets Manager:

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
        "secretsmanager:DescribeSecret",
        "secretsmanager:TagResource",
        "secretsmanager:ReplicateSecretToRegions"
      ],
      "Resource": "arn:aws:secretsmanager:*:*:secret:*"
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

### Cross-Account Access

For cross-account secret management, create a role in the target account:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::SOURCE-ACCOUNT-ID:root"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "your-external-id"
        }
      }
    }
  ]
}
```

## Best Practices

### 1. Use Secrets Manager for Sensitive Data

- **Database credentials**: Supports automatic rotation
- **API keys**: Requires versioning and audit trail
- **Private keys**: Needs replication across regions

Use Parameter Store for:
- **Configuration values**: Non-sensitive data
- **Feature flags**: Frequently accessed values
- **Service endpoints**: Static configuration

### 2. Implement Hierarchical Naming

```yaml
# Good: Hierarchical and descriptive
/myapp/prod/db/password
/myapp/prod/api/external-key
/myapp/staging/db/password

# Avoid: Flat structure
myapp-prod-db-password
api-key
password1
```

### 3. Tag Resources Consistently

```yaml
targets:
  - provider: aws
    kind: secrets_manager
    config:
      name: prod/db/password
      tags:
        - Key: Environment
          Value: production
        - Key: Application
          Value: myapp
        - Key: ManagedBy
          Value: secretzero
        - Key: Owner
          Value: backend-team
        - Key: CostCenter
          Value: engineering
```

### 4. Use Custom KMS Keys for Production

```yaml
secrets:
  - name: production_secret
    kind: random_password
    config:
      length: 32
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: prod/critical-secret
          kms_key_id: arn:aws:kms:us-east-1:123456789012:key/custom-key-id
```

Benefits:
- Separate audit trails
- Granular access control
- Compliance requirements
- Cross-account key usage

### 5. Enable Cross-Region Replication for Critical Secrets

```yaml
secrets:
  - name: disaster_recovery_key
    kind: random_string
    config:
      length: 64
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: prod/dr-key
          replica_regions:
            - region: us-west-2
            - region: eu-central-1
```

## Integration with AWS Services

### Lambda Functions

Access secrets in Lambda:

```python
import boto3
import json

def lambda_handler(event, context):
    secretsmanager = boto3.client('secretsmanager')
    
    # Get secret value
    response = secretsmanager.get_secret_value(SecretId='prod/db/password')
    secret = json.loads(response['SecretString'])
    
    # Use secret
    password = secret.get('password')
    # ... rest of your code
```

### ECS Task Definitions

Reference secrets in ECS task definitions:

```json
{
  "containerDefinitions": [
    {
      "name": "myapp",
      "image": "myapp:latest",
      "secrets": [
        {
          "name": "DB_PASSWORD",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/db/password"
        },
        {
          "name": "API_KEY",
          "valueFrom": "arn:aws:ssm:us-east-1:123456789012:parameter/myapp/prod/api-key"
        }
      ]
    }
  ]
}
```

### EKS with External Secrets Operator

Use AWS secrets in Kubernetes via External Secrets:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: aws-secrets
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets
---
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: database-credentials
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets
    kind: SecretStore
  target:
    name: database-credentials
  data:
    - secretKey: password
      remoteRef:
        key: prod/db/password
        property: password
```

## Troubleshooting

### Authentication Errors

**Error**: `AWS authentication failed. Check credentials and configuration.`

**Solutions**:
1. Verify environment variables are set:
   ```bash
   echo $AWS_ACCESS_KEY_ID
   echo $AWS_SECRET_ACCESS_KEY
   echo $AWS_REGION
   ```

2. Check AWS credentials file:
   ```bash
   cat ~/.aws/credentials
   cat ~/.aws/config
   ```

3. Test AWS CLI access:
   ```bash
   aws sts get-caller-identity
   ```

4. Verify IAM permissions with policy simulator

### Permission Denied

**Error**: `AccessDeniedException: User is not authorized to perform: secretsmanager:CreateSecret`

**Solutions**:
1. Check IAM permissions for the user/role
2. Verify resource-based policies on secrets
3. Check service control policies (SCPs) in AWS Organizations
4. Ensure KMS key policies allow encrypt/decrypt operations

### Region Mismatch

**Error**: `SecretNotFoundException: Secret not found in region`

**Solutions**:
1. Verify the region in provider configuration matches the secret's region
2. Check if cross-region replication is configured correctly
3. Ensure `AWS_REGION` environment variable is set correctly

### KMS Key Access Issues

**Error**: `KMS.AccessDeniedException: The ciphertext refers to a customer master key that does not exist`

**Solutions**:
1. Verify the KMS key ID is correct
2. Check KMS key policy allows the IAM principal
3. Ensure the key is in the same region
4. Verify the key hasn't been scheduled for deletion

### Parameter Store Throttling

**Error**: `ThrottlingException: Rate exceeded`

**Solutions**:
1. Implement exponential backoff in sync operations
2. Reduce the frequency of parameter updates
3. Consider using Parameter Store's higher tier
4. Batch parameter operations when possible

## Cost Optimization

### SSM Parameter Store Pricing

- **Standard parameters**: Free (up to 10,000 parameters)
- **Advanced parameters**: $0.05 per parameter per month
- **Higher throughput**: $0.05 per 10,000 API calls

**Recommendation**: Use standard parameters unless you need:
- Parameters larger than 4KB
- Parameter policies
- More than 10,000 parameters

### Secrets Manager Pricing

- **Secret storage**: $0.40 per secret per month
- **API calls**: $0.05 per 10,000 API calls
- **Replication**: Additional $0.40 per replica per month

**Cost-saving tips**:
1. Use Parameter Store for non-rotated secrets
2. Implement caching to reduce API calls
3. Archive unused secrets instead of deleting
4. Monitor costs with AWS Cost Explorer

## See Also

- [Providers Overview](index.md)
- [Azure Provider](azure.md)
- [HashiCorp Vault Provider](vault.md)
- [AWS Secrets Manager Documentation](https://docs.aws.amazon.com/secretsmanager/)
- [AWS Systems Manager Parameter Store Documentation](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html)
