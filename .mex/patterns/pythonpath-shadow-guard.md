---
name: pythonpath-shadow-guard
description: Keep SecretZero's own site-packages ahead of caller-injected PYTHONPATH so bundled deps (especially pydantic) cannot be shadowed at import time.
last_updated: 2026-07-09
---

# PYTHONPATH shadow guard

## When to use
- Embedding SecretZero under another app/venv (Hermes, OpenClaw, IDE agents) that exports `PYTHONPATH`
- Debugging `ModuleNotFoundError: No module named pydantic_core._pydantic_core` on `import secretzero`
- Changing early import / bootstrap code in `src/secretzero/__init__.py`

## Pattern
1. Keep the sys.path reorder as the **first executable code** in `src/secretzero/__init__.py` (before any other imports that pull third-party packages).
2. Prefer `sysconfig.get_paths()['purelib']` over mutating or deleting the `PYTHONPATH` env var — callers may still need their paths for plugins/extensions.
3. Do **not** rely on `python -E` (ignores all env vars); that breaks legitimate caller configuration.
4. Regression: `tests/test_pythonpath_guard.py` spawns a subprocess with a decoy `pydantic` on `PYTHONPATH` and asserts `import secretzero` succeeds.

## Why
`PYTHONPATH` entries are prepended to `sys.path` before site-packages. If a foreign `pydantic` package (wrong ABI / missing `pydantic_core`) wins, import fails before SecretZero can run. Re-inserting our `purelib` at index 0 restores the interpreter's bundled deps without discarding the caller's path for later lookups.
