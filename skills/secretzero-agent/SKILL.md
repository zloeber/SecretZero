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

- Never request, receive, or print plaintext secret values.
- Prefer JSON output for machine handling.
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
   - Run `secretzero agent sync --web`.
   - Direct user to localhost form.
   - Instruct user not to paste secrets into chat.
   - Poll/re-run until `pending_secrets` clears.

3. **Fully automated (Vector 3)**
   - Ensure provider auth is available (and optionally `SZ_AGENT=true`).
   - Run `secretzero agent sync --json`.
   - Handle `failed_secrets` with manifest fixes and retry.

## Standard Agent Loop

1. Run `secretzero agent sync --json` (or `--web`).
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
