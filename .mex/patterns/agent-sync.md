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

## Vector 2 operator handoff (agents)

- Prefer **`secretzero agent sync --web`** on the human’s machine; start in a **background terminal** when the agent runtime would block on the blocking wait for form submit.
- Echo the **verbatim** localhost URL from CLI stdout (full scheme/host/port/path). Do not paste secret values into chat.
- **`secretzero web`** is separate: it uses a **bootstrap token** in the login handoff — include the full URL + token from that command when applicable.
- After submit, the CLI helper stops the temporary localhost server; remind operators to close the tab and to **Ctrl+C** if they abandon the flow. API Vector 2: poll `GET /agent/sync/web/{session_id}`; localhost server may linger until API restart.

## Verify

- `task test` (excludes e2e) and `task test:e2e`
- `task schema:update` after model changes
