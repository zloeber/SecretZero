# Template Target

The template target renders Jinja2 templates with secret values and writes the result
to a file.

## Configuration

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| `template_path` | string | Yes | Path to the template file |
| `output_path` | string | Yes | Path to the rendered file |

## Example

```yaml
secrets:
  - name: app_config
    generator: static
    generator_config:
      value: "unused"
    targets:
      - provider: local
        kind: template
        config:
          template_path: config.yaml.j2
          output_path: config.yaml
```

## Related

- [Local Provider](../providers/local.md)
- [File Target](file.md)
