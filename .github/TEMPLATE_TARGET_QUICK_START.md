# Jinja2 Template Target - Quick Start Guide

## Quick Example

### 1. Create a template file (e.g., `config.j2`)

```jinja2
# Application Configuration
DATABASE_URL={{ DB_HOST }}:{{ DB_PORT }}/{{ DB_NAME }}
DATABASE_USER={{ DB_USER }}
DATABASE_PASSWORD={{ DB_PASSWORD }}

{% if ENVIRONMENT == 'production' %}
DEBUG=False
LOG_LEVEL=ERROR
{% else %}
DEBUG=True
LOG_LEVEL=DEBUG
{% endif %}
```

### 2. Define secrets in Secretfile.yml

```yaml
version: "1.0"

secrets:
  - name: DB_HOST
    kind: static
    config:
      value: "db.example.com"
    targets:
      - provider: local
        kind: template
        config:
          template_path: "config.j2"
          output_path: ".env"

  - name: DB_PORT
    kind: static
    config:
      value: "5432"
    targets:
      - provider: local
        kind: template
        config:
          template_path: "config.j2"
          output_path: ".env"

  - name: DB_NAME
    kind: static
    config:
      value: "myapp"
    targets:
      - provider: local
        kind: template
        config:
          template_path: "config.j2"
          output_path: ".env"

  - name: DB_USER
    kind: static
    config:
      value: "appuser"
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

  - name: ENVIRONMENT
    kind: static
    config:
      value: "development"
    targets:
      - provider: local
        kind: template
        config:
          template_path: "config.j2"
          output_path: ".env"
```

### 3. Run sync

```bash
secretzero sync -f Secretfile.yml
```

### 4. Result

The `.env` file is created with rendered content:

```bash
# Application Configuration
DATABASE_URL=db.example.com:5432/myapp
DATABASE_USER=appuser
DATABASE_PASSWORD=aB3dEfGhIjKlMnOpQrStUvWxYz1234567

DEBUG=True
LOG_LEVEL=DEBUG
```

## Key Differences from FileTarget

| Aspect | FileTarget | TemplateTarget |
|--------|-----------|----------------|
| **Purpose** | Store secrets as key=value pairs | Render secrets into formatted files |
| **Format** | Predefined formats (dotenv, json, yaml, toml) | Custom Jinja2 template |
| **Use Case** | Direct secret storage | Configuration generation |
| **Power** | Simple and straightforward | Full Jinja2 templating capabilities |
| **Example** | `DB_PASSWORD=secret123` | `password: {{ DB_PASSWORD }}` in YAML config |

## Use Cases

### 1. Generate Docker Compose Files
```yaml
services:
  postgres:
    environment:
      POSTGRES_PASSWORD: {{ DB_PASSWORD }}
```

### 2. Generate Kubernetes Secrets
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: app-secrets
data:
  api-key: {{ API_KEY | b64encode }}
```

### 3. Environment-Specific Configs
```ini
{% if ENV == 'prod' %}
LOG_LEVEL=ERROR
MAX_CONNECTIONS=100
{% else %}
LOG_LEVEL=DEBUG
MAX_CONNECTIONS=10
{% endif %}
```

### 4. Generate CloudFormation Templates
```yaml
Parameters:
  DBPassword:
    Type: String
    NoEcho: true
    Default: {{ DB_PASSWORD }}
```

## Jinja2 Features You Can Use

### Variables
```jinja2
{{ variable_name }}
{{ secrets.variable_name }}
```

### Filters
```jinja2
{{ api_key | upper }}
{{ password | length }}
{{ config | to_json }}
```

### Conditionals
```jinja2
{% if DEBUG %}
debug: true
{% else %}
debug: false
{% endif %}
```

### Loops
```jinja2
servers:
{% for server in SERVERS.split(',') %}
  - {{ server }}
{% endfor %}
```

### Set Variables
```jinja2
{% set config_name = 'myapp-' + ENVIRONMENT %}
{% include 'config.j2' %}
```

## Troubleshooting

**Q: Template not found**
```
Error: Template file not found: config.j2
```
- Ensure template_path is correct
- Use absolute paths or relative to where you run `secretzero sync`

**Q: Variable not defined**
```
Error: 'MISSING_VAR' is undefined
```
- Add the variable as a secret with the same template target
- Or use default filter: `{{ MISSING_VAR | default('default_value') }}`

**Q: Jinja2 syntax error**
```
Template rendering failed: unexpected '}'
```
- Check Jinja2 syntax in template
- Use `{% ... %}` for statements, `{{ ... }}` for variables

**Q: Template rendered but content is wrong**
- Check that all secrets have the same target output_path
- Verify template uses correct secret names
- Use `secretzero sync --dry-run` to preview

## Installation

Jinja2 is already included with SecretZero:
```bash
pip install secretzero
```

If installing manually:
```bash
pip install jinja2
```

## Next Steps

1. Create a `.j2` template file for your config
2. Add secrets with template targets pointing to it
3. Run `secretzero sync` to render
4. Check the generated file
5. Add to `.gitignore` if it contains secrets

See `TEMPLATE_TARGET_IMPLEMENTATION.md` for complete documentation!
