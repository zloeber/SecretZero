# Authentication

The SecretZero API uses API key authentication to secure access to your secrets and operations. This guide covers authentication setup, security best practices, and production deployment considerations.

## Authentication Overview

### API Key Authentication

SecretZero uses a simple but secure API key authentication mechanism:

- **Header-based**: API keys are passed via the `X-API-Key` HTTP header
- **Timing-attack resistant**: Uses constant-time comparison to prevent timing attacks
- **Optional**: Can run in insecure mode for local development (not recommended)
- **Flexible**: Easy to rotate and manage

### Security Features

- **SHA-256 hashing**: API keys are hashed before comparison
- **Constant-time comparison**: Prevents timing-based attacks using `secrets.compare_digest()`
- **No API key storage**: Keys are only stored in environment variables
- **Audit logging**: All authentication attempts are logged

## Generating API Keys

### Using Python

The most secure method:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

This generates a 32-byte (256-bit) cryptographically secure random token encoded in URL-safe base64.

### Using OpenSSL

Alternative method using OpenSSL:

```bash
openssl rand -base64 32
```

### Using the SecretZero CLI

```bash
secretzero api generate-key
```

### Example Output

```
dQw4w9WgXcQ-rMZN8H3Pq7FvKxY2TbLjN5aUzRcVdWg
```

**⚠️ Important**: Save this key securely! You'll need it for all API requests.

## Configuring Authentication

### Setting the API Key

#### Environment Variable (Recommended)

```bash
export SECRETZERO_API_KEY="your-secure-api-key-here"
secretzero-api
```

#### .env File (Local Development)

Create a `.env` file:

```env
SECRETZERO_API_KEY=your-secure-api-key-here
SECRETZERO_PORT=8000
SECRETZERO_CONFIG=Secretfile.yml
```

Load it before starting:

```bash
set -a
source .env
set +a
secretzero-api
```

#### Systemd Service (Production)

```ini
[Service]
Environment="SECRETZERO_API_KEY=your-secure-api-key-here"
ExecStart=/usr/local/bin/secretzero-api
```

#### Docker (Production)

```bash
docker run -e SECRETZERO_API_KEY=your-key secretzero-api
```

#### Kubernetes Secret (Production)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: secretzero-api-key
type: Opaque
stringData:
  api-key: your-secure-api-key-here
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: secretzero-api
spec:
  template:
    spec:
      containers:
      - name: api
        env:
        - name: SECRETZERO_API_KEY
          valueFrom:
            secretKeyRef:
              name: secretzero-api-key
              key: api-key
```

### Running Without Authentication (Insecure)

**⚠️ Warning**: Only for local development!

Simply don't set the `SECRETZERO_API_KEY` environment variable:

```bash
secretzero-api
```

The API will run in insecure mode and accept all requests without authentication.

## Making Authenticated Requests

### Using cURL

```bash
# Set your API key
export API_KEY="your-api-key-here"

# Make authenticated request
curl -H "X-API-Key: $API_KEY" http://localhost:8000/secrets
```

### Using Python requests

```python
import requests

API_KEY = "your-api-key-here"
BASE_URL = "http://localhost:8000"

headers = {"X-API-Key": API_KEY}

response = requests.get(f"{BASE_URL}/secrets", headers=headers)
print(response.json())
```

### Using JavaScript/fetch

```javascript
const API_KEY = "your-api-key-here";
const BASE_URL = "http://localhost:8000";

fetch(`${BASE_URL}/secrets`, {
  headers: {
    "X-API-Key": API_KEY
  }
})
  .then(response => response.json())
  .then(data => console.log(data));
```

### Using HTTPie

```bash
http GET localhost:8000/secrets X-API-Key:$API_KEY
```

### Using Postman

1. Open Postman
2. Create a new request
3. Go to the "Headers" tab
4. Add a header:
   - Key: `X-API-Key`
   - Value: `your-api-key-here`
5. Send the request

## Authentication Endpoints

### Unauthenticated Endpoints

These endpoints don't require authentication:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API root information |
| `/health` | GET | Health check |
| `/docs` | GET | Swagger UI documentation |
| `/redoc` | GET | ReDoc documentation |
| `/openapi.json` | GET | OpenAPI specification |

### Authenticated Endpoints

All other endpoints require a valid API key:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/secrets` | GET | List secrets |
| `/secrets/{name}/status` | GET | Get secret status |
| `/sync` | POST | Sync secrets |
| `/rotation/check` | POST | Check rotation |
| `/rotation/execute` | POST | Execute rotation |
| `/policy/check` | POST | Check policies |
| `/drift/check` | POST | Check drift |
| `/config/validate` | POST | Validate config |
| `/audit/logs` | GET | Get audit logs |

## Error Responses

### Missing API Key

**Request:**
```bash
curl http://localhost:8000/secrets
```

**Response:** `401 Unauthorized`
```json
{
  "detail": "Missing API key"
}
```

### Invalid API Key

**Request:**
```bash
curl -H "X-API-Key: wrong-key" http://localhost:8000/secrets
```

**Response:** `401 Unauthorized`
```json
{
  "detail": "Invalid API key"
}
```

### Headers Include WWW-Authenticate

```
HTTP/1.1 401 Unauthorized
WWW-Authenticate: ApiKey
Content-Type: application/json
```

## Security Best Practices

### 1. Always Use HTTPS in Production

Never send API keys over unencrypted HTTP in production:

```nginx
# Nginx configuration
server {
    listen 443 ssl http2;
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    # Modern SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    location / {
        proxy_pass http://localhost:8000;
    }
}
```

### 2. Rotate API Keys Regularly

