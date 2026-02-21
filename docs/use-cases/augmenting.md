# Augmentation Guide

## Overview

SecretZero is not a migration tool—it's a **secrets orchestration engine** that augments your existing secret management infrastructure. Instead of replacing your current systems, SecretZero works *alongside* them to solve problems that those systems don't handle well.

This guide provides practical scenarios where you're using traditional secret management tools and shows how SecretZero improves your workflow, reducing operational overhead and increasing security posture.

## Prerequisites

To use SecretZero for augmentation:

- Your current secret management system is operational and reliable
- SecretZero installed: `pip install secretzero`
- Read-only access to existing secret stores (no modification required)
- Target secret storage providers configured
- Understanding of your current secret lifecycle and rotation policies
- Ability to add new deployment targets alongside existing ones

## Augmentation Scenarios

These scenarios describe real-world problems with existing secret management approaches and how SecretZero augments your current setup to solve them.

### Problems SecretZero Solves

- **Secret Sprawl**: Secrets scattered across multiple systems with no unified view
- **Rotation Complexity**: Manual rotation procedures prone to human error
- **No Lifecycle Tracking**: Limited audit trail of secret changes and rotations
- **Bootstrap Challenges**: Difficult to provision new environments with consistent secrets
- **Multi-Target Sync**: Secrets need to exist in multiple places (vault + k8s + ci/cd + config)
- **Compliance Gaps**: Hard to enforce rotation policies and prove compliance
- **Team Overhead**: Each team maintains their own secret management procedures

## Augmenting Your Current Tools

### Augmenting Environment Variable Management (.env files)

**Current Problem**: Your team manages secrets in scattered `.env` files across multiple environments. There's no centralized control, audit trail, or automated rotation. New team members manually copy `.env.example` and guess at values. Secrets are regularly exposed in git history, and rotation requires manual updates across all environments.

**SecretZero Augmentation**: Use SecretZero as a declarative source of truth that automatically syncs to `.env` files while also backing them up in cloud vaults. Automate rotations and maintain audit history.

**Example Implementation**:

```yaml
# Secretfile.yml - Environment Variable Augmentation
version: '1.0'

metadata:
  project: myapp
  owner: engineering-team
  augmentation: env-files-to-cloud
  description: |
    Centralize .env management with SecretZero while maintaining
    .env file generation for backward compatibility.

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
  
  local:
    kind: local

secrets:
  # Database URL - maintain in .env, back up to cloud
  - name: database_url
    kind: static
    rotation_period: 90d
    config:
      default: "postgresql://user:password@localhost:5432/myapp"
    targets:
      # Primary: Cloud backup for disaster recovery
      - provider: aws
        kind: secrets_manager
        config:
          name: "{{ var.environment }}/{{ var.app_name }}/database-url"
          description: "Database connection string"
          tags:
            Source: environment-variables
            Environment: "{{ var.environment }}"
      # Secondary: Generated .env file for local development
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true

  # API Key - generate if missing, sync everywhere
  - name: api_key
    kind: random_string
    rotation_period: 90d
    config:
      length: 32
      prefix: "sk_live_"
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: "{{ var.environment }}/{{ var.app_name }}/api-key"
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true

  # JWT Secret - auto-generate with rotation
  - name: jwt_secret
    kind: random_password
    rotation_period: 90d
    config:
      length: 64
      special: true
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: "{{ var.environment }}/{{ var.app_name }}/jwt-secret"
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true

  # Redis Password - managed with rotation policy
  - name: redis_password
    kind: random_password
    rotation_period: 90d
    config:
      length: 32
      special: false
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: "{{ var.environment }}/{{ var.app_name }}/redis-password"
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true
```

**Implementation Steps**:

```bash
# 1. Set existing secret values as environment variables
export DATABASE_URL="postgresql://user:password@localhost:5432/myapp"
export API_KEY="sk_live_current_key"
export JWT_SECRET="current_jwt_secret"
export REDIS_PASSWORD="current_redis_password"

# 2. Create Secretfile.yml with augmentation targets
# (Use the YAML above)

# 3. Validate configuration
secretzero validate

# 4. Dry-run to see what will happen
secretzero sync --dry-run

# 5. Execute - generates .env and backs up to AWS
secretzero sync

# Result: .env file is generated automatically
cat .env
# DATABASE_URL=postgresql://user:password@localhost:5432/myapp
# API_KEY=sk_live_...
# JWT_SECRET=...
# REDIS_PASSWORD=...

# 6. Now you can rotate secrets automatically
secretzero rotate

# 7. Audit trail is maintained
secretzero lockfile show
# Shows rotation history, timestamps, who rotated, etc.
```

**Benefits**:

- ✓ `.env` files still work as before (no application changes)
- ✓ Secrets backed up in AWS (disaster recovery)
- ✓ Automated rotation with audit trail
- ✓ New environments bootstrap automatically
- ✓ Version control never sees actual secrets (lock file only)
- ✓ Rotation policy enforced across all environments

### Augmenting HashiCorp Vault

**Current Problem**: Your organization has invested in HashiCorp Vault for secret storage, but it lacks built-in support for automated lifecycle management, compliance tracking, and multi-target synchronization. Secrets exist only in Vault, and there's no unified way to enforce rotation policies across teams or ensure secrets are available where applications need them.

**SecretZero Augmentation**: Layer SecretZero on top of Vault to provide declarative secret lifecycle management, automated rotation with compliance tracking, and multi-target syncing while keeping Vault as the authoritative source.

**Example Implementation**:

