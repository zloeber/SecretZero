# Complete Working Examples

This page provides end-to-end examples for common SecretZero use cases with detailed explanations and step-by-step instructions.

## Example 1: Local Development Setup

**Use Case**: Developer workstation with no cloud dependencies

**What You'll Learn**:
- Basic Secretfile structure
- Local file generation
- Environment variable management
- Simple rotation policies

### Configuration

Create `Secretfile.yml`:

```yaml
version: '1.0'

metadata:
  project: local-dev
  description: Local development secrets

providers:
  local:
    kind: local
    config: {}

secrets:
  # Database password for local PostgreSQL
  - name: postgres_password
    kind: random_password
    config:
      length: 20
      special: true
    rotation_period: 90d
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true
  
  # API key for external service
  - name: api_key
    kind: random_string
    config:
      length: 32
      charset: alphanumeric
    rotation_period: 30d
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true
  
  # JWT secret (generated once)
  - name: jwt_secret
    kind: random_string
    config:
      length: 64
      charset: base64
    one_time: true
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true
```

### Step-by-Step Usage

1. **Install SecretZero**:
```bash
pip install secretzero
```

2. **Validate Configuration**:
```bash
secretzero validate
```

3. **Preview Changes (Dry Run)**:
```bash
secretzero sync --dry-run
```

4. **Generate Secrets**:
```bash
secretzero sync
```

5. **View Generated Secrets**:
```bash
cat .env
```

Output:
```
POSTGRES_PASSWORD=X9k#mP2$vN8qR4&tY7
API_KEY=a8f2d9c4e1b7f3g5h8j9k2l4m6n8p1q3
JWT_SECRET=aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789+/==
```

6. **Check Rotation Status**:
```bash
secretzero rotation check
```

7. **Use in Your Application**:
```python
import os
from dotenv import load_dotenv

load_dotenv()

db_password = os.getenv('POSTGRES_PASSWORD')
api_key = os.getenv('API_KEY')
jwt_secret = os.getenv('JWT_SECRET')
```

---

## Example 2: AWS Production Deployment

**Use Case**: Production application on AWS with secrets in SSM and Secrets Manager

**What You'll Learn**:
- AWS provider configuration
- Multiple target types
- Production-grade rotation
- Compliance policies

### Prerequisites

```bash
# Install AWS support
pip install secretzero[aws]

# Configure AWS credentials
aws configure
```

### Configuration

Create `Secretfile.yml`:

```yaml
version: '1.0'

metadata:
  project: production-app
  environment: production
  owner: platform-team
  compliance:
    - soc2
    - iso27001

variables:
  environment: production
  region: us-east-1
  app_name: myapp

providers:
  aws:
    kind: aws
    auth:
      kind: ambient
      region: "{{ var.region }}"

secrets:
  # Database credentials in SSM
  - name: rds_master_password
    kind: random_password
    config:
      length: 32
      special: true
      upper: true
      lower: true
      number: true
    rotation_period: 30d
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /{{ var.environment }}/{{ var.app_name }}/db/master-password
          type: SecureString
          tier: Standard
          tags:
            Environment: "{{ var.environment }}"
            Application: "{{ var.app_name }}"
            ManagedBy: SecretZero
  
  # API keys in Secrets Manager (with automatic rotation)
  - name: third_party_api_key
    kind: random_string
    config:
      length: 40
      charset: alphanumeric
    rotation_period: 90d
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: "{{ var.app_name }}/third-party-api-key"
          description: "API key for third-party service"
          kms_key_id: alias/aws/secretsmanager
          tags:
            - key: Environment
              value: "{{ var.environment }}"
            - key: Application
              value: "{{ var.app_name }}"
  
  # Redis password (shared across services)
  - name: redis_password
    kind: random_password
    config:
      length: 24
      special: false  # Redis doesn't handle special chars well
    rotation_period: 60d
    targets:
      # Store in SSM for application access
      - provider: aws
        kind: ssm_parameter
        config:
          name: /{{ var.environment }}/{{ var.app_name }}/redis/password
          type: SecureString
      # Also store in Secrets Manager for Lambda functions
      - provider: aws
        kind: secrets_manager
        config:
          name: "{{ var.app_name }}/redis-password"

policies:
  # Enforce rotation
  rotation_policy:
    kind: rotation
    config:
      require_rotation_period: true
      max_rotation_period: 90d
      warn_before_expiry: 7d
    severity: error
  
  # SOC2 compliance
  soc2_policy:
    kind: compliance
    config:
      standard: soc2
      require_encryption: true
      require_audit_logging: true
    severity: error
```

