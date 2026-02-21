# Rotation Policies

Rotation policies enforce how frequently secrets must rotate and when rotation
is required.

## Example

```yaml
policies:
  - name: rotation_guard
    kind: rotation
    config:
      max_age_days: 90
      require_rotation: true
```

## Notes

- Combine with compliance policies for regulated environments.
- Use `secretzero policy` in CI to enforce standards.
