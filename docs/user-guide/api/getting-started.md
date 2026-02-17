# Getting Started with the API

This guide will help you install, configure, and start using the SecretZero API.

## Installation

### Prerequisites

- Python 3.9 or higher
- A valid `Secretfile.yml` configuration
- (Optional) Cloud provider credentials for AWS, Azure, or Vault

### Install SecretZero with API Support

```bash
# Install with API dependencies
pip install secretzero[api]

# Or install all providers and API support
pip install secretzero[all]
```

### Verify Installation

```bash
# Check version
secretzero-api --version

# View help
secretzero-api --help
```

## Starting the Server

### Basic Usage (Development)

Start the API server with default settings:

```bash
secretzero-api
```

The server will start on `http://0.0.0.0:8000` by default.

**⚠️ Warning**: Running without authentication is insecure and should only be used for local development.

### With Authentication (Recommended)

Generate and use an API key for authentication:

```bash
# Generate a secure API key
export SECRETZERO_API_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")

# Save the key securely (you'll need it for API requests)
echo $SECRETZERO_API_KEY

# Start the server
secretzero-api
```

### Custom Configuration

Use environment variables to customize the server:

```bash
# Custom host and port
export SECRETZERO_HOST=127.0.0.1
export SECRETZERO_PORT=9000

# Custom Secretfile location
export SECRETZERO_CONFIG=/path/to/Secretfile.yml

# Enable auto-reload for development
export SECRETZERO_RELOAD=true

# Start with custom settings
secretzero-api
```

## Configuration Options

Configure the API server using environment variables:

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `SECRETZERO_HOST` | Host address to bind to | `0.0.0.0` | `127.0.0.1` |
| `SECRETZERO_PORT` | Port to listen on | `8000` | `9000` |
| `SECRETZERO_CONFIG` | Path to Secretfile.yml | `Secretfile.yml` | `/etc/secretzero/config.yml` |
| `SECRETZERO_API_KEY` | API key for authentication | (none) | `your-secure-key-here` |
| `SECRETZERO_RELOAD` | Auto-reload on code changes | `false` | `true` |

## Exploring the API

### Interactive Documentation

Once the server is running, access the interactive documentation:

#### Swagger UI (Recommended for Testing)

