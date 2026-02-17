# Kubernetes Provider

The Kubernetes provider enables SecretZero to manage secrets directly in Kubernetes clusters, supporting native Secret objects and External Secrets Operator integration for GitOps workflows.

## Overview

The Kubernetes provider is ideal for:

- **Native Kubernetes secret management** without external dependencies
- **Multi-namespace deployments** across development, staging, and production
- **GitOps workflows** with External Secrets Operator integration
- **Container applications** requiring secrets as environment variables or mounted files
- **Microservices architectures** with service-to-service authentication
- **TLS certificate management** for ingress controllers and services
- **Docker registry credentials** for private container registries
- **In-cluster automation** using ServiceAccount authentication

### Supported Target Types

| Target Type | Description | Use Case |
|-------------|-------------|----------|
| `kubernetes_secret` | Native Kubernetes Secret objects | Application secrets, TLS certificates, registry credentials, SSH keys |
| `external_secret` | External Secrets Operator manifests | GitOps workflows, cloud secret backend integration (AWS, Azure, Vault) |

## Authentication Methods

### Kubeconfig Authentication

Use a kubeconfig file for authentication. Best for local development and CI/CD systems.

```yaml
providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient
      config:
        # Use default kubeconfig (~/.kube/config)
        # kubeconfig: /path/to/kubeconfig
        # context: my-cluster
```

**When to use**: Local development, CI/CD pipelines, administrative tasks, multi-cluster management.

#### With Specific Context

```yaml
providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient
      config:
        kubeconfig: /home/user/.kube/config
        context: production-cluster
```

#### With Custom Kubeconfig Path

```yaml
providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient
      config:
        kubeconfig: /etc/kubernetes/admin.conf
        context: default
```

### In-Cluster Authentication

Use ServiceAccount credentials when running inside a Kubernetes pod. Recommended for production automation.

```yaml
providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient
      config:
        in_cluster: true
```

**When to use**: Jobs, CronJobs, Operators, Controllers, automation pods running inside the cluster.

### Token-Based Authentication

Use a bearer token for authentication (advanced use case).

```yaml
providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient
      config:
        token: eyJhbGciOiJSUzI1NiIsImtpZCI6...
```

**When to use**: Custom authentication workflows, external systems with service account tokens.

## Configuration

### Basic Configuration

```yaml
version: '1.0'

providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient
      config:
        # Use default kubeconfig
        context: my-cluster

secrets:
  - name: database_password
    kind: random_password
    config:
      length: 24
      special: true
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: default
          secret_name: postgres-credentials
          data_key: password
          secret_type: Opaque
```

### Variables and Templates

```yaml
version: '1.0'

variables:
  namespace: production
  cluster: prod-cluster-01
  domain: example.com

providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient
      config:
        context: "{{ var.cluster }}"

secrets:
  - name: app_secrets
    kind: templates.credentials
    
templates:
  credentials:
    description: Application credentials
    fields:
      api_key:
        generator:
          kind: random_string
          config:
            length: 32
            charset: hex
      secret_key:
        generator:
          kind: random_string
          config:
            length: 64
            charset: base64
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: "{{ var.namespace }}"
          secret_name: app-credentials
          labels:
            app: myapp
            environment: "{{ var.namespace }}"
```

### Multi-Namespace Deployment

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
      config:
        context: main-cluster

secrets:
  # Same secret across all namespaces
  - name: shared_database_password
    kind: random_password
    config:
      length: 32
      special: true
    one_time: true
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
```

## Target Types

### kubernetes_secret

Creates or updates native Kubernetes Secret objects in the cluster.

#### Configuration Options

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `namespace` | string | Yes | - | Target namespace for the secret |
| `secret_name` | string | Yes | - | Name of the Kubernetes Secret object |
| `data_key` | string | No | (field name) | Key name within the Secret's data field |
| `secret_type` | string | No | `Opaque` | Kubernetes secret type |
| `labels` | dict | No | `{}` | Labels to apply to the Secret |
| `annotations` | dict | No | `{}` | Annotations to apply to the Secret |

#### Supported Secret Types

| Secret Type | Description | Required Fields | Use Case |
|-------------|-------------|-----------------|----------|
| `Opaque` | Generic secret data | Any | Passwords, API keys, tokens, general configuration |
| `kubernetes.io/tls` | TLS certificate and key | `tls.crt`, `tls.key` | Ingress TLS, service certificates |
| `kubernetes.io/dockerconfigjson` | Docker registry credentials | `.dockerconfigjson` | Private registry authentication |
| `kubernetes.io/basic-auth` | HTTP basic authentication | `username`, `password` | Basic auth credentials |
| `kubernetes.io/ssh-auth` | SSH private key | `ssh-privatekey` | Git deployments, SSH access |
| `kubernetes.io/service-account-token` | Service account token | `token` | Custom service account tokens |

#### Examples

##### Opaque Secret (Application Credentials)

```yaml
secrets:
  - name: database_credentials
    kind: templates.db_creds

