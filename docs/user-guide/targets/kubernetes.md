# Kubernetes Targets

SecretZero provides two Kubernetes secret management strategies: **KubernetesSecretTarget** for direct secret storage in Kubernetes clusters and **ExternalSecretTarget** for GitOps workflows with External Secrets Operator. Both enable secure, native Kubernetes secret management with full integration into the Kubernetes RBAC and security model.

## Overview

Kubernetes targets allow you to:

- Store secrets directly as native Kubernetes Secret objects
- Generate External Secrets Operator manifests for GitOps workflows
- Support all Kubernetes secret types (Opaque, TLS, Docker config, SSH auth, Basic auth)
- Leverage Kubernetes RBAC for access control
- Enable encryption at rest with etcd encryption
- Integrate with External Secrets Operator for multi-cloud secret synchronization
- Manage secrets across multiple namespaces and clusters
- Audit access with Kubernetes audit logs
- Apply labels and annotations for organization and automation

## Target Types

### 1. KubernetesSecretTarget

Directly stores secrets as native Kubernetes Secret objects in your cluster. Best for:

- **Direct deployment workflows**: When you deploy directly to Kubernetes (kubectl, Helm, Kustomize)
- **Dynamic secrets**: Secrets that change frequently or are generated at deployment time
- **Simple use cases**: Small teams or projects without GitOps requirements
- **Testing and development**: Quick iteration on secret management
- **Immediate availability**: Secrets are available instantly in the cluster

### 2. ExternalSecretTarget

Generates External Secrets Operator manifests for GitOps workflows. Best for:

- **GitOps workflows**: When using ArgoCD, Flux, or other GitOps tools
- **Multi-cloud synchronization**: Syncing secrets from AWS, Azure, Vault, GCP
- **Separation of concerns**: Developers commit manifests, operator syncs secrets
- **Audit trails**: Git history provides complete audit trail of changes
- **Complex environments**: Multiple clusters, environments, or teams
- **Compliance**: When change management processes require Git-based approvals

## Prerequisites

### Installation

Kubernetes support requires the kubernetes Python client:

```bash
# Install with Kubernetes support
pip install secretzero[kubernetes]

# Or install kubernetes client directly
pip install kubernetes
```

For ExternalSecretTarget manifest generation:

```bash
# PyYAML is required for manifest generation
pip install pyyaml
```

### Kubernetes Cluster Access

SecretZero needs access to your Kubernetes cluster via a kubeconfig file or in-cluster authentication.

#### Option 1: Kubeconfig File (Default)

```bash
# Default location: ~/.kube/config
export KUBECONFIG=~/.kube/config

# Or specify a custom path
export KUBECONFIG=/path/to/custom/kubeconfig
```

#### Option 2: In-Cluster Authentication

When running SecretZero inside a Kubernetes Pod:

```yaml
providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient
      config:
        in_cluster: true
```

#### Option 3: Service Account

When using a dedicated service account:

```bash
# Extract service account token
kubectl create serviceaccount secretzero -n default
kubectl create token secretzero -n default

# Use token in kubeconfig or environment variable
```

### Required RBAC Permissions

SecretZero requires permissions to manage Secrets in target namespaces:

#### Basic Role (Single Namespace)

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: default
  name: secretzero-manager
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
```

#### ClusterRole (Multiple Namespaces)

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: secretzero-manager
rules:
- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["get", "list", "create", "update", "patch"]
- apiGroups: [""]
  resources: ["namespaces"]
  verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: secretzero-manager-binding
subjects:
- kind: ServiceAccount
  name: secretzero
  namespace: default
roleRef:
  kind: ClusterRole
  name: secretzero-manager
  apiGroup: rbac.authorization.k8s.io
```

### External Secrets Operator (Optional)

For ExternalSecretTarget, install External Secrets Operator:

```bash
# Using Helm
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets \
  external-secrets/external-secrets \
  -n external-secrets-system \
  --create-namespace

# Verify installation
kubectl get pods -n external-secrets-system
```

## Authentication Methods

### 1. Ambient Authentication (Recommended)

Uses the standard Kubernetes authentication chain:

```yaml
providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient
      config:
        # Optional: specify kubeconfig path (default: ~/.kube/config)
        kubeconfig: ~/.kube/config
        
        # Optional: specify context (default: current context)
        context: production-cluster
```

### 2. In-Cluster Authentication

When running inside a Kubernetes Pod:

```yaml
providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient
      config:
        in_cluster: true
```

### 3. Explicit Kubeconfig

Specify a custom kubeconfig file:

```yaml
providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient
      config:
        kubeconfig: /path/to/custom/kubeconfig
        context: my-cluster
```

## KubernetesSecretTarget Configuration

### Configuration Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `namespace` | string | No | `"default"` | Kubernetes namespace for the secret |
| `secret_name` | string | **Yes** | - | Name of the Kubernetes Secret object |
| `secret_type` | string | No | `"Opaque"` | Type of Kubernetes secret |
| `labels` | dict | No | `{}` | Labels to apply to the secret |
| `annotations` | dict | No | `{}` | Annotations to apply to the secret |
| `data_key` | string | No | `secret_name` | Key name within the Secret's data field |

### Supported Secret Types

#### 1. Opaque (Default)

Generic secrets for any key-value data:

```yaml
targets:
  - provider: kubernetes
    kind: kubernetes_secret
    config:
      namespace: default
      secret_name: app-secrets
      secret_type: Opaque
      data_key: api-key
```

**Use cases**: API keys, passwords, tokens, configuration values

