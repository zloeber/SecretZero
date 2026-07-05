---
name: secretzero
description: |
  Compatibility entrypoint for SecretZero skills. Enforces the absolute rule:
  never consume secrets in agent context — use SecretZero for all secret
  handling. Routes to secretzero-author, secretzero-agent, secretzero-handle,
  and secretzero-agent-adopt.
license: Apache-2.0
compatibility: Requires SecretZero CLI (Python 3.12+). Optional MCP extra for sz_* tools in agent hosts.
metadata:
  author: secretzero
  version: "1.1"
allowed-tools: Bash(secretzero:*) Read
---

# SecretZero Skill Router

This skill is retained for backwards compatibility and publishing stability.
Use one of the focused skills below for all new work.

## Absolute rule: SecretZero only — never secrets in context

**Agents must never consume secret values in LLM or tool context.** That includes reading, receiving, pasting, transcribing, “debugging with,” summarizing, or inferring plaintext from files the user shares in chat.

**Use SecretZero entirely for secrets handling** — discovery, authoring, validation, seeding, sync, rotate, drift, and human entry. The agent orchestrates **metadata-only** CLI/API/MCP results; SecretZero and approved human surfaces hold the values.

| Forbidden | Use instead |
|-----------|-------------|
| User pastes API keys/passwords into chat | `secretzero agent sync --web`, `secretzero web`, or Vector 1 instructions |
| `read_file` / grep / cat on `.env`, `.env.*`, `*.pem`, credential files | `secretzero detect`, `discover`, `ingest preseed`, or MCP **`sz_discover`** (metadata / hashes only) |
| `secretzero get --reveal`, `render`, `backup restore --print` under agents | `agent sync --json`, **`sz_status`** / `status`, `list secrets`, lockfile hashes |
| MCP sampling or host-LLM scans over secret file contents | **`sz_discover`** / `secretzero discover` / `detect` (names, paths, confidence — no values) |
| Putting literals in `Secretfile.yml` during agent authoring | `null`, `${VAR}`, `.szvar`; `SZ_AGENT_MODE=true` + `secretzero-handle` |

On spill-sensitive hosts set **`SZ_AGENT_MODE=true`** (see `skills/secretzero-handle/SKILL.md`). The MCP server (`secretzero-mcp`) sets this by default when unset. All focused skills below inherit this rule.

## MCP-capable hosts

When the agent host registers **`secretzero-mcp`** (see `docs/mcp-setup.md`):

| Task | Skill | MCP tools |
|------|-------|-----------|
| Author / edit `Secretfile.yml` | `secretzero-author` | `sz_discover`, then CLI `validate` / edit |
| Bootstrap / seed pending secrets | `secretzero-agent` | **CLI/API only** — `agent sync --json [--web]` (not on MCP) |
| Status, sync, rotate, drift | `secretzero-agent` | `sz_status`, `sz_sync`, `sz_rotate`, `sz_drift_check` |
| `.env` / spill-safe file workflows | `secretzero-handle` | MCP inherits `SZ_AGENT_MODE`; use `sz_discover` + `ingest preseed` via CLI |

Install: `uv tool install -U "secretzero[mcp]"` then `secretzero mcp config generate --workspace /path/to/repo`.

## Use `secretzero-author` when

- Creating or editing `Secretfile.yml` (guided: manifest root, inventory table, add/edit loop, optional `detect`/`discover`, optional `secretzero web`; Hermes + MCP notes in skill).
- Discovering valid generator/target kinds: `secretzero catalog --format json` (machine-complete registry).
- Performing schema-first, high-quality manifest authoring.
- Doing safe, contextless discovery and `.szvar` environment breakout.
- Adding least-privilege provider identity policy binding for targets.

File: `skills/secretzero-author/SKILL.md`

## Use `secretzero-agent` when

- Running agentic sync workflows (Vector 1/2/3).
- Operating CLI/API/MCP orchestration flows (`sz_status`, `sz_sync`, `sz_rotate`, `sz_drift_check`).
- Managing secure human-in-the-loop runtime scenarios.
- Handling install/onboarding/automation checks.

File: `skills/secretzero-agent/SKILL.md`

## Universal installation baseline

```bash
uv tool install -U "secretzero[all]"
```

For MCP hosts add the `mcp` extra: `uv tool install -U "secretzero[mcp]"`.

The focused skills include detailed workflows, safety rules, and usage examples.
