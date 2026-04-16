# Kubernetes Secret Management

## Problem Statement

Managing secrets in Kubernetes clusters presents several operational challenges:

- Manual `kubectl create secret` commands are error-prone and lack audit trails
- Secrets are often stored in Git repositories (security risk)
- No standardized way to sync secrets across multiple namespaces
- Difficult to manage different secret types (Opaque, TLS, Docker registry, etc.)
- Secret rotation requires manual intervention and coordination
- No integration with External Secrets Operator for GitOps workflows
- Tracking which secrets exist and their last update is challenging

**SecretZero solves this** by providing declarative Kubernetes secret management with native support for all secret types, multi-namespace deployments, External Secrets Operator integration, and automated rotation policies.

## Prerequisites

- SecretZero installed with Kubernetes support: `pip install secretzero[kubernetes]`
- Kubernetes cluster access with appropriate RBAC permissions
- `kubectl` configured with valid kubeconfig file
- For External Secrets Operator: ESO installed in the cluster
- For TLS secrets: Certificates and keys (or cert-manager integration)

## Authentication Setup

### 1. Kubeconfig-Based Authentication

SecretZero uses your existing kubeconfig file:

```bash
# Verify cluster access
kubectl cluster-info
kubectl get namespaces

# Check current context
kubectl config current-context

# List available contexts
kubectl config get-contexts
```

### 2. In-Cluster Authentication

When running SecretZero inside a Kubernetes pod:

```yaml
providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient
      config:
        in_cluster: true
```

### 3. Required RBAC Permissions

Create a Role or ClusterRole with necessary permissions:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: secretzero-manager
  namespace: default
rules:
  - apiGroups: [""]
    resources: ["secrets"]
    verbs: ["get", "list", "create", "update", "patch", "delete"]
  - apiGroups: [""]
    resources: ["namespaces"]
    verbs: ["get", "list"]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: secretzero-manager-binding
  namespace: default
subjects:
  - kind: ServiceAccount
    name: secretzero
    namespace: default
roleRef:
  kind: Role
  name: secretzero-manager
  apiGroup: rbac.authorization.k8s.io
```

## Configuration

### Basic Opaque Secrets

Create `Secretfile.yml`:

```yaml
version: '1.0'

metadata:
  project: my-app
  owner: platform-team

variables:
  namespace: default
  app_name: myapp

providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient
      config:
        # Use default kubeconfig location
        kubeconfig: ~/.kube/config
        # Optional: specify context
        # context: production-cluster

secrets:
  # Database password
  - name: database_password
    kind: random_password
    config:
      length: 32
      special: true
      exclude_characters: '"@/\`'
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: ${namespace}
          secret_name: postgres-credentials
          data_key: password
          secret_type: Opaque
          labels:
            app: ${app_name}
            component: database
            managed-by: secretzero
          annotations:
            description: PostgreSQL database password
            last-updated: "{{ timestamp }}"

  # API Key
  - name: api_key
    kind: random_string
    config:
      length: 32
      charset: hex
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: ${namespace}
          secret_name: app-secrets
          data_key: api-key
          labels:
            app: ${app_name}

  # Redis password
  - name: redis_password
    kind: random_password
    config:
      length: 24
      special: false
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: ${namespace}
          secret_name: app-secrets  # Same secret object
          data_key: redis-password
          labels:
            app: ${app_name}
```

### TLS Certificates

```yaml
secrets:
  # TLS certificate for ingress
  - name: ingress_tls
    kind: templates.tls_certificate

templates:
  tls_certificate:
    description: TLS certificate and private key
    fields:
      tls.crt:
        description: TLS certificate
        generator:
          kind: static
          config:
            # In production, use cert-manager or real certificates
            default: |
              -----BEGIN CERTIFICATE-----
              MIIDazCCAlOgAwIBAgIUXxZ9vKKHGhXXXXXXXXXX...
              -----END CERTIFICATE-----
      tls.key:
        description: TLS private key
        generator:
          kind: static
          config:
            # Store securely or use cert-manager
            default: |
              -----BEGIN PRIVATE KEY-----
              MIIEvgIBADANBgkqhkiG9w0BAQEFXXXXXXXXXXXX...
              -----END PRIVATE KEY-----
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: ${namespace}
          secret_name: myapp-tls
          secret_type: kubernetes.io/tls
          labels:
            app: ${app_name}
            type: tls
            cert-manager.io/issuer-name: letsencrypt-prod
          annotations:
            description: TLS certificate for ${app_name}.example.com
