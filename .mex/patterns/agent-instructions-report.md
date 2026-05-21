---
name: agent-instructions-report
description: Standalone `secretzero agent instructions` report for concise pending/all agent_instructions output.
triggers:
  - "agent instructions"
  - "instructions report"
  - "pending manual steps"
last_updated: 2026-05-21
---

# Agent Instructions Report

## Context

`secretzero agent sync` surfaces `agent_instructions` only as part of sync output for pending secrets. Operators and agents sometimes need a read-only, formatted checklist without running sync.

## Command

```bash
secretzero agent instructions [OPTIONS]
```

| Flag | Behavior |
|------|----------|
| (default) | Pending manual secrets only (not in lockfile, not auto-syncable, has `agent_instructions`) |
| `--all` | Every secret with `agent_instructions` |
| `--detailed` | Include prerequisites, tools, timing, docs, fallback, automation hint |
| `-s` / `--secret` | Filter to named secret(s) |
| `--format json` | Machine-readable payload (no secret values) |

Uses environment-aware Secretfile loading (`-f`, `-e`, `-v`, `-l`) like other CLI commands.

## Implementation

- Collection/render: `src/secretzero/agent_instructions_report.py`
- CLI: `agent instructions` under the `agent` group in `cli.py`
- `agent sync` pending output and generator manual prompts reuse `render_instruction_entries()`
- Templates resolved via `AgentInstructions.render_for_secret()`

## Verify

- [ ] `secretzero agent instructions --help` lists options
- [ ] Default pending scope matches `agent sync` pending semantics
- [ ] `--all` includes lockfile-backed secrets
- [ ] JSON output omits optional fields unless `--detailed`

## Update Scaffold

- [ ] Document in `docs/user-guide/agent-sync.md` when behavior changes
