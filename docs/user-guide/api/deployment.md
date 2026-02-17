# Production Deployment

This guide covers deploying the SecretZero API in production environments using systemd, Docker, Kubernetes, and cloud platforms.

## General Best Practices

Before deploying to production:

### 1. Security

- **Always use HTTPS** - Never expose the API over plain HTTP
- **Generate strong API keys** - Use cryptographically secure random keys
- **Rotate API keys regularly** - Establish a rotation schedule
- **Use secrets management** - Store API keys in vault/secrets manager
- **Enable audit logging** - Monitor all API access
- **Restrict network access** - Use firewalls and network policies

### 2. Reliability

- **Run behind a reverse proxy** - nginx, Caddy, or cloud load balancer
- **Implement health checks** - Use `/health` endpoint
- **Enable auto-restart** - Configure process managers to restart on failure
- **Set resource limits** - Prevent resource exhaustion
- **Use multiple replicas** - For high availability

### 3. Performance

- **Enable connection pooling** - Reuse HTTP connections
- **Configure timeouts** - Prevent hung requests
- **Implement rate limiting** - Protect against abuse
- **Use caching** - Where appropriate for read-heavy workloads
- **Monitor metrics** - Track API performance and errors

### 4. Operations

- **Centralized logging** - Aggregate logs from all instances
- **Monitoring and alerting** - Track availability and performance
- **Backup configuration** - Regularly backup Secretfile and lockfile
- **Document deployment** - Keep deployment procedures up to date
- **Test disaster recovery** - Practice recovery procedures

---

## systemd Deployment

Deploy SecretZero as a systemd service on Linux systems.

### Step 1: Create User and Directory

```bash
# Create dedicated user
sudo useradd -r -s /bin/false secretzero

# Create directories
sudo mkdir -p /opt/secretzero /var/log/secretzero
sudo chown secretzero:secretzero /opt/secretzero /var/log/secretzero
```

### Step 2: Install SecretZero

```bash
# Create virtual environment
sudo -u secretzero python3 -m venv /opt/secretzero/venv

# Install SecretZero
sudo -u secretzero /opt/secretzero/venv/bin/pip install secretzero[all]

# Copy Secretfile
sudo cp Secretfile.yml /opt/secretzero/
sudo chown secretzero:secretzero /opt/secretzero/Secretfile.yml
```

### Step 3: Configure API Key

```bash
# Generate API key
API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

# Store in secrets management or environment file
echo "SECRETZERO_API_KEY=$API_KEY" | sudo tee /opt/secretzero/.env
sudo chmod 600 /opt/secretzero/.env
sudo chown secretzero:secretzero /opt/secretzero/.env
```

### Step 4: Create systemd Service

Create `/etc/systemd/system/secretzero-api.service`:

```ini
[Unit]
Description=SecretZero API Server
Documentation=https://github.com/zloeber/SecretZero
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=secretzero
Group=secretzero
WorkingDirectory=/opt/secretzero

# Environment configuration
EnvironmentFile=/opt/secretzero/.env
Environment="SECRETZERO_HOST=127.0.0.1"
Environment="SECRETZERO_PORT=8000"
Environment="SECRETZERO_CONFIG=/opt/secretzero/Secretfile.yml"

# Start command
ExecStart=/opt/secretzero/venv/bin/secretzero-api

# Restart configuration
Restart=always
RestartSec=10
StartLimitBurst=3
StartLimitInterval=60

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/secretzero /var/log/secretzero
CapabilityBoundingSet=
AmbientCapabilities=
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
RestrictNamespaces=true
LockPersonality=true
RestrictRealtime=true
RestrictSUIDSGID=true
RemoveIPC=true
PrivateMounts=true
SystemCallFilter=@system-service
SystemCallErrorNumber=EPERM

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=secretzero-api

# Resource limits
MemoryMax=512M
TasksMax=100
CPUQuota=50%

[Install]
WantedBy=multi-user.target
```

### Step 5: Start and Enable Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Start service
sudo systemctl start secretzero-api

# Check status
sudo systemctl status secretzero-api

# Enable auto-start
sudo systemctl enable secretzero-api

# View logs
sudo journalctl -u secretzero-api -f
```

### Step 6: Configure nginx Reverse Proxy

Create `/etc/nginx/sites-available/secretzero`:

```nginx
upstream secretzero_api {
    server 127.0.0.1:8000;
    keepalive 32;
}

# Rate limiting
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_req_status 429;

server {
    listen 80;
    server_name api.example.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.example.com;
    
    # SSL configuration
    ssl_certificate /etc/ssl/certs/api.example.com.crt;
    ssl_certificate_key /etc/ssl/private/api.example.com.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    # Logging
    access_log /var/log/nginx/secretzero-api-access.log;
    error_log /var/log/nginx/secretzero-api-error.log;
    
    # Proxy configuration
    location / {
        # Rate limiting
        limit_req zone=api_limit burst=20 nodelay;
        
        proxy_pass http://secretzero_api;
        proxy_http_version 1.1;
        
        # Headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        
        # Timeouts
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
        
        # Buffer configuration
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_busy_buffers_size 8k;
    }
    
    # Health check endpoint (optional bypass of rate limit)
    location = /health {
        proxy_pass http://secretzero_api;
        access_log off;
    }
}
```

Enable and restart nginx:

```bash
sudo ln -s /etc/nginx/sites-available/secretzero /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## Docker Deployment

