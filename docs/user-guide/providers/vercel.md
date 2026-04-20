# Vercel Provider

The `vercel` provider manages project environment variables in Vercel for
`development`, `preview`, and `production` targets.

## Install

```bash
uv tool install "secretzero[vercel]"
```

## Authentication

Set a Vercel token:

```bash
export VERCEL_TOKEN=your_token
```

Optional team context:

```bash
export VERCEL_TEAM_ID=team_xxxxx
```

## Provider config

```yaml
providers:
  vercel:
    kind: vercel
    auth:
      kind: token
      config:
        token: ${VERCEL_TOKEN}
        team_id: ${VERCEL_TEAM_ID}
    config:
      project_id: prj_xxxxx
```

## Target: `vercel_env`

```yaml
secrets:
  - name: app_database_url
    kind: random_password
    config:
      length: 32
    targets:
      - provider: vercel
        kind: vercel_env
        config:
          project_id: prj_xxxxx
          secret_name: DATABASE_URL
          environments: [preview, production]
```

## Notes

- Sync writes encrypted environment variables in Vercel.
- Retrieval returns metadata (Vercel does not expose decrypted values for existing vars).
- Deletion can be environment-scoped using `environments`.
