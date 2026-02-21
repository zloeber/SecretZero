# File Target

The file target stores secrets in local files such as `.env`, JSON, YAML, or TOML.
It is commonly used for development environments or local testing.

## Configuration

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| `path` | string | Yes | File path to write |
| `format` | string | Yes | `dotenv`, `json`, `yaml`, or `toml` |
| `merge` | bool | No | Merge with existing content |

## Example

```yaml
secrets:
  - name: database_password
    generator: random_password
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
          merge: true
```

## Related

- [Local Provider](../providers/local.md)
- [Template Target](template.md)
