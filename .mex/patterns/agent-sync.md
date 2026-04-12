---
name: agent-sync
description: Unified `secretzero agent sync` (CLI) and `POST /agent/sync` (API) — three vectors, shared synchronizer.
---

# Agent sync (unified workflow)

## When to use

- Bootstrapping secrets with agents: automation, human instructions, or localhost web form (Vector 2).
- Any change to agent sync behavior must touch **both** CLI (`src/secretzero/cli.py`) and API (`src/secretzero/api/app.py`) and reuse `AgentSecretSynchronizer` in `src/secretzero/agent.py`.

## Core files

- Models: `AgentConfig`, `AgentMode`, `Secretfile.agent` — `src/secretzero/models.py`
- Templating: `AgentInstructions.render_for_secret`, `render_template_with_agent_context` — `src/secretzero/config.py`
- Web UI / sessions: `src/secretzero/agent_webui.py`
- E2E: `tests/e2e/test_agent_vector*.tavern.yaml`, `task test:e2e`

## Verify

- `task test` (excludes e2e) and `task test:e2e`
- `task schema:update` after model changes
