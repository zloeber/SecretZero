# Ansible Vault File Target

Target kind: `ansible_vault_file`

Stores one secret key/value entry into the provider-configured Ansible Vault encrypted file.

## Config

| Option | Type | Required | Description |
|---|---|---|---|
| `key` | string | No | Override key name in vault payload (defaults to `Secret.name`) |