Visit [http://localhost:8000/docs](http://localhost:8000/docs)

Features:
- Interactive API explorer
- Try out endpoints with live requests
- Automatic request/response examples
- Built-in authentication support

#### ReDoc (Recommended for Reading)

Visit [http://localhost:8000/redoc](http://localhost:8000/redoc)

Features:
- Beautiful, searchable documentation
- Detailed schema descriptions
- Code samples in multiple languages
- Organized by endpoint categories

#### OpenAPI Specification

Download the machine-readable spec:

```bash
curl http://localhost:8000/openapi.json > secretzero-openapi.json
```

Use this spec to:
- Generate client SDKs in any language
- Import into API testing tools (Postman, Insomnia)
- Validate API contracts

## Quick Examples

### Health Check

Test that the API is running:

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### List Secrets

Get all secrets from your Secretfile:

```bash
# Without authentication (if no API key is set)
curl http://localhost:8000/secrets

# With authentication
curl -H "X-API-Key: your-api-key-here" http://localhost:8000/secrets
```

Response:
```json
{
  "secrets": [
    {
      "name": "database_password",
      "kind": "random_password",
      "rotation_period": "90d",
      "targets": ["aws_ssm", "local_file"]
    }
  ],
  "count": 1
}
```

### Get Secret Status

Check the status of a specific secret:

```bash
curl -H "X-API-Key: your-api-key" \
  http://localhost:8000/secrets/database_password/status
```

Response:
```json
{
  "name": "database_password",
  "exists": true,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "last_rotated": "2024-01-01T00:00:00Z",
  "rotation_count": 3,
  "targets": ["aws_ssm", "local_file"]
}
```

### Validate Configuration

Test a Secretfile configuration before applying:

```bash
curl -X POST http://localhost:8000/config/validate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "config": {
      "version": "1.0",
      "secrets": [
        {
          "name": "test_secret",
          "kind": "random_password"
        }
      ]
    }
  }'
```

Response:
```json
{
  "valid": true,
  "errors": [],
  "warnings": []
}
```

### Sync Secrets (Dry Run)

Preview what would happen during a sync:

```bash
curl -X POST http://localhost:8000/sync \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "dry_run": true,
    "force": false
  }'
```

Response:
```json
{
  "secrets_generated": ["database_password", "api_key"],
  "secrets_skipped": ["oauth_secret"],
  "message": "Would generate 2 secret(s), skipped 1"
}
```

### Sync a Specific Secret

Generate and sync just one secret:

```bash
curl -X POST http://localhost:8000/sync \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "dry_run": false,
    "force": false,
    "secret_name": "database_password"
  }'
```

### Check Rotation Status

Find secrets that need rotation:

```bash
curl -X POST http://localhost:8000/rotation/check \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "dry_run": true
  }'
```

Response:
```json
{
  "secrets_checked": 5,
  "secrets_due": ["api_key"],
  "secrets_overdue": ["old_password"],
  "results": [
    {
      "name": "old_password",
      "should_rotate": true,
      "status": "Overdue for rotation by 15 days"
    }
  ]
}
```

## Using with cURL

### Setting Up Authentication

Store your API key for easy reuse:

```bash
export API_KEY="your-api-key-here"
```

Then use it in requests:

```bash
curl -H "X-API-Key: $API_KEY" http://localhost:8000/secrets
```

### Common cURL Patterns

**GET Request:**
```bash
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/secrets
```

**POST Request with JSON:**
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"dry_run": true}' \
  http://localhost:8000/sync
```

**Pretty Print JSON Response:**
```bash
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/secrets | jq '.'
```

**Save Response to File:**
```bash
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/secrets > secrets.json
```

## Using with HTTPie

[HTTPie](https://httpie.io/) provides a more user-friendly command-line interface:

### Installation

```bash
pip install httpie
```

### Examples

**GET Request:**
```bash
http GET localhost:8000/secrets X-API-Key:$API_KEY
```

**POST Request:**
```bash
http POST localhost:8000/sync \
  X-API-Key:$API_KEY \
  dry_run:=true \
  force:=false
```

**Query Parameters:**
```bash
http GET localhost:8000/audit/logs \
  X-API-Key:$API_KEY \
  limit==10 \
  offset==0
```

## Error Handling

### Common Error Codes

| Code | Description | Solution |
|------|-------------|----------|
| `400` | Bad Request - Invalid input | Check request format and parameters |
| `401` | Unauthorized - Missing/invalid API key | Provide valid API key in X-API-Key header |
| `404` | Not Found - Resource doesn't exist | Verify resource name and Secretfile |
| `500` | Internal Server Error | Check server logs for details |

### Error Response Format

All errors follow a consistent format:

```json
{
  "error": "Brief error description",
  "detail": "Detailed error message",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Example Error Responses

**Missing API Key:**
```json
{
  "detail": "Missing API key"
}
```

**Invalid Secret Name:**
```json
{
  "detail": "Secret not found: nonexistent_secret"
}
```

**Sync Failure:**
```json
{
  "detail": "Sync failed: Unable to connect to AWS SSM"
}
```

## Testing the API

### Using the Swagger UI

1. Navigate to `http://localhost:8000/docs`
2. Click "Authorize" button (if authentication is enabled)
3. Enter your API key
4. Click "Authorize" to save it
5. Try any endpoint by clicking "Try it out"

### Using Python requests

```python
import requests

BASE_URL = "http://localhost:8000"
API_KEY = "your-api-key-here"

# Health check
response = requests.get(f"{BASE_URL}/health")
print(response.json())

# List secrets (with auth)
response = requests.get(
    f"{BASE_URL}/secrets",
    headers={"X-API-Key": API_KEY}
)
print(response.json())
```

### Using JavaScript/Node.js

```javascript
const axios = require('axios');

const BASE_URL = 'http://localhost:8000';
const API_KEY = 'your-api-key-here';

// Health check
axios.get(`${BASE_URL}/health`)
  .then(response => console.log(response.data));

// List secrets (with auth)
axios.get(`${BASE_URL}/secrets`, {
  headers: { 'X-API-Key': API_KEY }
})
  .then(response => console.log(response.data));
```

## Next Steps

- Learn about [authentication](authentication.md) and security best practices
- Explore the complete [endpoint reference](endpoints.md)
- Use the [Python client](python-client.md) for easier integration
- Deploy the API in [production](deployment.md)

## Troubleshooting

### Server Won't Start

**Problem**: Port already in use

```
Error: [Errno 48] Address already in use
```

**Solution**: Use a different port or kill the process using port 8000

```bash
# Find process using port 8000
lsof -ti:8000

# Kill the process
kill $(lsof -ti:8000)

# Or use a different port
SECRETZERO_PORT=9000 secretzero-api
```

### Secretfile Not Found

**Problem**: Configuration file not found

```
Error: Secretfile not found: Secretfile.yml
```

**Solution**: Specify the correct path

```bash
export SECRETZERO_CONFIG=/path/to/Secretfile.yml
secretzero-api
```

### Import Errors

**Problem**: Missing dependencies

```
ModuleNotFoundError: No module named 'fastapi'
```

**Solution**: Install API dependencies

```bash
pip install secretzero[api]
```

### Authentication Not Working

**Problem**: API key not recognized

**Solution**: Verify the API key is set and matches

```bash
# Check if API key is set
echo $SECRETZERO_API_KEY

# Ensure there are no extra spaces or newlines
export SECRETZERO_API_KEY=$(echo $SECRETZERO_API_KEY | tr -d '[:space:]')
```
