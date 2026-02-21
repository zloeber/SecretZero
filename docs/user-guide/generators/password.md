# Password Generator

The password generator creates high-entropy passwords suitable for databases, APIs, and
service credentials.

## Configuration

Common options include:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `length` | int | 32 | Total password length |
| `special` | bool | true | Include special characters |
| `exclude_characters` | string | "" | Characters to omit |

## Example

```yaml
secrets:
  - name: database_password
    generator: random_password
    generator_config:
      length: 32
      special: true
      exclude_characters: '"@/\'
```

## Notes

- Use `exclude_characters` to satisfy legacy systems.
- Rotate passwords regularly. See [Rotation](../rotation.md).
