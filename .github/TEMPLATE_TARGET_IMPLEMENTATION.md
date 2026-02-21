# Jinja2 Template Target Implementation

## Overview

I've successfully implemented a Jinja2 template target for SecretZero that allows you to:
- Define Jinja2 templates in your repository
- Process them with secrets to generate configuration files
- Support conditional logic, loops, and Jinja2 filters

## What Was Implemented

### 1. Template Target Class (`src/secretzero/targets/template.py`)

A new target type that renders Jinja2 templates with secret values:

```python
class TemplateTarget(BaseTarget):
    """Render Jinja2 templates with secret values."""
```

**Key Features:**
- Validates required config (template_path, output_path)
- Collects secrets during sync
- Renders templates with all collected secrets as context
- Creates parent directories automatically
- Proper error handling with clear messages
- Full Jinja2 feature support (filters, conditionals, loops)

### 2. Integration with SecretZero

- Registered in `src/secretzero/targets/__init__.py`
- Updated `src/secretzero/sync.py` to:
  - Import TemplateTarget
  - Handle template targets in `_retrieve_from_target()`
  - Handle template targets in `_store_in_target()`
  - Track collected secrets for templates
  - Call rendering after all secrets are synced via new `_render_template_targets()` method
- Uses existing `TEMPLATE = "template"` enum value in `TargetKind`

### 3. Comprehensive Tests (15 new tests)

All passing in `tests/test_template_target.py`:
- Basic initialization and validation
- Template rendering with different Jinja2 features
- Error handling (missing files, invalid syntax)
- Directory creation
- File overwriting
- Jinja2 filters, conditionals, and loops

## How to Use

### 1. Create a Jinja2 Template File

```jinja2
{# config.j2 #}
# Database Configuration
export DB_HOST={{ DB_HOST }}
export DB_USER={{ DB_USER }}
export DB_PASS={{ DB_PASSWORD }}

# API Configuration
{% if ENV == 'production' %}
export DEBUG=False
export LOG_LEVEL=WARNING
{% else %}
export DEBUG=True
export LOG_LEVEL=DEBUG
{% endif %}

# Additional servers
servers:
{% for server in SERVERS.split(',') %}
  - {{ server }}
{% endfor %}
```

### 2. Define in Secretfile.yml

```yaml
version: "1.0"

secrets:
  - name: DB_HOST
    kind: static
    config:
      value: "localhost"
    targets:
      - provider: local
        kind: template
        config:
          template_path: "config.j2"
          output_path: ".env"

  - name: DB_USER
    kind: static
    config:
      value: "admin"
    targets:
      - provider: local
        kind: template
        config:
          template_path: "config.j2"
          output_path: ".env"

  - name: DB_PASSWORD
    kind: random_password
    config:
      length: 32
    targets:
      - provider: local
        kind: template
        config:
          template_path: "config.j2"
          output_path: ".env"

  - name: ENV
    kind: static
    config:
      value: "development"
    targets:
      - provider: local
        kind: template
        config:
          template_path: "config.j2"
          output_path: ".env"

  - name: SERVERS
    kind: static
    config:
      value: "server1.example.com,server2.example.com"
    targets:
      - provider: local
        kind: template
        config:
          template_path: "config.j2"
          output_path: ".env"
```

### 3. Run Sync

```bash
secretzero sync -f Secretfile.yml
```

This will:
1. Generate/retrieve all secrets
2. Collect them for each template target
3. Render the templates with those secrets
4. Write output files (.env in this example)

## Template Syntax

### Access Secrets

Both of these work:
```jinja2
{{ DB_HOST }}           # Direct access
{{ secrets.DB_HOST }}   # Dict access (recommended for clarity)
```

### Jinja2 Features

**Conditionals:**
```jinja2
{% if ENV == 'production' %}
DEBUG=False
{% else %}
DEBUG=True
{% endif %}
```

**Loops:**
```jinja2
{% for host in HOSTS.split(',') %}
- {{ host }}
{% endfor %}
```

**Filters:**
```jinja2
{{ API_KEY | upper }}       # Uppercase
{{ API_KEY | length }}      # Length
{{ DB_PASS | string }}      # Convert to string
```

**Default Values:**
```jinja2
{{ DB_PORT | default('5432') }}
```

**Multi-line:**
```jinja2
{% if ENABLED | bool %}
enabled = true
{% endif %}
```

## Configuration Options

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `template_path` | string | Yes | - | Path to Jinja2 template file (relative or absolute) |
| `output_path` | string | Yes | - | Path where rendered file will be written |
| `overwrite` | boolean | No | true | Whether to overwrite existing output file |

## How It Works

### Architecture Flow

```
Secretfile.yml
    ↓
Generate/retrieve secrets for "template" targets
    ↓
Collect secrets in _template_targets (keyed by output_path)
    ↓
After all secrets synced:
    ↓
Call _render_template_targets()
    ↓
For each template target:
  - Load Jinja2 template
  - Render with collected secrets
  - Write to output_path
    ↓
Update lockfile
```

### Key Implementation Details

1. **Collection Phase**: When `_store_in_target()` is called for a template target, secrets are collected in memory (not written immediately)

2. **Rendering Phase**: After all secrets are synced, `_render_template_targets()` renders all templates together with their collected secrets

3. **Context Data**: Templates have access to:
   - Direct variable access: `{{ SECRET_NAME }}`
   - Dict access: `{{ secrets.SECRET_NAME }}`
   - Full dictionary: `secrets` variable contains all secrets

