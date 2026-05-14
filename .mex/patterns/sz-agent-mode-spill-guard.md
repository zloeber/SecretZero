---
name: sz-agent-mode-spill-guard
description: SZ_AGENT_MODE / spill_guard_active CLI behavior, ingest preseed, manifest plaintext validation.
---

# SZ_AGENT_MODE spill guards

## When to use

- Adding or changing commands that emit manifest content, variables, Terraform static defaults, backup plaintext, or `get --reveal`.
- Documenting agent-safe workflows for `.env` / local file targets.

## Core behavior

- `src/secretzero/agent_context.py` — `env_sz_agent_mode()`, `spill_guard_active()` (SZ_AGENT **or** SZ_AGENT_MODE).
- `src/secretzero/manifest_plaintext.py` — strict static-like literal detection for `validate` / CI.
- `secretzero ingest preseed` — lockfile import scoped to secrets whose `local/file` path matches `--source`.

## Verify

- `uv run pytest tests/test_cli_features.py::test_validate_sz_agent_mode_rejects_manifest_plaintext tests/test_manifest_plaintext.py tests/test_ingest_preseed.py tests/test_agent_context.py`