```

### Docker Registry Credentials

```yaml
secrets:
  - name: docker_registry_credentials
    kind: templates.docker_registry

templates:
  docker_registry:
    description: Docker registry authentication
    fields:
      .dockerconfigjson:
        description: Docker config JSON with registry credentials
        generator:
          kind: static
          config:
            default: |
              {
                "auths": {
                  "registry.example.com": {
                    "username": "robot-account",
                    "password": "secret-token",
                    "email": "robot@example.com",
                    "auth": "cm9ib3QtYWNjb3VudDpzZWNyZXQtdG9rZW4="
                  }
                }
              }
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: ${namespace}
          secret_name: registry-credentials
          secret_type: kubernetes.io/dockerconfigjson
          labels:
            app: ${app_name}
            type: registry
          annotations:
            description: Docker registry credentials
```

### Basic Authentication

```yaml
secrets:
  - name: basic_auth_credentials
    kind: templates.basic_auth

templates:
  basic_auth:
    description: HTTP basic authentication
    fields:
      username:
        description: Username for basic auth
        generator:
          kind: static
          config:
            default: admin
      password:
        description: Password for basic auth
        generator:
          kind: random_password
          config:
            length: 24
            special: true
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: ${namespace}
          secret_name: basic-auth-credentials
          secret_type: kubernetes.io/basic-auth
          labels:
            app: ${app_name}
            type: auth
          annotations:
            description: Basic auth for admin panel
```

### SSH Keys

```yaml
secrets:
  - name: deploy_ssh_key
    kind: templates.ssh_key

templates:
  ssh_key:
    description: SSH key for Git operations
    fields:
      ssh-privatekey:
        description: SSH private key
        generator:
          kind: static
          config:
            # Generate with: ssh-keygen -t ed25519 -C "deploy@example.com"
            default: |
              -----BEGIN OPENSSH PRIVATE KEY-----
              b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAA...
              -----END OPENSSH PRIVATE KEY-----
      ssh-publickey:
        description: SSH public key
        generator:
          kind: static
          config:
            default: ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... deploy@example.com
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: ${namespace}
          secret_name: git-deploy-key
          secret_type: kubernetes.io/ssh-auth
          labels:
            app: ${app_name}
            type: deploy-key
          annotations:
            description: SSH key for Git deployments
```

## Step-by-Step Instructions

### 1. Validate Configuration

```bash
secretzero validate -f Secretfile.yml

# Expected output:
# ✓ Configuration is valid
# ✓ All providers configured correctly
# ✓ 5 secrets defined
# ✓ 5 targets configured
```

### 2. Test Kubernetes Connectivity

```bash
secretzero test

# Expected output:
# ✓ Testing Kubernetes provider...
# ✓ Cluster connection successful
# ✓ Namespace 'default' exists
# ✓ RBAC permissions verified
# ✓ All providers ready
```

### 3. Preview Secret Creation

```bash
secretzero sync --dry-run

# Expected output:
# [DRY RUN] Would create:
#   ✓ database_password → Secret (postgres-credentials) in namespace default
#   ✓ api_key → Secret (app-secrets) in namespace default
#   ✓ redis_password → Secret (app-secrets) in namespace default
#   ✓ ingress_tls → Secret (myapp-tls) in namespace default
#   ✓ docker_registry_credentials → Secret (registry-credentials) in namespace default
```

### 4. Create Secrets in Kubernetes

```bash
secretzero sync

# Expected output:
# ✓ Generated database_password
# ✓ Created Secret: postgres-credentials (data key: password)
# ✓ Generated api_key
# ✓ Created Secret: app-secrets (data key: api-key)
# ✓ Generated redis_password
# ✓ Updated Secret: app-secrets (data key: redis-password)
# ✓ Created Secret: myapp-tls
# ✓ Created Secret: registry-credentials
# ✓ Updated .gitsecrets.lock
```

### 5. Verify Secrets in Cluster

```bash
# List secrets in namespace
kubectl get secrets -n default