#### 2. kubernetes.io/tls

TLS certificates for Ingress controllers and services:

```yaml
targets:
  - provider: kubernetes
    kind: kubernetes_secret
    config:
      namespace: default
      secret_name: tls-cert
      secret_type: kubernetes.io/tls
```

**Required keys**: `tls.crt` (certificate), `tls.key` (private key)

#### 3. kubernetes.io/dockerconfigjson

Docker registry authentication:

```yaml
targets:
  - provider: kubernetes
    kind: kubernetes_secret
    config:
      namespace: default
      secret_name: registry-creds
      secret_type: kubernetes.io/dockerconfigjson
```

**Required key**: `.dockerconfigjson` (Docker config JSON)

#### 4. kubernetes.io/basic-auth

HTTP basic authentication credentials:

```yaml
targets:
  - provider: kubernetes
    kind: kubernetes_secret
    config:
      namespace: default
      secret_name: basic-auth
      secret_type: kubernetes.io/basic-auth
```

**Required keys**: `username`, `password`

#### 5. kubernetes.io/ssh-auth

SSH authentication keys:

```yaml
targets:
  - provider: kubernetes
    kind: kubernetes_secret
    config:
      namespace: default
      secret_name: ssh-key
      secret_type: kubernetes.io/ssh-auth
```

**Required keys**: `ssh-privatekey`, optionally `ssh-publickey`

### Labels and Annotations

Labels enable selection and organization:

```yaml
config:
  labels:
    app: myapp
    component: database
    environment: production
    managed-by: secretzero
    version: "1.0"
```

Annotations provide metadata:

```yaml
config:
  annotations:
    description: "PostgreSQL database password"
    owner: "platform-team@example.com"
    managed-by: secretzero
    rotation-policy: "90-days"
    last-rotated: "2024-01-15"
```

### Data Key Behavior

The `data_key` parameter controls the key name within the Secret's data field:

```yaml
# Without data_key: uses secret_name
secrets:
  - name: database_password  # Will be stored as "database_password" key
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          secret_name: postgres-creds

# With data_key: uses custom key name
secrets:
  - name: database_password  # Will be stored as "password" key
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          secret_name: postgres-creds
          data_key: password
```

This allows multiple secrets to be stored in the same Secret object:

```yaml
secrets:
  - name: db_user
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          secret_name: postgres-creds
          data_key: username

  - name: db_password
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          secret_name: postgres-creds
          data_key: password
```

## ExternalSecretTarget Configuration

### Configuration Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `namespace` | string | No | `"default"` | Kubernetes namespace for the ExternalSecret |
| `secret_name` | string | **Yes** | - | Name of the target Kubernetes Secret |
| `external_secret_name` | string | No | `secret_name` | Name of the ExternalSecret resource |
| `secret_store_ref` | string | No | `"default"` | Reference to SecretStore/ClusterSecretStore |
| `backend_type` | string | No | `"aws"` | Backend system type |
| `backend_key` | string | No | `secret_name` | Key/path in the backend system |
| `output_path` | string | **Yes** | - | Path to write manifest YAML file |
| `refresh_interval` | string | No | `"1h"` | How often to sync from backend |
| `labels` | dict | No | `{}` | Labels for the ExternalSecret |
| `annotations` | dict | No | `{}` | Annotations for the ExternalSecret |

### Backend Types

Supported backend types for `backend_type`:

- `aws` - AWS Secrets Manager / Parameter Store
- `azure` - Azure Key Vault
- `vault` - HashiCorp Vault
- `gcp` - Google Cloud Secret Manager
- `gcpsm` - Google Cloud Secret Manager (alias)
- `kubernetes` - Kubernetes Secret (cross-namespace/cluster)

### Refresh Intervals

Common refresh interval values:

- `15s` - 15 seconds (testing)
- `1m` - 1 minute (rapid changes)
- `5m` - 5 minutes (frequent updates)
- `15m` - 15 minutes (moderate)
- `30m` - 30 minutes
- `1h` - 1 hour (default, recommended)
- `6h` - 6 hours (stable secrets)
- `24h` - 24 hours (rarely changing)

### SecretStore vs ClusterSecretStore

**SecretStore**: Namespaced, can only sync secrets within the same namespace:

```yaml
config:
  secret_store_ref: my-secret-store  # Looks for SecretStore in same namespace
```

**ClusterSecretStore**: Cluster-wide, can sync secrets to any namespace:

```yaml
# Change SecretStore kind to ClusterSecretStore
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
spec:
  secretStoreRef:
    name: aws-cluster-store
    kind: ClusterSecretStore  # Cluster-wide
```

## Complete Examples

### Example 1: Basic Opaque Secrets

```yaml
version: '1.0'

providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient

secrets:
  # Database password
  - name: database_password
    kind: random_password
    config:
      length: 32
      special: true
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: default
          secret_name: postgres-credentials
          data_key: password
          labels:
            app: postgres
            tier: database

  # API key
  - name: api_key
    kind: random_string
    config:
      length: 32
      charset: hex
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: default
          secret_name: app-secrets
          data_key: api-key
```

### Example 2: TLS Certificates

```yaml
version: '1.0'

providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient

secrets:
  - name: ingress_tls
    kind: templates.tls_cert

templates:
  tls_cert:
    description: TLS certificate for ingress
    fields:
      tls.crt:
        generator:
          kind: static
          config:
            # Use cert-manager or provide real certificate
            default: |
              -----BEGIN CERTIFICATE-----
              MIICljCCAX4CCQCExample...
              -----END CERTIFICATE-----
      tls.key:
        generator:
          kind: static
          config:
            # Use cert-manager or provide real key
            default: |
              -----BEGIN PRIVATE KEY-----
              MIIEvgIBADANExample...
              -----END PRIVATE KEY-----
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: default
          secret_name: ingress-tls
          secret_type: kubernetes.io/tls
          labels:
            app: myapp
            cert-manager.io/issuer-name: letsencrypt-prod
```