### Step-by-Step Deployment

1. **Test AWS Connectivity**:
```bash
secretzero test --provider aws
```

2. **Validate Configuration**:
```bash
secretzero validate
secretzero policy check
```

3. **Dry Run**:
```bash
secretzero sync --dry-run
```

4. **Deploy Secrets**:
```bash
secretzero sync
```

5. **Verify in AWS**:
```bash
# Check SSM Parameter
aws ssm get-parameter \
  --name /production/myapp/db/master-password \
  --with-decryption

# Check Secrets Manager
aws secretsmanager get-secret-value \
  --secret-id myapp/third-party-api-key
```

6. **Use in Application** (Python/Boto3):
```python
import boto3

ssm = boto3.client('ssm', region_name='us-east-1')
secrets = boto3.client('secretsmanager', region_name='us-east-1')

# Get from SSM
db_password = ssm.get_parameter(
    Name='/production/myapp/db/master-password',
    WithDecryption=True
)['Parameter']['Value']

# Get from Secrets Manager
api_key = secrets.get_secret_value(
    SecretId='myapp/third-party-api-key'
)['SecretString']
```

7. **Set Up Rotation Schedule** (cron):
```bash
# Add to crontab
0 2 * * * cd /opt/secretzero && secretzero rotation execute
```

---

## Example 3: Kubernetes Integration

**Use Case**: Managing Kubernetes Secrets with SecretZero

**What You'll Learn**:
- Kubernetes provider setup
- Native Secret objects
- Multiple namespaces
- Integration with deployments

### Prerequisites

```bash
# Install Kubernetes support
pip install secretzero[kubernetes]

# Ensure kubectl is configured
kubectl cluster-info
```

### Configuration

Create `Secretfile.yml`:

```yaml
version: '1.0'

metadata:
  project: k8s-app
  description: Kubernetes secret management

variables:
  namespace: default
  app_name: myapp

providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient
      config:
        # Uses default kubeconfig
        # context: my-cluster

secrets:
  # Application database password
  - name: postgres_password
    kind: random_password
    config:
      length: 24
      special: true
    rotation_period: 90d
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: "{{ var.namespace }}"
          secret_name: "{{ var.app_name }}-db"
          data_key: password
          secret_type: Opaque
          labels:
            app: "{{ var.app_name }}"
            component: database
          annotations:
            managed-by: secretzero
            rotation-period: 90d
  
  # Redis credentials
  - name: redis_password
    kind: random_password
    config:
      length: 16
      special: false
    rotation_period: 60d
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: "{{ var.namespace }}"
          secret_name: "{{ var.app_name }}-cache"
          data_key: redis-password
          labels:
            app: "{{ var.app_name }}"
            component: cache
  
  # API credentials (multiple keys in one Secret)
  - name: api_key
    kind: random_string
    config:
      length: 32
      charset: hex
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: "{{ var.namespace }}"
          secret_name: "{{ var.app_name }}-api"
          data_key: api-key
          labels:
            app: "{{ var.app_name }}"
  
  - name: api_secret
    kind: random_string
    config:
      length: 64
      charset: base64
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: "{{ var.namespace }}"
          secret_name: "{{ var.app_name }}-api"  # Same Secret
          data_key: api-secret
          labels:
            app: "{{ var.app_name }}"
```

### Step-by-Step Usage

1. **Test Kubernetes Access**:
```bash
secretzero test --provider kubernetes
```

2. **Generate Secrets**:
```bash
secretzero sync
```

3. **Verify Secrets Created**:
```bash
kubectl get secrets -l app=myapp
kubectl describe secret myapp-db
kubectl describe secret myapp-cache
kubectl describe secret myapp-api
```