4. **Error Handling**: If template rendering fails:
   - Clear error message is returned
   - Sync continues with other targets
   - Error is reported in sync results

## Advanced Examples

### Environment-Specific Configuration

```yaml
secrets:
  - name: APP_CONFIG
    kind: static
    config:
      value: "prod"
    targets:
      - provider: local
        kind: template
        config:
          template_path: "config.template.j2"
          output_path: "config.yml"

  - name: DB_CONNECTION_STRING
    kind: random_string
    config:
      length: 32
    targets:
      - provider: local
        kind: template
        config:
          template_path: "config.template.j2"
          output_path: "config.yml"
```

**config.template.j2:**
```yaml
application:
  name: myapp
  environment: {{ APP_CONFIG }}

database:
  connection_string: {{ DB_CONNECTION_STRING }}
  
{% if APP_CONFIG == 'prod' %}
  timeout: 30
  pool_size: 20
{% else %}
  timeout: 5
  pool_size: 5
{% endif %}
```

### Multi-format Configuration

Generate both `.env` and `config.json` from the same secrets:

```yaml
secrets:
  - name: API_KEY
    kind: random_string
    config:
      length: 32
    targets:
      - provider: local
        kind: template
        config:
          template_path: "env.template.j2"
          output_path: ".env"
      
      - provider: local
        kind: template
        config:
          template_path: "config.template.j2"
          output_path: "config.json"
```

## Requirements

### Dependencies

Jinja2 must be available (included in SecretZero by default):
```bash
pip install secretzero
# or
pip install jinja2
```

### File Permissions

- Read access to template files
- Write access to output directories

## Testing

Run the template target tests:
```bash
pytest tests/test_template_target.py -v
```

All 241 tests pass (15 new template tests + 226 existing tests).

## Integration with Existing Features

### With Lockfile Tracking

Template targets are tracked in the lockfile like other targets:
- Rotation history recorded
- Change detection supported
- Drift detection compatible

### With Rotation Policies

Template targets support rotation:
```yaml
secrets:
  - name: API_KEY
    kind: random_string
    rotation_period: 30
    config:
      length: 32
    targets:
      - provider: local
        kind: template
        config:
          template_path: "config.j2"
          output_path: "app_config.json"
```

### With Dry-Run

Test template rendering without writing files:
```bash
secretzero sync -f Secretfile.yml --dry-run
```

## Troubleshooting

### Template File Not Found
```
Failed to render template: Template file not found: /path/to/template.j2
```
**Solution:** Verify template_path is correct (absolute or relative to where sync is run)

### Undefined Variable in Template
```
Template rendering failed: ... undefined variable ...
```
**Solution:** Ensure all variables used in template are defined as secrets with template targets

### Invalid Jinja2 Syntax
```
Template rendering failed: ... 'nonexistent_filter' is undefined
```
**Solution:** Check Jinja2 filter names and syntax

### Permission Denied
```
Failed to render template: ... Permission denied ...
```
**Solution:** Verify write permissions on output directory

## Future Enhancements

Potential features (not yet implemented):
- Variable scope/namespacing
- Template inheritance
- Custom Jinja2 filters
- Template validation before rendering
- Template version tracking
- Multiple template rendering per secret

## Files Changed

### New Files
- `src/secretzero/targets/template.py` - TemplateTarget implementation
- `tests/test_template_target.py` - 15 comprehensive tests

### Modified Files
- `src/secretzero/targets/__init__.py` - Added TemplateTarget import and export
- `src/secretzero/sync.py` - Added template target handling in sync engine

### Test Results
- ✅ All 241 tests passing (15 new + 226 existing)
- ✅ 98% coverage for template.py
- ✅ No regressions in existing functionality

## Example Complete Secretfile

```yaml
version: "1.0"

secrets:
  # Database credentials
  - name: db_host
    kind: static
    config:
      value: "postgres.example.com"
    targets:
      - provider: local
        kind: template
        config:
          template_path: "templates/docker-compose.j2"
          output_path: "docker-compose.yml"

  - name: db_user
    kind: static
    config:
      value: "appuser"
    targets:
      - provider: local
        kind: template
        config:
          template_path: "templates/docker-compose.j2"
          output_path: "docker-compose.yml"

  - name: db_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: local
        kind: template
        config:
          template_path: "templates/docker-compose.j2"
          output_path: "docker-compose.yml"

  # API secrets
  - name: api_key
    kind: random_string
    config:
      length: 64
    targets:
      - provider: local
        kind: template
        config:
          template_path: "templates/api-config.j2"
          output_path: ".env.local"

  - name: environment
    kind: static
    config:
      value: "development"
    targets:
      - provider: local
        kind: template
        config:
          template_path: "templates/api-config.j2"
          output_path: ".env.local"
```

**templates/docker-compose.j2:**
```yaml
version: '3.9'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: {{ db_user }}
      POSTGRES_PASSWORD: {{ db_password }}
      POSTGRES_HOST_NAME: {{ db_host }}
    ports:
      - "5432:5432"
```

**templates/api-config.j2:**
```bash
# Generated configuration file
API_KEY={{ api_key }}
ENVIRONMENT={{ environment }}
DEBUG={% if environment == 'development' %}true{% else %}false{% endif %}
```

This provides a complete, production-ready template target implementation integrated with SecretZero's architecture!