templates:
  db_creds:
    fields:
      username:
        generator:
          kind: static
          config:
            default: postgres_admin
      password:
        generator:
          kind: random_password
          config:
            length: 32
            special: true
      connection_string:
        generator:
          kind: static
          config:
            default: postgresql://postgres_admin@postgres:5432/myapp
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: default
          secret_name: postgres-credentials
          secret_type: Opaque
          labels:
            app: myapp
            component: database
            managed-by: secretzero
          annotations:
            description: PostgreSQL database credentials
            rotation-policy: 90-days
```

##### TLS Certificate Secret

```yaml
secrets:
  - name: ingress_tls
    kind: templates.tls_cert

templates:
  tls_cert:
    fields:
      tls.crt:
        generator:
          kind: static
          config:
            # Use cert-manager or provide real certificate
            default: |
              -----BEGIN CERTIFICATE-----
              MIIDXTCCAkWgAwIBAgIJAKZ...
              -----END CERTIFICATE-----
      tls.key:
        generator:
          kind: static
          config:
            # Use cert-manager or provide real key
            default: |
              -----BEGIN PRIVATE KEY-----
              MIIEvgIBADANBgkqhkiG9w...
              -----END PRIVATE KEY-----
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: default
          secret_name: myapp-tls
          secret_type: kubernetes.io/tls
          labels:
            app: myapp
            cert-manager.io/certificate-name: myapp-cert
          annotations:
            cert-manager.io/alt-names: myapp.example.com,www.myapp.example.com
```

##### Docker Registry Secret

```yaml
secrets:
  - name: docker_registry_auth
    kind: templates.docker_config

templates:
  docker_config:
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
                    "password": "secret-token-here",
                    "email": "robot@example.com",
                    "auth": "bXlhcHAtcm9ib3Q6c2VjcmV0LXRva2VuLWhlcmU="
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
          annotations:
            description: Docker registry credentials for private images
```

Usage in Pod:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: myapp
spec:
  containers:
  - name: app
    image: registry.example.com/myapp:latest
  imagePullSecrets:
  - name: registry-credentials
```

##### Basic Authentication Secret

```yaml
secrets:
  - name: admin_credentials
    kind: templates.basic_auth

templates:
  basic_auth:
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
          secret_name: basic-auth
          secret_type: kubernetes.io/basic-auth
          labels:
            app: myapp
            type: auth
          annotations:
            description: Basic auth for admin panel
```

##### SSH Private Key Secret

```yaml
secrets:
  - name: deploy_key
    kind: templates.ssh_key

templates:
  ssh_key:
    fields:
      ssh-privatekey:
        generator:
          kind: static
          config:
            # Generate with: ssh-keygen -t ed25519 -C "deploy@example.com"
            default: |
              -----BEGIN OPENSSH PRIVATE KEY-----
              b3BlbnNzaC1rZXktdjEAAAAABG5vbmUA...
              -----END OPENSSH PRIVATE KEY-----
      ssh-publickey:
        generator:
          kind: static
          config:
            default: ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA... deploy@example.com
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: default
          secret_name: deploy-key
          secret_type: kubernetes.io/ssh-auth
          labels:
            app: myapp
            type: deploy-key
          annotations:
            description: SSH key for Git repository access
```

Usage in Pod:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: git-sync
spec:
  containers:
  - name: git-sync
    image: k8s.gcr.io/git-sync/git-sync:v3.6.3
    volumeMounts:
    - name: git-secret
      mountPath: /etc/git-secret
      readOnly: true
  volumes:
  - name: git-secret
    secret:
      secretName: deploy-key
      defaultMode: 0400
```

##### Multiple Secrets in Same Object

```yaml
secrets:
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
          labels:
            app: myapp

  - name: redis_password
    kind: random_password
    config:
      length: 16
      special: false
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: default
          secret_name: app-secrets  # Same secret object
          data_key: redis-password
          labels:
            app: myapp

  - name: jwt_secret
    kind: random_string
    config:
      length: 64
      charset: base64
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: default
          secret_name: app-secrets  # Same secret object
          data_key: jwt-secret
          labels:
            app: myapp