# View secret details
kubectl describe secret postgres-credentials -n default

# Check secret data keys (base64 encoded)
kubectl get secret postgres-credentials -n default -o yaml

# Decode a secret value
kubectl get secret postgres-credentials -n default -o jsonpath='{.data.password}' | base64 -d
```

## Using Secrets in Applications

### Environment Variables

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: myapp
  namespace: default
spec:
  containers:
    - name: app
      image: myapp:latest
      env:
        # Single environment variable from secret
        - name: DATABASE_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-credentials
              key: password
        
        - name: API_KEY
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: api-key
        
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: redis-password
```

### Environment Variables from All Keys

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: myapp
spec:
  containers:
    - name: app
      image: myapp:latest
      envFrom:
        # Load all keys from secret as environment variables
        - secretRef:
            name: app-secrets
```

### Volume Mounts

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: myapp
spec:
  containers:
    - name: app
      image: myapp:latest
      volumeMounts:
        # Mount secret as files
        - name: db-credentials
          mountPath: /etc/secrets/database
          readOnly: true
        
        # Mount TLS certificates
        - name: tls-certs
          mountPath: /etc/tls
          readOnly: true
  
  volumes:
    - name: db-credentials
      secret:
        secretName: postgres-credentials
        items:
          - key: password
            path: password.txt
    
    - name: tls-certs
      secret:
        secretName: myapp-tls
        items:
          - key: tls.crt
            path: tls.crt
          - key: tls.key
            path: tls.key
```

### Ingress with TLS

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp-ingress
  namespace: default
spec:
  tls:
    - hosts:
        - myapp.example.com
      secretName: myapp-tls  # TLS secret created by SecretZero
  rules:
    - host: myapp.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: myapp
                port:
                  number: 80
```

### Image Pull Secrets

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: myapp
spec:
  containers:
    - name: app
      image: registry.example.com/myapp:latest
  
  # Use Docker registry credentials
  imagePullSecrets:
    - name: registry-credentials
```

## Advanced Scenarios

### Multi-Namespace Deployment

Deploy the same secrets across multiple namespaces:

```yaml
version: '1.0'

variables:
  namespaces:
    - production
    - staging
    - development

providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient

secrets:
  # Shared database admin password
  - name: postgres_admin_password
    kind: random_password
    one_time: true  # Generate once, use everywhere
    config:
      length: 32
      special: true
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: production
          secret_name: postgres-admin
          data_key: password
          labels:
            environment: production
            managed-by: secretzero
      
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: staging
          secret_name: postgres-admin
          data_key: password
          labels:
            environment: staging
            managed-by: secretzero
      
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: development
          secret_name: postgres-admin
          data_key: password
          labels:
            environment: development
            managed-by: secretzero

  # Environment-specific application secrets
  - name: app_secret_production
    kind: random_string
    config:
      length: 64
      charset: base64
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: production
          secret_name: app-config
          data_key: secret-key
          labels:
            environment: production

  - name: app_secret_staging
    kind: random_string
    config:
      length: 64
      charset: base64
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: staging
          secret_name: app-config
          data_key: secret-key
          labels:
            environment: staging

  - name: app_secret_development
    kind: random_string
    config:
      length: 64
      charset: base64
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: development
          secret_name: app-config
          data_key: secret-key
          labels:
            environment: development
```

### External Secrets Operator Integration

Generate ExternalSecret manifests for GitOps workflows:

