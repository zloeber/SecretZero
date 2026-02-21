# Rotation Policy

Rotation policies enforce maximum secret age and rotation requirements.

## Example

```yaml
policies:
  - name: prod-rotation
    kind: rotation
    config:
      max_age_days: 60
      require_rotation: true
```