4. **Create Deployment Using Secrets**:

Create `deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
  namespace: default
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      containers:
      - name: app
        image: myapp:latest
        env:
        # Database credentials
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: myapp-db
              key: password
        # Redis credentials
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: myapp-cache
              key: redis-password
        # API credentials
        - name: API_KEY
          valueFrom:
            secretKeyRef:
              name: myapp-api
              key: api-key
        - name: API_SECRET
          valueFrom:
            secretKeyRef:
              name: myapp-api
              key: api-secret
```

5. **Deploy Application**:
```bash
kubectl apply -f deployment.yaml
```

6. **Verify Application**:
```bash
kubectl get pods -l app=myapp
kubectl logs -l app=myapp --tail=50
```

7. **Rotate Secrets**:
```bash
# Check rotation status
secretzero rotation check

# Rotate secrets
secretzero rotation execute

# Restart pods to pick up new secrets
kubectl rollout restart deployment/myapp
```

---

## Example 4: CI/CD Pipeline Integration

**Use Case**: Automating secret management in GitHub Actions

**What You'll Learn**:
- CI/CD integration
- Automated rotation
- Policy enforcement
- Drift detection

### GitHub Actions Workflow

Create `.github/workflows/secrets.yml`:

```yaml
name: Secret Management

on:
  schedule:
    # Check rotation daily at 2 AM
    - cron: '0 2 * * *'
  workflow_dispatch:
  push:
    paths:
      - 'Secretfile.yml'

jobs:
  manage-secrets:
    runs-on: ubuntu-latest
    permissions:
      id-token: write  # For OIDC
      contents: read
    
    steps:
      - name: Checkout
        uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install SecretZero
        run: pip install secretzero[all]
      
      - name: Configure AWS Credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: us-east-1
      
      - name: Validate Configuration
        run: |
          secretzero validate
          secretzero policy check --fail-on-warning
      
      - name: Check Rotation Status
        id: rotation
        run: |
          secretzero rotation check --json > rotation.json
          cat rotation.json
          
          # Check if any secrets are overdue
          overdue=$(jq -r '.secrets_overdue | length' rotation.json)
          echo "overdue=$overdue" >> $GITHUB_OUTPUT
      
      - name: Check for Drift
        run: secretzero drift check
      
      - name: Execute Rotation
        if: steps.rotation.outputs.overdue > 0
        run: secretzero rotation execute
      
      - name: Generate Audit Report
        run: |
          secretzero audit report --format json > audit-report.json
      
      - name: Upload Audit Report
        uses: actions/upload-artifact@v3
        with:
          name: audit-report
          path: audit-report.json
      
      - name: Notify on Failure
        if: failure()
        uses: slackapi/slack-github-action@v1
        with:
          webhook-url: ${{ secrets.SLACK_WEBHOOK }}
          payload: |
            {
              "text": "SecretZero workflow failed!",
              "blocks": [
                {
                  "type": "section",
                  "text": {
                    "type": "mrkdwn",
                    "text": "❌ Secret management workflow failed in ${{ github.repository }}"
                  }
                }
              ]
            }
```

### Secretfile for CI/CD

```yaml
version: '1.0'

metadata:
  project: cicd-secrets
  description: Secrets managed via CI/CD

providers:
  aws:
    kind: aws
    auth:
      kind: ambient  # Uses GitHub OIDC

secrets:
  - name: prod_db_password
    kind: random_password
    config:
      length: 32
      special: true
    rotation_period: 30d
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /prod/db/password
          type: SecureString

policies:
  rotation_enforcement:
    kind: rotation
    config:
      require_rotation_period: true
      max_rotation_period: 90d
    severity: error
```

### Usage

1. **Initial Setup**:
```bash
# Commit Secretfile
git add Secretfile.yml
git commit -m "Add Secretfile configuration"
git push
```

2. **Manual Trigger**:
- Go to Actions tab in GitHub
- Select "Secret Management" workflow
- Click "Run workflow"

3. **Monitor Execution**:
- View workflow logs
- Check audit reports in artifacts
- Review rotation status

