---
name: stack
description: Technology stack, library choices, and the reasoning behind them. Load when working with specific technologies or making decisions about libraries and tools.
triggers:
  - "library"
  - "package"
  - "dependency"
  - "which tool"
  - "technology"
edges:
  - target: context/decisions.md
    condition: when the reasoning behind a tech choice is needed
  - target: context/conventions.md
    condition: when understanding how to use a technology in this codebase
  - target: context/setup.md
    condition: when command/tooling details are needed to run locally
last_updated: 2026-04-10
---

# Stack

## Core Technologies
- **Python 3.12+** — primary runtime, required by `pyproject.toml`.
- **Pydantic v2** — core model validation for config, lockfile, and schemas.
- **Click + Rich** — CLI command layer with rich terminal rendering.
- **YAML stack (`pyyaml`, `ruamel-yaml`)** — parse and maintain Secretfile formatting.
- **Task + uv** — project-standard task orchestration and dependency/runtime management.

## Key Libraries
- **`pydantic` (v2)** — canonical modeling/validation APIs; use `model_dump*` methods.
- **`click` (not Typer)** — existing command surface is Click-based in `cli.py`.
- **`rich` (not `print`)** — all user-facing terminal output should use Rich console/table APIs.
- **`pytest` + `pytest-cov`** — test suite and coverage baseline under `tests/`.
- **`ruff` + `black`** — lint and format toolchain with line length 100.
- **`importlib.metadata.entry_points`** — bundle discovery for third-party provider extensions.
- **Provider extras (`boto3`, `hvac`, `PyGithub`, etc.)** — loaded as optional extras by capability.

## What We Deliberately Do NOT Use
- No Pydantic v1 API style; v1 methods are intentionally excluded from conventions.
- No hard-coded provider dispatch logic in sync flows; registry indirection is required.
- No mandatory install of all provider SDKs; optional extras are preferred for lean environments.

## Version Constraints
- Python must be `>=3.12`.
- Ruff/Black use line length `100`.
- `secretzero-api` path depends on FastAPI/Uvicorn optional extras.