**Using in Ingress:**

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp-ingress
spec:
  tls:
  - hosts:
    - example.com
    secretName: ingress-tls  # References the secret
  rules:
  - host: example.com
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

### Example 3: Docker Registry Credentials

```yaml
version: '1.0'

providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient

secrets:
  - name: docker_registry
    kind: templates.docker_config

templates:
  docker_config:
    description: Docker registry authentication
    fields:
      .dockerconfigjson:
        generator:
          kind: static
          config:
            default: |
              {
                "auths": {
                  "registry.example.com": {
                    "username": "myapp-robot",
                    "password": "secret-token",
                    "email": "robot@example.com",
                    "auth": "bXlhcHAtcm9ib3Q6c2VjcmV0LXRva2Vu"
                  }
                }
              }
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: default
          secret_name: registry-credentials
          secret_type: kubernetes.io/dockerconfigjson
          labels:
            app: myapp
            type: registry
```

**Using in Pod:**

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: myapp
spec:
  imagePullSecrets:
  - name: registry-credentials  # References the secret
  containers:
  - name: app
    image: registry.example.com/myapp:latest
```

### Example 4: Basic Authentication

```yaml
version: '1.0'

providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient

secrets:
  - name: admin_auth
    kind: templates.basic_auth

templates:
  basic_auth:
    description: Admin panel authentication
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
            length: 24
            special: true
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: default
          secret_name: admin-basic-auth
          secret_type: kubernetes.io/basic-auth
          labels:
            app: myapp
            component: admin
```

**Using in Ingress (nginx):**

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: admin-ingress
  annotations:
    nginx.ingress.kubernetes.io/auth-type: basic
    nginx.ingress.kubernetes.io/auth-secret: admin-basic-auth
    nginx.ingress.kubernetes.io/auth-realm: "Admin Area"
spec:
  rules:
  - host: admin.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: admin-panel
            port:
              number: 80
```

### Example 5: SSH Keys

```yaml
version: '1.0'

providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient

secrets:
  - name: deploy_key
    kind: templates.ssh_key

templates:
  ssh_key:
    description: SSH deployment key
    fields:
      ssh-privatekey:
        generator:
          kind: static
          config:
            # Generate with: ssh-keygen -t ed25519
            default: |
              -----BEGIN OPENSSH PRIVATE KEY-----
              b3BlbnNzaC1rZXktdjEAExample...
              -----END OPENSSH PRIVATE KEY-----
      ssh-publickey:
        generator:
          kind: static
          config:
            default: ssh-ed25519 AAAAC3NzaC1lZExample...
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: default
          secret_name: git-deploy-key
          secret_type: kubernetes.io/ssh-auth
          labels:
            app: myapp
            type: deploy-key
```

**Using in Pod:**

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: git-sync
spec:
  containers:
  - name: git-sync
    image: k8s.gcr.io/git-sync:v3.6.3
    volumeMounts:
    - name: ssh-key
      mountPath: /etc/git-secret
      readOnly: true
    env:
    - name: GIT_SSH_COMMAND
      value: "ssh -i /etc/git-secret/ssh-privatekey"
  volumes:
  - name: ssh-key
    secret:
      secretName: git-deploy-key
      defaultMode: 0400
```

### Example 6: Service Account Tokens

```yaml
version: '1.0'

providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient

secrets:
  # Service account token for API access
  - name: service_account_token
    kind: random_string
    config:
      length: 64
      charset: base64
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: default
          secret_name: api-service-account
          data_key: token
          secret_type: Opaque
          labels:
            app: myapp
            type: service-account

  # Multiple service accounts
  - name: monitoring_token
    kind: random_string
    config:
      length: 64
      charset: base64
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: monitoring
          secret_name: prometheus-token
          data_key: token
```

### Example 7: External Secrets Operator - AWS

```yaml
version: '1.0'

providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient

secrets:
  # Database password from AWS Secrets Manager
  - name: database_password
    kind: random_password
    config:
      length: 32
      special: true
    targets:
      # Store in AWS Secrets Manager (using AWS target)
      - provider: aws
        kind: secrets_manager
        config:
          secret_name: prod/db/postgres/password
      
      # Generate ExternalSecret manifest
      - provider: kubernetes
        kind: external_secret
        config:
          namespace: default
          secret_name: postgres-credentials
          external_secret_name: postgres-password-sync
          secret_store_ref: aws-secretsmanager
          backend_type: aws
          backend_key: prod/db/postgres/password
          refresh_interval: 1h
          output_path: ./manifests/external-secret-postgres.yaml
          labels:
            app: postgres
            managed-by: secretzero

  # API key from AWS Parameter Store
  - name: stripe_api_key
    kind: static
    config:
      default: sk_live_example_key
    targets:
      - provider: kubernetes
        kind: external_secret
        config:
          namespace: default
          secret_name: stripe-credentials
          secret_store_ref: aws-parameter-store
          backend_type: aws
          backend_key: /prod/stripe/api-key
          refresh_interval: 24h
          output_path: ./manifests/external-secret-stripe.yaml
