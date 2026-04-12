---
name: secretzero
description: |
  Use whenever a Secretfile.yml exists in the repository (or sub-directory). 
  Ideal for bootstrapping secrets, running sync/rotate operations, authoring schema-compliant manifests, 
  or handling secure human-in-the-loop secret-zero workflows with AI agents. 
  Supports fully automated, agent-instructed, and secure web-UI assisted secret seeding.
---

# SecretZero for Coding Agents

**Always operate from the repository root** where `Secretfile.yml` lives (unless the manifest specifies a different path — then use `-f` / `--file` consistently for all commands).

## Core Principles for Agents
- **Never** request or receive plaintext secret values in your context, logs, or history.
- Prefer the **unified `secretzero agent sync`** command for all secret-zero scenarios.
- Use `--json` output when possible for reliable parsing.
- Keep the agent loop simple: call the command → act on results → repeat until clean.

## Unified Agent Workflow (Covers All Secret-Zero Vectors)

SecretZero now provides **one primary command** that intelligently handles every common secret bootstrapping case:

```bash
secretzero agent sync --json [--web] [--dry-run] [--verbose]
```

### The Three Vectors (Handled Automatically)

**Vector 1 – Agent instructs human (CLI-guided seeding)**  
Human is expected to perform steps (create keys in consoles, run commands, etc.).  
- Run: `secretzero agent sync --json`  
- Parse `pending_secrets` → relay the rendered `summary` + ordered `steps` to the human.  
- Human follows instructions (often running `secretzero sync` locally or external actions).  
- Re-run the command until `pending_secrets` is empty.

**Vector 2 – Secure human input via local web UI (no value leakage)**  
Agent triggers a temporary, localhost-only form for the human to enter values.  
- Run: `secretzero agent sync --web`  
- Tell the human: “A secure local page has opened at http://127.0.0.1:XXXX — please enter the requested secrets there and submit. Do **not** paste them here.”  
- The web UI feeds values directly into the sync engine; values never enter your context or logs.  
- Server auto-shuts down after submission.

**Vector 3 – Fully automated (no human intervention)**  
Providers have sufficient authentication.  
- Set `SZ_AGENT=true` in the environment, or rely on `Secretfile.agent.mode: auto`.  
- Run: `secretzero agent sync --json` (or plain `secretzero sync`).  
- Everything that can be generated or pulled automatically is handled; any remaining issues appear clearly in `failed_secrets`.

**Recommended Agent Loop (works for all vectors):**
1. Execute `secretzero agent sync --json` (add `--web` when appropriate).
2. If `pending_secrets` exist:
   - For Vector 1: Present templated instructions to the human.
   - For Vector 2: Trigger `--web` and guide the user to the local form.
3. Re-run the command after human action.
4. If `failed_secrets` appear, fix the `Secretfile.yml` (usually by adding better `agent_instructions`) and retry.
5. Proceed only when `pending_secrets` and `failed_secrets` are empty.

**Top-level configuration** (in `Secretfile.yml`):
```yaml
agent:
  mode: auto | human | web   # default: auto
  web_port_min: 49152        # optional bounds for the Vector 2 localhost form
  web_port_max: 65535
```

### REST API (same contract as the CLI)

Remote clients should call **`POST /agent/sync`** with JSON fields aligned to the CLI: `dry_run`, `web`, optional `lockfile`, and optional `sz_agent` (per-request override of the `SZ_AGENT` environment on the server). Responses mirror `secretzero agent sync --json` (no plaintext secret values).

- **Vector 2 over HTTP:** when manual secrets are pending and `web` is true, the response includes `status: awaiting_web_input`, a `web_url` on `127.0.0.1`, and `web_session_id`. Poll **`GET /agent/sync/web/{session_id}`** until `done` is true; structured results are in `result` (still no secret values).

Example:

```bash
curl -s -X POST "http://127.0.0.1:8000/agent/sync" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true}'
```

## Installation

Requires **Python 3.12+** and [`uv`](https://docs.astral.sh/uv/) (preferred) or `pip`.

```bash
# Minimal install
uv tool install secretzero

# Add extras for your providers (or use [all] if unsure)
uv tool install secretzero[aws]
uv tool install secretzero[azure]
uv tool install secretzero[vault]
uv tool install secretzero[kubernetes]
uv tool install secretzero[cicd]
uv tool install secretzero[all]
```

Verify: `secretzero --help`

## Baseline Onboarding Commands (Run in Order)

1. `secretzero validate` — Validates structure and variables (`--var-file` if needed).
2. `secretzero init --install` — Installs declared provider extras.
3. `secretzero test` — Checks provider connectivity.
4. `secretzero sync --dry-run` — Previews the full sync (may prompt for manual secrets).

Default lockfile: `.gitsecrets.lock` (derived automatically from the manifest filename).

## Authoring `Secretfile.yml` (Schema-Driven)

Use the CLI as the single source of truth.

**Useful commands:**
- `secretzero schema export -o Secretfile.schema.json` — Export JSON Schema for IDE support.
- `secretzero validate [--format json]` — Validate your manifest.
- `secretzero create --template-type basic` — Scaffold a new manifest (also supports `aws`, `azure`, etc.).
- `secretzero secret-types [--type <kind>] --verbose` — List available generators and options.

**Best practices for agent-friendly secrets:**
- For any secret that cannot be fully automated, define `agent_instructions` with:
  - `summary`: Short human-readable description.
  - `steps`: Ordered list of actions (supports templating with `{{secret_name}}`, `{{target.xxx}}`, etc.).
- Templated instructions are automatically rendered with Secretfile variables and target details.

Example structure for a manual secret:
```yaml
secrets:
  external_api_key:
    kind: static
    agent_instructions:
      summary: "Create a new API key in the Example.com console"
      steps:
        - "Go to https://console.example.com/api-keys and create a key named {{secret_name}} for this environment."
        - "Run `secretzero sync -s {{secret_name}}` locally to seed it."
        - "Confirm to the agent when complete."
```

## Common Pitfalls to Avoid

- Missing or incomplete `agent_instructions` on non-auto secrets → results in `failed_secrets`.
- Forgetting `--var-file` when variables are used.
- Running commands from the wrong directory.
- Expecting plaintext values — always use the agent workflow instead.
- Installing without the correct provider extras.

## Quick Reference Cheat Sheet

```bash
secretzero validate
secretzero schema export -o Secretfile.schema.json
secretzero agent sync --json          # Vector 1 & 3
secretzero agent sync --web           # Vector 2
secretzero sync --dry-run
secretzero secret-types --verbose
```

## Tips for Effective Agent Use

- Always prefer `--json` output when parsing results programmatically.
- When guiding the human, quote the exact rendered `summary` and `steps` from the JSON.
- For Vector 2, clearly communicate that the web UI is temporary, localhost-only, and secure.
- After any manual changes or human actions, re-run `secretzero agent sync --json` to confirm state.
- Combine with `secretzero drift` or `secretzero rotate` when maintenance is needed post-bootstrap.

This workflow keeps secrets **out of agent context**, provides clear guidance, and scales from fully manual to fully automated scenarios with minimal friction.

For the absolute latest behavior, run `secretzero --help` and `secretzero agent sync --help` in the target repository.