```yaml
# Secretfile.yml - Vault Augmentation with Lifecycle Management
version: '1.0'

metadata:
  project: myapp
  owner: platform-team
  augmentation: vault-lifecycle-management
  description: |
    Use SecretZero to add automated rotation policies, compliance tracking,
    and multi-target syncing on top of existing Vault installation.

variables:
  environment: production
  app_name: myapp
  vault_addr: "https://vault.example.com:8200"
  vault_path: "secret/production/myapp"

providers:
  vault:
    kind: vault
    auth:
      kind: token
      config:
        url: "{{ var.vault_addr }}"
        token: "${VAULT_TOKEN}"
  
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient

secrets:
  # Database credentials - rotate automatically
  - name: database_password
    kind: provider_backed
    rotation_period: 90d
    rotation_policy:
      enforcement: strict
      skip_first: true
      notify_before_expiry: 7d
    config:
      provider: vault
      path: "{{ var.vault_path }}/database/password"
    targets:
      # Sync to Kubernetes for pod access
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: production
          secret_name: database-credentials
          data_key: password
          labels:
            app: "{{ var.app_name }}"
            managed-by: secretzero

  # API Keys - managed with compliance policies
  - name: api_keys
    kind: provider_backed
    rotation_period: 180d
    one_time: false
    config:
      provider: vault
      path: "{{ var.vault_path }}/api-keys"
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: production
          secret_name: api-keys
          secret_type: Opaque
          labels:
            compliance: required

  # Service Account - multi-environment sync
  - name: service_account
    kind: provider_backed
    rotation_period: 365d
    config:
      provider: vault
      path: "{{ var.vault_path }}/service-account"
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: production
          secret_name: service-account
          secret_type: service-account

policies:
  rotation_enforcement:
    kind: rotation
    enabled: true
    require_rotation_period: true
    max_age: 90d
    severity: error
    
  compliance_soc2:
    kind: compliance
    enabled: true
    frameworks:
      - soc2
    required_fields:
      - owner
      - description
      - rotation_period
    severity: warning
```

**Implementation Steps**:

```bash
# 1. Create Secretfile.yml with Vault as provider
# (Use configuration above)

# 2. Validate configuration
secretzero validate

# 3. Dry-run shows what will be synced from Vault to targets
secretzero sync --dry-run

# 4. Execute - now secrets are automatically synced to Kubernetes
secretzero sync

# 5. Automatic rotation is now enforced
# Get rotation status
secretzero rotate --dry-run

# 6. Perform automatic rotation
secretzero rotate

# 7. Audit trail is maintained (who rotated, when, etc.)
secretzero lockfile show

# 8. Compliance checking
secretzero policy --check --framework soc2
```

**Benefits**:

- ✓ Vault remains the authoritative source (no changes to Vault)
- ✓ Automatic rotation policies enforced with audit trail
- ✓ Secrets automatically synced to Kubernetes, CI/CD, applications
- ✓ Compliance tracking and reporting (SOC2, ISO27001, etc.)
- ✓ Notifications before secret expiration
- ✓ Drift detection (alerts if secrets changed outside SecretZero)
- ✓ Unified interface for all secret lifecycle operations

### Augmenting AWS Secrets Manager & Systems Manager

**Current Problem**: You're using AWS Secrets Manager for important secrets, but there's no declarative way to manage them, no standardized rotation policies, no multi-region replication, and no easy way to sync those secrets to applications running on Kubernetes or other platforms. Manual secret creation and rotation is error-prone.

**SecretZero Augmentation**: Define secrets declaratively in a Secretfile, implement consistent rotation policies, and automatically sync to all necessary locations (Kubernetes, parameter store, external APIs).

**Example Implementation**:

```yaml
# Secretfile.yml - AWS Secrets Manager Augmentation
version: '1.0'

metadata:
  project: myapp
  owner: platform-team
  augmentation: aws-secrets-with-rotation
  description: |
    Augment AWS Secrets Manager with automated rotation,
    declarative management, and multi-region replication.

variables:
  environment: production
  app_name: myapp
  aws_region: us-east-1
  aws_regions: ["us-east-1", "eu-west-1"]

providers:
  aws_primary:
    kind: aws
    auth:
      kind: ambient
      config:
        region: "{{ var.aws_region }}"

  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient

secrets:
  # Database credentials with automatic rotation
  - name: database_credentials
    kind: templates.db_creds
    rotation_period: 90d
    rotation_policy:
      grace_period: 7d
      notify_teams:
        - platform-team@example.com
      automatic_deployment: true

  # API keys with scheduled rotation
  - name: external_api_keys
    kind: templates.api_keys_with_backup
    rotation_period: 180d

  # Certificates or tokens with expiry tracking
  - name: service_token
    kind: static
    rotation_period: 365d
    config:
      default: "${SERVICE_TOKEN}"

templates:
  db_creds:
    description: Database credentials
    fields:
      hostname:
        generator:
          kind: static
          config:
            default: "db.example.com"
      port:
        generator:
          kind: static
          config:
            default: "5432"
      username:
        generator:
          kind: static
          config:
            default: "app_user"
      password:
        generator:
          kind: random_password
          config:
            length: 32
            special: true
    targets:
      # Primary: AWS Secrets Manager
      - provider: aws_primary
        kind: secrets_manager
        config:
          name: "{{ var.environment }}/{{ var.app_name }}/database"
          description: "Database credentials (auto-rotated)"
          rotation_lambda: "arn:aws:lambda:{{ var.aws_region }}:123456789012:function:rotate-db-password"
          rotation_days: 90
          tags:
            Environment: "{{ var.environment }}"
            Rotation: "automatic"
            ManagedBy: secretzero
      
      # Secondary: Kubernetes for pod access
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: production
          secret_name: database-credentials
          secret_type: Opaque
          labels:
            app: "{{ var.app_name }}"
            rotation: "managed-by-secretzero"

  api_keys_with_backup:
    description: External API keys with automated backup
    fields:
      stripe_key:
        generator:
          kind: static
          config:
            default: "${STRIPE_KEY}"
      sendgrid_key:
        generator:
          kind: static
          config:
            default: "${SENDGRID_KEY}"
      github_token:
        generator:
          kind: static
          config:
            default: "${GITHUB_TOKEN}"
    targets:
      - provider: aws_primary
        kind: secrets_manager
        config:
          name: "{{ var.environment }}/{{ var.app_name }}/api-keys"
          description: "External API credentials"
          tags:
            Rotation: "manual-review"
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: production
          secret_name: api-keys

policies:
  enforce_rotation:
    kind: rotation
    enabled: true
    require_rotation_period: true
    max_age_days: 90
    severity: error
    
  enforce_compliance:
    kind: compliance
    enabled: true
    frameworks:
      - soc2
      - pci-dss
    required_metadata:
      - owner
      - description
      - rotation_period
      - data_classification
```

