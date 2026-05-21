# Agent Instructions Report — Design Spec

**Date:** 2026-05-21  
**Status:** Approved

## Summary

Add `secretzero agent instructions` — a dedicated command that prints a concise, numbered Rich console report of `agent_instructions` (summary + steps) without running sync.

## Command

```bash
secretzero agent instructions [OPTIONS]
```

| Flag | Purpose |
|------|---------|
| `-f` / `--file` | Secretfile path (default `Secretfile.yml`) |
| `-l` / `--lockfile` | Lockfile path (default `.gitsecrets.lock`) |
| `-v` / `--var-file` | Merge `.szvar` files (repeatable) |
| `-e` / `--environment` | Environment profile |
| `-s` / `--secret` | Filter to specific secret(s) (repeatable) |
| `--all` | Show every secret with `agent_instructions` |
| `--detailed` | Include optional metadata fields |
| `--format text\|json` | Default `text` |

## Scope

**Default (`pending`):** Secrets that have `agent_instructions`, are not in the lockfile, and are not auto-syncable — aligned with `agent sync` pending semantics.

**With `--all`:** Every secret defining `agent_instructions` (respects `-s` filter).

## Output

### Text (default)

Per secret: Rich rule header, summary, numbered steps (`action` primary, dim `description`).

### Text (`--detailed`)

Adds prerequisites, required tools, automation hint, estimated time, fallback, documentation URL.

### JSON

```json
{
  "scope": "pending",
  "total": 1,
  "secrets": {
    "stripe_api_key": {
      "summary": "...",
      "steps": [...]
    }
  }
}
```

With `--detailed`, optional instruction fields are included per secret.

## Rendering

Use `AgentInstructions.render_for_secret()` with resolved Secretfile variables.

## Safety

Instruction text only — no secret values. No spill-guard block under `SZ_AGENT` / `SZ_AGENT_MODE`.

## Implementation

- New module: `src/secretzero/agent_instructions_report.py`
- CLI wiring in `src/secretzero/cli.py` under `agent` group
- Tests: `tests/test_agent_instructions_report.py`
- Docs: `docs/user-guide/agent-sync.md`, `examples/agent-guided.yml`

## Follow-up (completed)

`agent sync` pending output and generator manual prompts reuse `render_instruction_entries()` from the shared module.
