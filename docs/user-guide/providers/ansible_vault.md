# Ansible Vault Provider

Use `kind: ansible_vault` when your repo workflow stores secrets in an Ansible Vault encrypted file.

## Provider and target kinds

- Provider: `ansible_vault`
- Target: `ansible_vault_file`

## Example

```yaml
providers:
  repo_vault:
    kind: ansible_vault
    auth:
      kind: ambient
      config:
        vault_password_env: ANSIBLE_VAULT_PASSWORD
    config:
      vault_file: secrets/group_vars/all/vault.yml
      format: yaml

secrets:
  - name: app_db_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: repo_vault
        kind: ansible_vault_file
        config:
          key: APP_DB_PASSWORD
```

## Notes

- Supports `yaml`, `json`, and `dotenv` payload formats inside the encrypted vault file.
- Uses your configured vault password (direct config or env-var indirection).