**Usage**:

```bash
# 1. Create Secretfile.yml with AWS configuration
# (Use configuration above)

# 2. Set current secret values
export STRIPE_KEY="sk_live_..."
export SENDGRID_KEY="sg_..."
export GITHUB_TOKEN="ghp_..."
export SERVICE_TOKEN="svc_..."

# 3. Validate and sync
secretzero validate
secretzero sync

# 4. Verify in AWS Secrets Manager
aws secretsmanager list-secrets \
  --query 'SecretList[?starts_with(Name, `production/myapp`)].Name'

# 5. Check Kubernetes secrets
kubectl get secrets -n production

# 6. View rotation status
secretzero rotate --dry-run

# 7. Perform scheduled rotation
secretzero rotate

# 8. Check rotation history
secretzero lockfile show database_credentials

# 9. Get compliance report
secretzero compliance --framework soc2
```

**Benefits**:

- ✓ Declarative secret management (Secretfile as source of truth)
- ✓ Consistent rotation policies across all secrets
- ✓ Multi-region replication support
- ✓ Automatic sync to multiple targets (K8s, CI/CD, etc.)
- ✓ Compliance tracking and reporting
- ✓ Rotation history with audit trail
- ✓ Pre-rotation notifications
- ✓ Automated policy enforcement

### Augmenting Jenkins Credentials

**Current Problem**: Jenkins stores credentials in its internal database, making them difficult to manage, audit, and rotate at scale. Teams have no visibility into which credentials are used where, rotation is manual, and there's no drift detection to ensure credentials match across systems.

**SecretZero Augmentation**: Treat Jenkins as one target among many for secrets defined in SecretZero. Maintain credentials in Jenkins while ensuring they're synchronized with external vaults and properly rotated.

**Example Implementation**:

```yaml
# Secretfile.yml - Jenkins Credentials Augmentation
version: '1.0'

metadata:
  project: ci-infrastructure
  owner: devops-team
  augmentation: jenkins-credentials-orchestration
  description: |
    Use SecretZero to manage Jenkins credentials while syncing to
    external vaults for backup, rotation, and compliance.

variables:
  environment: production
  jenkins_url: "https://jenkins.example.com"

providers:
  jenkins:
    kind: jenkins
    auth:
      kind: token
      config:
        url: "{{ var.jenkins_url }}"
        username: "secretzero-user"
        token: "${JENKINS_API_TOKEN}"
  
  vault:
    kind: vault
    auth:
      kind: token
      config:
        url: "${VAULT_ADDR}"
        token: "${VAULT_TOKEN}"

secrets:
  # Database credentials used in tests
  - name: database_credentials
    kind: templates.db_creds_jenkins
    rotation_period: 90d
    
  # API keys for deployments
  - name: deployment_api_keys
    kind: templates.api_keys_jenkins
    rotation_period: 180d
    
  # SSH keys for git operations
  - name: git_ssh_key
    kind: templates.ssh_key_jenkins
    rotation_period: 365d

templates:
  db_creds_jenkins:
    description: Database credentials for test pipelines
    fields:
      username:
        generator:
          kind: static
          config:
            default: "${DB_TEST_USER}"
      password:
        generator:
          kind: random_password
          config:
            length: 32
            special: true
    targets:
      # Sync to Jenkins as username/password credential
      - provider: jenkins
        kind: jenkins_username_password
        config:
          credential_id: "database-test-credentials"
          description: "Managed by SecretZero"
          scope: "global"
      
      # Backup to Vault for security and audit
      - provider: vault
        kind: vault_kv
        config:
          path: "secret/jenkins/database-credentials"
          mount_point: "secret"

  api_keys_jenkins:
    description: API keys for deployments
    fields:
      docker_registry_token:
        generator:
          kind: static
          config:
            default: "${DOCKER_REGISTRY_TOKEN}"
      aws_access_key:
        generator:
          kind: static
          config:
            default: "${AWS_ACCESS_KEY_ID}"
      aws_secret_key:
        generator:
          kind: static
          config:
            default: "${AWS_SECRET_ACCESS_KEY}"
    targets:
      - provider: jenkins
        kind: jenkins_secret_text
        config:
          credential_id: "docker-registry-token"
          description: "Docker registry token"
          scope: "global"
      
      - provider: jenkins
        kind: jenkins_secret_text
        config:
          credential_id: "aws-credentials"
          description: "AWS credentials"
          scope: "global"
      
      - provider: vault
        kind: vault_kv
        config:
          path: "secret/jenkins/api-keys"

  ssh_key_jenkins:
    description: SSH key for git operations
    fields:
      private_key:
        generator:
          kind: static
          config:
            default: "${GIT_SSH_PRIVATE_KEY}"
      public_key:
        generator:
          kind: static
          config:
            default: "${GIT_SSH_PUBLIC_KEY}"
      passphrase:
        generator:
          kind: random_password
          config:
            length: 16
            special: false
    targets:
      - provider: jenkins
        kind: jenkins_ssh_key
        config:
          credential_id: "git-ssh-key"
          username: "git-deployer"
          description: "SSH key for git operations"
          scope: "global"
      
      - provider: vault
        kind: vault_kv
        config:
          path: "secret/jenkins/ssh-key"

policies:
  enforce_jenkins_security:
    kind: jenkins_credential_policy
    enabled: true
    rules:
      - validate_credential_scope
      - validate_credential_description
      - ensure_backup_in_vault
      - enforce_rotation_schedule
```

