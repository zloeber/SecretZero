# secretzero get

Retrieve secret metadata (and optionally plaintext) using provider bundle retrieval methods.

## Synopsis

```bash
secretzero get --provider <provider_alias> --secret-id <id> [OPTIONS]
```

## Description

`secretzero get` executes provider capability methods through the bundle system (via `SyncEngine.get_provider_secret`), so retrieval behavior stays provider-agnostic at the CLI layer.

By default, output is metadata-only. Plaintext is shown only when `--reveal` is passed and the provider API supports returning secret values.

## Safety Controls

- If `SZ_SANDBOX=true`, the command is blocked by default.
- Use `SZ_ALLOW_GET_IN_SANDBOX=true` to explicitly override that block.
- Policy preflight runs by default (`--policy-check`) and blocks on error-severity policy violations.

## Arguments

None.

## Required Options

| Option | Description |
|--------|-------------|
| `--provider` | Provider alias defined under `providers:` in `Secretfile.yml` |
| `--secret-id` | Provider-specific secret identifier/path/name |

## Optional Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--file`, `-f` | path | `Secretfile.yml` | Path to Secretfile |
| `--lockfile`, `-l` | path | `.gitsecrets.lock` | Path to lockfile |
| `--method` | string | `retrieve_secret` (fallback `get_secret`) | Retrieval method name |
| `--arg` | repeatable `KEY=VALUE` | none | Method kwargs; JSON values accepted |
| `--reveal` | flag | false | Include plaintext in output (if revealable) |
| `--policy-check/--no-policy-check` | flag | `--policy-check` | Enable/disable policy preflight |
| `--format` | `text` or `json` | `text` | Output format |

## Examples

### Metadata-only retrieval (default)

```bash
secretzero get --provider aws --secret-id "/prod/api/token"
```

### Reveal plaintext (when provider supports it)

```bash
secretzero get \
  --provider aws \
  --secret-id "/prod/api/token" \
  --reveal \
  --format json
```

### Use a specific provider method and args

```bash
secretzero get \
  --provider vault \
  --secret-id "secret/myapp/db" \
  --method retrieve_secret \
  --arg field=password \
  --arg version=2
```

### Sandbox override (explicit)

```bash
export SZ_SANDBOX=true
export SZ_ALLOW_GET_IN_SANDBOX=true
secretzero get --provider aws --secret-id "/prod/api/token"
```

## JSON Output

Example response (`--format json`):

```json
{
  "provider": "aws",
  "secret_id": "/prod/api/token",
  "method": "retrieve_secret",
  "retrieved": true,
  "revealable": true,
  "notes": null,
  "revealed": false
}
```

When `--reveal` is used and the secret is revealable, `value` is included.

## Exit Behavior

- Returns validation error when sandbox block applies.
- Returns validation error when policy preflight blocks.
- Returns unknown error for provider retrieval failures (for example bad method args, auth failure, provider error).

## Related Commands

- [`show`](show.md) - Inspect manifest and lockfile metadata for configured secrets
- [`policy`](policy.md) - Validate policy compliance directly
- [`sync`](sync.md) - Generate/store secrets through normal lifecycle workflows
