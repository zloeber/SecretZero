---
name: secretzero-agent-adopt
description: |
  Use for agent runtime integration: discover Hermes/OpenClaw installs,
  bootstrap SecretZero environments with `secretzero agent list` / `agent adopt`,
  lockfile preseed, and restore loops. Inherits absolute rule from
  `skills/secretzero/SKILL.md` (SecretZero only; never secrets in context).
license: Apache-2.0
compatibility: Requires SecretZero CLI (Python 3.12+). Set SZ_AGENT_MODE=true for automated adopt flows.
metadata:
  author: secretzero
  version: "1.1"
allowed-tools: Bash(secretzero:*) Read
---

# SecretZero Agent Adopt Skill

Use when an agent runtime (Hermes, OpenClaw, or future claw-like installs) needs a
SecretZero environment, disaster recovery, or GitOps capture of **present** credentials.

Pair with `skills/secretzero-agent/SKILL.md` (sync vectors) and
`skills/secretzero-handle/SKILL.md` (spill-safe mode).

## Cold-start (remote repo)

1. Read repository `README.md` HTML comment `agent-entrypoint` block.
2. Install CLI: `uv tool install -U "secretzero[all]"`.
3. Set spill-safe mode when automating: `export SZ_AGENT_MODE=true`.
4. Discover installs (read-only):

```bash
secretzero agent list --format json
```

5. Plan adopt (no writes):

```bash
secretzero agent adopt --dry-run --format json
```

6. Bootstrap environment (default output = agent home):

```bash
secretzero agent adopt --format json
```

GitOps capture into the workspace:

```bash
secretzero agent adopt --target hermes --source-dir ~/.hermes --output-dir ./agents/hermes --template
```

## Command map

| Command | Purpose |
|---------|---------|
| `secretzero agent list` | Detect Hermes/OpenClaw installs + existing SecretZero envs |
| `secretzero agent adopt` | Write `Secretfile.yml` (present credentials only) |
| `secretzero agent backup` | Alias of `adopt` — **not** `secretzero backup create` |

## Safety contract

- stdout/JSON is **metadata only** (names, paths, counts).
- Generated manifests use `default: null` — never copy live values into YAML.
- Use `--preseed-lockfile` to hash present values without printing them.
- For missing secrets after restore: `secretzero agent sync --web`.
- Encrypted DR payloads: `secretzero backup create --encrypted` **after** adopt/sync.

## Standard restore loop

```bash
secretzero agent list --format json
secretzero agent adopt --target hermes --preseed-lockfile --format json
secretzero validate -f ~/.hermes/Secretfile.yml
secretzero agent sync --json -f ~/.hermes/Secretfile.yml
secretzero sync -f ~/.hermes/Secretfile.yml
```

Repeat `agent sync` until `pending_secrets` is empty.

## Autodetect rules

- `--target` omitted → try **Hermes**, then **OpenClaw**.
- `--source-dir` omitted → default install paths (`~/.hermes`, `~/.openclaw`, env overrides).
- If target or source cannot be resolved → **no files written**; JSON includes `reason`.

## Definition of done

- SecretZero env exists at chosen `output-dir`.
- Lockfile preseeded when requested.
- `agent sync` / `sync` complete with no pending manual secrets.
- No secret values appeared in agent context or logs.
