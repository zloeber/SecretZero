# Agent adopt (Hermes / OpenClaw)

Bootstrap a SecretZero environment from a local agent install without exposing secret values.

## Commands

```bash
secretzero agent list --format json
secretzero agent adopt --dry-run --format json
secretzero agent adopt --preseed-lockfile --format json
```

`secretzero agent backup` is an alias of `agent adopt`. It is **not** `secretzero backup create`.

## Defaults

- `--output-dir` defaults to the resolved agent install path (`~/.hermes`, `~/.openclaw`, …).
- `--target` autodetects **Hermes**, then **OpenClaw**.
- Only **present** catalog credentials become manifest secrets.

## GitOps capture

```bash
secretzero agent adopt \
  --target hermes \
  --source-dir ~/.hermes \
  --output-dir ./agents/hermes \
  --template
```

## Restore loop

1. `secretzero agent adopt --preseed-lockfile`
2. `secretzero validate -f <Secretfile>`
3. `secretzero agent sync --json -f <Secretfile>`
4. `secretzero sync -f <Secretfile>`

See `skills/secretzero-agent-adopt/SKILL.md` and
`docs/superpowers/specs/2026-05-27-agent-adopt-design.md`.
