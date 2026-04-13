# Configuration Validation

SecretZero provides comprehensive validation to ensure your configuration is correct before generating and syncing secrets. This page covers validation concepts, error messages, and best practices.

## Validation Layers

SecretZero validates configuration at multiple layers:

1. **Schema Validation** - YAML structure and required fields
2. **Type Validation** - Data types and value formats
3. **Semantic Validation** - Logical consistency and references
4. **Provider Validation** - Provider connectivity and authentication
5. **Policy Validation** - Compliance with defined policies

## Schema Validation

### Basic Validation

The `validate` command checks your Secretfile syntax and structure:

```bash
secretzero validate
```

**Successful validation:**

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

**Failed validation:**

```
Validating: Secretfile.yml
✗ Validation failed: secrets.0.name: Field required
```

### Required Fields

The minimum valid Secretfile:

```yaml
secrets: []
```

### Common Schema Errors

#### Missing Required Secret Fields

**Error:**

```
Validation failed: secrets.0.name: Field required
```

**Fix:**

```yaml
secrets:
  - name: api_key
    kind: random_password
```

#### Missing Secret Name

**Error:**

```
Validation failed: secret definition missing 'name' field
```

**Fix:**

```yaml
secrets:
  - name: my_secret  # Add name field
    kind: random_password
```

#### Invalid Secret Kind

**Error:**

```
Validation failed: unknown secret kind 'random_pass'
```

**Fix:**

```yaml
secrets:
  - name: my_secret
    kind: random_password  # Use valid kind
```

**Valid kinds:**

- `random_password`
- `random_string`
- `static`
- `script`
- `api`
- `templates.<template_name>`

## Type Validation

### Data Type Errors

#### String vs Number

**Error:**

```
Validation failed: expected string, got integer
```

**Fix:**

```yaml
secrets:
  - name: db_config
    kind: static
    config:
      # Wrong: unquoted number
      port: 5432
      
      # Right: quoted string
      port: "5432"
```

#### Boolean Values

**Error:**

```
Validation failed: expected boolean, got string 'true'
```

**Fix:**

```yaml
secrets:
  - name: my_password
    kind: random_password
    config:
      # Wrong: quoted boolean
      special: "true"
      
      # Right: unquoted boolean
      special: true
```

### Format Validation

#### Rotation Period

**Error:**

```
Validation failed: invalid rotation_period format '90days'
```

**Fix:**

```yaml
secrets:
  - name: my_secret
    # Wrong formats
    rotation_period: "90days"
    rotation_period: "3months"
    
    # Right formats
    rotation_period: 90d     # 90 days
    rotation_period: 2w      # 2 weeks
    rotation_period: 3m      # 3 months
    rotation_period: 1y      # 1 year
```

**Valid suffixes:**

- `d` - days
- `w` - weeks
- `m` - months
- `y` - years

#### Variable Interpolation

**Error:**

```
Validation failed: invalid variable syntax '{{ var.name }}'
```

**Fix:**

```yaml
secrets:
  - name: my_secret
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          # Wrong: spaces inside braces
          name: "{{ var.environment }}"
          
          # Right: no spaces
          name: "{{var.environment}}"
```

## Semantic Validation

### Reference Validation

#### Template References

**Error:**

```
Validation failed: template 'database_creds' not found
```

**Fix:**

```yaml
templates:
  database_creds:  # Define template first
    description: Database credentials
    fields:
      password:
        generator:
          kind: random_password
          config:
            length: 32

secrets:
  - name: db
    kind: templates.database_creds  # Reference defined template
```

#### Provider References

**Error:**

```
Validation failed: provider 'aws-prod' not found
```

**Fix:**

```yaml
providers:
  aws-prod:  # Define provider first
    kind: aws
    auth:
      kind: ambient

secrets:
  - name: my_secret
    targets:
      - provider: aws-prod  # Reference defined provider
        kind: ssm_parameter
```

### Duplicate Names

**Error:**

```
Validation failed: duplicate secret name 'api_key'
```

**Fix:**

```yaml
secrets:
  # Wrong: duplicate names
  - name: api_key
    kind: random_password
  
  - name: api_key  # Duplicate!
    kind: static

  # Right: unique names
  - name: api_key_primary
    kind: random_password
  
  - name: api_key_secondary
    kind: static
```

### Circular Dependencies

**Error:**

```
Validation failed: circular variable reference detected
```

**Fix:**