```yaml
version: '1.0'

variables:
  namespace: production
  aws_region: us-west-2

providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient

secrets:
  # Database password synced from AWS Secrets Manager
  - name: database_password
    kind: random_password
    config:
      length: 32
      special: true
    targets:
      # Generate ExternalSecret manifest
      - provider: kubernetes
        kind: external_secret
        config:
          namespace: ${namespace}
          secret_name: postgres-credentials
          external_secret_name: postgres-password-sync
          secret_store_ref: aws-secretsmanager
          backend_type: aws
          backend_key: production/database/postgres/password
          refresh_interval: 1h
          output_path: ./manifests/external-secret-postgres.yaml
          labels:
            app: postgres
            managed-by: secretzero
          annotations:
            description: PostgreSQL password from AWS Secrets Manager

  # Stripe API key from AWS Secrets Manager
  - name: stripe_api_key
    kind: static
    config:
      default: ${STRIPE_API_KEY}
    targets:
      - provider: kubernetes
        kind: external_secret
        config:
          namespace: ${namespace}
          secret_name: stripe-credentials
          external_secret_name: stripe-api-key-sync
          secret_store_ref: aws-secretsmanager
          backend_type: aws
          backend_key: production/stripe/api-key
          refresh_interval: 24h
          output_path: ./manifests/external-secret-stripe.yaml
          labels:
            app: payment-service

  # Azure Key Vault integration
  - name: azure_storage_key
    kind: static
    config:
      default: placeholder
    targets:
      - provider: kubernetes
        kind: external_secret
        config:
          namespace: ${namespace}
          secret_name: azure-storage
          external_secret_name: azure-storage-sync
          secret_store_ref: azure-keyvault
          backend_type: azure
          backend_key: storage-account-key
          refresh_interval: 12h
          output_path: ./manifests/external-secret-azure.yaml
          labels:
            cloud-provider: azure

  # HashiCorp Vault integration
  - name: vault_database_creds
    kind: static
    config:
      default: placeholder
    targets:
      - provider: kubernetes
        kind: external_secret
        config:
          namespace: ${namespace}
          secret_name: vault-db-creds
          external_secret_name: vault-db-sync
          secret_store_ref: vault-backend
          backend_type: vault
          backend_key: secret/data/production/database
          refresh_interval: 15m
          output_path: ./manifests/external-secret-vault.yaml
          labels:
            backend: vault

metadata:
  project: external-secrets-integration
  owner: platform-team
```

Deploy with GitOps:

```bash
# Generate manifests
secretzero sync -f Secretfile.yml

# Review generated manifests
ls -l manifests/

# Commit to Git repository
git add manifests/
git commit -m "Add External Secrets manifests"
git push

# ArgoCD or Flux will automatically sync
```

### Secret Rotation with Policies

```yaml
version: '1.0'

metadata:
  project: production-app
  owner: security-team
  compliance:
    - soc2
    - iso27001

variables:
  namespace: production

providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient

policies:
  # Require rotation for all secrets
  production_rotation:
    kind: rotation
    require_rotation_period: true
    max_age: 90d
    severity: error
    enabled: true

secrets:
  # Database password - rotates every 90 days
  - name: database_password
    kind: random_password
    rotation_period: 90d
    config:
      length: 32
      special: true
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: ${namespace}
          secret_name: postgres-credentials
          data_key: password

  # API key - rotates every 30 days
  - name: api_secret_key
    kind: random_password
    rotation_period: 30d
    config:
      length: 64
      special: false
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: ${namespace}
          secret_name: api-credentials
          data_key: secret-key

  # Service account token - one-time, manual rotation
  - name: service_account_token
    kind: random_string
    one_time: true
    rotation_period: 180d
    config:
      length: 48
      charset: base64
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: ${namespace}
          secret_name: service-account
          data_key: token
```

Automate rotation in CI/CD:

```yaml
# .github/workflows/rotate-secrets.yml
name: Rotate Kubernetes Secrets

on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly
  workflow_dispatch:

jobs:
  rotate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install SecretZero
        run: pip install secretzero[kubernetes]
      
      - name: Configure kubectl
        run: |
          echo "${{ secrets.KUBECONFIG }}" | base64 -d > ~/.kube/config
      
      - name: Check rotation status
        run: secretzero rotate --dry-run
      
      - name: Rotate due secrets
        run: secretzero rotate
      
      - name: Verify rotation
        run: kubectl get secrets -n production
```

### Cert-Manager Integration

Integrate with cert-manager for automatic TLS certificate management:

