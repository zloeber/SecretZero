---
name: optional-extra-import-guards
description: Keep extras-only SDKs out of module-level imports so bare installs can load the CLI.
triggers:
  - "ModuleNotFoundError gitlab"
  - "optional extra"
  - "python-gitlab"
  - "bare pip install"
edges:
  - target: patterns/mcp-server.md
    condition: when optional MCP SDK majors also need dual-path resolution
last_updated: 2026-08-21
---

# Optional Extra Import Guards

## Context
Heavy SDKs (`python-gitlab`, `boto3`, etc.) live behind extras. A single unguarded top-level `import` in a module pulled by `secretzero.cli` makes that extra mandatory for every command, including `--version`.

## Steps
1. Prefer deferred `import` inside the functions/methods that need the SDK (or a tiny `_require_*()` helper).
2. Mirror existing provider patterns (`providers/gitlab.py` already guards `import gitlab`).
3. Add a regression that simulates a missing extra (`sys.modules["pkg"] = None`) and asserts the module / `secretzero.cli` still imports.
4. For dual-major optional packages (for example `mcp` 1.x vs 2.x), resolve the API via try/except and widen the extra floor instead of forcing one major.

## Gotchas
- Dev environments with `--all-extras` hide this class of regression — always test a bare editable install.
- Exception types from optional SDKs (`gitlab.exceptions.*`) also require the deferred import before `except` clauses.

## Verify
- [ ] `python -c "import secretzero.cli"` in a venv with no extras
- [ ] Focused unit tests for the previously unguarded module
- [ ] `./scripts/agent.pre-commit.sh --mode fast --quiet`
