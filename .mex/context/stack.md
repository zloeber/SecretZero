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
  - target: context/architecture.md
    condition: when understanding how stack components fit together
last_updated: 2026-04-09
---

# Stack

## Core Technologies

- **Python 3.12+** — primary language; 3.12 minimum is hard-enforced in `pyproject.toml`
- **Pydantic v2** (`>=2.0.0`) — data validation and models used everywhere; all config, lockfile, and API schema models subclass `pydantic.BaseModel`
- **Click 8+** — CLI framework; all commands registered on the `main` Click group in `cli.py`
- **Rich 13+** — terminal output; all `console.print()` calls go through a `rich.console.Console` instance, tables via `rich.table.Table`
- **PyYAML + ruamel-yaml** — YAML parsing (`pyyaml` for read-only; `ruamel-yaml` for format-preserving writes)
- **Jinja2** — variable interpolation in Secretfiles (`{{var.name}}` style); `StrictUndefined` used in the loader

## Key Libraries

- **pydantic v2** (not v1) — use `model_dump()` not `.dict()`, `model_dump_json()` not `.json()`. The lockfile, all config models, and API schemas all use Pydantic v2 APIs.
- **click** (not argparse or typer) — all CLI commands go in `cli.py`, attached to the `main` group; use `@click.pass_context` when needing global flags like `--non-interactive`
- **rich** (not plain `print`) — all user-facing output uses `Console.print()` with markup; structured output uses `rich.table.Table`
- **importlib.metadata entry_points** (not stevedore directly) — bundle discovery at startup via group `"secretzero.providers"`; see `BundleRegistry.discover_and_register()`
- **pytest + pytest-cov** (not unittest) — all tests use pytest style; config in `pyproject.toml` under `[tool.pytest.ini_options]`, `pythonpath = ["src"]`
- **ruff + black** (both configured) — linting via ruff, formatting via black; **line-length = 100** for both
- **setuptools-scm** — version derived from git tags; written to `src/secretzero/_version.py`

## Provider Optional Extras

Provider-specific packages are optional extras declared in `pyproject.toml`:
- `secretzero[aws]` → `boto3`
- `secretzero[vault]` → `hvac`
- `secretzero[github]` → `PyGithub`, `PyNaCl`
- `secretzero[gitlab]` → `python-gitlab`
- `secretzero[jenkins]` → `python-jenkins`
- `secretzero[kubernetes]` → `kubernetes`
- `secretzero[azure]` → `azure-identity`, `azure-keyvault-secrets`
- `secretzero[infisical]` → `httpx`
- `secretzero[api]` → `fastapi`, `uvicorn`
- `secretzero[ai]` → `langchain-core`, `langgraph`, `langchain-anthropic`, etc.
- `secretzero[dev]` → `pytest`, `black`, `ruff`, `mypy`, etc.

## What We Deliberately Do NOT Use

- **No raw if/elif provider chains** — never add `if provider_kind == "aws": ...` in `SyncEngine`; all dispatch goes through `BundleRegistry`.
- **No plaintext secret storage** — never log, write, or cache secret values; only SHA-256 hashes go into the lockfile.
- **No synchronous database/ORM** — the only persistence is the JSON lockfile (`.gitsecrets.lock`) and Secretfile.yml on disk.
- **No class-level state in generators/targets** — each generator and target is instantiated fresh per secret; do not share state between calls.

## Version Constraints

- Python 3.12+ required — `match` statements, newer `typing` features used throughout.
- Pydantic v2 only — `BaseModel.model_dump()`, `BaseModel.model_dump_json()`, `Field()` semantics are v2. Pydantic v1 compatibility shims are NOT present.
- `uv` is the recommended package manager (see `[tool.uv]` in `pyproject.toml`); `pip` also works.
