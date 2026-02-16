# API Reference

The SecretZero API provides a comprehensive REST interface for managing secrets, enforcing policies, detecting drift, and automating secret rotation. Built with FastAPI, it offers automatic OpenAPI documentation, type safety, and high performance.

## Overview

The API allows you to:

- **Manage Secrets**: List, generate, sync, and retrieve secret status
- **Enforce Policies**: Check compliance with security and rotation policies
- **Detect Drift**: Monitor for unauthorized changes to secrets
- **Automate Rotation**: Check and execute automatic secret rotation
- **Audit Activity**: Track all API operations and access patterns
- **Validate Configuration**: Test Secretfile configurations before deployment

## Key Features

### 🔒 Security First
- API key authentication with timing-attack resistant comparison
- Comprehensive audit logging for all operations
- Secure credential storage and transmission
- TLS/HTTPS support for production deployments

### 📊 Interactive Documentation
- **Swagger UI** (`/docs`) - Interactive API explorer with live testing
- **ReDoc** (`/redoc`) - Beautiful, searchable API documentation
- **OpenAPI Spec** (`/openapi.json`) - Machine-readable API definition

### 🚀 Production Ready
- Built on battle-tested FastAPI framework
- Async/await support for high concurrency
- Health checks and monitoring endpoints
- Docker and Kubernetes deployment support

### 🔄 Comprehensive Operations
- Dry-run mode for all mutation operations
- Bulk operations for managing multiple secrets
- Flexible filtering and pagination
- Detailed error messages and validation

## Quick Start

### Installation

```bash
# Install SecretZero with API support
pip install secretzero[api]
```

### Start the Server

```bash
# Basic start (insecure mode - no authentication)
secretzero-api

# With authentication (recommended)
export SECRETZERO_API_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
secretzero-api
```

### Test the API

```bash
# Health check (no auth required)
curl http://localhost:8000/health

# List secrets (auth required if API key is set)
curl -H "X-API-Key: your-api-key" http://localhost:8000/secrets
```

### Explore the Documentation

Once the server is running, visit:

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

## Documentation Structure

This API reference is organized into the following sections:

### [Getting Started](getting-started.md)
Learn how to install, configure, and start using the SecretZero API. Includes basic examples and configuration options.

### [Authentication](authentication.md)
Understand API key authentication, security best practices, and how to secure your API in production.

### [Endpoints](endpoints.md)
Complete reference for all API endpoints with request/response examples, parameters, and error codes.

### [Python Client](python-client.md)
Use the Python client library for easy integration with your applications. Includes SDK examples and patterns.

### [Deployment](deployment.md)
Deploy the API in production using systemd, Docker, Kubernetes, or cloud platforms. Includes configuration and monitoring.

## API Endpoints Overview

| Category | Endpoints | Description |
|----------|-----------|-------------|
| **Health** | `GET /health` | Health check and version info |
| **Secrets** | `GET /secrets`<br>`GET /secrets/{name}/status` | List and inspect secrets |
| **Sync** | `POST /sync` | Generate and store secrets |
| **Rotation** | `POST /rotation/check`<br>`POST /rotation/execute` | Check and execute rotation |
| **Policy** | `POST /policy/check` | Validate policy compliance |
| **Drift** | `POST /drift/check` | Detect configuration drift |
| **Configuration** | `POST /config/validate` | Validate Secretfile configs |
| **Audit** | `GET /audit/logs` | Retrieve audit logs |

## Common Use Cases

### CI/CD Integration
Automate secret management in your CI/CD pipelines:

```bash
# Check if secrets need rotation before deployment
curl -X POST http://api.example.com/rotation/check \
  -H "X-API-Key: $API_KEY" | jq '.secrets_due'

# Sync secrets during deployment
curl -X POST http://api.example.com/sync \
  -H "X-API-Key: $API_KEY" \
  -d '{"dry_run": false}'
```

### Monitoring and Alerting
Monitor secret health and compliance:

```bash
# Check for policy violations
curl -X POST http://api.example.com/policy/check \
  -H "X-API-Key: $API_KEY" | jq '.compliant'

# Detect unauthorized changes
curl -X POST http://api.example.com/drift/check \
  -H "X-API-Key: $API_KEY" | jq '.has_drift'
```

### Operational Management
Manage secrets through your infrastructure tools:

```python
from secretzero import SecretZeroClient

client = SecretZeroClient(api_key=os.environ["API_KEY"])

# Rotate all due secrets
rotation_status = client.check_rotation()
if rotation_status["secrets_due"]:
    client.execute_rotation()
```

## API Versioning

The API version follows the SecretZero package version. Breaking changes will be avoided when possible, and any breaking changes will be clearly documented in release notes.

Current API version: Check `/health` endpoint for version information.

## Rate Limiting

The API does not currently implement rate limiting. For production deployments, consider:

- Using a reverse proxy (nginx, Caddy) with rate limiting
- Implementing API gateway rate limits (AWS API Gateway, Azure API Management)
- Using Kubernetes ingress controllers with rate limiting features

## Support and Feedback

- **Documentation**: Browse this API reference for detailed information
- **GitHub Issues**: Report bugs or request features at [github.com/zloeber/SecretZero](https://github.com/zloeber/SecretZero)
- **Examples**: See the [Examples](../../examples/index.md) section for practical use cases

## Next Steps

- [Get started](getting-started.md) with installation and basic usage
- Learn about [authentication](authentication.md) and security
- Explore the complete [endpoint reference](endpoints.md)
- Check out [Python client examples](python-client.md)
- Read about [production deployment](deployment.md)
