---
name: secretzero
description: |
  Compatibility entrypoint for SecretZero skills. Enforces the absolute rule:
  never consume secrets in agent context — use SecretZero for all secret
  handling. Routes to secretzero-author, secretzero-agent, secretzero-handle,
  and secretzero-agent-adopt.
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
| `read_file` / grep / cat on `.env`, `.env.*`, `*.pem`, credential files | `secretzero detect`, `discover`, `ingest preseed` (metadata / hashes only) |
| `secretzero get --reveal`, `render`, `backup restore --print` under agents | `agent sync --json`, `status`, `list secrets`, lockfile hashes |
| MCP sampling or host-LLM scans over secret file contents | `detect` / `discover` tools (names, paths, confidence — no values) |
| Putting literals in `Secretfile.yml` during agent authoring | `null`, `${VAR}`, `.szvar`; `SZ_AGENT_MODE=true` + `secretzero-handle` |

On spill-sensitive hosts set **`SZ_AGENT_MODE=true`** (see `skills/secretzero-handle/SKILL.md`). All focused skills below inherit this rule.

## Use `secretzero-author` when

- Creating or editing `Secretfile.yml` (guided: manifest root, inventory table, add/edit loop, optional `detect`/`discover`, optional `secretzero web`; Hermes + MCP notes in skill).
- Performing schema-first, high-quality manifest authoring.
- Doing safe, contextless discovery and `.szvar` environment breakout.
- Adding least-privilege provider identity policy binding for targets.

File: `skills/secretzero-author/SKILL.md`

## Use `secretzero-agent` when

- Running agentic sync workflows (Vector 1/2/3).
- Operating CLI/API orchestration flows.
- Managing secure human-in-the-loop runtime scenarios.
- Handling install/onboarding/automation checks.

File: `skills/secretzero-agent/SKILL.md`

## Universal installation baseline

```bash
uv tool install -U "secretzero[all]"
```

The two focused skills include detailed workflows, safety rules, and usage examples.
