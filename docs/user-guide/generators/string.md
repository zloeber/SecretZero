# Random String Generator

The random string generator creates strings for API keys, tokens, and identifiers.

## Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `length` | int | 32 | Total string length |
| `charset` | string | alphanumeric | Character set (`hex`, `base64`, `alphanumeric`) |
| `uppercase` | bool | true | Allow uppercase characters |
| `lowercase` | bool | true | Allow lowercase characters |

## Example

```yaml
secrets:
  - name: api_key
    generator: random_string
    generator_config:
      length: 64
      charset: alphanumeric
```
