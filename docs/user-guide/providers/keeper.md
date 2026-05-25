# Keeper Password Manager Provider

The `keeper` provider reads and writes **Password Manager vault records** using the
[Keeper Commander](https://github.com/Keeper-Security/Commander) Python SDK.

## Install

```bash
uv tool install "secretzero[keeper]"
```

## Authentication

Preferred: Commander config file with a registered device token (after one interactive login).

```bash
export KEEPER_CONFIG_FILE="$HOME/.keeper/config.json"
```

Alternative (discouraged for production automation):

```bash
export KEEPER_USER="admin@example.com"
export KEEPER_PASSWORD="..."
```

## Provider config

```yaml
providers:
  keeper:
    kind: keeper
    auth:
      kind: token
      config:
        config_file: ${KEEPER_CONFIG_FILE}
    config:
      sync_ttl_seconds: 300
      default_folder: "Shared Folders/SecretZero"
```

## Target: `keeper_record`

### Update an existing record (scalar field)

```yaml
targets:
  - provider: keeper
    kind: keeper_record
    config:
      record_uid: InS1KiJBf1XGK16itcLnyA
      field: password
```

After the first sync, SecretZero tracks the resolved UID in the lockfile as
`keeper/keeper_record/<record_uid>` even when the manifest only specified `title` or `path`.

### Create when missing

```yaml
targets:
  - provider: keeper
    kind: keeper_record
    config:
      title: "SecretZero Service Account"
      create_if_missing: true
      record_type: login
      folder: "Shared Folders/SecretZero"
      field: password
```

### Structured login records

Use `structured: true` to read/write multiple typed fields (`login`, `password`, `url`, `notes` by default):

```yaml
secrets:
  - name: service_account
    kind: static
    config:
      value:
        login: service-bot
        password: null
        url: https://app.example.com
    targets:
      - provider: keeper
        kind: keeper_record
        config:
          title: "SecretZero Service Account"
          create_if_missing: true
          structured: true
          fields: [login, password, url]
```

Locator options (use one, unless `create_if_missing: true`):

| Config key | Description |
|------------|-------------|
| `record_uid` | Stable UID (preferred for production) |
| `path` | Vault path, e.g. `Shared Folders/App/DB Password` |
| `title` | Exact record title (errors if ambiguous) |
| `secret_name` | Alias for title-style lookup |

## Source: `provider_read`

```yaml
source:
  kind: provider_read
  required: true
  config:
    provider: keeper
    kind: keeper
    read:
      path: "Shared Folders/Vendors/Stripe"
      field: password
```

Structured reads:

```yaml
read:
  title: "SecretZero Service Account"
  structured: true
  fields: [login, password, url]
```

## Import / refresh

`secretzero import` reads live values from Keeper targets (including structured JSON payloads)
and updates `.gitsecrets.lock` hashes without writing back to Keeper.

## Rotation

Keeper targets participate in `secretzero rotate` / `secretzero sync --force-rotation` like other
provider-backed targets. The provider exposes:

- `generate_password(length=32)` for optional `provider_backed` workflows
- `rotate_secret(...)` which delegates to the same record update path as sync

## Notes

- Commander decrypts vault data locally; SecretZero never writes plaintext to the lockfile.
- Automation requires a registered device or non-interactive MFA configuration.
- This bundle targets **Password Manager** vault records, not Keeper Secrets Manager (KSM).