**Usage**:

```bash
# 1. Create Secretfile.yml with Jenkins as provider
# (Use configuration above)

# 2. Set environment variables with current secret values
export JENKINS_API_TOKEN="..."
export VAULT_ADDR="https://vault.example.com"
export VAULT_TOKEN="..."
export DB_TEST_USER="testuser"
# ... etc for other credentials

# 3. Validate and sync
secretzero validate
secretzero sync

# 4. Check Jenkins credentials are updated
curl -s -u admin:token https://jenkins.example.com/credentials/api/json | jq

# 5. Verify backup in Vault
vault kv get secret/jenkins/database-credentials

# 6. Rotate credentials across Jenkins and Vault simultaneously
secretzero rotate

# 7. Audit trail shows all changes
secretzero lockfile show

# 8. Detect drift (if Jenkins credentials change outside SecretZero)
secretzero drift --check
```

**Benefits**:

- ✓ Jenkins credentials remain in Jenkins (no application changes)
- ✓ Automatic backup to Vault for disaster recovery
- ✓ Unified rotation policy across Jenkins and Vault
- ✓ Audit trail of all credential changes
- ✓ Drift detection (alerts if credentials manually changed in Jenkins)
- ✓ Compliance reporting
- ✓ Automated rotation reduces manual credential management

### Augmenting Kubernetes Secrets

**Current Problem**: You're using Kubernetes secrets for application configuration, but they're only encrypted at rest (by default), not in transit. There's no centralized rotation mechanism, no audit trail of changes, and secrets can only be accessed from within the cluster. Bootstrapping new clusters is manual and error-prone.

**SecretZero Augmentation**: Maintain Kubernetes secrets while layering in external vaults for backup, automatic rotation, and cluster bootstrap automation.

**Example Implementation**:

```yaml
# Secretfile.yml - Kubernetes Secrets Augmentation
version: '1.0'

metadata:
  project: platform
  owner: platform-team
  augmentation: kubernetes-secrets-with-rotation
  description: |
    Augment Kubernetes secrets with centralized vault backup,
    automated rotation, and cluster bootstrap automation.

variables:
  namespace: production
  app_name: myapp
  vault_addr: "${VAULT_ADDR}"
  clusters:
    - name: us-east-1
      context: arn:aws:eks:us-east-1:123456789012:cluster/prod-east
    - name: eu-west-1
      context: arn:aws:eks:eu-west-1:123456789012:cluster/prod-eu

providers:
  vault:
    kind: vault
    auth:
      kind: token
      config:
        url: "{{ var.vault_addr }}"
        token: "${VAULT_TOKEN}"
  
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient

secrets:
  # Application database credentials
  - name: database_credentials
    kind: templates.db_creds_k8s
    rotation_period: 90d
    rotation_policy:
      grace_period: 7d
      rolling_restart: true

  # API credentials for external services
  - name: external_api_credentials
    kind: templates.external_apis
    rotation_period: 180d

  # TLS certificates (manual rotation)
  - name: tls_certificates
    kind: templates.tls_certs
    rotation_period: 365d

  # ConfigMaps for non-secret configuration
  - name: app_configuration
    kind: templates.app_config

templates:
  db_creds_k8s:
    description: Database credentials for Kubernetes pods
    fields:
      host:
        generator:
          kind: static
          config:
            default: "postgresql.rds.amazonaws.com"
      port:
        generator:
          kind: static
          config:
            default: "5432"
      database:
        generator:
          kind: static
          config:
            default: "productiondb"
      username:
        generator:
          kind: static
          config:
            default: "dbuser"
      password:
        generator:
          kind: random_password
          config:
            length: 32
            special: true
    targets:
      # Primary target: Kubernetes secret in all clusters
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: "{{ var.namespace }}"
          secret_name: "database-credentials"
          secret_type: Opaque
          labels:
            app: "{{ var.app_name }}"
            rotation: "managed"
            backup: "vault"
      
      # Backup: Vault for disaster recovery
      - provider: vault
        kind: vault_kv
        config:
          path: "secret/kubernetes/{{ var.namespace }}/database"
          mount_point: "secret"

  external_apis:
    description: Credentials for external API services
    fields:
      stripe_api_key:
        generator:
          kind: static
          config:
            default: "${STRIPE_KEY}"
      sendgrid_api_key:
        generator:
          kind: static
          config:
            default: "${SENDGRID_KEY}"
      twilio_auth_token:
        generator:
          kind: static
          config:
            default: "${TWILIO_TOKEN}"
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: "{{ var.namespace }}"
          secret_name: "external-api-credentials"
          secret_type: Opaque
          labels:
            app: "{{ var.app_name }}"
      
      - provider: vault
        kind: vault_kv
        config:
          path: "secret/kubernetes/{{ var.namespace }}/api-keys"

  tls_certs:
    description: TLS certificates for ingress
    fields:
      tls_crt:
        generator:
          kind: static
          config:
            default: "${TLS_CRT}"
      tls_key:
        generator:
          kind: static
          config:
            default: "${TLS_KEY}"
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: "{{ var.namespace }}"
          secret_name: "tls-certificate"
          secret_type: "kubernetes.io/tls"
          labels:
            cert-rotation: "manual"
      
      - provider: vault
        kind: vault_kv
        config:
          path: "secret/kubernetes/{{ var.namespace }}/tls"

  app_config:
    description: Non-secret application configuration
    fields:
      log_level:
        generator:
          kind: static
          config:
            default: "info"
      environment:
        generator:
          kind: static
          config:
            default: "production"
      feature_flags:
        generator:
          kind: static
          config:
            default: '{"feature_a": true, "feature_b": false}'
    targets:
      - provider: kubernetes
        kind: kubernetes_configmap
        config:
          namespace: "{{ var.namespace }}"
          configmap_name: "app-configuration"

bootstrap:
  # Configuration for new cluster provisioning
  on_cluster_provision:
    - name: create_namespace
      action: kubectl
      command: "namespace create {{ var.namespace }}"
    
    - name: create_secrets
      action: sync_all
      description: "Sync all secrets from Vault to new cluster"
    
    - name: verify_secrets
      action: test
      description: "Verify all secrets deployed correctly"

policies:
  kubernetes_secret_security:
    kind: kubernetes_security
    enabled: true
    rules:
      - name: require_encryption_at_rest
        value: true
      - name: require_backup_in_vault
        value: true
      - name: require_rotation_period
        value: true
      - name: enforce_rbac_labels
        value: true
```

