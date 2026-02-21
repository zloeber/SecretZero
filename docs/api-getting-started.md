# SecretZero API - Getting Started

## Overview

The SecretZero API provides a REST interface for managing secrets, checking policies, detecting drift, and rotating secrets. It's built with FastAPI and includes OpenAPI documentation.

## Installation

Install the API dependencies:

```bash
pip install secretzero[api]
```

## Starting the Server

### Basic Usage

```bash
# Start with default settings (port 8000)
secretzero-api

# Or with custom settings
SECRETZERO_PORT=9000 secretzero-api
```

### Configuration

Environment variables:
- `SECRETZERO_HOST`: Host to bind to (default: `0.0.0.0`)
- `SECRETZERO_PORT`: Port to listen on (default: `8000`)
- `SECRETZERO_CONFIG`: Path to Secretfile.yml (default: `Secretfile.yml`)
- `SECRETZERO_API_KEY`: API key for authentication (optional, enables auth)
- `SECRETZERO_RELOAD`: Enable auto-reload on code changes (default: `false`)

### With Authentication

```bash
# Generate a secure API key
export SECRETZERO_API_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")

# Start server with authentication
secretzero-api
```

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Spec**: http://localhost:8000/openapi.json

## Quick Examples

### Health Check

```bash
curl http://localhost:8000/health
```

### List Secrets

```bash
# Without authentication
curl http://localhost:8000/secrets

# With authentication
curl -H "X-API-Key: your-api-key-here" http://localhost:8000/secrets
```

### Validate Configuration

```bash
curl -X POST http://localhost:8000/config/validate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "config": {
      "version": "1.0",
      "secrets": [
        {
          "name": "example",
          "kind": "random_password"
        }
      ]
    }
  }'
```

### Sync Secrets (Dry Run)

```bash
curl -X POST http://localhost:8000/sync \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "dry_run": true,
    "force": false
  }'
```

### Check Rotation Status

```bash
curl -X POST http://localhost:8000/rotation/check \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "dry_run": true
  }'
```

### Check Policy Compliance

```bash
curl -X POST http://localhost:8000/policy/check \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "fail_on_warning": false
  }'
```

### Check for Drift

```bash
curl -X POST http://localhost:8000/drift/check \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{}'
```

### Get Audit Logs

```bash
curl "http://localhost:8000/audit/logs?limit=10" \
  -H "X-API-Key: your-api-key-here"
```

## Python Client Example

```python
import requests

class SecretZeroClient:
    def __init__(self, base_url="http://localhost:8000", api_key=None):
        self.base_url = base_url
        self.headers = {}
        if api_key:
            self.headers["X-API-Key"] = api_key
    
    def health_check(self):
        """Check API health."""
        response = requests.get(f"{self.base_url}/health")
        return response.json()
    
    def list_secrets(self):
        """List all secrets."""
        response = requests.get(
            f"{self.base_url}/secrets",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def sync_secrets(self, dry_run=True, force=False, secret_name=None):
        """Sync secrets."""
        data = {
            "dry_run": dry_run,
            "force": force
        }
        if secret_name:
            data["secret_name"] = secret_name
        
        response = requests.post(
            f"{self.base_url}/sync",
            headers=self.headers,
            json=data
        )
        response.raise_for_status()
        return response.json()
    
    def check_rotation(self, secret_name=None):
        """Check rotation status."""
        data = {"dry_run": True}
        if secret_name:
            data["secret_name"] = secret_name
        
        response = requests.post(
            f"{self.base_url}/rotation/check",
            headers=self.headers,
            json=data
        )
        response.raise_for_status()
        return response.json()
    
    def check_policy(self, fail_on_warning=False):
        """Check policy compliance."""
        response = requests.post(
            f"{self.base_url}/policy/check",
            headers=self.headers,
            json={"fail_on_warning": fail_on_warning}
        )
        response.raise_for_status()
        return response.json()
    
    def check_drift(self, secret_name=None):
        """Check for drift."""
        data = {}
        if secret_name:
            data["secret_name"] = secret_name
        
        response = requests.post(
            f"{self.base_url}/drift/check",
            headers=self.headers,
            json=data
        )
        response.raise_for_status()
        return response.json()


# Usage
client = SecretZeroClient(api_key="your-api-key")

# Health check
print(client.health_check())

# List secrets
secrets = client.list_secrets()
print(f"Found {secrets['count']} secrets")

# Sync secrets (dry run)
result = client.sync_secrets(dry_run=True)
print(f"Would sync: {result['message']}")

# Check rotation
rotation = client.check_rotation()
print(f"Checked {rotation['secrets_checked']} secrets")
print(f"Due for rotation: {rotation['secrets_due']}")

# Check policy compliance
policy = client.check_policy()
if policy['compliant']:
    print("All policies compliant!")
else:
    print(f"Policy violations: {len(policy['errors'])} errors, {len(policy['warnings'])} warnings")

# Check drift
drift = client.check_drift()
if drift['has_drift']:
    print(f"Drift detected in: {drift['secrets_with_drift']}")
else:
    print("No drift detected")
```

## Security Considerations

### Authentication

When `SECRETZERO_API_KEY` is set:
- All endpoints (except `/health` and `/`) require authentication
- API key must be provided in the `X-API-Key` header
- Failed authentication returns 401 Unauthorized

### Best Practices

1. **Use HTTPS in Production**: Always deploy behind a reverse proxy with TLS
2. **Rotate API Keys**: Regularly rotate your API keys
3. **Limit Access**: Use network policies to restrict API access
4. **Monitor Audit Logs**: Review audit logs for suspicious activity
5. **Rate Limiting**: Consider adding rate limiting for production deployments

### Running in Production {#production-deployment}

Example with Nginx and systemd:

#### systemd service file (`/etc/systemd/system/secretzero-api.service`):

```ini
[Unit]
Description=SecretZero API Server
After=network.target

[Service]
Type=simple
User=secretzero
WorkingDirectory=/opt/secretzero
Environment="SECRETZERO_API_KEY=your-secure-key-here"
Environment="SECRETZERO_CONFIG=/opt/secretzero/Secretfile.yml"
ExecStart=/opt/secretzero/venv/bin/secretzero-api
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

#### Nginx configuration:

```nginx
server {
    listen 443 ssl http2;
    server_name secrets.example.com;
    
    ssl_certificate /etc/ssl/certs/secrets.example.com.crt;
    ssl_certificate_key /etc/ssl/private/secrets.example.com.key;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY Secretfile.yml /app/
COPY pyproject.toml /app/

RUN pip install -e ".[api]"

ENV SECRETZERO_HOST=0.0.0.0
ENV SECRETZERO_PORT=8000

EXPOSE 8000

CMD ["secretzero-api"]
```

Build and run:

```bash
docker build -t secretzero-api .
docker run -p 8000:8000 \
  -e SECRETZERO_API_KEY=your-secure-key \
  -v $(pwd)/Secretfile.yml:/app/Secretfile.yml:ro \
  secretzero-api
```

## Troubleshooting

### Server Won't Start

Check that:
- Port 8000 (or custom port) is available
- Secretfile.yml exists and is valid
- Dependencies are installed: `pip install secretzero[api]`

### Authentication Failures

- Verify API key is set correctly
- Check that `X-API-Key` header is included in requests
- Ensure no spaces in the API key value

### Secrets Not Syncing

- Check Secretfile.yml is valid
- Verify provider configurations are correct
- Check logs for specific error messages

## Next Steps

- Explore the interactive docs at `/docs`
- Check out example Secretfiles in the `examples/` directory
- Read the full documentation
- Set up automated secret rotation workflows
