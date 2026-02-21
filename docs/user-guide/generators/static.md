# Static Generator

The static generator provides fixed values. It is useful for values that already exist
or must be provided externally.

## Configuration

| Option | Type | Description |
|--------|------|-------------|
| `value` | string | Explicit value to store |
| `default` | string | Default when value is unset |

## Example

```yaml
secrets:
  - name: external_api_key
    generator: static
    generator_config:
      value: ${EXTERNAL_API_KEY}
```

## Notes

- Avoid committing static values to source control.
- Prefer environment variables or a provider-backed generator when possible.
