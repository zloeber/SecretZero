# Script Generator

The script generator runs a local command and captures its output as the secret value.

## Configuration

| Option | Type | Description |
|--------|------|-------------|
| `command` | string | Command to execute |
| `args` | list | Optional arguments |
| `timeout` | int | Timeout in seconds |

## Example

```yaml
secrets:
  - name: signed_token
    generator: script
    generator_config:
      command: ./scripts/generate-token.sh
      args:
        - --issuer
        - secretzero
      timeout: 30
```

## Notes

- Keep scripts deterministic and non-interactive.
- Avoid logging sensitive output in scripts.