Deploy SecretZero API as a Docker container.

### Dockerfile

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create app user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements or install directly
RUN pip install secretzero[all]

# Copy Secretfile
COPY --chown=appuser:appuser Secretfile.yml /app/

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run API server
CMD ["secretzero-api"]
```

### Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  secretzero-api:
    build: .
    image: secretzero-api:latest
    container_name: secretzero-api
    restart: unless-stopped
    
    ports:
      - "127.0.0.1:8000:8000"
    
    environment:
      - SECRETZERO_HOST=0.0.0.0
      - SECRETZERO_PORT=8000
      - SECRETZERO_CONFIG=/app/Secretfile.yml
      - SECRETZERO_API_KEY=${SECRETZERO_API_KEY}
    
    volumes:
      - ./Secretfile.yml:/app/Secretfile.yml:ro
      - ./.gitsecrets.lock:/app/.gitsecrets.lock
    
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
    
    security_opt:
      - no-new-privileges:true
    
    read_only: true
    tmpfs:
      - /tmp
    
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### Build and Run

```bash
# Build image
docker build -t secretzero-api:latest .

# Generate API key
export SECRETZERO_API_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")

# Run with docker-compose
docker-compose up -d

# Check logs
docker-compose logs -f secretzero-api

# Check health
curl http://localhost:8000/health
```

### Docker with nginx Sidecar

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  secretzero-api:
    build: .
    image: secretzero-api:latest
    restart: unless-stopped
    environment:
      - SECRETZERO_HOST=0.0.0.0
      - SECRETZERO_PORT=8000
      - SECRETZERO_API_KEY=${SECRETZERO_API_KEY}
    volumes:
      - ./Secretfile.yml:/app/Secretfile.yml:ro
    networks:
      - secretzero-net
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    networks:
      - secretzero-net
    depends_on:
      - secretzero-api

networks:
  secretzero-net:
    driver: bridge
```

---

## Kubernetes Deployment

Deploy SecretZero API on Kubernetes.

### Namespace

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: secretzero
  labels:
    name: secretzero
```

### Secret (API Key)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: secretzero-api-key
  namespace: secretzero
type: Opaque
stringData:
  api-key: "your-api-key-here"  # Replace with actual key
```

Generate and apply:

```bash
kubectl create secret generic secretzero-api-key \
  --from-literal=api-key=$(python -c "import secrets; print(secrets.token_urlsafe(32))") \
  -n secretzero
```

### ConfigMap (Secretfile)

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: secretzero-config
  namespace: secretzero
data:
  Secretfile.yml: |
    version: "1.0"
    secrets:
      - name: example_secret
        kind: random_password
        rotation_period: 90d
        targets:
          - provider: aws
            kind: ssm_parameter
            config:
              name: /prod/example
```

### Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: secretzero-api
  namespace: secretzero
  labels:
    app: secretzero-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: secretzero-api
  template:
    metadata:
      labels:
        app: secretzero-api
    spec:
      serviceAccountName: secretzero-api
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
        seccompProfile:
          type: RuntimeDefault
      
      containers:
      - name: api
        image: secretzero-api:latest
        imagePullPolicy: IfNotPresent
        
        ports:
        - containerPort: 8000
          name: http
          protocol: TCP
        
        env:
        - name: SECRETZERO_HOST
          value: "0.0.0.0"
        - name: SECRETZERO_PORT
          value: "8000"
        - name: SECRETZERO_CONFIG
          value: "/config/Secretfile.yml"
        - name: SECRETZERO_API_KEY
          valueFrom:
            secretKeyRef:
              name: secretzero-api-key
              key: api-key
        
        volumeMounts:
        - name: config
          mountPath: /config
          readOnly: true
        - name: lockfile
          mountPath: /app/.gitsecrets.lock
          subPath: .gitsecrets.lock
        
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 500m
            memory: 512Mi
        
        livenessProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 10
          periodSeconds: 30
          timeoutSeconds: 5
          failureThreshold: 3
        
        readinessProbe:
          httpGet:
            path: /health
            port: http
          initialDelaySeconds: 5
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          runAsNonRoot: true
          runAsUser: 1000
          capabilities:
            drop:
            - ALL
      
      volumes:
      - name: config
        configMap:
          name: secretzero-config
      - name: lockfile
        persistentVolumeClaim:
          claimName: secretzero-lockfile
```

### PersistentVolumeClaim (Lockfile Storage)

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: secretzero-lockfile
  namespace: secretzero
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
  storageClassName: standard