```yaml
variables:
  # Wrong: circular reference
  a: "{{var.b}}"
  b: "{{var.a}}"  # Circular!

  # Right: linear dependency
  base: myapp
  name: "{{var.base}}-service"
  full_name: "{{var.name}}-production"
```

## Provider Validation

### Testing Provider Connectivity

Test provider authentication and connectivity:

```bash
secretzero test
```

**Output:**

```
Testing Provider Connectivity:

  • aws: ✓ Connected to AWS (us-east-1)
  • vault: ✗ Connection failed: invalid token
  • kubernetes: ✓ Connected to cluster 'production'
  • local: ✓ Local provider (always available)

Some provider tests failed. Check the messages above.
```

### Common Provider Errors

#### AWS Authentication

**Error:**

```
✗ AWS authentication failed: Unable to locate credentials
```

**Solutions:**

1. Configure AWS credentials:

```bash
aws configure
```

2. Use environment variables:

```bash
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_REGION=us-east-1
```

3. Use IAM role (if on EC2/ECS/Lambda):

```yaml
providers:
  aws:
    kind: aws
    auth:
      kind: ambient  # Will use IAM role
```

#### Vault Connection

**Error:**

```
✗ Vault connection failed: dial tcp: connection refused
```

**Solutions:**

1. Check Vault is running:

```bash
vault status
```

2. Set correct URL:

```yaml
providers:
  vault:
    kind: vault
    auth:
      kind: token
      config:
        url: http://localhost:8200  # Correct URL
        token: ${VAULT_TOKEN}
```

3. Check token:

```bash
export VAULT_TOKEN=$(vault token create -format=json | jq -r .auth.client_token)
```

#### Kubernetes Access

**Error:**

```
✗ Kubernetes connection failed: context 'production' not found
```

**Solutions:**

1. List available contexts:

```bash
kubectl config get-contexts
```

2. Use correct context:

```yaml
providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient
      config:
        context: correct-context-name
```

3. Or use current context:

```yaml
providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient  # Uses current context
```

## Policy Validation

### Checking Policy Compliance

Validate secrets against defined policies:

```bash
secretzero policy
```

**Output:**

```
Checking policy compliance...

Warnings:
  ⚠ database_password: No rotation_period defined
    → Add rotation_period to enable automatic rotation
  
  ⚠ api_token: Rotation period 180d exceeds policy maximum of 90d
    → Reduce rotation_period to 90d or less

Info:
  ℹ service_key: One-time secret cannot be automatically rotated

Summary:
  Errors: 0
  Warnings: 2
  Info: 1
```

### Policy Severity Levels

Policies can have different severity levels:

- **error**: Blocks sync operation
- **warning**: Allows sync but warns
- **info**: Informational only

```yaml
policies:
  rotation_required:
    kind: rotation
    require_rotation_period: true
    severity: warning  # Won't block sync
    enabled: true
  
  max_rotation_age:
    kind: rotation
    max_age: 90d
    severity: error  # Will block sync
    enabled: true
```

### Fail on Warnings

Treat warnings as errors:

```bash
secretzero policy --fail-on-warning
```

This will exit with an error code if any warnings are found, useful for CI/CD pipelines.

## Validation in CI/CD

### GitHub Actions

```yaml
name: Validate Secrets

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install SecretZero
        run: pip install secretzero
      
      - name: Validate Configuration
        run: secretzero validate
      
      - name: Check Policies
        run: secretzero policy --fail-on-warning
```

### GitLab CI

```yaml
validate:
  stage: test
  image: python:3.11
  script:
    - pip install secretzero
    - secretzero validate
    - secretzero policy --fail-on-warning
  only:
    - merge_requests
    - main
```

### Pre-commit Hook

```bash
# .git/hooks/pre-commit
#!/bin/bash

echo "Validating Secretfile..."
secretzero validate

if [ $? -ne 0 ]; then
  echo "Secretfile validation failed. Commit aborted."
  exit 1
fi

echo "Checking policies..."
secretzero policy --fail-on-warning

if [ $? -ne 0 ]; then
  echo "Policy check failed. Commit aborted."
  exit 1
fi

exit 0
```

Make it executable:

```bash
chmod +x .git/hooks/pre-commit
```

## Dry Run Validation

### Preview Changes

Test secret generation without making changes:

```bash
secretzero sync --dry-run
```

**Output:**

