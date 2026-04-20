# git-crypt Provider

Use `kind: git_crypt` when you use git-crypt clean/smudge filters for encrypted-at-rest files in git.

## Provider and target kinds

- Provider: `git_crypt`
- Target: `git_crypt_file`

## Example

```yaml
providers:
  repo_gitcrypt:
    kind: git_crypt
    auth:
      kind: ambient
    config:
      secret_file: secrets/app.secrets.yaml
      format: yaml

secrets:
  - name: app_jwt_secret
    kind: random_password
    config:
      length: 48
    targets:
      - provider: repo_gitcrypt
        kind: git_crypt_file
        config:
          key: APP_JWT_SECRET
```

## Notes

- Requires `git-crypt` in `PATH` and repository unlocked for write workflows.
- Supports `yaml`, `json`, and `dotenv` formats.