```

### Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: secretzero-api
  namespace: secretzero
  labels:
    app: secretzero-api
spec:
  type: ClusterIP
  ports:
  - port: 80
    targetPort: http
    protocol: TCP
    name: http
  selector:
    app: secretzero-api
```

### Ingress

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: secretzero-api
  namespace: secretzero
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/rate-limit: "10"
    nginx.ingress.kubernetes.io/limit-rps: "10"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - api.example.com
    secretName: secretzero-api-tls
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: secretzero-api
            port:
              number: 80
```

### ServiceAccount and RBAC

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: secretzero-api
  namespace: secretzero
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: secretzero-api
  namespace: secretzero
rules:
- apiGroups: [""]
  resources: ["secrets", "configmaps"]
  verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: secretzero-api
  namespace: secretzero
subjects:
- kind: ServiceAccount
  name: secretzero-api
roleRef:
  kind: Role
  name: secretzero-api
  apiGroup: rbac.authorization.k8s.io
```

### NetworkPolicy

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: secretzero-api-access
  namespace: secretzero
spec:
  podSelector:
    matchLabels:
      app: secretzero-api
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to:
    - namespaceSelector: {}
    ports:
    - protocol: TCP
      port: 443
  - to:
    - namespaceSelector: {}
    ports:
    - protocol: TCP
      port: 53
    - protocol: UDP
      port: 53
```

### Deploy to Kubernetes

```bash
# Apply all manifests
kubectl apply -f namespace.yaml
kubectl apply -f secret.yaml
kubectl apply -f configmap.yaml
kubectl apply -f pvc.yaml
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f ingress.yaml
kubectl apply -f rbac.yaml
kubectl apply -f networkpolicy.yaml

# Check deployment
kubectl get all -n secretzero
kubectl logs -n secretzero deployment/secretzero-api -f

# Test service
kubectl port-forward -n secretzero svc/secretzero-api 8000:80
curl http://localhost:8000/health
```

---

## Cloud Platform Deployment

### AWS ECS (Fargate)

**Task Definition:**

```json
{
  "family": "secretzero-api",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "containerDefinitions": [
    {
      "name": "secretzero-api",
      "image": "secretzero-api:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "SECRETZERO_HOST",
          "value": "0.0.0.0"
        }
      ],
      "secrets": [
        {
          "name": "SECRETZERO_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:secretzero-api-key"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/secretzero-api",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

### Azure Container Instances

```bash
az container create \
  --resource-group secretzero-rg \
  --name secretzero-api \
  --image secretzero-api:latest \
  --cpu 1 \
  --memory 1 \
  --ports 8000 \
  --environment-variables \
    SECRETZERO_HOST=0.0.0.0 \
    SECRETZERO_PORT=8000 \
  --secure-environment-variables \
    SECRETZERO_API_KEY=$API_KEY \
  --dns-name-label secretzero-api
```

### Google Cloud Run

```bash
gcloud run deploy secretzero-api \
  --image secretzero-api:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars SECRETZERO_HOST=0.0.0.0 \
  --set-secrets SECRETZERO_API_KEY=secretzero-api-key:latest
```

---

## Monitoring and Observability

### Prometheus Metrics

Add metrics endpoint (future feature):

```python
from prometheus_client import make_asgi_app

# Add metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
```

### Health Check Monitoring

```bash
#!/bin/bash
# health-check.sh

ENDPOINT="https://api.example.com/health"
TIMEOUT=5

if ! response=$(curl -sf --max-time $TIMEOUT "$ENDPOINT"); then
    echo "CRITICAL: API health check failed"
    exit 2
fi

status=$(echo "$response" | jq -r '.status')
if [ "$status" != "healthy" ]; then
    echo "CRITICAL: API reports unhealthy status"
    exit 2
fi

echo "OK: API is healthy"
exit 0
```

### Log Aggregation

Configure centralized logging:

```yaml
# Filebeat configuration
filebeat.inputs:
- type: log
  enabled: true
  paths:
    - /var/log/secretzero/*.log
  fields:
    app: secretzero-api
  fields_under_root: true

output.elasticsearch:
  hosts: ["elasticsearch:9200"]
```

---

## Backup and Recovery

### Backup Secretfile and Lockfile

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backup/secretzero"
DATE=$(date +%Y%m%d-%H%M%S)

# Create backup
mkdir -p "$BACKUP_DIR"
tar -czf "$BACKUP_DIR/secretzero-$DATE.tar.gz" \
    Secretfile.yml \
    .gitsecrets.lock

# Keep only last 30 days
find "$BACKUP_DIR" -name "secretzero-*.tar.gz" -mtime +30 -delete
```

### Restore from Backup

```bash
#!/bin/bash
# restore.sh

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup-file>"
    exit 1
fi

tar -xzf "$BACKUP_FILE" -C /opt/secretzero/
systemctl restart secretzero-api
```

---

## Next Steps

- Review [authentication](authentication.md) security
- Check [endpoint reference](endpoints.md) for API usage
- See [examples](../../examples/index.md) for common patterns
