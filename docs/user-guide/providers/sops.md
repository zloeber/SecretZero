# SOPS Provider

Use `kind: sops` when your encrypted secrets are managed by the `sops` CLI and committed to git.

## Provider and target kinds

- Provider: `sops`
- Target: `sops_file`

## Example

```yaml
providers:
  repo_sops:
    kind: sops
    auth:
      kind: ambient
    config:
      sops_file: secrets/app.enc.yaml
      format: yaml

secrets:
  - name: app_api_token
    kind: random_string
    config:
      length: 48
    targets:
      - provider: repo_sops
        kind: sops_file
        config:
          key: APP_API_TOKEN
```

## Notes

- Requires `sops` available in `PATH`.
- Supports `yaml`, `json`, and `dotenv` content formats.
- SecretZero handles structured key/value updates, then re-encrypts via `sops`.
