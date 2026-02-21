# Access Control Policy

Access control policies restrict where secrets may be stored.

## Example

```yaml
policies:
  - name: prod-access
    kind: access
    config:
      allow_targets:
        - aws/secrets_manager
        - azure/key_vault
```
