# SOPS File Target

Target kind: `sops_file`

Stores one secret key/value entry into the provider-configured SOPS encrypted file.

## Config

| Option | Type | Required | Description |
|---|---|---|---|
| `key` | string | No | Override key name in encrypted payload (defaults to `Secret.name`) |
