# API Endpoints Reference

Complete reference for all SecretZero API endpoints with request/response examples, parameters, and error codes.

## Base URL

```
http://localhost:8000
```

For production, use your deployed domain with HTTPS:
```
https://api.example.com
```

## Authentication

Most endpoints require authentication via API key. See [Authentication](authentication.md) for details.

**Header:**
```
X-API-Key: your-api-key-here
```

**Unauthenticated endpoints:** `/`, `/health`, `/docs`, `/redoc`, `/openapi.json`

---

## Health and Information

### GET / - API Root

Get API information and links.

**Authentication:** None required

**Example Request:**
```bash
curl http://localhost:8000/
```

**Example Response:** `200 OK`
```json
{
  "message": "SecretZero API",
  "version": "0.1.0",
  "docs": "/docs"
}
```

---

### GET /health - Health Check

Check API health and version.

**Authentication:** None required

**Example Request:**
```bash
curl http://localhost:8000/health
```

**Example Response:** `200 OK`
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Always "healthy" when API is running |
| `version` | string | SecretZero version |
| `timestamp` | string | Current server time in ISO 8601 format |

---

## Secrets Management

### GET /secrets - List Secrets

List all secrets from the Secretfile.

**Authentication:** Required

**Example Request:**
```bash
curl -H "X-API-Key: $API_KEY" http://localhost:8000/secrets
```