**Usage**:

```bash
# 1. Create Secretfile.yml with Kubernetes as target
# (Use configuration above)

# 2. Sync secrets to cluster
secretzero sync

# 3. Verify secrets created in Kubernetes
kubectl get secrets -n production
kubectl describe secret database-credentials -n production

# 4. View secret in Vault backup
vault kv get secret/kubernetes/production/database

# 5. Rotate secrets in both Kubernetes and Vault
secretzero rotate

# 6. Kubernetes pods will pick up rotated secrets automatically
# (if using rolling restart strategy)
kubectl rollout restart deployment myapp -n production

# 7. Bootstrap new cluster automatically
# Create new cluster context
kubectx dev-cluster

# Sync all secrets to new cluster
secretzero sync --context dev-cluster

# Verify cluster provisioning
kubectl get secrets --context dev-cluster -n production

# 8. Audit trail shows all changes
secretzero lockfile show database_credentials
```

**Benefits**:

- ✓ Kubernetes secrets continue to work as before
- ✓ Automatic backup to Vault (disaster recovery)
- ✓ Centralized rotation policy across all clusters
- ✓ Automated cluster bootstrap
- ✓ Audit trail of secret changes
- ✓ Drift detection (alerts if secrets manually changed)
- ✓ Rolling restart strategy for secret updates
- ✓ Multi-cluster support

## Getting Started with Augmentation

SecretZero augmentation works best when introduced gradually. Here's a practical approach:

### Phase 1: Assessment & Planning

```bash
# 1. Inventory your current secrets
cat > inventory-current-secrets.sh << 'EOF'
#!/bin/bash
echo "Current Secret Systems"
echo "====================="

# Check for .env files
echo "Environment files:"
find . -name ".env*" -not -path "*/node_modules/*" | wc -l

# Check for Kubernetes secrets
echo "Kubernetes secrets:"
kubectl get secrets --all-namespaces 2>/dev/null | wc -l

# Check for AWS Secrets Manager
echo "AWS Secrets Manager secrets:"
aws secretsmanager list-secrets --query 'length(SecretList)' 2>/dev/null

# Check for Vault
echo "Vault secrets:"
vault kv list -format=json secret/ 2>/dev/null | jq 'length'
EOF

chmod +x inventory-current-secrets.sh
./inventory-current-secrets.sh

# 2. Document your current rotation practices
cat > rotation-practices.md << 'EOF'
# Current Rotation Practices

## .env Secrets
- Rotation frequency: Manual, ~quarterly
- Procedure: Developer manually updates
- Audit trail: Git history only
- Issues: Error-prone, inconsistent

## Kubernetes Secrets
- Rotation frequency: As needed
- Procedure: Manual kubectl apply
- Audit trail: Limited
- Issues: Hard to track across clusters

## AWS Secrets
- Rotation frequency: Varies
- Procedure: Manual via console or CLI
- Audit trail: CloudTrail
- Issues: No enforcement, inconsistent policy

## Action Items
- [ ] Identify critical secrets needing rotation
- [ ] Document current rotation schedule
- [ ] Plan SecretZero augmentation targets
EOF

# 3. Identify pain points
cat > pain-points.txt << 'EOF'
Identify which of these apply:
- [ ] Secrets scattered across multiple systems (no unified view)
- [ ] Manual rotation is tedious and error-prone
- [ ] No audit trail of secret changes
- [ ] Difficult to bootstrap new environments
- [ ] Hard to enforce consistent rotation policies
- [ ] Limited compliance reporting
- [ ] Team overhead managing secrets
- [ ] No automated drift detection
EOF
```

### Phase 2: Pilot Augmentation (Non-Critical Service)