```yaml
version: '1.0'

variables:
  namespace: production
  domain: example.com

providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient

secrets:
  # Initial TLS secret (cert-manager will manage renewals)
  - name: letsencrypt_tls
    kind: templates.tls_cert_initial

templates:
  tls_cert_initial:
    description: Initial TLS certificate (cert-manager handles renewals)
    fields:
      tls.crt:
        generator:
          kind: static
          config:
            # Temporary self-signed certificate
            # cert-manager will replace with real certificate
            default: |
              -----BEGIN CERTIFICATE-----
              MIICljCCAX4CCQDummyCertificateForInitialization...
              -----END CERTIFICATE-----
      tls.key:
        generator:
          kind: static
          config:
            # Temporary key
            default: |
              -----BEGIN PRIVATE KEY-----
              MIIEvgIBADANBgDummyKeyForInitialization...
              -----END PRIVATE KEY-----
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: ${namespace}
          secret_name: ${domain}-tls
          secret_type: kubernetes.io/tls
          labels:
            app: myapp
            cert-manager.io/issuer-name: letsencrypt-prod
          annotations:
            cert-manager.io/common-name: ${domain}
            cert-manager.io/alt-names: "*.${domain}"
```

Create cert-manager Certificate resource:

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: example-com-tls
  namespace: production
spec:
  secretName: example.com-tls  # Same as SecretZero secret_name
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
    - example.com
    - "*.example.com"
  duration: 2160h  # 90 days
  renewBefore: 360h  # 15 days before expiry
```

### Service Mesh Integration (Istio)

Integrate with Istio for mTLS and service authentication:

```yaml
version: '1.0'

variables:
  namespace: production
  service_name: payment-service

providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient

secrets:
  # Service-to-service authentication token
  - name: service_auth_token
    kind: random_string
    rotation_period: 30d
    config:
      length: 64
      charset: base64
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: ${namespace}
          secret_name: ${service_name}-auth
          data_key: token
          labels:
            app: ${service_name}
            istio.io/type: auth
          annotations:
            sidecar.istio.io/inject: "true"

  # mTLS certificates (if not using Istio's built-in mTLS)
  - name: service_mtls_cert
    kind: templates.service_cert

templates:
  service_cert:
    description: Service mTLS certificate
    fields:
      cert-chain.pem:
        generator:
          kind: static
          config:
            default: |
              -----BEGIN CERTIFICATE-----
              ServiceCertificateChainHere...
              -----END CERTIFICATE-----
      key.pem:
        generator:
          kind: static
          config:
            default: |
              -----BEGIN PRIVATE KEY-----
              ServicePrivateKeyHere...
              -----END PRIVATE KEY-----
      root-cert.pem:
        generator:
          kind: static
          config:
            default: |
              -----BEGIN CERTIFICATE-----
              RootCACertificateHere...
              -----END CERTIFICATE-----
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: ${namespace}
          secret_name: ${service_name}-mtls
          labels:
            istio.io/type: cert
```

## Best Practices

1. **Use Labels and Annotations** - Always add comprehensive labels and annotations to secrets for easier discovery, management, and troubleshooting. Include metadata like `app`, `environment`, `managed-by`, `component`, and timestamps.

2. **Never Store Plaintext Secrets in Git** - Store Secretfile manifests and non-sensitive configuration in Git, but never plaintext secret values. Lockfiles contain hashes/metadata (not secret values) and are typically committed for GitOps/audit workflows; if your org treats metadata as sensitive, use the exception process in [Lockfile Version Control Policy](../user-guide/lockfile-version-control-policy.md).

3. **Implement RBAC Least Privilege** - Grant SecretZero service accounts only the minimum permissions needed (create, update, get secrets in specific namespaces). Use Role instead of ClusterRole when possible. Avoid cluster-wide secret access.

4. **Use Namespace Isolation** - Deploy secrets to specific namespaces and use Kubernetes RBAC to restrict access between namespaces. Don't share secrets across trust boundaries. Consider using separate clusters for different environments.

5. **Rotate Secrets Regularly** - Define rotation_period for all sensitive secrets (30-90 days for high-security, 90-180 days for standard). Automate rotation checks in CI/CD pipelines. Monitor rotation status and set up alerts for overdue rotations.

6. **Enable Secret Encryption at Rest** - Configure Kubernetes encryption at rest for secrets using EncryptionConfiguration. Use AWS KMS, Azure Key Vault, or Google Cloud KMS for key management. Regularly rotate encryption keys.

7. **Use External Secrets Operator for GitOps** - For GitOps workflows, use External Secrets Operator to sync from external secret stores (AWS Secrets Manager, Azure Key Vault, Vault). This keeps secrets out of Git while maintaining declarative configuration.

8. **Implement Secret Scanning** - Use tools like git-secrets, truffleHog, or GitHub secret scanning to prevent accidental secret commits. Add pre-commit hooks to scan for secrets before committing. Set up repository secret scanning alerts.

9. **Monitor Secret Access** - Enable Kubernetes audit logging to track secret access. Use tools like Falco to detect unusual secret access patterns. Set up alerts for unauthorized secret access attempts.

10. **Document Secret Owners and Purpose** - Use annotations to document secret ownership, purpose, compliance requirements, and rotation schedules. Maintain a secret inventory with contact information for incident response.

## Troubleshooting

### Connection Failed

**Problem**: `Error: Unable to connect to Kubernetes cluster`

**Solutions**:

```bash
# Verify kubectl connectivity
kubectl cluster-info
kubectl get nodes

