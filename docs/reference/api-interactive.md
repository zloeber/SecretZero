# API Interactive Reference

This page provides an interactive API explorer powered by Swagger UI. You can test API endpoints directly from this page.

## Interactive API Explorer

The SecretZero API is built with FastAPI and provides automatic OpenAPI documentation. Use the interactive explorer below to:

- Browse all available endpoints
- View request/response schemas
- Test endpoints directly (if you have a running API server)
- Download the OpenAPI specification

!!! note "Running API Server Required"
    To test endpoints from this page, you need a running SecretZero API server:
    ```bash
    # Install API dependencies
    pip install secretzero[api]
    
    # Start the API server
    export SECRETZERO_API_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
    secretzero-api
    ```

## OpenAPI Specification

The full OpenAPI specification can be accessed at:

- **JSON**: `http://localhost:8000/openapi.json`
- **Interactive Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## Embedded API Documentation

<swagger-ui src="http://localhost:8000/openapi.json"/>

!!! tip "Local vs Production"
    This embedded documentation connects to `http://localhost:8000` by default.
    
    For production deployments, access the API documentation directly from your API server:
    - Swagger UI: `https://your-api-server.com/docs`
    - ReDoc: `https://your-api-server.com/redoc`

## Quick Start

### 1. Start the API Server

```bash
# With authentication
export SECRETZERO_API_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
secretzero-api

# Without authentication (development only)
secretzero-api
```

### 2. Test the Health Endpoint

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

### 3. Authenticate (if enabled)

Add the `X-API-Key` header to your requests:

```bash
curl -H "X-API-Key: your-api-key-here" http://localhost:8000/secrets
```

## Common Endpoints

### Configuration

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/config/validate` | POST | Validate a Secretfile configuration |
| `/config/render` | POST | Render configuration with variables |

### Secrets

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/secrets` | GET | List all secrets |
| `/secrets/{name}/status` | GET | Get secret status and metadata |
| `/secrets/{name}` | GET | Get decrypted secret value |

### Operations

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/sync` | POST | Synchronize secrets to targets |
| `/rotation/check` | POST | Check which secrets need rotation |
| `/rotation/execute` | POST | Execute secret rotation |
| `/drift` | POST | Check for configuration drift |
| `/policy` | POST | Run policy compliance checks |

### Metadata

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/providers` | GET | List available providers |
| `/targets` | GET | List available targets |
| `/generators` | GET | List available generators |
| `/secret-types` | GET | List supported secret types |

## Authentication

The API supports API key authentication via the `X-API-Key` header.

### Enable Authentication

Set the `SECRETZERO_API_KEY` environment variable:

```bash
export SECRETZERO_API_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
secretzero-api
```

### Making Authenticated Requests

Include the API key in the header:

```bash
curl -H "X-API-Key: your-api-key-here" http://localhost:8000/secrets
```

Or in Python:

```python
import requests

headers = {"X-API-Key": "your-api-key-here"}
response = requests.get("http://localhost:8000/secrets", headers=headers)
```

## Error Handling

The API uses standard HTTP status codes:

| Status Code | Meaning |
|-------------|---------|
| 200 | Success |
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Missing or invalid API key |
| 404 | Not Found - Resource doesn't exist |
| 422 | Unprocessable Entity - Validation error |
| 500 | Internal Server Error |

Error responses include details:

```json
{
  "error": "Validation error",
  "detail": "Secret 'database_password' not found in configuration"
}
```

## Rate Limiting

!!! warning "Production Deployment"
    The current API does not include built-in rate limiting. For production deployments, use a reverse proxy (nginx, Traefik) or API gateway to implement rate limiting.

## CORS Configuration

!!! danger "Security Warning"
    The default CORS configuration allows all origins (`*`) for development convenience.
    
    **For production**, modify [app.py](https://github.com/zloeber/SecretZero/blob/main/src/secretzero/api/app.py) to restrict origins:
    
    ```python
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://yourdomain.com"],  # Specific domains only
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    ```

## Next Steps

- [API Getting Started Guide](../api-getting-started.md) - Detailed setup and examples
- [Python API Reference](api-python.md) - Auto-generated from docstrings
- [Configuration Guide](../user-guide/configuration/index.md) - Configure your Secretfile
- [Examples](../examples/complete.md) - Real-world usage examples
