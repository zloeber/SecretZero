# File Target

The file target stores secrets in local files such as `.env`, JSON, YAML, TOML, or Terraform `.tfvars`.
It is commonly used for development environments or local testing.

## Configuration

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| `path` | string | Yes | File path to write |
| `format` | string | Yes | `dotenv`, `json`, `yaml`, `toml`, or `tfvars` |
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

### Terraform tfvars (HCL assignments)

Use `format: tfvars` for flat `variable_name = "value"` files consumed by `terraform plan -var-file=...`.
Paths ending in `.tfvars` (but not `.tfvars.json`) infer this format when `format` is omitted.

```yaml
secrets:
  - name: cloudflare_api_token
    kind: static
    config:
      value: null
    targets:
      - provider: local
        kind: file
        config:
          path: terraform/terraform.tfvars
          format: tfvars
          merge: true
          key: cloudflare_api_token
```

For JSON var files (`terraform.auto.tfvars.json`), use `format: json` instead.

**Limitations (v1):** string values only; no maps, lists, or heredocs. Rewriting the file does not preserve comments.

## Related

- [Local Provider](../providers/local.md)
- [Template Target](template.md)