**Example Response:** `200 OK`
```json
{
  "secrets": [
    {
      "name": "database_password",
      "kind": "random_password",
      "rotation_period": "90d",
      "targets": ["ssm_parameter", "file"]
    },
    {
      "name": "api_key",
      "kind": "random_hex",
      "rotation_period": "30d",
      "targets": ["secrets_manager"]
    }
  ],
  "count": 2
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `secrets` | array | List of secret configurations |
| `secrets[].name` | string | Secret name |
| `secrets[].kind` | string | Secret generator type |
| `secrets[].rotation_period` | string | Rotation period (e.g., "90d") or null |
| `secrets[].targets` | array | List of target types |
| `count` | integer | Total number of secrets |

**Error Responses:**

| Code | Description |
|------|-------------|
| `401` | Missing or invalid API key |
| `404` | Secretfile not found |
| `500` | Failed to load or parse Secretfile |

---

### GET /secrets/{secret_name}/status - Get Secret Status

Get detailed status information for a specific secret.

**Authentication:** Required

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `secret_name` | string | Name of the secret |

**Example Request:**
```bash
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/secrets/database_password/status
```

**Example Response (Secret Exists):** `200 OK`
```json
{
  "name": "database_password",
  "exists": true,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-15T10:00:00Z",
  "last_rotated": "2024-01-15T10:00:00Z",
  "rotation_count": 3,
  "targets": ["ssm_parameter", "file"]
}
```

**Example Response (Secret Doesn't Exist):** `200 OK`
```json
{
  "name": "database_password",
  "exists": false
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Secret name |
| `exists` | boolean | Whether secret has been generated |
| `created_at` | string/null | When secret was first created |
| `updated_at` | string/null | When secret was last updated |
| `last_rotated` | string/null | When secret was last rotated |
| `rotation_count` | integer | Number of times rotated |
| `targets` | array | List of target names |

**Error Responses:**

| Code | Description |
|------|-------------|
| `401` | Missing or invalid API key |
| `500` | Failed to read lockfile |

---

## Synchronization

### POST /sync - Sync Secrets

Generate and store secrets to their targets.

**Authentication:** Required

**Request Body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `dry_run` | boolean | No | `false` | Preview changes without applying |
| `force` | boolean | No | `false` | Force regeneration of existing secrets |
| `refresh` | boolean | No | `true` | Refresh lockfile target validity right before sync (`false` opts out) |
| `secret_name` | string | No | `null` | Sync only this specific secret |
| `environment` | string | No | `null` | Named environment profile from `environments.profiles` |

**Example Request (Dry Run):**
```bash
curl -X POST http://localhost:8000/sync \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "dry_run": true,
    "force": false
  }'
```

**Example Response:** `200 OK`
```json
{
  "secrets_generated": ["database_password", "api_key"],
  "secrets_skipped": ["oauth_secret"],
  "message": "Would generate 2 secret(s), skipped 1"
}
```

**Example Request (Sync Specific Secret):**
```bash
curl -X POST http://localhost:8000/sync \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "dry_run": false,
    "force": false,
    "secret_name": "database_password"
  }'
```

**Example Response:** `200 OK`
```json
{
  "secrets_generated": ["database_password"],
  "secrets_skipped": [],
  "message": "Generated secret: database_password"
}
```

**Example Request (Force Sync All):**
```bash
curl -X POST http://localhost:8000/sync \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "dry_run": false,
    "force": true
  }'
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `secrets_generated` | array | List of secrets that were/would be generated |
| `secrets_skipped` | array | List of secrets that were skipped |
| `message` | string | Human-readable summary |
| `selected_environment` | string/null | Selected environment profile (if any) |
| `resolved_var_files` | array | Effective var-file list used for this sync |
| `resolved_lockfile` | string | Effective lockfile path used for this sync |
| `resolved_target_profile` | string/null | Applied target profile name (if any) |

**Error Responses:**

| Code | Description |
|------|-------------|
| `401` | Missing or invalid API key |
| `404` | Secretfile or specific secret not found |
| `500` | Sync operation failed |

---

## Rotation Management

### POST /rotation/check - Check Rotation Status

Check which secrets need rotation based on their rotation policies.

**Authentication:** Required

**Request Body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `secret_name` | string | No | `null` | Check only this specific secret |
| `dry_run` | boolean | No | `true` | Currently ignored (always true) |

**Example Request:**
```bash
curl -X POST http://localhost:8000/rotation/check \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{}'
```

**Example Response:** `200 OK`
```json
{
  "secrets_checked": 5,
  "secrets_due": ["api_key"],
  "secrets_overdue": ["old_password"],
  "results": [
    {
      "name": "database_password",
      "should_rotate": false,
      "status": "Up to date"
    },
    {
      "name": "api_key",
      "should_rotate": true,
      "status": "Due for rotation in 2 days"
    },
    {
      "name": "old_password",
      "should_rotate": true,
      "status": "Overdue for rotation by 15 days"
    }
  ]
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `secrets_checked` | integer | Number of secrets checked |
| `secrets_due` | array | Secrets due for rotation soon |
| `secrets_overdue` | array | Secrets overdue for rotation |
| `results` | array | Detailed status for each secret |
| `results[].name` | string | Secret name |
| `results[].should_rotate` | boolean | Whether rotation is needed |
| `results[].status` | string | Human-readable status |

**Error Responses:**

| Code | Description |
|------|-------------|
| `401` | Missing or invalid API key |
| `404` | Secretfile or specific secret not found |
| `500` | Rotation check failed |

---

### POST /rotation/execute - Execute Rotation

Rotate secrets that are due for rotation or force rotate specific secrets.

**Authentication:** Required

**Request Body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `secret_name` | string | No | `null` | Rotate only this specific secret |
| `force` | boolean | No | `false` | Force rotation even if not due |

**Example Request (Rotate Due Secrets):**
```bash
curl -X POST http://localhost:8000/rotation/execute \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "force": false
  }'
```

**Example Response:** `200 OK`
```json
{
  "rotated": ["api_key", "old_password"],
  "failed": [],
  "message": "Rotated 2 secret(s)"
}
```

**Example Request (Force Rotate Specific Secret):**
```bash
curl -X POST http://localhost:8000/rotation/execute \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "secret_name": "database_password",
    "force": true
  }'
```

**Example Response:** `200 OK`
```json
{
  "rotated": ["database_password"],
  "failed": [],
  "message": "Rotated 1 secret(s)"
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `rotated` | array | List of successfully rotated secrets |
| `failed` | array | List of secrets that failed to rotate |
| `message` | string | Human-readable summary |

**Error Responses:**

| Code | Description |
|------|-------------|
| `401` | Missing or invalid API key |
| `404` | Secretfile or specific secret not found |
| `500` | Rotation execution failed |

---

## Policy and Compliance

### POST /policy/check - Check Policy Compliance

Validate secrets against security policies.

**Authentication:** Required

**Request Body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `fail_on_warning` | boolean | No | `false` | Treat warnings as failures |

**Example Request:**
```bash
curl -X POST http://localhost:8000/policy/check \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "fail_on_warning": false
  }'
```

**Example Response (Compliant):** `200 OK`
```json
{
  "compliant": true,
  "errors": [],
  "warnings": [],
  "info": []
}
```

**Example Response (Policy Violations):** `200 OK`
```json
{
  "compliant": false,
  "errors": [
    {
      "secret": "weak_password",
      "policy": "minimum_length",
      "message": "Password length must be at least 16 characters",
      "severity": "error"
    }
  ],
  "warnings": [
    {
      "secret": "api_key",
      "policy": "rotation_period",
      "message": "No rotation period specified",
      "severity": "warning"
    }
  ],
  "info": [
    {
      "secret": "database_password",
      "policy": "best_practice",
      "message": "Using recommended password generator",
      "severity": "info"
    }
  ]
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `compliant` | boolean | Whether all policies pass |
| `errors` | array | Policy violations (errors) |
| `warnings` | array | Policy violations (warnings) |
| `info` | array | Policy information messages |
| `*.secret` | string | Secret name with violation |
| `*.policy` | string | Policy name |
| `*.message` | string | Violation description |
| `*.severity` | string | Severity level |

**Error Responses:**

| Code | Description |
|------|-------------|
| `401` | Missing or invalid API key |
| `404` | Secretfile not found |
| `500` | Policy check failed |

---

## Drift Detection

### POST /drift/check - Check for Drift

Detect unauthorized changes to secrets in target storage.

**Authentication:** Required

**Request Body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `secret_name` | string | No | `null` | Check only this specific secret |

**Example Request:**
```bash
curl -X POST http://localhost:8000/drift/check \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{}'
```

**Example Response (No Drift):** `200 OK`
```json
{
  "has_drift": false,
  "secrets_with_drift": [],
  "details": []
}
```

**Example Response (Drift Detected):** `200 OK`
```json
{
  "has_drift": true,
  "secrets_with_drift": ["database_password", "api_key"],
  "details": [
    {
      "secret": "database_password",
      "message": "Secret value has changed in target storage",
      "details": {
        "target": "aws_ssm",
        "path": "/prod/db/password",
        "expected_hash": "abc123...",
        "actual_hash": "def456..."
      }
    },
    {
      "secret": "api_key",
      "message": "Secret not found in expected target",
      "details": {
        "target": "key_vault",
        "name": "prod-api-key"
      }
    }
  ]
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `has_drift` | boolean | Whether any drift was detected |
| `secrets_with_drift` | array | List of secrets with drift |
| `details` | array | Detailed drift information |
| `details[].secret` | string | Secret name |
| `details[].message` | string | Drift description |
| `details[].details` | object | Additional drift details |

**Error Responses:**

| Code | Description |
|------|-------------|
| `401` | Missing or invalid API key |
| `404` | Secretfile not found |
| `500` | Drift check failed |

---

## Configuration

### POST /config/validate - Validate Configuration

Validate a Secretfile configuration before applying it.

**Authentication:** Required

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `config` | object | Yes | Secretfile configuration as JSON |

**Example Request:**
```bash
curl -X POST http://localhost:8000/config/validate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "config": {
      "secrets": [
        {
          "name": "test_secret",
          "kind": "random_password",
          "rotation_period": "90d"
        }
      ]
    }
  }'