```

### external_secret

Generates External Secrets Operator manifests for GitOps workflows. The manifests reference secrets stored in external backends (AWS Secrets Manager, Azure Key Vault, HashiCorp Vault, etc.).

#### Configuration Options

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `namespace` | string | Yes | - | Target namespace for the ExternalSecret |
| `secret_name` | string | Yes | - | Name of the Kubernetes Secret to create |
| `external_secret_name` | string | Yes | - | Name of the ExternalSecret resource |
| `secret_store_ref` | string | Yes | - | Reference to SecretStore or ClusterSecretStore |
| `backend_type` | string | Yes | - | Backend type: `aws`, `azure`, `vault`, `gcpsm` |
| `backend_key` | string | Yes | - | Path to secret in backend system |
| `refresh_interval` | string | No | `1h` | How often to sync (e.g., `15m`, `1h`, `24h`) |
| `output_path` | string | No | - | Path to write ExternalSecret manifest |
| `labels` | dict | No | `{}` | Labels for the ExternalSecret resource |
| `annotations` | dict | No | `{}` | Annotations for the ExternalSecret resource |

#### Examples

##### AWS Secrets Manager Integration

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
      config:
        context: production-cluster

secrets:
  - name: database_password
    kind: random_password
    config:
      length: 32
      special: true
    targets:
      - provider: kubernetes
        kind: external_secret
        config:
          namespace: "{{ var.namespace }}"
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
          annotations:
            description: PostgreSQL password from AWS Secrets Manager
```

Generated manifest:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: postgres-password-sync
  namespace: production
  labels:
    app: postgres
    managed-by: secretzero
  annotations:
    description: PostgreSQL password from AWS Secrets Manager
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secretsmanager
    kind: SecretStore
  target:
    name: postgres-credentials
    creationPolicy: Owner
  data:
  - secretKey: password
    remoteRef:
      key: prod/db/postgres/password
```

##### Azure Key Vault Integration

```yaml
secrets:
  - name: api_key
    kind: random_string
    config:
      length: 32
      charset: hex
    targets:
      - provider: kubernetes
        kind: external_secret
        config:
          namespace: default
          secret_name: stripe-credentials
          external_secret_name: stripe-api-key-sync
          secret_store_ref: azure-keyvault
          backend_type: azure
          backend_key: stripe-api-key
          refresh_interval: 24h
          output_path: ./manifests/external-secret-stripe.yaml
          labels:
            app: payment-service
            cloud-provider: azure
```

##### HashiCorp Vault Integration

```yaml
secrets:
  - name: vault_secret
    kind: random_string
    config:
      length: 64
      charset: base64
    targets:
      - provider: kubernetes
        kind: external_secret
        config:
          namespace: default
          secret_name: app-config
          external_secret_name: app-config-sync
          secret_store_ref: vault-backend
          backend_type: vault
          backend_key: secret/data/myapp/config
          refresh_interval: 15m
          output_path: ./manifests/external-secret-vault.yaml
          labels:
            app: myapp
            backend: vault
```

##### Google Cloud Secret Manager Integration

```yaml
secrets:
  - name: gcp_secret
    kind: random_password
    config:
      length: 32
      special: true
    targets:
      - provider: kubernetes
        kind: external_secret
        config:
          namespace: default
          secret_name: gcp-credentials
          external_secret_name: gcp-secret-sync
          secret_store_ref: gcpsm
          backend_type: gcpsm
          backend_key: projects/123456789/secrets/myapp-credentials
          refresh_interval: 30m
          output_path: ./manifests/external-secret-gcp.yaml
          labels:
            app: myapp
            cloud-provider: gcp
```

## Complete Working Examples

### Basic Kubernetes Secrets

Minimal setup for common secret types:

```yaml
version: '1.0'

variables:
  namespace: default

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
      length: 24
      special: true
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: "{{ var.namespace }}"
          secret_name: postgres-credentials
          data_key: password
          labels:
            app: myapp
            component: database

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
          namespace: "{{ var.namespace }}"
          secret_name: app-secrets
          data_key: api-key
          labels:
            app: myapp
```

### TLS Certificates for Ingress

```yaml
version: '1.0'

variables:
  namespace: default
  domain: example.com

providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient
      config:
        context: production

secrets:
  - name: tls_certificate
    kind: templates.tls_cert