```

**SecretStore for AWS Secrets Manager:**

```yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: aws-secretsmanager
  namespace: default
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-west-2
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets-sa
```

### Example 8: External Secrets Operator - Azure Key Vault

```yaml
version: '1.0'

providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient

secrets:
  - name: azure_secret
    kind: static
    config:
      default: placeholder
    targets:
      - provider: kubernetes
        kind: external_secret
        config:
          namespace: default
          secret_name: azure-app-secret
          secret_store_ref: azure-keyvault
          backend_type: azure
          backend_key: app-secret-key
          refresh_interval: 30m
          output_path: ./manifests/external-secret-azure.yaml
          labels:
            cloud-provider: azure
```

**SecretStore for Azure Key Vault:**

```yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: azure-keyvault
  namespace: default
spec:
  provider:
    azurekv:
      vaultUrl: https://my-vault.vault.azure.net
      tenantId: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
      authSecretRef:
        clientId:
          name: azure-secret-sp
          key: client-id
        clientSecret:
          name: azure-secret-sp
          key: client-secret
```

### Example 9: External Secrets Operator - HashiCorp Vault

```yaml
version: '1.0'

providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient

secrets:
  - name: vault_database_creds
    kind: static
    config:
      default: placeholder
    targets:
      - provider: kubernetes
        kind: external_secret
        config:
          namespace: default
          secret_name: database-credentials
          secret_store_ref: vault-backend
          backend_type: vault
          backend_key: secret/data/myapp/database
          refresh_interval: 15m
          output_path: ./manifests/external-secret-vault.yaml
          labels:
            backend: vault
            app: myapp
```

**SecretStore for Vault:**

```yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: vault-backend
  namespace: default
spec:
  provider:
    vault:
      server: https://vault.example.com
      path: secret
      version: v2
      auth:
        kubernetes:
          mountPath: kubernetes
          role: external-secrets
          serviceAccountRef:
            name: external-secrets-sa
```

### Example 10: Multi-Namespace Deployment

```yaml
version: '1.0'

variables:
  environments:
    - production
    - staging
    - development

providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient

secrets:
  # Shared database admin password across all environments
  - name: postgres_admin_password
    kind: random_password
    config:
      length: 32
      special: true
    one_time: true  # Generate once, use everywhere
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: production
          secret_name: postgres-admin
          data_key: password
          labels:
            app: postgres
            environment: production
      
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: staging
          secret_name: postgres-admin
          data_key: password
          labels:
            app: postgres
            environment: staging
      
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: development
          secret_name: postgres-admin
          data_key: password
          labels:
            app: postgres
            environment: development

  # Different app secrets per environment
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

  # Docker registry credentials for all namespaces
  - name: docker_creds
    kind: templates.docker_registry
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: production
          secret_name: registry-creds
          secret_type: kubernetes.io/dockerconfigjson
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: staging
          secret_name: registry-creds
          secret_type: kubernetes.io/dockerconfigjson
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: development
          secret_name: registry-creds
          secret_type: kubernetes.io/dockerconfigjson

templates:
  docker_registry:
    fields:
      .dockerconfigjson:
        generator:
          kind: static
          config:
            default: |
              {
                "auths": {
                  "registry.example.com": {
                    "username": "robot",
                    "password": "token",
                    "auth": "cm9ib3Q6dG9rZW4="
                  }
                }
              }
```

## Using Secrets in Pods

### Method 1: Environment Variables

Inject individual secret keys as environment variables:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: myapp
spec:
  containers:
  - name: app
    image: myapp:latest
    env:
    # Single secret value
    - name: DATABASE_PASSWORD
      valueFrom:
        secretKeyRef:
          name: postgres-credentials
          key: password
    
    # Multiple values
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

### Method 2: Environment Variables from All Secret Keys

Inject all keys from a secret as environment variables:

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
    # All keys from this secret become environment variables
    - secretRef:
        name: app-secrets
    
    # Can include multiple secrets
    - secretRef:
        name: database-config
```

### Method 3: Volume Mounts

Mount secrets as files in the container:

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
    # Mount entire secret
    - name: app-secrets
      mountPath: /etc/secrets
      readOnly: true
    
    # Mount specific keys
    - name: tls-certs
      mountPath: /etc/tls
      readOnly: true
    
  volumes:
  # Mount all keys as separate files
  - name: app-secrets
    secret:
      secretName: app-secrets
      # Each key becomes a file: /etc/secrets/api-key, /etc/secrets/redis-password
  
  # Mount specific keys with custom names
  - name: tls-certs
    secret:
      secretName: ingress-tls
      items:
      - key: tls.crt
        path: server.crt
      - key: tls.key
        path: server.key
        mode: 0400  # Restrict permissions
```

### Method 4: Projected Volumes

Combine multiple secrets in a single volume:

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
    - name: combined-secrets
      mountPath: /etc/combined
      readOnly: true
  
  volumes:
  - name: combined-secrets
    projected:
      sources:
      - secret:
          name: app-secrets
          items:
          - key: api-key
            path: api/key
      - secret:
          name: database-config
          items:
          - key: password
            path: db/password
```

### File Permissions

Control file permissions for mounted secrets:

```yaml
volumes:
- name: ssh-key
  secret:
    secretName: git-deploy-key
    defaultMode: 0400  # Read-only for owner
    items:
    - key: ssh-privatekey
      path: id_rsa
      mode: 0400
```

Common modes:
- `0400` (256 decimal) - Read-only for owner
- `0440` (288 decimal) - Read-only for owner and group
- `0444` (292 decimal) - Read-only for all
- `0600` (384 decimal) - Read-write for owner
- `0644` (420 decimal) - Read-write for owner, read for others