```bash
# 1. Select a non-critical service to augment
# (e.g., internal tool, staging environment service)

SERVICE="reporting-service"

# 2. Create Secretfile.yml for the service
cat > "${SERVICE}/Secretfile.yml" << 'YAML'
version: '1.0'

metadata:
  project: reporting-service
  owner: platform-team
  augmentation_phase: pilot
  description: "Pilot augmentation with centralized rotation and audit"

variables:
  environment: staging
  service_name: reporting-service

providers:
  vault:
    kind: vault
    auth:
      kind: token
      config:
        url: "${VAULT_ADDR}"
        token: "${VAULT_TOKEN}"
  
  local:
    kind: local

secrets:
  - name: database_password
    kind: random_password
    rotation_period: 90d
    config:
      length: 32
      special: true
    targets:
      # Backup in vault
      - provider: vault
        kind: vault_kv
        config:
          path: "secret/services/{{ var.service_name }}/database"
      # Maintain in .env for backward compat
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true

  - name: api_key
    kind: static
    rotation_period: 180d
    config:
      default: "${API_KEY_PILOT}"
    targets:
      - provider: vault
        kind: vault_kv
        config:
          path: "secret/services/{{ var.service_name }}/api-key"
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true
YAML

# 3. Validate configuration
cd "${SERVICE}"
secretzero validate

# 4. Dry run to see what will happen
secretzero sync --dry-run

# 5. Perform augmentation
secretzero sync

# 6. Monitor service for 48 hours
cat > monitor-pilot.sh << 'EOF'
#!/bin/bash
END_TIME=$(($(date +%s) + 172800))  # 48 hours

while [ $(date +%s) -lt $END_TIME ]; do
  echo "=== Monitoring $(date) ==="
  
  # Health check
  curl -f http://reporting-service/health || echo "WARNING: Health check failed"
  
  # Check error logs
  ERROR_COUNT=$(journalctl -u reporting-service --since "1 hour ago" 2>/dev/null | grep -c ERROR || echo 0)
  echo "Errors in past hour: $ERROR_COUNT"
  
  # Verify secrets rotated
  vault kv get secret/services/reporting-service/database
  
  sleep 3600  # Check hourly
done
EOF

chmod +x monitor-pilot.sh
./monitor-pilot.sh &

# 7. Document lessons learned
cat > PILOT_LESSONS.md << 'EOF'
# Pilot Augmentation Lessons Learned

## What Worked
- Secretfile validation is fast and comprehensive
- Zero downtime during augmentation
- Vault backup is transparent to application
- Rotation tracking is excellent

## Challenges
- [ ] Document any issues found

## Improvements
- [ ] List suggestions for full deployment

## Recommendation
- [ ] Ready for production rollout? (yes/no)
EOF
```

### Phase 3: Expand to Critical Services

```bash
# 1. Apply lessons from pilot
# - Update documentation
# - Adjust rotation schedules
# - Add additional targets if needed

# 2. Augment high-value services incrementally
for service in api-gateway authentication database-proxy; do
  echo "Augmenting $service..."
  cp reporting-service/Secretfile.yml "$service/Secretfile.yml"
  sed -i "s/reporting-service/${service}/g" "$service/Secretfile.yml"
  
  cd "$service"
  secretzero validate
  secretzero sync
  cd ..
done

# 3. Cross-service validation
# Verify all services are using consistent policies
secretzero list --all --show-policies

# 4. Enable drift detection across services
secretzero drift --detect-all --alert-on-changes
```

### Phase 4: Continuous Improvement

```bash
# 1. Monitor augmentation effectiveness
cat > augmentation-metrics.sh << 'EOF'
#!/bin/bash

echo "SecretZero Augmentation Metrics"
echo "==============================="
echo ""

# Count augmented services
SERVICE_COUNT=$(find . -name "Secretfile.yml" | wc -l)
echo "Services augmented: $SERVICE_COUNT"

# Track rotation compliance
echo "Rotation compliance:"
secretzero list --all --show-compliance

# Monitor rotation history
echo "Recent rotations:"
secretzero lockfile show --last 10

# Check for drift
echo "Drift detection:"
secretzero drift --check-all

# Compliance status
echo "Compliance frameworks enabled:"
secretzero policy --list-frameworks
EOF

chmod +x augmentation-metrics.sh
./augmentation-metrics.sh

# 2. Document augmentation procedures
cat > docs/AUGMENTATION_PROCEDURES.md << 'EOF'
# SecretZero Augmentation Procedures

## Adding a Service to SecretZero

1. **Create Secretfile.yml** in service directory
2. **Validate** configuration: `secretzero validate`
3. **Dry-run** to preview changes: `secretzero sync --dry-run`
4. **Execute** sync: `secretzero sync`
5. **Monitor** service for 24-48 hours
6. **Document** any special handling needed

## Regular Maintenance

- **Weekly**: Check rotation status (`secretzero rotate --dry-run`)
- **Monthly**: Rotate secrets (`secretzero rotate`)
- **Quarterly**: Compliance audit (`secretzero compliance --check`)
- **Annually**: Disaster recovery test

## Adding New Secrets to Existing Service

```bash
vim Secretfile.yml
# Add new secret definition

# Validate
secretzero validate

# Sync
secretzero sync

# Verify
secretzero list
```

## Team Responsibilities

- **SecretZero Admin**: Manages global policies, documentation
- **Service Owners**: Maintain service Secretfile.yml, rotation schedules
- **Security Team**: Compliance audits, incident response
- **Platform Team**: Infrastructure, provider access, deployment automation
EOF

# 3. Set up continuous compliance checks
cat > .github/workflows/secret-compliance.yml << 'EOF'
name: Secret Compliance Check

on:
  - push
  - schedule:
      - cron: '0 0 * * 0'  # Weekly

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Install SecretZero
        run: pip install secretzero
      
      - name: Validate Secretfiles
        run: |
          for file in $(find . -name "Secretfile.yml"); do
            secretzero validate -f $file
          done
      
      - name: Check Compliance
        run: |
          secretzero policy --check --framework soc2
          secretzero policy --check --framework pci-dss
      
      - name: Rotation Status
        run: secretzero rotate --dry-run --report
EOF
```

## Best Practices for Augmentation

1. **Start with a Non-Critical Service** - Augment an internal tool or staging service first. This lets you learn the workflow, document procedures, and build confidence without production risk.

2. **Maintain Existing Systems** - Augmentation means your current secret storage stays operational. Don't remove old systems immediately. Let SecretZero sit alongside them, proving value before you rely on it exclusively.

3. **Declarative Secrets** - Create a Secretfile.yml as the source of truth for each service. Keep it in version control. Review changes like code reviews. This provides auditability and repeatability.

4. **Universal Providers** - Use a backup provider (Vault, AWS Secrets Manager, etc.) even if your primary secret store is Kubernetes or Jenkins. This provides disaster recovery without changing your primary systems.

5. **Consistent Rotation Policy** - Define your rotation periods in Secretfile.yml once and enforce them everywhere. No more manual rotation schedules. Make rotation automatic and auditable.

6. **Test Configuration Before Production** - Always run `secretzero validate` before syncing. Use `--dry-run` to see what will happen. Test in staging/development first.