```
DRY RUN: No changes will be made

Synchronizing secrets...

✓ Processed 3 secrets
  • Generated: 2
  • Skipped: 1
  • Stored: 0

Details:

  database_password [random_password]: would generate
    → aws/ssm_parameter: would store

  api_key [static]: skipped (already exists)

  redis_password [random_password]: would generate
    → aws/ssm_parameter: would store
    → kubernetes/kubernetes_secret: would store

This was a dry run. Use 'secretzero sync' to apply changes.
```

### Benefits of Dry Run

1. **Preview generation** - See what would be generated
2. **Validate targets** - Check storage locations
3. **Test configuration** - Verify settings work
4. **Safe testing** - No actual changes made

## Validation Best Practices

### 1. Validate Early and Often

```bash
# After every change
secretzero validate

# Before syncing
secretzero validate && secretzero sync --dry-run
```

### 2. Automate Validation

Add validation to your development workflow:

```bash
# Makefile
.PHONY: validate
validate:
	secretzero validate
	secretzero policy
	secretzero test

.PHONY: sync
sync: validate
	secretzero sync
```

### 3. Use Version Control

Track validation in commits:

```bash
git add Secretfile.yml
secretzero validate && git commit -m "Update secrets configuration"
```

### 4. Document Requirements

Add comments to your Secretfile:

```yaml
version: '1.0'

# Required environment variables:
# - ENVIRONMENT: deployment environment
# - AWS_REGION: AWS region
# - API_KEY: external service API key

variables:
  environment: ${ENVIRONMENT}
  aws_region: ${AWS_REGION}
```

### 5. Test Provider Access

Regularly test provider connectivity:

```bash
# In CI/CD pipeline
secretzero test || exit 1
```

### 6. Maintain Policy Compliance

Keep policies up to date:

```yaml
policies:
  # SOC2 compliance
  rotation_required:
    kind: rotation
    require_rotation_period: true
    severity: error
    enabled: true
  
  max_rotation_age:
    kind: rotation
    max_age: 90d  # Required by policy
    severity: error
    enabled: true
```

## Troubleshooting Validation

### Get Detailed Error Information

For complex validation errors, check:

1. **YAML syntax**:

```bash
# Check YAML is valid
python -c "import yaml; yaml.safe_load(open('Secretfile.yml'))"
```

2. **Variable expansion**:

```bash
# Show resolved variables
secretzero validate --verbose
```

3. **Provider configuration**:

```bash
# Test individual provider
secretzero test --provider aws
```

### Common Mistakes

#### Incorrect Indentation

```yaml
# Wrong
secrets:
- name: my_secret
  kind: random_password
  targets:
  - provider: aws
    kind: ssm_parameter

# Right
secrets:
  - name: my_secret
    kind: random_password
    targets:
      - provider: aws
        kind: ssm_parameter
```

#### Missing Quotes

```yaml
# Wrong
variables:
  account: 123456789012  # Interpreted as number

# Right
variables:
  account: "123456789012"  # String
```

#### Trailing Spaces

Some YAML parsers reject trailing whitespace. Use a linter:

```bash
yamllint Secretfile.yml
```

### Enable Debug Mode

Set environment variable for detailed output:

```bash
export SECRETZERO_DEBUG=1
secretzero validate
```

## Error Reference

### Common Error Codes

| Code | Error | Solution |
|------|-------|----------|
| `E001` | Missing required field | Add the required field |
| `E002` | Invalid field type | Use correct data type |
| `E003` | Unknown reference | Define referenced entity |
| `E004` | Duplicate name | Use unique names |
| `E005` | Invalid format | Fix format/syntax |
| `E006` | Provider connection failed | Check provider config |
| `E007` | Policy violation | Fix policy compliance issue |
| `E008` | Circular dependency | Remove circular references |

### Getting Help

If validation fails and you can't determine why:

1. Check [Troubleshooting Guide](../../reference/troubleshooting.md)
2. Review [Examples](../../examples/index.md) for reference
3. Search [GitHub Issues](https://github.com/zloeber/SecretZero/issues)
4. Ask in [Discussions](https://github.com/zloeber/SecretZero/discussions)

## Next Steps

<div class="grid cards" markdown>

-   :material-file-document: **Secretfile Reference**

    ---

    Complete specification of Secretfile.yml
    
    [Read Reference →](secretfile.md)

-   :material-variable: **Variables**

    ---

    Learn about variable interpolation
    
    [Variable Guide →](variables.md)

-   :material-console: **CLI Commands**

    ---

    Use validation commands
    
    [CLI Reference →](../cli/index.md)

-   :material-help-circle: **Troubleshooting**

    ---

    Solve common problems
    
    [Troubleshooting →](../../reference/troubleshooting.md)

</div>
