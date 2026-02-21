# Compliance Policy

Compliance policies enforce standards such as SOC2 or ISO27001.

## Example

```yaml
policies:
  - name: soc2
    kind: compliance
    config:
      require_rotation: true
      require_audit: true
```