7. **Gradual Service Adoption** - Augment 2-3 services first. Once your team is comfortable, augment more. Have each service owner maintain their own Secretfile.yml.

8. **Leverage Drift Detection** - Use `secretzero drift --check` regularly to detect when secrets change outside SecretZero. This catches accidental manual changes and security incidents.

9. **Automate Compliance Checks** - Run SecretZero compliance checks in CI/CD pipelines. Catch policy violations before they reach production. Generate compliance reports regularly.

10. **Monitor Rotation Status** - Set up regular reports on secret rotation status. Know which secrets are due for rotation. Have alerts for secrets approaching expiration. Automate this with cron jobs or CI/CD schedules.

## Troubleshooting Augmentation Issues

### Secretfile Validation Failed

**Problem**: `secretzero validate` fails with configuration errors

**Solution**:

```bash
# Get detailed error messages
secretzero validate --verbose

# Common issues and fixes:
# 1. Invalid YAML syntax
yamllint Secretfile.yml

# 2. Provider not configured
# Ensure provider is defined at top level and referenced in targets
secretzero test --provider vault

# 3. Missing required fields in secret definition
# All secrets need: name, kind, targets with provider and kind

# Fix configuration and retry
vim Secretfile.yml
secretzero validate
```

### Sync Fails Due to Provider Issues

**Problem**: `secretzero sync` fails with provider connection errors

**Solution**:

```bash
# Verify provider connectivity
secretzero test

# Check authentication credentials
# For AWS:
aws sts get-caller-identity

# For Vault:
vault token lookup

# For Kubernetes:
kubectl auth can-i get secrets

# Fix credentials and retry
secretzero sync
```

### Secrets Not Syncing to All Targets

**Problem**: Secret exists in one target but not another

**Solution**:

```bash
# Check specific secret status
secretzero list --secret database_password

# Verify target configuration
secretzero list --show-targets

# Check target-specific errors
secretzero sync --verbose --secret database_password

# Verify target is accessible:
# For Kubernetes:
kubectl get secrets -n production

# For Vault:
vault kv list secret/production/myapp

# For AWS Secrets Manager:
aws secretsmanager get-secret-value --secret-id production/myapp/db-password
```

### Rotation Not Executing

**Problem**: Secrets not rotating on schedule

**Solution**:

```bash
# Check rotation schedule
secretzero rotate --dry-run

# Verify rotation is enabled for secret
secretzero list --secret database_password --show-policy

# Check rotation policy for errors
secretzero policy --check --show-errors

# Manually trigger rotation for testing
secretzero rotate --force

# Verify rotation completed
secretzero lockfile show database_password
```

### Drift Detected Between Systems

**Problem**: `secretzero drift` shows secrets differ from Secretfile

**Solution**:

```bash
# View drift details
secretzero drift --check --show-details

# Two options:

# Option 1: Remediate drift (reset to Secretfile)
secretzero sync --force-overwrite

# Option 2: Update Secretfile to match current state
# Export current secret values
aws secretsmanager get-secret-value --secret-id production/myapp/secret

# Update Secretfile.yml
vim Secretfile.yml

# Validate and sync
secretzero validate
secretzero sync
```

### Provider Credentials Expired

**Problem**: Sync or rotation fails with authentication errors

**Solution**:

```bash
# Refresh credentials for your environment:

# AWS:
aws sso login --profile myprofile
export AWS_PROFILE=myprofile

# Vault:
vault login -method=oidc

# Kubernetes:
aws eks update-kubeconfig --name myc cluster

# GitHub:
gh auth login

# Then retry:
secretzero sync
```

## Real-World Augmentation Example

Here's a practical example of augmenting a production service that currently uses scattered secret storage:

**Current State**:
- Database credentials in `.env` file
- API keys manually managed in Vault
- CI/CD secrets stored in GitHub Actions
- SSH keys for deployments scattered across team members

**Goal**: Centralize secret management with SecretZero while keeping existing systems running

