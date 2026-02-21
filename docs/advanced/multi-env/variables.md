# Variable Overrides

Variables allow you to reuse a single Secretfile across environments.

## Example

```yaml
variables:
  environment: ${ENVIRONMENT:-dev}

secrets:
  - name: api_key
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /{{var.environment}}/api/key
```