```

**Example Response (Valid):** `200 OK`
```json
{
  "valid": true,
  "errors": [],
  "warnings": []
}
```

**Example Response (Invalid):** `200 OK`
```json
{
  "valid": false,
  "errors": [
    "Missing required field: version",
    "Missing required field: secrets"
  ],
  "warnings": [
    "No rotation_period specified for secret 'test_secret'"
  ]
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `valid` | boolean | Whether configuration is valid |
| `errors` | array | List of validation errors |
| `warnings` | array | List of validation warnings |

**Error Responses:**

| Code | Description |
|------|-------------|
| `401` | Missing or invalid API key |
| `400` | Malformed configuration |
| `500` | Validation failed |

---

## Audit Logs

### GET /audit/logs - Get Audit Logs

Retrieve audit logs of API operations.

**Authentication:** Required

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `limit` | integer | No | `50` | Number of logs to return (max 1000) |
| `offset` | integer | No | `0` | Number of logs to skip |
| `action` | string | No | `null` | Filter by action type |
| `resource` | string | No | `null` | Filter by resource |

**Example Request:**
```bash
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/audit/logs?limit=10&offset=0"
```

**Example Response:** `200 OK`
```json
{
  "entries": [
    {
      "timestamp": "2024-01-15T10:30:00Z",
      "action": "sync",
      "resource": "secrets",
      "user": null,
      "details": {
        "dry_run": false,
        "generated": ["database_password"],
        "skipped": []
      },
      "success": true
    },
    {
      "timestamp": "2024-01-15T10:25:00Z",
      "action": "check_rotation",
      "resource": "secrets",
      "user": null,
      "details": {
        "secrets_checked": 5,
        "secrets_due": 2
      },
      "success": true
    }
  ],
  "count": 2,
  "page": 1,
  "per_page": 10
}
```

**Example Request (Filtered):**
```bash
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/audit/logs?action=sync&limit=20"
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `entries` | array | List of audit log entries |
| `entries[].timestamp` | string | When action occurred |
| `entries[].action` | string | Action type |
| `entries[].resource` | string | Resource affected |
| `entries[].user` | string/null | User identifier (if available) |
| `entries[].details` | object | Additional details |
| `entries[].success` | boolean | Whether action succeeded |
| `count` | integer | Number of entries returned |
| `page` | integer | Current page number |
| `per_page` | integer | Entries per page |

**Error Responses:**

| Code | Description |
|------|-------------|
| `401` | Missing or invalid API key |
| `500` | Failed to retrieve logs |

---

## Error Responses

All error responses follow this format:

```json
{
  "error": "Brief error description",
  "detail": "Detailed error message",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Common HTTP Status Codes

| Code | Description | Common Causes |
|------|-------------|---------------|
| `200` | OK | Request succeeded |
| `400` | Bad Request | Invalid input or malformed request |
| `401` | Unauthorized | Missing or invalid API key |
| `404` | Not Found | Resource doesn't exist |
| `500` | Internal Server Error | Server-side error or exception |

---

## Best Practices

### 1. Always Use Dry Run First

Preview changes before applying:

```bash
# Dry run
curl -X POST http://localhost:8000/sync \
  -H "X-API-Key: $API_KEY" \
  -d '{"dry_run": true}'

# Actual sync
curl -X POST http://localhost:8000/sync \
  -H "X-API-Key: $API_KEY" \
  -d '{"dry_run": false}'
```

### 2. Check Rotation Regularly

Schedule rotation checks:

```bash
# Check what needs rotation
curl -X POST http://localhost:8000/rotation/check \
  -H "X-API-Key: $API_KEY"

# Execute if needed
curl -X POST http://localhost:8000/rotation/execute \
  -H "X-API-Key: $API_KEY"
```

### 3. Monitor for Drift

Detect unauthorized changes:

```bash
curl -X POST http://localhost:8000/drift/check \
  -H "X-API-Key: $API_KEY"
```

### 4. Validate Before Deploying

Test configurations:

```bash
curl -X POST http://localhost:8000/config/validate \
  -H "X-API-Key: $API_KEY" \
  -d @new-config.json
```

### 5. Review Audit Logs

Monitor activity:

```bash
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/audit/logs?limit=100"
```

---

## Next Steps

- Use the [Python client](python-client.md) for easier integration
- Learn about [deployment](deployment.md) options
- Check out [examples](../../examples/index.md) for common use cases