templates:
  tls_cert:
    description: TLS certificate for ingress
    fields:
      tls.crt:
        generator:
          kind: static
          config:
            # In production, use cert-manager or real certificates
            default: |
              -----BEGIN CERTIFICATE-----
              MIIDXTCCAkWgAwIBAgIJAKZ4N5gR8o0pMA0GCSqGSIb3DQEBCwUAMEUxCzAJBgNV
              ...
              -----END CERTIFICATE-----
      tls.key:
        generator:
          kind: static
          config:
            default: |
              -----BEGIN PRIVATE KEY-----
              MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDExample...
              -----END PRIVATE KEY-----
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: "{{ var.namespace }}"
          secret_name: "{{ var.domain }}-tls"
          secret_type: kubernetes.io/tls
          labels:
            app: myapp
            cert-manager.io/certificate-name: "{{ var.domain }}"
          annotations:
            description: TLS certificate for {{ var.domain }}
```

Ingress usage:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp
  namespace: default
spec:
  tls:
  - hosts:
    - example.com
    secretName: example.com-tls
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

### Docker Registry Credentials

```yaml
version: '1.0'

variables:
  namespace: default
  registry_url: registry.example.com
  registry_username: myapp-robot

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
    fields:
      .dockerconfigjson:
        generator:
          kind: static
          config:
            default: |
              {
                "auths": {
                  "{{ var.registry_url }}": {
                    "username": "{{ var.registry_username }}",
                    "password": "generated-token-here",
                    "email": "robot@example.com",
                    "auth": "bXlhcHAtcm9ib3Q6Z2VuZXJhdGVkLXRva2VuLWhlcmU="
                  }
                }
              }
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: "{{ var.namespace }}"
          secret_name: registry-credentials
          secret_type: kubernetes.io/dockerconfigjson
          labels:
            app: myapp
            type: registry
```

Deployment usage:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  template:
    spec:
      imagePullSecrets:
      - name: registry-credentials
      containers:
      - name: app
        image: registry.example.com/myapp:latest
```

### Multiple Namespaces

```yaml
version: '1.0'

variables:
  cluster: production
  namespaces:
    - production
    - staging
    - development

providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient
      config:
        context: "{{ var.cluster }}"

secrets:
  # Same password across all environments
  - name: shared_database_password
    kind: random_password
    config:
      length: 32
      special: true
    one_time: true
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
            tier: database
      
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: staging
          secret_name: postgres-admin
          data_key: password
          labels:
            app: postgres
            environment: staging
            tier: database
      
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: development
          secret_name: postgres-admin
          data_key: password
          labels:
            app: postgres
            environment: development
            tier: database

  # Different secrets per environment
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
            app: myapp
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
            app: myapp
            environment: staging
```

### External Secrets Operator

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
      config:
        context: production-cluster

secrets:
  # Database credentials from AWS Secrets Manager
  - name: database_credentials
    kind: templates.db_creds_external

  # API keys from Azure Key Vault
  - name: api_keys
    kind: templates.api_keys_external

templates:
  db_creds_external:
    description: Database credentials synced from AWS
    fields:
      password:
        generator:
          kind: random_password
          config:
            length: 32
            special: true
    targets:
      - provider: kubernetes
        kind: external_secret
        config:
          namespace: "{{ var.namespace }}"
          secret_name: postgres-credentials
          external_secret_name: postgres-creds-sync
          secret_store_ref: aws-secretsmanager
          backend_type: aws
          backend_key: prod/db/postgres/credentials
          refresh_interval: 1h
          output_path: ./manifests/external-secret-db.yaml
          labels:
            app: postgres
            managed-by: secretzero

  api_keys_external:
    description: API keys synced from Azure Key Vault
    fields:
      stripe_key:
        generator:
          kind: random_string
          config:
            length: 32
            charset: hex
      sendgrid_key:
        generator:
          kind: random_string
          config:
            length: 32
            charset: hex
    targets:
      - provider: kubernetes
        kind: external_secret
        config:
          namespace: "{{ var.namespace }}"
          secret_name: api-keys
          external_secret_name: api-keys-sync
          secret_store_ref: azure-keyvault
          backend_type: azure
          backend_key: api-keys
          refresh_interval: 24h
          output_path: ./manifests/external-secret-api.yaml
          labels:
            app: myapp
            cloud-provider: azure
```

## RBAC Permissions

### ServiceAccount for In-Cluster Usage

When using `in_cluster: true` authentication, create a ServiceAccount with appropriate permissions:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: secretzero
  namespace: default
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: secretzero-manager
  namespace: default
rules:
- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["get", "list", "create", "update", "patch"]
- apiGroups: [""]
  resources: ["namespaces"]
  verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: secretzero-manager
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

### Multi-Namespace RBAC

For managing secrets across multiple namespaces, use ClusterRole:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: secretzero
  namespace: secretzero-system
---
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
  name: secretzero-manager
subjects:
- kind: ServiceAccount
  name: secretzero
  namespace: secretzero-system
roleRef:
  kind: ClusterRole
  name: secretzero-manager
  apiGroup: rbac.authorization.k8s.io
```

