# Local-only secrets

Workstation-specific secrets (for example a MySQL root password used only on a developer laptop) should not pollute the shared `.gitsecrets.lock` that teams merge on `main`.

## `local: true`

Add `local: true` on a secret definition to store sync state in **`.gitsecrets.local.lock`** next to your shared lockfile instead of `.gitsecrets.lock`:

```yaml
secrets:
  - name: mysql_root_password
    kind: random_password
    local: true
    config:
      length: 32
    targets:
      - provider: local
        kind: file
        config:
          path: .env.local
          format: dotenv
          merge: true
```

The flag supports variable interpolation:

```yaml
variables:
  IS_LOCAL_ENV: "true"

secrets:
  - name: mysql_root_password
    kind: random_password
    local: ${IS_LOCAL_ENV:-false}
    # ...
```

When `local` resolves to false, behavior is unchanged (shared lockfile).

## MySQL local root workflow

1. Developer A adds the secret to `Secretfile.yml` with `local: true` and merges to `main`.
2. Developer A runs `secretzero sync` — SecretZero generates a password, writes `.env.local`, and records hashes in `.gitsecrets.local.lock` (gitignored).
3. Developer B pulls `main` and runs `secretzero sync` — SecretZero sees no local lockfile entry on B's machine, generates a **different** password, and writes B's `.env.local` without touching the shared lockfile.

Shared `.gitsecrets.lock` continues to track team-wide secrets only.

## Target restrictions

Local secrets may only use **`local/file`** or **`local/template`** targets unless you set `local_allow_cloud: true` (discouraged).

## Agent safety

Local sync follows the same spill guards as other commands: under `SZ_AGENT_MODE=true`, plaintext is never printed; only lockfile hashes and metadata are persisted.

## Files

| File | Committed | Purpose |
|------|-----------|---------|
| `.gitsecrets.lock` | Usually yes | Shared team sync state |
| `.gitsecrets.local.lock` | No (gitignored) | Per-workstation local secret state |
| `.env.local` | No | Local target file for dev credentials |