## External Secrets Operator Integration

### Workflow Overview

1. **Create Backend Secret Stores**: Configure SecretStore/ClusterSecretStore for your backends
2. **Generate Manifests**: Use SecretZero to generate ExternalSecret manifests
3. **Commit to Git**: Add manifests to your GitOps repository
4. **Deploy**: GitOps tool (ArgoCD, Flux) deploys ExternalSecret resources
5. **Sync**: External Secrets Operator syncs secrets from backends to Kubernetes

### Complete GitOps Workflow Example

#### Step 1: Install External Secrets Operator

```bash
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets \
  external-secrets/external-secrets \
  -n external-secrets-system \
  --create-namespace \
  --set installCRDs=true
```

#### Step 2: Configure SecretStore

```yaml
# secretstore.yaml
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: aws-secretsmanager
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-west-2
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets-sa
            namespace: external-secrets-system
```

Deploy the SecretStore:

```bash
kubectl apply -f secretstore.yaml
```

#### Step 3: Create IAM Role for External Secrets Operator

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:us-west-2:*:secret:prod/*"
    }
  ]
}
```

#### Step 4: Generate ExternalSecret Manifests

```yaml
# secretzero-config.yml
version: '1.0'

providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient

secrets:
  - name: database_password
    kind: random_password
    config:
      length: 32
    targets:
      # Store in AWS (separately or as part of another job)
      - provider: aws
        kind: secrets_manager
        config:
          secret_name: prod/db/postgres/password
      
      # Generate ExternalSecret manifest
      - provider: kubernetes
        kind: external_secret
        config:
          namespace: production
          secret_name: postgres-credentials
          secret_store_ref: aws-secretsmanager
          backend_type: aws
          backend_key: prod/db/postgres/password
          refresh_interval: 1h
          output_path: ./k8s/external-secrets/postgres.yaml
```

Run SecretZero:

```bash
secretzero sync -f secretzero-config.yml
```

#### Step 5: Review Generated Manifest

```yaml
# k8s/external-secrets/postgres.yaml (generated)
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: postgres-password-sync
  namespace: production
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secretsmanager
    kind: SecretStore
  target:
    name: postgres-credentials
    creationPolicy: Owner
  data:
  - secretKey: database_password
    remoteRef:
      key: prod/db/postgres/password
```

#### Step 6: Commit and Deploy via GitOps

```bash
# Add to Git repository
git add k8s/external-secrets/postgres.yaml
git commit -m "Add database password external secret"
git push origin main

# ArgoCD will automatically deploy the ExternalSecret
# Or manually sync
argocd app sync myapp
```

#### Step 7: Verify Secret Synchronization

```bash
# Check ExternalSecret status
kubectl get externalsecret -n production
kubectl describe externalsecret postgres-password-sync -n production

# Verify the synced Kubernetes Secret
kubectl get secret postgres-credentials -n production
kubectl get secret postgres-credentials -n production -o yaml

# Check External Secrets Operator logs
kubectl logs -n external-secrets-system -l app.kubernetes.io/name=external-secrets
```

### Multi-Backend Setup

Use different SecretStores for different backends:

```yaml
secrets:
  # AWS Secrets Manager
  - name: aws_secret
    targets:
      - provider: kubernetes
        kind: external_secret
        config:
          secret_store_ref: aws-secretsmanager
          backend_type: aws
          backend_key: prod/api/key
          output_path: ./manifests/aws-secret.yaml

  # Azure Key Vault
  - name: azure_secret
    targets:
      - provider: kubernetes
        kind: external_secret
        config:
          secret_store_ref: azure-keyvault
          backend_type: azure
          backend_key: api-secret
          output_path: ./manifests/azure-secret.yaml

  # HashiCorp Vault
  - name: vault_secret
    targets:
      - provider: kubernetes
        kind: external_secret
        config:
          secret_store_ref: vault-backend
          backend_type: vault
          backend_key: secret/data/app/config
          output_path: ./manifests/vault-secret.yaml
```

## Best Practices

### 1. RBAC Principle of Least Privilege

Grant only necessary permissions:

```yaml
# Bad: Cluster-wide admin access
kind: ClusterRoleBinding
subjects:
- kind: ServiceAccount
  name: secretzero
roleRef:
  kind: ClusterRole
  name: cluster-admin  # Too permissive!

# Good: Limited to secrets in specific namespaces
kind: RoleBinding
subjects:
- kind: ServiceAccount
  name: secretzero
roleRef:
  kind: Role
  name: secrets-manager  # Only secret management
```

### 2. Namespace Isolation

Use separate namespaces for different environments:

```yaml
secrets:
  - name: db_password
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: production  # Isolated from staging
          secret_name: db-creds
```

### 3. Enable Encryption at Rest

Configure etcd encryption for all secrets:

```yaml
# /etc/kubernetes/enc/encryption-config.yaml
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
  - resources:
    - secrets
    providers:
    - aescbc:
        keys:
        - name: key1
          secret: <base64-encoded-32-byte-key>
    - identity: {}
```

Enable in API server:

```bash
kube-apiserver \
  --encryption-provider-config=/etc/kubernetes/enc/encryption-config.yaml
```

### 4. Use Labels for Organization

Apply consistent labels:

```yaml
config:
  labels:
    app: myapp
    component: database
    environment: production
    managed-by: secretzero
    team: platform
    criticality: high
```

### 5. Meaningful Annotations

Add context via annotations:

```yaml
config:
  annotations:
    description: "PostgreSQL master database password"
    owner: "platform-team@example.com"
    contact: "Slack: #platform-team"
    docs: "https://wiki.example.com/db-access"
    rotation-schedule: "quarterly"
    compliance: "pci-dss,sox"
```

### 6. Secret Rotation Strategy

Implement regular rotation:

```yaml
# Rotation annotation
annotations:
  secretzero.io/rotation-policy: "90-days"
  secretzero.io/last-rotated: "2024-01-15T10:30:00Z"
  secretzero.io/rotation-job: "secretzero-rotator"
```

Use External Secrets for automatic rotation:

```yaml
config:
  refresh_interval: 1h  # Sync frequently
  backend_key: prod/db/password/current  # Backend handles rotation
```

### 7. GitOps for External Secrets

Store manifests in Git:

```
repo/
├── base/
│   └── external-secrets/
│       ├── postgres.yaml
│       ├── redis.yaml
│       └── kustomization.yaml
├── overlays/
│   ├── production/
│   │   └── kustomization.yaml
│   └── staging/
│       └── kustomization.yaml
```

### 8. Avoid Storing Secrets in ConfigMaps

Never use ConfigMaps for sensitive data:

```yaml
# Bad: Secrets in ConfigMap
apiVersion: v1
kind: ConfigMap
data:
  password: supersecret  # Visible in logs, not encrypted

# Good: Use Secrets
apiVersion: v1
kind: Secret
data:
  password: c3VwZXJzZWNyZXQ=  # Base64-encoded, encrypted at rest
```

### 9. Limit Secret Access in Pods

Mount only required secrets:

```yaml
# Bad: Mount all secrets
envFrom:
- secretRef:
    name: all-secrets  # Exposes everything

# Good: Mount specific secrets
env:
- name: DB_PASSWORD
  valueFrom:
    secretKeyRef:
      name: db-creds
      key: password  # Only this value
```

### 10. Use Projected Volumes for Complex Scenarios

Combine secrets efficiently:

```yaml
volumes:
- name: combined
  projected:
    sources:
    - secret:
        name: api-creds
        items:
        - key: token
          path: api/token
    - secret:
        name: db-creds
        items:
        - key: password
          path: db/password
```

## Security Considerations

### 1. Etcd Encryption at Rest

**Why**: Kubernetes stores secrets in etcd. Without encryption, they're stored in plaintext.

**Implementation**:

```yaml
# encryption-config.yaml
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
  - resources:
    - secrets
    providers:
    - aescbc:
        keys:
        - name: key1
          secret: <32-byte-base64-key>
    - identity: {}
```

**Enable**:

```bash
# Add to kube-apiserver flags
--encryption-provider-config=/etc/kubernetes/enc/encryption-config.yaml

# Encrypt existing secrets
kubectl get secrets --all-namespaces -o json | kubectl replace -f -
```

**Key Rotation**:

```yaml
providers:
- aescbc:
    keys:
    - name: key2
      secret: <new-key>  # New key (will be used for writes)
    - name: key1
      secret: <old-key>  # Old key (for reads)
- identity: {}
```

### 2. RBAC Best Practices

**Principle of Least Privilege**:

```yaml
# Minimal permissions
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: production
  name: app-secrets-reader
rules:
- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["get"]  # Only read
  resourceNames: ["app-secrets"]  # Specific secret only
```

**Avoid Wildcards**:

```yaml
# Bad
- apiGroups: ["*"]
  resources: ["*"]
  verbs: ["*"]

# Good
- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["get", "list"]
  resourceNames: ["specific-secret"]
```

**Service Account per Application**:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: myapp-sa
  namespace: production
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: myapp-secrets-binding
  namespace: production
subjects:
- kind: ServiceAccount
  name: myapp-sa
roleRef:
  kind: Role
  name: myapp-secrets-reader
```

### 3. Network Policies

Restrict pod-to-API server communication:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-api-access
  namespace: production
spec:
  podSelector: {}
  policyTypes:
  - Egress
  egress:
  # Allow DNS
  - to:
    - namespaceSelector:
        matchLabels:
          name: kube-system
    ports:
    - protocol: UDP
      port: 53
  # Block API server access (pods shouldn't need it)
  # Only pods that need it should have explicit allow rules
```

### 4. Audit Logging

Enable Kubernetes audit logs to track secret access:

```yaml
# audit-policy.yaml
apiVersion: audit.k8s.io/v1
kind: Policy
rules:
# Log all secret access at RequestResponse level
- level: RequestResponse
  resources:
  - group: ""
    resources: ["secrets"]
  
# Log secret modifications with full body
- level: RequestResponse
  verbs: ["create", "update", "patch", "delete"]
  resources:
  - group: ""
    resources: ["secrets"]
```

**Enable in API server**:

```bash
kube-apiserver \
  --audit-policy-file=/etc/kubernetes/audit-policy.yaml \
  --audit-log-path=/var/log/kubernetes/audit.log
```

**Monitor for suspicious activity**:

```bash
# Failed secret access attempts
grep "secrets.*Forbidden" /var/log/kubernetes/audit.log

# Secret deletions
grep "secrets.*delete" /var/log/kubernetes/audit.log

# Unexpected namespaces
grep "secrets" /var/log/kubernetes/audit.log | grep "namespace: production"
```

### 5. Sealed Secrets for GitOps

Use Sealed Secrets to safely store encrypted secrets in Git:

```bash
# Install Sealed Secrets controller
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.24.0/controller.yaml

# Install kubeseal CLI
brew install kubeseal

# Create a secret
kubectl create secret generic mysecret \
  --from-literal=password=supersecret \
  --dry-run=client -o yaml > secret.yaml

# Seal the secret
kubeseal -f secret.yaml -w sealed-secret.yaml

# Commit sealed secret to Git
git add sealed-secret.yaml
git commit -m "Add sealed secret"
```

**Sealed Secret example**:

```yaml
apiVersion: bitnami.com/v1alpha1
kind: SealedSecret
metadata:
  name: mysecret
  namespace: default
spec:
  encryptedData:
    password: AgBvLqkr5...encrypted...base64...  # Safe to commit
```

### 6. Secret Scanning in CI/CD

Prevent secrets from being committed:

```yaml
# .pre-commit-config.yaml
repos:
- repo: https://github.com/Yelp/detect-secrets
  rev: v1.4.0
  hooks:
  - id: detect-secrets
    args: ['--baseline', '.secrets.baseline']
```

```bash
# GitHub Actions
- name: Secret Scanning
  uses: trufflesecurity/trufflehog@main
  with:
    path: ./
    base: ${{ github.event.repository.default_branch }}
    head: HEAD
```

### 7. Pod Security Standards

Enforce security contexts:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: secure-app
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    fsGroup: 2000
    seccompProfile:
      type: RuntimeDefault
  
  containers:
  - name: app
    image: myapp:latest
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop:
        - ALL
    
    volumeMounts:
    - name: secrets
      mountPath: /etc/secrets
      readOnly: true  # Always read-only for secrets
  
  volumes:
  - name: secrets
    secret:
      secretName: app-secrets
      defaultMode: 0400  # Restrictive permissions
```

### 8. Secrets in Memory Only

Configure applications to keep secrets in memory:

```python
# Good: Load once, keep in memory
with open('/etc/secrets/password') as f:
    DB_PASSWORD = f.read().strip()

# Bad: Read from disk repeatedly
def get_password():
    return open('/etc/secrets/password').read()  # Don't do this
```

```go
// Good: Load at startup
func init() {
    data, _ := os.ReadFile("/etc/secrets/password")
    dbPassword = string(data)
}

// Bad: Read every time
func getPassword() string {
    data, _ := os.ReadFile("/etc/secrets/password")
    return string(data)  // Inefficient and risky
}
```

### 9. Avoid Logging Secrets

Redact secrets from logs:

```python
import logging

# Bad
logging.info(f"Connecting with password: {password}")

# Good
logging.info("Connecting to database")  # No password in logs

# Better: Use structured logging with redaction
logger.info("database_connect", 
           extra={"user": username, "password": "[REDACTED]"})
```

### 10. External Secrets Operator Security

**Use ClusterSecretStore carefully**:

```yaml
# ClusterSecretStore can access any namespace
# Only create if necessary, restrict access
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: aws-cluster-store
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-west-2
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets-sa
            namespace: external-secrets-system
  
  # Restrict to specific namespaces
  conditions:
  - namespaces:
    - production
    - staging
```

**Monitor External Secrets Operator**:

```bash
# Check sync status
kubectl get externalsecrets --all-namespaces

# View detailed status
kubectl describe externalsecret mysecret -n production

# Check operator logs for errors
kubectl logs -n external-secrets-system \
  -l app.kubernetes.io/name=external-secrets -f
```

## Troubleshooting

### Secret Not Found

**Symptoms**: Pod crashes with "secret not found" error

**Diagnosis**:

```bash
# Check if secret exists
kubectl get secret mysecret -n production

# Check secret details
kubectl describe secret mysecret -n production

# Check namespace
kubectl get secrets --all-namespaces | grep mysecret
```

**Solutions**:

```bash
# Verify SecretZero ran successfully
secretzero sync -f config.yml --verbose

# Check RBAC permissions
kubectl auth can-i create secrets -n production --as=system:serviceaccount:default:secretzero

# Verify secret was created
kubectl get secret mysecret -n production -o yaml
```

### Permission Denied

**Symptoms**: "secrets is forbidden: User cannot create resource 'secrets'"

**Diagnosis**:

```bash
# Check current permissions
kubectl auth can-i create secrets -n production

# Check service account permissions
kubectl auth can-i create secrets -n production \
  --as=system:serviceaccount:default:secretzero

# View role bindings
kubectl get rolebindings -n production
kubectl describe rolebinding secretzero-binding -n production
```

**Solutions**:

```yaml
# Create proper RBAC
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: production
  name: secret-manager
rules:
- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["get", "list", "create", "update", "patch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: secret-manager-binding
  namespace: production
subjects:
- kind: ServiceAccount
  name: secretzero
  namespace: default
roleRef:
  kind: Role
  name: secret-manager
  apiGroup: rbac.authorization.k8s.io
```

### External Secret Not Syncing

**Symptoms**: ExternalSecret exists but Kubernetes Secret is not created

**Diagnosis**:

```bash
# Check ExternalSecret status
kubectl get externalsecret mysecret -n production
kubectl describe externalsecret mysecret -n production

# Check operator logs
kubectl logs -n external-secrets-system \
  -l app.kubernetes.io/name=external-secrets --tail=100

# Verify SecretStore
kubectl get secretstore -n production
kubectl describe secretstore aws-store -n production
```

**Common Issues**:

1. **SecretStore not configured**:
   ```bash
   # Create SecretStore
   kubectl apply -f secretstore.yaml
   ```

2. **Backend credentials invalid**:
   ```bash
   # Check service account
   kubectl get sa external-secrets-sa -n external-secrets-system
   
   # Verify IAM role (AWS)
   aws sts get-caller-identity
   ```

3. **Backend key doesn't exist**:
   ```bash
   # Check AWS Secrets Manager
   aws secretsmanager describe-secret --secret-id prod/db/password
   
   # Check Azure Key Vault
   az keyvault secret show --vault-name myvault --name mysecret
   ```

4. **Refresh interval too long**:
   ```yaml
   # Reduce refresh interval for testing
   spec:
     refreshInterval: 1m  # Instead of 1h
   ```

### Secret Data Corrupted

**Symptoms**: Secret exists but data is invalid or malformed

**Diagnosis**:

```bash
# View secret data
kubectl get secret mysecret -n production -o yaml

# Decode base64 data
kubectl get secret mysecret -n production -o jsonpath='{.data.password}' | base64 -d

# Check for encoding issues
kubectl get secret mysecret -n production -o json | jq -r '.data | to_entries[] | "\(.key): \(.value)"'
```

**Solutions**:

```bash
# Delete and recreate secret
kubectl delete secret mysecret -n production
secretzero sync -f config.yml

# Verify data after recreation
kubectl get secret mysecret -n production -o yaml
```

### TLS Secret Invalid

**Symptoms**: Ingress shows certificate errors

**Diagnosis**:

```bash
# Check TLS secret structure
kubectl get secret tls-cert -n production -o yaml

# Verify required keys exist
kubectl get secret tls-cert -n production -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -text -noout

kubectl get secret tls-cert -n production -o jsonpath='{.data.tls\.key}' | base64 -d | openssl rsa -check
```

**Solutions**:

```yaml
# Ensure correct secret type
apiVersion: v1
kind: Secret
metadata:
  name: tls-cert
type: kubernetes.io/tls  # Must be this type
data:
  tls.crt: <base64-cert>  # Must be named tls.crt
  tls.key: <base64-key>   # Must be named tls.key
```

### Docker Registry Authentication Fails

**Symptoms**: ImagePullBackOff errors

**Diagnosis**:

```bash
# Check imagePullSecrets
kubectl get pod mypod -n production -o jsonpath='{.spec.imagePullSecrets}'

# Verify secret type
kubectl get secret registry-creds -n production -o jsonpath='{.type}'

# Check dockerconfigjson format
kubectl get secret registry-creds -n production -o jsonpath='{.data.\.dockerconfigjson}' | base64 -d | jq .
```

**Solutions**:

```yaml
# Correct format for dockerconfigjson
{
  "auths": {
    "registry.example.com": {
      "username": "user",
      "password": "pass",
      "email": "user@example.com",
      "auth": "base64(user:pass)"
    }
  }
}
```

```bash
# Generate correct auth value
echo -n "username:password" | base64
```

### Cannot Connect to Cluster

**Symptoms**: "The connection to the server was refused"

**Diagnosis**:

```bash
# Check kubectl connectivity
kubectl cluster-info

# Verify kubeconfig
kubectl config view
kubectl config current-context

# Test API server
kubectl get nodes
```

**Solutions**:

```bash
# Set correct context
kubectl config use-context production-cluster

# Verify kubeconfig path
export KUBECONFIG=~/.kube/config

# Update kubeconfig from cloud provider
aws eks update-kubeconfig --name my-cluster --region us-west-2
gcloud container clusters get-credentials my-cluster --zone us-central1-a
az aks get-credentials --resource-group mygroup --name my-cluster
```

### Namespace Doesn't Exist

**Symptoms**: "namespaces 'production' not found"

**Diagnosis**:

```bash
# List all namespaces
kubectl get namespaces

# Check if namespace exists
kubectl get namespace production
```

**Solutions**:

```bash
# Create namespace
kubectl create namespace production

# Or use YAML
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    environment: production
EOF
```

### Verbose Logging for Debugging

Enable verbose output:

```bash
# SecretZero verbose mode
secretzero sync -f config.yml --verbose

# Kubernetes client debug logging
export KUBERNETES_DEBUG=true
secretzero sync -f config.yml

# Check API server audit logs
kubectl logs -n kube-system kube-apiserver-<pod> --tail=100
```

### Validation Commands

```bash
# Complete secret validation
kubectl get secret mysecret -n production -o yaml
kubectl describe secret mysecret -n production
kubectl get secret mysecret -n production -o jsonpath='{.data}' | jq .

# Test secret in pod
kubectl run test-pod --rm -i --tty \
  --image=busybox \
  --restart=Never \
  --namespace=production \
  --overrides='
{
  "spec": {
    "containers": [{
      "name": "test",
      "image": "busybox",
      "command": ["sh"],
      "env": [{
        "name": "SECRET",
        "valueFrom": {
          "secretKeyRef": {
            "name": "mysecret",
            "key": "password"
          }
        }
      }]
    }]
  }
}'

# Inside the pod
echo $SECRET
```

## Additional Resources

- [Kubernetes Secrets Documentation](https://kubernetes.io/docs/concepts/configuration/secret/)
- [External Secrets Operator](https://external-secrets.io/)
- [Encrypting Secret Data at Rest](https://kubernetes.io/docs/tasks/administer-cluster/encrypt-data/)
- [Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets)
- [Kubernetes RBAC](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
- [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)

## Summary

Kubernetes targets in SecretZero provide comprehensive secret management with two complementary approaches:

- **KubernetesSecretTarget**: Direct secret deployment for immediate availability
- **ExternalSecretTarget**: GitOps-friendly manifest generation for External Secrets Operator

Both support all Kubernetes secret types, RBAC integration, multi-namespace deployments, and production security requirements. Choose the approach that best fits your deployment workflow and security posture.