### Restricted RBAC (Single Namespace)

For least-privilege access limited to specific namespaces:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: secretzero
  namespace: production
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: secretzero-secrets-only
  namespace: production
rules:
- apiGroups: [""]
  resources: ["secrets"]
  resourceNames: ["postgres-credentials", "app-secrets", "myapp-tls"]
  verbs: ["get", "update", "patch"]
- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["create"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: secretzero-secrets-only
  namespace: production
subjects:
- kind: ServiceAccount
  name: secretzero
  namespace: production
roleRef:
  kind: Role
  name: secretzero-secrets-only
  apiGroup: rbac.authorization.k8s.io
```

### External Secrets Operator RBAC

For External Secrets Operator integration:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: secretzero
  namespace: default
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: secretzero-external-secrets
  namespace: default
rules:
- apiGroups: ["external-secrets.io"]
  resources: ["externalsecrets", "secretstores", "clustersecretstores"]
  verbs: ["get", "list", "create", "update", "patch"]
- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: secretzero-external-secrets
  namespace: default
subjects:
- kind: ServiceAccount
  name: secretzero
  namespace: default
roleRef:
  kind: Role
  name: secretzero-external-secrets
  apiGroup: rbac.authorization.k8s.io
```

### Job or CronJob Deployment

Example CronJob using ServiceAccount:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: secretzero-sync
  namespace: default
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: secretzero
          restartPolicy: OnFailure
          containers:
          - name: secretzero
            image: secretzero/secretzero:latest
            command:
            - secretzero
            - sync
            - -f
            - /config/Secretfile.yml
            volumeMounts:
            - name: config
              mountPath: /config
              readOnly: true
          volumes:
          - name: config
            configMap:
              name: secretzero-config
```

## Best Practices

### Use Namespaces for Isolation

Organize secrets by namespace to enforce isolation and RBAC boundaries:

```yaml
# Good: Separate namespaces per environment
namespace: production  # Prod secrets
namespace: staging     # Staging secrets
namespace: development # Dev secrets

# Avoid: All secrets in default namespace
namespace: default
```

### Label Secrets Consistently

Use consistent labeling for organization, filtering, and management:

```yaml
labels:
  app: myapp                    # Application name
  component: database           # Component type
  environment: production       # Environment
  managed-by: secretzero        # Management tool
  team: platform               # Owning team
  version: v1.2.3              # Application version
```

### Use Appropriate Secret Types

Choose the correct secret type for your use case:

```yaml
# Good: TLS type for certificates
secret_type: kubernetes.io/tls

# Good: Docker config for registry
secret_type: kubernetes.io/dockerconfigjson

# Good: Opaque for general secrets
secret_type: Opaque

# Avoid: Opaque for everything
secret_type: Opaque  # For TLS cert (should be kubernetes.io/tls)
```

### Rotate Secrets Regularly

Use annotations to track rotation schedules:

```yaml
annotations:
  description: Database credentials
  rotation-policy: 90-days
  last-rotated: "2024-01-15"
  next-rotation: "2024-04-15"
  owner: platform-team@example.com
```

### Use External Secrets for Cloud Integration

For cloud-native deployments, use External Secrets Operator:

```yaml
# Good: Sync from cloud backends
kind: external_secret
config:
  backend_type: aws
  backend_key: prod/db/credentials
  refresh_interval: 1h

# Avoid: Hardcoding cloud credentials in Kubernetes
kind: kubernetes_secret
config:
  # Cloud credentials embedded
```

### Limit RBAC Permissions

Follow principle of least privilege:

```yaml
# Good: Specific permissions
rules:
- apiGroups: [""]
  resources: ["secrets"]
  resourceNames: ["app-secrets"]  # Specific secret
  verbs: ["get", "update"]

# Avoid: Overly broad permissions
rules:
- apiGroups: ["*"]
  resources: ["*"]
  verbs: ["*"]
```

### Use Templates for Consistency

Define reusable templates for common secret patterns:

```yaml
templates:
  database_credentials:
    fields:
      username:
        generator: {kind: static, config: {default: postgres}}
      password:
        generator: {kind: random_password, config: {length: 32}}
      host:
        generator: {kind: static, config: {default: postgres.default.svc}}
      port:
        generator: {kind: static, config: {default: "5432"}}
      database:
        generator: {kind: static, config: {default: myapp}}
```

### Version Control Secret Configurations

Store Secretfile.yml in version control (not the secrets themselves):

```yaml
# Good: Configuration in Git
git add Secretfile.yml

# Never commit actual secrets
# Add to .gitignore:
*.secret
*.key
.env
```

### Use Descriptive Annotations

Add helpful metadata:

```yaml
annotations:
  description: PostgreSQL admin credentials for production
  owner: database-team@example.com
  docs: https://wiki.example.com/db-credentials
  support: https://support.example.com/secrets/pg-admin
  pagerduty: https://example.pagerduty.com/services/database
```

### Monitor Secret Access

Use audit logging and monitoring:

```yaml
labels:
  monitoring: enabled
  audit-log: required
  compliance: pci-dss
  
annotations:
  audit-retention: 90-days
  alert-on-access: "true"
```

## Integration Examples

### Mounting Secrets as Files

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
    - name: secrets
      mountPath: /etc/secrets
      readOnly: true
  volumes:
  - name: secrets
    secret:
      secretName: app-secrets
      items:
      - key: api-key
        path: api-key.txt
        mode: 0400
      - key: redis-password
        path: redis.password
        mode: 0400
```

### Using Secrets as Environment Variables

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

### Init Containers with Secrets

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: myapp
spec:
  initContainers:
  - name: init-config
    image: busybox:latest
    command:
    - sh
    - -c
    - |
      cat /secrets/config.yaml > /config/app-config.yaml
      chmod 0600 /config/app-config.yaml
    volumeMounts:
    - name: secrets
      mountPath: /secrets
      readOnly: true
    - name: config
      mountPath: /config
  containers:
  - name: app
    image: myapp:latest
    volumeMounts:
    - name: config
      mountPath: /config
      readOnly: true
  volumes:
  - name: secrets
    secret:
      secretName: app-secrets
  - name: config
    emptyDir: {}
```

### External Secrets Operator

Prerequisites:

```bash
# Install External Secrets Operator
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets -n external-secrets-system --create-namespace

# Create SecretStore for AWS Secrets Manager
kubectl apply -f - <<EOF
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
            name: external-secrets
EOF
```

SecretZero configuration:

```yaml
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
      special: true
    targets:
      - provider: kubernetes
        kind: external_secret
        config:
          namespace: default
          secret_name: postgres-credentials
          external_secret_name: postgres-sync
          secret_store_ref: aws-secretsmanager
          backend_type: aws
          backend_key: prod/db/postgres/password
          refresh_interval: 1h
          output_path: ./manifests/external-secret.yaml
```

Deploy generated manifest:

```bash
# Generate manifest
secretzero sync -f Secretfile.yml

# Apply to cluster
kubectl apply -f ./manifests/external-secret.yaml

# Verify ExternalSecret
kubectl get externalsecrets -n default

# Check synced Secret
kubectl get secret postgres-credentials -n default
```

### Sealed Secrets Integration

Install Sealed Secrets controller:

```bash
helm repo add sealed-secrets https://bitnami-labs.github.io/sealed-secrets
helm install sealed-secrets sealed-secrets/sealed-secrets -n kube-system
```

Generate secrets, seal them, and commit to Git:

```bash
# Generate regular secrets
secretzero sync -f Secretfile.yml

# Seal the secrets
kubectl get secret app-secrets -n default -o yaml | \
  kubeseal -o yaml > sealed-secret.yaml

# Commit sealed secret to Git
git add sealed-secret.yaml
git commit -m "Add sealed secrets"
```

### Cert-Manager Integration

Use cert-manager for automated TLS certificate management:

```yaml
# Let cert-manager handle TLS certificates
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: myapp-tls
  namespace: default
spec:
  secretName: myapp-tls
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
  - myapp.example.com
  - www.myapp.example.com

# Use SecretZero for other secrets
secrets:
  - name: database_password
    kind: random_password
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: default
          secret_name: postgres-credentials
```

## Troubleshooting

### RBAC Permission Errors

**Symptom:**

```
Error: secrets is forbidden: User "system:serviceaccount:default:secretzero" 
cannot create resource "secrets" in API group "" in the namespace "production"
```

**Solution:**

Check ServiceAccount permissions:

```bash
# Check current permissions
kubectl auth can-i create secrets --as=system:serviceaccount:default:secretzero -n production

# Review RoleBindings
kubectl get rolebindings -n production
kubectl describe rolebinding secretzero-manager -n production

# Verify Role has correct permissions
kubectl get role secretzero-manager -n production -o yaml
```

Fix RBAC:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: secretzero-manager
  namespace: production
rules:
- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["get", "list", "create", "update", "patch"]
```

### Namespace Not Found

**Symptom:**

```
Error: namespace "production" not found
```

**Solution:**

Create namespace before syncing secrets:

```bash
# Create namespace
kubectl create namespace production

# Or use YAML
kubectl apply -f - <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    name: production
    environment: production
EOF
```

Add namespace creation to CI/CD:

```bash
# In CI/CD pipeline
kubectl create namespace production --dry-run=client -o yaml | kubectl apply -f -
secretzero sync -f Secretfile.yml
```

### Secret Not Mounting in Pod

**Symptom:**

```
Error: couldn't find key api-key in Secret default/app-secrets
```

**Solution:**

Verify secret exists and contains the key:

```bash
# Check if secret exists
kubectl get secret app-secrets -n default

# Inspect secret data
kubectl get secret app-secrets -n default -o json | jq '.data | keys'

# Decode and view secret value
kubectl get secret app-secrets -n default -o json | jq -r '.data["api-key"]' | base64 -d
```

Check Pod volume mount configuration:

```yaml
# Ensure key name matches
volumeMounts:
- name: secrets
  mountPath: /etc/secrets
volumes:
- name: secrets
  secret:
    secretName: app-secrets
    items:
    - key: api-key  # Must match key in Secret
      path: api-key.txt
```

### Secret Too Large

**Symptom:**

```
Error: Secret "large-secret" is invalid: data: Too long: must have at most 1048576 bytes
```

**Solution:**

Kubernetes secrets are limited to 1MB. For large data:

1. **Split into multiple secrets:**

```yaml
secrets:
  - name: config_part1
    kind: static
    config:
      default: <first 500KB>
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: default
          secret_name: config-part1

  - name: config_part2
    kind: static
    config:
      default: <second 500KB>
    targets:
      - provider: kubernetes
        kind: kubernetes_secret
        config:
          namespace: default
          secret_name: config-part2
```

2. **Use ConfigMap for non-sensitive large data**

3. **Store in external system** (S3, cloud storage) and use External Secrets

### Authentication Failures

**Symptom:**

```
Error: unable to load in-cluster configuration, KUBERNETES_SERVICE_HOST and 
KUBERNETES_SERVICE_PORT must be defined
```

**Solution:**

When using `in_cluster: true`, ensure running inside a Kubernetes pod:

```yaml
# Correct: In-cluster config
providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient
      config:
        in_cluster: true  # Only works inside pods
```

For local development, use kubeconfig:

```yaml
# Local development
providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient
      config:
        kubeconfig: ~/.kube/config
        context: my-cluster
```

### ImagePullSecrets Not Working

**Symptom:**

```
Error: ErrImagePull
Failed to pull image "registry.example.com/myapp:latest": 
rpc error: code = Unknown desc = Error response from daemon: 
pull access denied for registry.example.com/myapp
```

**Solution:**

Verify imagePullSecret:

```bash
# Check secret exists
kubectl get secret registry-credentials -n default

# Verify secret type
kubectl get secret registry-credentials -n default -o yaml | grep type
# Should be: type: kubernetes.io/dockerconfigjson

# Test secret format
kubectl get secret registry-credentials -n default -o json | \
  jq -r '.data[".dockerconfigjson"]' | base64 -d | jq
```

Ensure Pod references the secret:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: myapp
spec:
  imagePullSecrets:
  - name: registry-credentials  # Must match secret name
  containers:
  - name: app
    image: registry.example.com/myapp:latest
```

Add imagePullSecret to ServiceAccount (applies to all pods using it):

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: default
  namespace: default
imagePullSecrets:
- name: registry-credentials
```

### External Secret Not Syncing

**Symptom:**

```
ExternalSecret status: SecretSyncedError
```

**Solution:**

Check ExternalSecret status:

```bash
# View ExternalSecret
kubectl get externalsecrets -n default
kubectl describe externalsecret postgres-sync -n default

# Check events
kubectl get events -n default --sort-by='.lastTimestamp' | grep ExternalSecret

# Verify SecretStore
kubectl get secretstore aws-secretsmanager -n default -o yaml

# Check operator logs
kubectl logs -n external-secrets-system -l app.kubernetes.io/name=external-secrets
```

Verify backend access:

```bash
# Test AWS Secrets Manager access
aws secretsmanager get-secret-value --secret-id prod/db/postgres/password

# Check IAM permissions for ServiceAccount (IRSA)
kubectl describe serviceaccount external-secrets -n default
```

## Security Considerations

### Encryption at Rest

Enable encryption for Secrets at rest in etcd:

```yaml
# /etc/kubernetes/encryption-config.yaml
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
  - resources:
    - secrets
    providers:
    - aescbc:
        keys:
        - name: key1
          secret: <base64-encoded-key>
    - identity: {}
```

Configure API server:

```bash
# Add to kube-apiserver flags
--encryption-provider-config=/etc/kubernetes/encryption-config.yaml
```

Verify encryption:

```bash
# Check if secrets are encrypted in etcd
ETCDCTL_API=3 etcdctl get /registry/secrets/default/app-secrets | hexdump -C
# Should show encrypted data, not plaintext
```

### RBAC Least Privilege

Minimize permissions:

```yaml
# Good: Specific resources and verbs
rules:
- apiGroups: [""]
  resources: ["secrets"]
  resourceNames: ["app-secrets", "postgres-credentials"]
  verbs: ["get", "update"]

# Avoid: Wildcard permissions
rules:
- apiGroups: ["*"]
  resources: ["*"]
  verbs: ["*"]
```

Use separate ServiceAccounts:

```yaml
# Read-only ServiceAccount for applications
apiVersion: v1
kind: ServiceAccount
metadata:
  name: app-readonly
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: secret-reader
rules:
- apiGroups: [""]
  resources: ["secrets"]
  resourceNames: ["app-secrets"]
  verbs: ["get"]

# Write ServiceAccount for SecretZero
apiVersion: v1
kind: ServiceAccount
metadata:
  name: secretzero
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: secret-writer
rules:
- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["get", "create", "update"]
```

### Namespace Isolation

Use namespaces for security boundaries:

```yaml
# Separate namespaces per environment
production:   # PCI-compliant workloads
staging:      # Pre-production testing
development:  # Development workloads

# Separate namespaces per team/application
team-a:       # Team A secrets
team-b:       # Team B secrets
shared:       # Shared infrastructure secrets
```

Enable NetworkPolicies:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-cross-namespace
  namespace: production
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: production
```

### Audit Logging

Enable audit logging for secret access:

```yaml
# /etc/kubernetes/audit-policy.yaml
apiVersion: audit.k8s.io/v1
kind: Policy
rules:
- level: RequestResponse
  verbs: ["get", "list", "create", "update", "patch", "delete"]
  resources:
  - group: ""
    resources: ["secrets"]
  namespaces: ["production", "staging"]
```

Configure API server:

```bash
# Add to kube-apiserver flags
--audit-log-path=/var/log/kubernetes/audit.log
--audit-policy-file=/etc/kubernetes/audit-policy.yaml
--audit-log-maxage=30
--audit-log-maxbackup=10
--audit-log-maxsize=100
```

### Secret Scanning

Use tools to prevent secret leaks:

```bash
# Scan Git repositories
truffleHog --regex --entropy=True https://github.com/org/repo

# Scan container images
trivy image myapp:latest

# Scan Kubernetes manifests
kubesec scan deployment.yaml

# Check for secrets in etcd backups
grep -r "password\|token\|key" /var/lib/etcd/backup/
```

Pre-commit hook:

```bash
#!/bin/bash
# .git/hooks/pre-commit

# Check for common secret patterns
if git diff --cached | grep -E "(password|token|secret|key).*:.*['\"]" | grep -v "secretzero"; then
    echo "Error: Potential secret detected in commit"
    exit 1
fi

# Run secret scanner
if command -v gitleaks &> /dev/null; then
    gitleaks protect --staged
fi
```

### Pod Security Standards

Enforce Pod Security Standards:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

Use security contexts:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: myapp
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    fsGroup: 1000
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
      readOnly: true
  volumes:
  - name: secrets
    secret:
      secretName: app-secrets
      defaultMode: 0400
```

### External Secrets Best Practices

For External Secrets Operator:

1. **Use IRSA (IAM Roles for Service Accounts)**:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: external-secrets
  namespace: external-secrets-system
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/external-secrets-role
```

2. **Limit SecretStore scope**:

```yaml
# Use SecretStore (namespace-scoped) instead of ClusterSecretStore
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: aws-secretsmanager
  namespace: production  # Limited to production namespace
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-west-2
```

3. **Set appropriate refresh intervals**:

```yaml
# Balance freshness vs. API costs
refresh_interval: 1h   # Frequently changing secrets
refresh_interval: 24h  # Static secrets
refresh_interval: 15m  # Time-sensitive credentials
```

4. **Monitor ExternalSecret status**:

```bash
# Alert on sync failures
kubectl get externalsecrets -A -o json | \
  jq -r '.items[] | select(.status.conditions[] | select(.type=="Ready" and .status=="False")) | 
  "\(.metadata.namespace)/\(.metadata.name): \(.status.conditions[0].message)"'
```

---

For more information, see:
- [Kubernetes Secrets Documentation](https://kubernetes.io/docs/concepts/configuration/secret/)
- [External Secrets Operator](https://external-secrets.io/)
- [Kubernetes RBAC](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
- [Examples](../../examples/)
