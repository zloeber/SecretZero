---
name: secretzero-agent
description: |
  Use for agentic and operational SecretZero workflows including unified
  `agent sync`, CLI/API parity, secure human-in-the-loop vectors, and
  automation-safe run loops.
---

# SecretZero Agent Skill

Use this skill when running SecretZero in agentic workflows (manual-assisted, web-assisted, or fully automated), or when guiding users through runtime usage scenarios.

## Install / Verify

Preferred install:

```bash
uv tool install -U "secretzero[all]"
```

Lean or provider-specific installs:

```bash
uv tool install -U secretzero
uv tool install -U "secretzero[aws]"
uv tool install -U "secretzero[azure]"
```

Alternative:

```bash
pip install -U "secretzero[all]"
```

Verify CLI:

```bash
secretzero --help
secretzero agent sync --help
```

## Core Agent Contract

**Absolute rule:** `skills/secretzero/SKILL.md` — never consume secrets in context; use SecretZero for all handling (`agent sync`, `--web`, validate, status). Never request, receive, or print plaintext secret values.
- Prefer JSON output for machine handling.
- When running in automation or spill-sensitive hosts, set **`SZ_AGENT_MODE=true`** so the CLI blocks or redacts commands that would dump secret-bearing config (see `skills/secretzero-handle/SKILL.md`).
- Use the unified entrypoint:

```bash
secretzero agent sync --json [--web] [--dry-run] [--verbose]
```

## Three Usage Vectors

1. **Human-instructed (Vector 1)**
   - Run `secretzero agent sync --json`.
   - Relay `pending_secrets[].summary` and ordered `steps` exactly.
   - Re-run until clean.

2. **Secure local web capture (Vector 2)**
   - Run `secretzero agent sync --web` (add `--json` only when you also need structured stdout after the run finishes).
   - **Do not block the whole agent session on the foreground TTY if your environment allows it:** start the command in a **background terminal** (or equivalent job control) on the operator’s machine so the process can stay alive until the form is submitted, and **capture stdout** if you need to quote the URL line back reliably.
   - When the CLI prints the localhost URL, **relay the complete URL verbatim** to the user (scheme, host, port, and path — no truncation). Vector 2 binds to `127.0.0.1`; the printed URL is the handoff surface (this is **not** the same as `secretzero web`, which uses a separate **bootstrap token** for the network dashboard — if you use that command, pass through its **full login URL including the token** per that command’s output).
   - Remind the operator **not to paste secret values into chat**; only the URL and UI instructions belong in the agent thread.
   - Remind the operator to **submit the form once** and close the browser tab when done: the CLI helper **stops the temporary localhost server** after a successful submit; if they walk away, **Ctrl+C** (or waiting for timeout) ends the wait.
   - **API Vector 2:** `POST /agent/sync` with `web: true` returns `web_url` and `web_session_id` — give the operator the **exact `web_url`**, poll `GET /agent/sync/web/{web_session_id}` until `done`, and treat the session id as sensitive correlation data. The API process may keep that localhost port open until restart; do not forward `web_url` beyond the trusted operator.
   - Poll/re-run `agent sync --json` until `pending_secrets` clears.

3. **Fully automated (Vector 3)**
   - Ensure provider auth is available (and optionally `SZ_AGENT=true`).
   - Run `secretzero agent sync --json`.
   - Handle `failed_secrets` with manifest fixes and retry.

## Agent runtime integration

When bootstrapping or restoring Hermes/OpenClaw installs:

```bash
secretzero agent list --format json
secretzero agent adopt --dry-run --format json
secretzero agent adopt --preseed-lockfile --format json
```

Load `skills/secretzero-agent-adopt/SKILL.md` for the full adopt/restore playbook. `agent backup` is an alias of `agent adopt` (not `secretzero backup create`).

## Standard Agent Loop

1. Run `secretzero agent sync --json` first; escalate to `--web` when you need the localhost form (see Vector 2 handoff above).
2. Parse status and `pending_secrets`/`failed_secrets`.
3. Execute the appropriate vector behavior.
4. Re-run command until both arrays are empty.
5. Continue downstream only after clean completion.

## API Parity

Use API when running remote orchestration:

- `POST /agent/sync` with `{ dry_run, web, lockfile?, sz_agent? }`
- For Vector 2 polling: `GET /agent/sync/web/{session_id}`

Treat API payload semantics the same as CLI semantics.

## Operational Playbooks

- **Agent adopt (Hermes/OpenClaw):** see `skills/secretzero-agent-adopt/SKILL.md` — `agent list` → `agent adopt` → `agent sync`
- **Bootstrap:** `validate` -> `init --install` -> `test` -> `agent sync --json`
- **Preflight:** `secretzero sync --dry-run` before mutating runs
- **Maintenance:** pair with `secretzero rotate`, `secretzero drift`, `secretzero status --format json`

## Common Failure Handling

- Missing extras/provider dependencies -> run install/`secretzero init --install`
- Auth missing/expired -> fix provider auth, re-run `secretzero test`
- Manual-seeded secret lacks instructions -> add `agent_instructions`, retry
- Variable interpolation issues -> check vars and `--var-file` usage

## Definition of Done

- Secret bootstrap/sync flow reaches no pending or failed secrets.
- Workflow used secure vector handling with no secret leakage.
- CLI/API behavior stays consistent for the selected scenario.
