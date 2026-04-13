# secretzero validate

Validate Secretfile configuration.

## Synopsis

```bash
secretzero validate [OPTIONS]
```

## Description

The `validate` command checks the syntax and structure of your `Secretfile.yml`, ensuring all required fields are present and properly formatted. It performs schema validation, type checking, and reference validation.

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--file`, `-f` | path | `Secretfile.yml` | Path to Secretfile |
| `--help` | flag | - | Show help message |

## Examples

### Basic Validation

Validate the default Secretfile:

```bash
secretzero validate
```

**Successful output:**

```
Validating: Secretfile.yml
✓ Configuration is valid

Configuration Summary:
  Manifest spec version: 1
  Variables: 3
  Providers: 2
  Secrets: 5
  Templates: 1
```

### Validate Specific File

Validate a non-default Secretfile:

```bash
secretzero validate --file Secretfile.prod.yml
```

Or using short form:

```bash
secretzero validate -f Secretfile.staging.yml
```

### Validation in Scripts

Use in automation scripts:

```bash
#!/bin/bash

if secretzero validate; then
  echo "Configuration valid"
  secretzero sync
else
  echo "Configuration invalid"
  exit 1
fi
```

## What Gets Validated

### 1. Schema Structure

- Required `version` field
- Proper YAML syntax
- Valid field names
- Correct data types

### 2. Secret Definitions

- Each secret has a `name`
- Each secret has a `kind`
- Generator configurations are valid
- At least one target per secret

### 3. Provider References

- All referenced providers exist
- Provider configurations are valid
- Auth methods are supported

### 4. Template References

- Referenced templates are defined
- Template fields are properly structured
- Generators are valid

### 5. Variable References

- Variable syntax is correct
- No circular dependencies

## Validation Output

### Success

```
Validating: Secretfile.yml
✓ Configuration is valid

Configuration Summary:
  Version: 1.0
  Variables: 3
  Providers: 2
  Secrets: 5
  Templates: 1
```

### Failure

```
Validating: Secretfile.yml
✗ Validation failed: secrets.0.name: Field required
```

## Common Validation Errors

### Missing Required Secret Fields

**Error:**

```
✗ Validation failed: secrets.0.name: Field required
```

**Fix:**

```yaml
secrets:
  - name: api_key
    kind: random_password
```

### Invalid Secret Kind

**Error:**

```
✗ Validation failed: unknown secret kind 'random_pass'
```

**Fix:**

```yaml
secrets:
  - name: my_secret
    kind: random_password  # Use correct kind name
```

### Missing Provider

**Error:**

```
✗ Validation failed: provider 'aws-prod' not found
```

**Fix:**

```yaml
providers:
  aws-prod:  # Define the provider
    kind: aws
    auth:
      kind: ambient

secrets:
  - name: my_secret
    targets:
      - provider: aws-prod  # Now references defined provider
        kind: ssm_parameter
```

### Invalid Template Reference

**Error:**

```
✗ Validation failed: template 'db_creds' not found
```

**Fix:**

```yaml
templates:
  db_creds:  # Define the template
    description: Database credentials
    fields:
      password:
        generator:
          kind: random_password
          config:
            length: 32

secrets:
  - name: database
    kind: templates.db_creds  # Reference defined template
```

## Integration Examples

### Pre-commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

echo "Validating Secretfile..."
secretzero validate

if [ $? -ne 0 ]; then
  echo "❌ Secretfile validation failed"
  echo "Please fix errors before committing"
  exit 1
fi

echo "✅ Secretfile validation passed"
exit 0
```

### GitHub Actions

```yaml
name: Validate Secrets

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install SecretZero
        run: pip install secretzero
      
      - name: Validate Configuration
        run: secretzero validate
```

### GitLab CI

```yaml
validate:
  stage: test
  image: python:3.11
  script:
    - pip install secretzero
    - secretzero validate
  only:
    - merge_requests
    - main
```

### Makefile

```makefile
.PHONY: validate
validate:
secretzero validate

.PHONY: sync
sync: validate
secretzero sync
```

## Best Practices

### 1. Validate Before Committing

```bash
git add Secretfile.yml
secretzero validate && git commit -m "Update secrets configuration"
```

### 2. Validate in CI/CD

Always validate in your CI/CD pipeline:

```yaml
# .github/workflows/secrets.yml
- name: Validate Secrets
  run: secretzero validate
```

### 3. Validate Multiple Environments

```bash
# Validate all environment files
for env in dev staging prod; do
  echo "Validating $env..."
  secretzero validate -f "Secretfile.$env.yml"
done
```

### 4. Combine with Other Checks

```bash
#!/bin/bash
# Full validation script

echo "Checking YAML syntax..."
yamllint Secretfile.yml

echo "Validating SecretZero configuration..."
secretzero validate

echo "Checking policy compliance..."
secretzero policy

echo "All checks passed!"
```

## Troubleshooting

### YAML Syntax Errors

If validation fails with YAML errors:

```bash
# Check YAML syntax separately
python -c "import yaml; yaml.safe_load(open('Secretfile.yml'))"
```

### Indentation Issues

YAML is sensitive to indentation. Use consistent spacing (2 or 4 spaces):

```yaml
# Correct
secrets:
  - name: my_secret
    kind: random_password
    config:
      length: 32

# Wrong - inconsistent indentation
secrets:
- name: my_secret
  kind: random_password
    config:
    length: 32
```

### Quote Issues

Some values need quotes:

```yaml
# AWS account IDs should be quoted
variables:
  aws_account: "123456789012"  # Quoted

# Rotation periods don't need quotes
secrets:
  - name: my_secret
    rotation_period: 90d  # Not quoted
```

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Validation successful |
| `1` | Validation failed |
| `2` | File not found or not readable |

## Related Commands

- [`create`](create.md) - Create a new Secretfile
- [`test`](test.md) - Test provider connectivity
- [`policy`](policy.md) - Check policy compliance
- [`sync`](sync.md) - Sync secrets after validation

## See Also

- [Validation Guide](../configuration/validation.md) - Complete validation documentation
- [Secretfile Reference](../configuration/secretfile.md) - Secretfile specification
- [Troubleshooting](../../reference/troubleshooting.md) - Common issues and solutions
