# Encrypted-in-Git Provider Workflows

SecretZero supports multiple workflows for teams that intentionally keep **encrypted secret files in git** while keeping plaintext out of commits.

Use this page as a quick decision guide:

| Workflow | Provider kind | Target kind | Best when |
|---|---|---|---|
| Ansible Vault | `ansible_vault` | `ansible_vault_file` | You already use Ansible vault files in infra automation |
| SOPS | `sops` | `sops_file` | You want modern structured-file encryption (age/KMS/PGP backends) |
| git-crypt | `git_crypt` | `git_crypt_file` | You rely on transparent git clean/smudge encryption filters |

## Why use these with SecretZero?

- Keep secret *values* out of plaintext commits.
- Keep secret *shape and lifecycle* in `Secretfile.yml`.
- Reuse `secretzero sync`, rotation metadata, and lockfile tracking.
- Mix encrypted-file targets with cloud targets in the same secret definition.

## Common pattern

```yaml
providers:
  repo_encrypted:
    kind: sops
    auth:
      kind: ambient
    config:
      sops_file: secrets/app.enc.yaml
      format: yaml

secrets:
  - name: app_db_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: repo_encrypted
        kind: sops_file
        config:
          key: APP_DB_PASSWORD
```

The `config.key` value is optional. If omitted, SecretZero uses `Secret.name` as the key inside the encrypted file.

## Operational notes

- SecretZero does not commit files for you. It writes/updates encrypted-file artifacts; your git workflow decides what to commit.
- Ambient auth means the underlying tool/CLI (for example `sops`, `git-crypt`, or BlackBox commands) must already be installed and usable in that shell environment.
- Keep one source of truth per lane/environment where possible (`dev`, `staging`, `prod`) to avoid merge conflicts in encrypted blobs.

## Next

- [Ansible Vault provider](ansible_vault.md)
- [SOPS provider](sops.md)
- [git-crypt provider](git_crypt.md)
