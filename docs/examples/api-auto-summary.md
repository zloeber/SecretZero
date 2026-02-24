# API Documentation Setup - Quick Reference

## What Was Set Up

✅ **Interactive OpenAPI Documentation** - Swagger UI embedded in MkDocs
✅ **Python API Reference** - Auto-generated from docstrings  
✅ **Setup Guide** - Complete documentation on usage

## Files Created

1. **[docs/reference/api-interactive.md](../reference/api-interactive.md)** - Interactive Swagger UI explorer
2. **[docs/reference/api-python.md](../reference/api-python.md)** - Python API reference from docstrings
3. **[docs/examples/api-auto-summary.md](api-auto-summary.md)** - Setup summary and quick reference

## Dependencies Installed

```toml
# pyproject.toml
docs = [
    "mkdocs-swagger-ui-tag>=0.6.0",  # Interactive API docs
    "mkdocstrings[python]>=0.24.0",  # Python reference
]
api = [
    "fastapi>=0.129.0",
    "uvicorn[standard]>=0.41.0",
]
```

## Configuration Added

```yaml
# mkdocs.yml
plugins:
  - swagger-ui-tag               # Enables <swagger-ui> tags
  - mkdocstrings:                # Enables ::: docstring blocks
      handlers:
        python:
          paths: [src]
```

## How to Use

### View Interactive API Docs

```bash
# 1. Start API server
export SECRETZERO_API_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
secretzero-api &

# 2. Serve documentation
mkdocs serve

# 3. Open in browser
open http://127.0.0.1:8000/reference/api-interactive/
```

### View Python Reference

```bash
# Build and serve docs
mkdocs serve

# Navigate to
open http://127.0.0.1:8000/reference/api-python/
```

## Documentation Approaches

### 1. Interactive API Testing (Swagger UI)

**File**: [docs/reference/api-interactive.md](../reference/api-interactive.md)

**Features**:
- Live OpenAPI specification from running server
- Interactive endpoint testing
- Request/response schemas
- Try endpoints directly in browser

**Syntax**:
```markdown
<swagger-ui src="http://localhost:8000/openapi.json"/>
```

**Requires**: Running API server at `http://localhost:8000`

### 2. Python API Reference (mkdocstrings)

**File**: [docs/reference/api-python.md](../reference/api-python.md)

**Features**:
- Auto-generated from docstrings
- Shows source code
- Searchable by MkDocs
- No running server needed

**Syntax**:
```markdown
::: secretzero.api.app
    options:
      show_source: true
      members:
        - create_app
```

**Requires**: Good docstrings in code

## Testing

### Test the Build

```bash
# Clean build
mkdocs build --clean

# Should see:
# INFO - mkdocs_swagger_ui_tag: Processing file 'reference/api-interactive.md'
# INFO - Documentation built in X.XX seconds
```

### Test Interactive Docs

```bash
# Start API
secretzero-api &

# Verify OpenAPI spec
curl http://localhost:8000/openapi.json | jq '.info'

# Should return:
# {
#   "title": "SecretZero API",
#   "description": "REST API for SecretZero...",
#   "version": "0.1.0"
# }
```

### Test Python Reference

View generated docs at:
- http://127.0.0.1:8000/reference/api-python/

Should show auto-generated docs for:
- `create_app()` function
- Pydantic schemas
- Authentication module
- Audit logging

## Comparison: CLI vs API Auto-Documentation

| Feature | CLI (mkdocs-click) | API (mkdocs-swagger-ui-tag + mkdocstrings) |
|---------|-------------------|-------------------------------------------|
| **Auto-generation** | ✅ From Click commands | ✅ From FastAPI app + docstrings |
| **Interactive testing** | ❌ No | ✅ Yes (Swagger UI) |
| **Shows source code** | ❌ No | ✅ Yes (mkdocstrings) |
| **Requires running service** | ❌ No | ⚠️ Only for interactive testing |
| **Searchable** | ✅ Yes | ✅ Yes |
| **Configuration syntax** | `::: mkdocs-click` blocks | `<swagger-ui>` tags + `::: module` blocks |

## Next Steps

### 1. Enhance FastAPI Docstrings

Add comprehensive docstrings to all endpoints:

```python
@app.post("/sync", response_model=SyncResponse)
async def sync_secrets(request: SyncRequest):
    """Synchronize secrets to all targets.
    
    Generates secret values and stores them in configured targets.
    
    Args:
        request: Sync request with optional dry_run flag
        
    Returns:
        SyncResponse with generation statistics
        
    Raises:
        HTTPException: If sync fails
        
    Example:
        ```bash
        curl -X POST http://localhost:8000/sync \\
          -H "X-API-Key: xxx" \\
          -d '{"dry_run": false}'
        ```
    """
```

### 2. Add to Navigation

Update `mkdocs.yml` to include in nav:

```yaml
nav:
  - Reference:
      - API Interactive: reference/api-interactive.md
      - API Python: reference/api-python.md
      - CLI Auto: reference/cli-auto.md
```

### 3. Integrate with Existing Docs

Link from existing pages:

```markdown
# API Documentation

- [API Getting Started](../api-getting-started.md) - Manual guide
- [API Interactive Reference](reference/api-interactive.md) - Auto-generated Swagger UI
- [API Python Reference](reference/api-python.md) - Auto-generated from code
```

### 4. Production Deployment

For production API docs, use actual API URL:

```markdown
<swagger-ui src="https://api.secret0.com/openapi.json"/>
```

## Resources

- **API Quick Reference**: [api-auto-summary.md](api-auto-summary.md)
- **CLI Quick Reference**: [cli-auto-summary.md](cli-auto-summary.md)
- **mkdocs-swagger-ui-tag**: https://github.com/blueswen/mkdocs-swagger-ui-tag
- **mkdocstrings**: https://mkdocstrings.github.io/
- **FastAPI**: https://fastapi.tiangolo.com/

## Summary

You now have **two complementary API documentation approaches**:

1. **Interactive Swagger UI** - For testing and exploring the live API
2. **Python Reference** - For understanding implementation details

Both stay automatically in sync with your code! 🎉