# Check kubeconfig file
cat ~/.kube/config

# Verify context
kubectl config current-context

# Test with specific context
kubectl --context=production-cluster get namespaces

# Update kubeconfig
export KUBECONFIG=/path/to/kubeconfig

# For in-cluster authentication, verify service account
kubectl get serviceaccount secretzero -n default
kubectl get secret $(kubectl get sa secretzero -n default -o jsonpath='{.secrets[0].name}') -n default -o yaml
```

### Permission Denied

**Problem**: `Error: secrets is forbidden: User cannot create resource "secrets" in API group "" in the namespace "default"`

**Solutions**:

```bash
# Check current permissions
kubectl auth can-i create secrets -n default

# View role bindings
kubectl get rolebindings -n default
kubectl describe rolebinding secretzero-manager-binding -n default

# Create required RBAC (as cluster admin)
kubectl apply -f - <<EOF
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: secretzero-manager
  namespace: default
rules:
  - apiGroups: [""]
    resources: ["secrets"]
    verbs: ["get", "list", "create", "update", "patch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: secretzero-manager-binding
  namespace: default
subjects:
  - kind: ServiceAccount
    name: secretzero
    namespace: default
roleRef:
  kind: Role
  name: secretzero-manager
  apiGroup: rbac.authorization.k8s.io
EOF

# Verify permissions
kubectl auth can-i create secrets -n default --as=system:serviceaccount:default:secretzero
```

### Secret Not Appearing

**Problem**: Secret sync completes but secret doesn't appear in cluster

**Solutions**:

```bash
# 1. Verify namespace exists
kubectl get namespace production

# Create if missing
kubectl create namespace production

# 2. Check for errors in sync
secretzero sync --verbose

# 3. List all secrets in namespace
kubectl get secrets -n production

# 4. Check secret with labels
kubectl get secrets -n production -l managed-by=secretzero

# 5. Force re-sync
secretzero sync --force

# 6. Check lockfile
cat .gitsecrets.lock
```

### Wrong Secret Type

**Problem**: `Error: Secret type mismatch` or pod can't use secret

**Solutions**:

```bash
# Check current secret type
kubectl get secret myapp-tls -n default -o jsonpath='{.type}'

# Expected types:
# - Opaque (default)
# - kubernetes.io/tls (for TLS certs)
# - kubernetes.io/dockerconfigjson (for registry)
# - kubernetes.io/basic-auth (for basic auth)
# - kubernetes.io/ssh-auth (for SSH keys)

# Delete and recreate with correct type
kubectl delete secret myapp-tls -n default
secretzero sync --force

# Verify secret type in Secretfile.yml
grep -A 5 "secret_type:" Secretfile.yml
```

### Base64 Encoding Issues

**Problem**: Secret value appears corrupted or invalid

**Solutions**:

```bash
# Kubernetes secrets are automatically base64 encoded
# Don't base64 encode values in SecretZero - it handles this automatically

# Check raw secret data
kubectl get secret postgres-credentials -n default -o yaml

# Decode secret value
kubectl get secret postgres-credentials -n default -o jsonpath='{.data.password}' | base64 -d

# Verify secret length
kubectl get secret postgres-credentials -n default -o jsonpath='{.data.password}' | base64 -d | wc -c

# Check for newlines or extra characters
kubectl get secret postgres-credentials -n default -o jsonpath='{.data.password}' | base64 -d | od -c
```

### Pod Can't Access Secret

**Problem**: Pod fails with `Error: secret "app-secrets" not found`

**Solutions**:

```bash
# 1. Verify secret exists in same namespace as pod
kubectl get secret app-secrets -n production
kubectl get pod myapp -n production

# 2. Check secret name matches exactly (case-sensitive)
kubectl describe pod myapp -n production | grep -A 5 "Environment:"

# 3. Verify data key exists in secret
kubectl get secret app-secrets -n production -o jsonpath='{.data}' | jq

# 4. Check pod RBAC permissions
kubectl auth can-i get secrets --as=system:serviceaccount:production:default -n production

# 5. Check for secret mount errors
kubectl describe pod myapp -n production | grep -i secret
kubectl logs myapp -n production
```

### External Secrets Operator Not Syncing

**Problem**: ExternalSecret created but secret not syncing

**Solutions**:

```bash
# 1. Verify ESO is installed and running
kubectl get pods -n external-secrets-system

# 2. Check ExternalSecret status
kubectl get externalsecret -n production
kubectl describe externalsecret postgres-password-sync -n production

# 3. Verify SecretStore/ClusterSecretStore exists
kubectl get secretstore -n production
kubectl get clustersecretstore

# 4. Check ESO controller logs
kubectl logs -n external-secrets-system deployment/external-secrets

# 5. Verify backend connectivity (AWS/Azure/Vault)
kubectl describe secretstore aws-secretsmanager -n production

# 6. Test backend access manually
aws secretsmanager get-secret-value --secret-id production/database/password

# 7. Check refresh interval
kubectl get externalsecret postgres-password-sync -n production -o jsonpath='{.spec.refreshInterval}'
```

### TLS Certificate Issues

**Problem**: Ingress shows certificate warnings or errors

**Solutions**:

```bash
# 1. Verify TLS secret exists and has correct type
kubectl get secret myapp-tls -n production
kubectl get secret myapp-tls -n production -o jsonpath='{.type}'
# Should be: kubernetes.io/tls

# 2. Check certificate has both tls.crt and tls.key
kubectl get secret myapp-tls -n production -o jsonpath='{.data}' | jq 'keys'

# 3. Verify certificate validity
kubectl get secret myapp-tls -n production -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -text -noout

# 4. Check certificate expiration
kubectl get secret myapp-tls -n production -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -enddate -noout

# 5. Verify certificate matches domain
kubectl get secret myapp-tls -n production -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -subject -noout

# 6. Test with curl
curl -v https://myapp.example.com

# 7. Check Ingress configuration
kubectl describe ingress myapp-ingress -n production
```

## Complete Example

Full production-ready Kubernetes secret management:

```yaml
version: '1.0'

metadata:
  project: production-app
  owner: platform-team
  compliance:
    - soc2
    - iso27001
  description: Production Kubernetes secret management

variables:
  cluster: production
  namespace: production
  app_name: myapp
  domain: myapp.example.com

providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient
      config:
        context: ${cluster}

policies:
  # Require rotation for all secrets
  production_rotation:
    kind: rotation
    require_rotation_period: true
    max_age: 90d
    severity: error
    enabled: true
  
  # Audit trail requirements
  audit_required:
    kind: audit
    require_annotations: true
    severity: warning
    enabled: true

secrets:
  # 1. Database credentials
  - name: postgres_credentials
    kind: templates.database_creds
    rotation_period: 90d

  # 2. Application secrets
  - name: app_secrets
    kind: templates.app_config
    rotation_period: 90d

  # 3. TLS certificate
  - name: tls_certificate
    kind: templates.tls_cert
    rotation_period: 90d

  # 4. Docker registry
  - name: docker_registry
    kind: templates.registry_auth
    rotation_period: 180d

  # 5. Service account token
  - name: service_account_token
    kind: random_string
    rotation_period: 90d
    config:
      length: 64
      charset: base64
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: ${namespace}
          secret_name: service-account-token
          data_key: token
          labels:
            app: ${app_name}
            type: service-account
            managed-by: secretzero
          annotations:
            description: Service account token for API access
            owner: platform-team
            last-rotated: "{{ timestamp }}"

templates:
  # Database credentials template
  database_creds:
    description: PostgreSQL database credentials
    fields:
      username:
        generator:
          kind: static
          config:
            default: ${DB_USERNAME}
      password:
        generator:
          kind: random_password
          config:
            length: 32
            special: true
            exclude_characters: '"@/\'
      host:
        generator:
          kind: static
          config:
            default: postgres.production.svc.cluster.local
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
      url:
        generator:
          kind: static
          config:
            default: postgresql://${DB_USERNAME}:{{password}}@postgres.production.svc.cluster.local:5432/${app_name}
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: ${namespace}
          secret_name: postgres-credentials
          secret_type: Opaque
          labels:
            app: ${app_name}
            component: database
            managed-by: secretzero
          annotations:
            description: PostgreSQL database credentials
            owner: platform-team
            compliance: soc2,iso27001

  # Application configuration template
  app_config:
    description: Application runtime configuration
    fields:
      secret_key:
        generator:
          kind: random_string
          config:
            length: 64
            charset: base64
      api_token:
        generator:
          kind: random_string
          config:
            length: 32
            charset: hex
      jwt_secret:
        generator:
          kind: random_password
          config:
            length: 48
            special: false
      encryption_key:
        generator:
          kind: random_string
          config:
            length: 32
            charset: base64
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: ${namespace}
          secret_name: app-config
          secret_type: Opaque
          labels:
            app: ${app_name}
            component: application
            managed-by: secretzero
          annotations:
            description: Application runtime secrets
            owner: platform-team

  # TLS certificate template
  tls_cert:
    description: TLS certificate for ingress
    fields:
      tls.crt:
        generator:
          kind: static
          config:
            # Use cert-manager or provide real certificate
            default: ${TLS_CERTIFICATE}
      tls.key:
        generator:
          kind: static
          config:
            # Use cert-manager or provide real key
            default: ${TLS_PRIVATE_KEY}
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: ${namespace}
          secret_name: ${app_name}-tls
          secret_type: kubernetes.io/tls
          labels:
            app: ${app_name}
            type: tls
            cert-manager.io/issuer-name: letsencrypt-prod
          annotations:
            description: TLS certificate for ${domain}
            cert-manager.io/common-name: ${domain}

  # Docker registry authentication
  registry_auth:
    description: Docker registry credentials
    fields:
      .dockerconfigjson:
        generator:
          kind: static
          config:
            default: ${DOCKER_CONFIG_JSON}
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: ${namespace}
          secret_name: registry-credentials
          secret_type: kubernetes.io/dockerconfigjson
          labels:
            app: ${app_name}
            type: registry
            managed-by: secretzero
          annotations:
            description: Docker registry credentials for ${app_name}
```

Deploy:

```bash
# 1. Set environment variables
export DB_USERNAME=myapp_user
export TLS_CERTIFICATE="$(cat /path/to/cert.pem)"
export TLS_PRIVATE_KEY="$(cat /path/to/key.pem)"
export DOCKER_CONFIG_JSON="$(cat ~/.docker/config.json)"

# 2. Validate configuration
secretzero validate

# 3. Check compliance policies
secretzero policy

# 4. Preview changes
secretzero sync --dry-run

# 5. Create secrets in Kubernetes
secretzero sync

# 6. Verify secrets
kubectl get secrets -n production -l managed-by=secretzero
kubectl describe secret postgres-credentials -n production
kubectl describe secret app-config -n production

# 7. Test application
kubectl apply -f deployment.yaml
kubectl get pods -n production
kubectl logs -f deployment/myapp -n production
```

## Next Steps

- **[External Secrets Operator](https://external-secrets.io/)** - Advanced GitOps secret management
- **[Multi-Cloud Setup](multi-cloud.md)** - Sync secrets across cloud providers
- **[Compliance Scenarios](compliance.md)** - Implement SOC2/ISO27001 requirements
- **[Secret Rotation](https://kubernetes.io/docs/concepts/configuration/secret/)** - Kubernetes secret best practices