4. **Automatic Rotation**:
- Workflow runs daily at 2 AM
- Checks for overdue secrets
- Rotates automatically if needed

---

## Example 5: Multi-Cloud Setup

**Use Case**: Large organization using AWS, Azure, and Vault

**What You'll Learn**:
- Multi-provider configuration
- Complex secret distribution
- Policy-backed rotation and compliance rules
- Centralized management

### Configuration

Create `Secretfile.yml`:

```yaml
version: '1.0'

metadata:
  project: multi-cloud-secrets
  organization: acme-corp
  compliance:
    - soc2
    - hipaa
    - pci-dss

variables:
  environment: production
  aws_region: us-east-1
  azure_region: eastus
  vault_url: https://vault.example.com

providers:
  aws:
    kind: aws
    auth:
      kind: assume_role
      role_arn: arn:aws:iam::123456789012:role/SecretZeroRole
      region: "{{ var.aws_region }}"
  
  azure:
    kind: azure
    auth:
      kind: managed_identity
      client_id: 12345678-1234-1234-1234-123456789012
  
  vault:
    kind: vault
    auth:
      kind: token
      token: "${VAULT_TOKEN}"
      url: "{{ var.vault_url }}"
  
  local:
    kind: local

secrets:
  # Critical database password - stored everywhere
  - name: master_db_password
    kind: random_password
    config:
      length: 32
      special: true
    rotation_period: 30d
    targets:
      # AWS for EC2 instances
      - provider: aws
        kind: ssm_parameter
        config:
          name: /prod/db/master-password
          type: SecureString
      # Azure for AKS clusters
      - provider: azure
        kind: key_vault
        config:
          vault_url: https://acme-prod-kv.vault.azure.net
          secret_name: master-db-password
      # Vault for on-prem services
      - provider: vault
        kind: kv
        config:
          path: prod/db/master-password
          mount_point: secret
      # Local backup
      - provider: local
        kind: file
        config:
          path: backups/master-password.txt
          format: raw
  
  # Application secrets per cloud
  - name: aws_api_key
    kind: random_string
    config:
      length: 40
    rotation_period: 90d
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: prod/api-key
      - provider: vault
        kind: kv
        config:
          path: aws/api-key
  
  - name: azure_api_key
    kind: random_string
    config:
      length: 40
    rotation_period: 90d
    targets:
      - provider: azure
        kind: key_vault
        config:
          vault_url: https://acme-prod-kv.vault.azure.net
          secret_name: api-key
      - provider: vault
        kind: kv
        config:
          path: azure/api-key

policies:
  strict_rotation:
    kind: rotation
    config:
      require_rotation_period: true
      max_rotation_period: 90d
      warn_before_expiry: 14d
    severity: error
  
  compliance:
    kind: compliance
    config:
      standards:
        - soc2
        - hipaa
        - pci-dss
      require_encryption: true
      require_audit: true
      require_mfa: true
    severity: error
  
  access_control:
    kind: access
    config:
      require_approval: true
      allowed_targets:
        - aws_ssm
        - azure_key_vault
        - vault_kv
      deny_local: true  # No local files in production
    severity: error
```

### Deployment

1. **Set Up Credentials**:
```bash
# AWS
aws configure

# Azure
az login

# Vault
export VAULT_TOKEN=your-token
export VAULT_ADDR=https://vault.example.com
```

2. **Validate Everything**:
```bash
# Test all providers
secretzero test

# Validate configuration
secretzero validate

# Check policies
secretzero policy check --fail-on-warning
```

3. **Deploy**:
```bash
# Dry run first
secretzero sync --dry-run

# Deploy to all clouds
secretzero sync
```

4. **Verify Across Clouds**:
```bash
# AWS
aws ssm get-parameter --name /prod/db/master-password

# Azure
az keyvault secret show \
  --vault-name acme-prod-kv \
  --name master-db-password

# Vault
vault kv get secret/prod/db/master-password
```

---

## Next Steps

- Explore more examples in the [GitHub repository](repository.md)
- Learn about [API usage](../user-guide/api/index.md)
- Read the [Configuration Guide](../user-guide/configuration/index.md)
- Check [Best Practices](../user-guide/best-practices.md)
