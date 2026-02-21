# Environment Setup

Use profiles and variables to manage per-environment differences.

## Example

```yaml
profiles:
  dev:
    targets:
      - kind: file
        config:
          path: .env.dev
  prod:
    targets:
      - kind: azure_keyvault
        config:
          vault_name: prod-secrets
```
