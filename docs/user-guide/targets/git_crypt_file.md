# git-crypt File Target

Target kind: `git_crypt_file`

Stores one secret key/value entry into the provider-configured git-crypt managed file.

## Config

| Option | Type | Required | Description |
|---|---|---|---|
| `key` | string | No | Override key name in file payload (defaults to `Secret.name`) |