Establish a rotation schedule:

```bash
# Generate new key
NEW_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")

# Update environment
export SECRETZERO_API_KEY=$NEW_KEY

# Restart service
systemctl restart secretzero-api

# Update clients with new key
# Wait for confirmation
# Revoke old key
```

### 3. Use Environment Variables

Never hardcode API keys in source code:

**❌ Bad:**
```python
API_KEY = "dQw4w9WgXcQ-rMZN8H3Pq7FvKxY2TbLjN5aUzRcVdWg"
```

**✅ Good:**
```python
import os
API_KEY = os.environ["SECRETZERO_API_KEY"]
```

### 4. Limit API Key Exposure

- Don't commit API keys to version control
- Don't log API keys
- Don't include API keys in URLs or query parameters
- Use secret management systems (Vault, AWS Secrets Manager)

### 5. Implement Network Restrictions

Restrict API access at the network level:

**Firewall Rules:**
```bash
# Only allow specific IPs
iptables -A INPUT -p tcp --dport 8000 -s 10.0.0.0/8 -j ACCEPT
iptables -A INPUT -p tcp --dport 8000 -j DROP
```

**Kubernetes NetworkPolicy:**
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: secretzero-api-access
spec:
  podSelector:
    matchLabels:
      app: secretzero-api
  ingress:
  - from:
    - podSelector:
        matchLabels:
          access: secretzero-api
```

### 6. Monitor and Audit

Enable comprehensive audit logging:

```bash
# Check audit logs regularly
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/audit/logs?limit=100" | jq '.'
```

Set up alerts for:
- Failed authentication attempts
- Unusual access patterns
- High-frequency requests
- Access from unexpected sources

### 7. Use Separate Keys for Different Environments

```bash
# Development
export SECRETZERO_API_KEY=$DEV_API_KEY

# Staging
export SECRETZERO_API_KEY=$STAGING_API_KEY

# Production
export SECRETZERO_API_KEY=$PROD_API_KEY
```

### 8. Implement Rate Limiting

Use a reverse proxy for rate limiting:

**Nginx Example:**
```nginx
http {
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    
    server {
        location / {
            limit_req zone=api burst=20;
            proxy_pass http://localhost:8000;
        }
    }
}
```

**Traefik Example:**
```yaml
http:
  middlewares:
    rate-limit:
      rateLimit:
        average: 100
        burst: 50
```

### 9. Principle of Least Privilege

If implementing multiple API keys (future feature):

- Use separate keys for different applications
- Grant minimal necessary permissions
- Revoke keys when no longer needed

### 10. Secure Key Storage

**For Services:**
- AWS Secrets Manager
- Azure Key Vault
- HashiCorp Vault
- Kubernetes Secrets

**For Developers:**
- Password managers (1Password, LastPass)
- Encrypted files
- Environment variable managers (direnv)

## Advanced Authentication Patterns

### API Key Rotation Script

```bash
#!/bin/bash
# rotate-api-key.sh

# Generate new key
NEW_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
echo "New API key: $NEW_KEY"

# Update Kubernetes secret
kubectl create secret generic secretzero-api-key \
  --from-literal=api-key=$NEW_KEY \
  --dry-run=client -o yaml | kubectl apply -f -

# Rolling restart
kubectl rollout restart deployment/secretzero-api

# Wait for rollout
kubectl rollout status deployment/secretzero-api

echo "API key rotated successfully"
```

### Multi-Key Support (Future)

Currently, SecretZero supports a single API key. For multi-key support:

```python
# Example implementation (not currently supported)
API_KEYS = {
    "ci-cd-key": {"name": "CI/CD", "permissions": ["read", "sync"]},
    "admin-key": {"name": "Admin", "permissions": ["*"]},
    "monitoring-key": {"name": "Monitoring", "permissions": ["read"]},
}
```

### OAuth2/OIDC Integration (Future)

For enterprise deployments, consider OAuth2/OIDC:

```yaml
# Future configuration example
auth:
  type: oauth2
  issuer: https://auth.example.com
  audience: secretzero-api
  scopes:
    - secretzero:read
    - secretzero:write
```

## Troubleshooting Authentication

### Check API Key is Set

```bash
# Verify environment variable
echo $SECRETZERO_API_KEY

# Check if server is using it
curl http://localhost:8000/secrets
# Should return 401 if key is set
```

### Test Authentication

```bash
# Should fail (401)
curl -i http://localhost:8000/secrets

# Should succeed (200)
curl -i -H "X-API-Key: $SECRETZERO_API_KEY" \
  http://localhost:8000/secrets
```

### Debug Authentication Issues

**Check server logs:**
```bash
# If running with systemd
journalctl -u secretzero-api -f

# If running in Docker
docker logs secretzero-api -f

# If running directly
secretzero-api --log-level debug
```

**Common issues:**

1. **Extra whitespace in API key**
   ```bash
   # Clean the key
   export SECRETZERO_API_KEY=$(echo $SECRETZERO_API_KEY | tr -d '[:space:]')
   ```

2. **Wrong header name**
   - Must be `X-API-Key` (case-sensitive)
   
3. **API key not set on server**
   - Check server environment variables
   
4. **API key set but still accepts unauthenticated requests**
   - Restart the server after setting the environment variable

## Next Steps

- Learn about all available [endpoints](endpoints.md)
- Use the [Python client](python-client.md) for easier authentication handling
- Set up [production deployment](deployment.md) with proper security
- Review [audit logs](endpoints.md#audit-logs) to monitor access

## Security Disclosure

If you discover a security vulnerability in SecretZero's authentication system, please report it to the maintainers privately through GitHub's security advisory system.