```yaml
# Secretfile.yml - Production App Augmentation
version: '1.0'

metadata:
  project: ecommerce-api
  owner: backend-team
  augmentation_phase: pilot
  description: |
    Augment production ecommerce API with centralized secret
    management, automated rotation, and compliance tracking.

variables:
  environment: production
  app_name: ecommerce-api
  aws_region: us-east-1

providers:
  aws:
    kind: aws
    auth:
      kind: ambient
      config:
        region: "{{ var.aws_region }}"
  
  vault:
    kind: vault
    auth:
      kind: token
      config:
        url: "${VAULT_ADDR}"
        token: "${VAULT_TOKEN}"
  
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient
  
  local:
    kind: local

secrets:
  # Existing .env database credentials
  - name: database
    kind: templates.db_credentials
    rotation_period: 90d
    rotation_policy:
      grace_period: 7d
      before_expiry_notify: 14d
  
  # Existing Vault API keys
  - name: external_apis
    kind: templates.api_credentials
    rotation_period: 180d
  
  # SSH deployment keys
  - name: deployment_keys
    kind: templates.ssh_keys
    rotation_period: 365d
  
  # GitHub/GitLab access tokens
  - name: git_tokens
    kind: static
    rotation_period: 90d
    config:
      default: "${GIT_TOKEN}"

templates:
  db_credentials:
    description: PostgreSQL database credentials
    fields:
      hostname:
        generator:
          kind: static
          config:
            default: "postgres.c.us-east-1.rds.amazonaws.com"
      port:
        generator:
          kind: static
          config:
            default: "5432"
      database:
        generator:
          kind: static
          config:
            default: "ecommerce_prod"
      username:
        generator:
          kind: static
          config:
            default: "${DB_USER}"
      password:
        generator:
          kind: static
          config:
            default: "${DB_PASSWORD}"
    targets:
      # Maintain in .env for local dev
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true
      
      # Backup in AWS
      - provider: aws
        kind: secrets_manager
        config:
          name: "{{ var.environment }}/{{ var.app_name }}/database"
          description: "PostgreSQL credentials (auto-rotated)"
          tags:
            Owner: backend-team
            DataClassification: sensitive
      
      # Sync to Kubernetes
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: production
          secret_name: database-credentials
          secret_type: Opaque
      
      # Keep in Vault for legacy systems
      - provider: vault
        kind: vault_kv
        config:
          path: "secret/ecommerce/database"

  api_credentials:
    description: Third-party API credentials
    fields:
      stripe_key:
        generator:
          kind: static
          config:
            default: "${STRIPE_API_KEY}"
      paypal_client_id:
        generator:
          kind: static
          config:
            default: "${PAYPAL_CLIENT_ID}"
      paypal_secret:
        generator:
          kind: static
          config:
            default: "${PAYPAL_SECRET}"
      sendgrid_api_key:
        generator:
          kind: static
          config:
            default: "${SENDGRID_KEY}"
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true
      
      - provider: aws
        kind: secrets_manager
        config:
          name: "{{ var.environment }}/{{ var.app_name }}/api-keys"
      
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: production
          secret_name: external-api-credentials

  ssh_keys:
    description: SSH keys for deployments
    fields:
      private_key:
        generator:
          kind: static
          config:
            default: "${DEPLOY_SSH_PRIVATE_KEY}"
      public_key:
        generator:
          kind: static
          config:
            default: "${DEPLOY_SSH_PUBLIC_KEY}"
      passphrase:
        generator:
          kind: random_password
          config:
            length: 24
            special: false
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: "{{ var.environment }}/{{ var.app_name }}/ssh-key"
          description: "Deployment SSH key"
      
      - provider: vault
        kind: vault_kv
        config:
          path: "secret/ecommerce/deploy-ssh-key"

policies:
  enforce_rotation:
    kind: rotation
    enabled: true
    require_rotation_period: true
    max_age: 90d
    severity: error
    
  compliance_soc2:
    kind: compliance
    enabled: true
    frameworks:
      - soc2
    required_metadata:
      - owner
      - data_classification
      - rotation_period
```

**Augmentation Execution**:

```bash
# 1. Collect current secret values
export DB_USER="ecommerce_user"
export DB_PASSWORD="current_password_from_dotenv"
export STRIPE_API_KEY="sk_live_..."
export PAYPAL_CLIENT_ID="..."
export PAYPAL_SECRET="..."
export SENDGRID_KEY="..."
export GIT_TOKEN="ghp_..."
export DEPLOY_SSH_PRIVATE_KEY="$(cat ~/.ssh/deploy_key)"
export DEPLOY_SSH_PUBLIC_KEY="$(cat ~/.ssh/deploy_key.pub)"

# 2. Create Secretfile.yml in service directory
# (Use configuration above)

# 3. Validate configuration
secretzero validate

# 4. Dry-run to preview changes
secretzero sync --dry-run

# Output shows:
# - Will maintain .env file (no breaking changes)
# - Will back up to AWS Secrets Manager
# - Will sync to Kubernetes
# - Will update Vault

# 5. Execute augmentation
secretzero sync

# Result: All systems now have secrets, audit trail started

# 6. Verify augmentation successful
# Check .env still works
grep DB_PASSWORD .env

# Check AWS backup
aws secretsmanager list-secrets \
  --query 'SecretList[?starts_with(Name, `production/ecommerce`)].Name'

# Check K8s deployment can see secrets
kubectl get secret database-credentials -n production

# Check Vault updated
vault kv get secret/ecommerce/database

# 7. Monitor application for 48 hours
kubectl logs -n production -l app=ecommerce-api --tail=100

# 8. Schedule automated rotation
# Rotation will now happen automatically on schedule

# 9. Future: Update application to use AWS Secrets Manager directly
# No need to read .env file

# 10. Eventually: Remove local provider target
# (But keep others for redundancy)
```

**Results After Augmentation**:

✓ No application code changes (still uses .env)  
✓ Secrets backed up in AWS (disaster recovery)  
✓ Secrets replicated to Kubernetes (failover support)  
✓ Secrets maintained in Vault (legacy system compatibility)  
✓ Automatic rotation on 90-day schedule  
✓ Complete audit trail of changes  
✓ Compliance reports generated automatically  
✓ Drift detection alerts if secrets change outside SecretZero

## Summary

SecretZero augmentation is about **enhancing what you already have**, not replacing it. Rather than a disruptive migration, you get:

- **Gradual Adoption**: Start with one service, expand at your own pace
- **No Breaking Changes**: Existing systems continue to work
- **Increased Visibility**: Unified view of all secrets across systems
- **Automated Lifecycle**: Rotations, audits, and compliance happen automatically
- **Peace of Mind**: Backups, drift detection, and audit trails
- **Team Empowerment**: Service owners maintain their own Secretfiles

The goal is to layer SecretZero capabilities **on top of** your existing secret management infrastructure, solving problems those systems weren't designed to handle.

## Next Steps

1. **Assess Your Current State** - Use the inventory scripts above to understand what you have
2. **Choose a Pilot Service** - Pick something non-critical to learn with
3. **Create a Secretfile.yml** - Define your secrets declaratively
4. **Sync and Monitor** - Roll out gradually while monitoring
5. **Iterate and Expand** - Learn from each service, apply lessons to the next

Once you've successfully augmented 2-3 services, consider expanding to:

- **[Multi-Cloud Setup](multi-cloud.md)** - Sync across AWS, Azure, GCP simultaneously
- **[Compliance Automation](compliance.md)** - Automated compliance reporting (SOC2, PCI-DSS, ISO27001)
- **[GitHub Actions Integration](github-actions.md)** - Secrets synced directly to CI/CD workflows
- **[Disaster Recovery](disaster-recovery.md)** - Automated backup and restore procedures
