---
name: deps-upgrade
description: Repeatable dependency upgrade workflow — lock refresh, pyproject floor sync, and full QA gate.
triggers:
  - "deps:upgrade"
  - "sync_pyproject_dep_floors"
  - "dependency upgrade"
  - "bump dependencies"
edges:
  - target: "patterns/security-scan-remediation.md"
    condition: "When pip-audit fails after an upgrade"
last_updated: 2026-06-16
---

# Dependency Upgrade Workflow

## Context

Direct dependency floors live in `pyproject.toml` (`[project.dependencies]`, optional extras, and `[tool.uv.override-dependencies]`). Resolved versions live in `uv.lock`. Security scans (`pip-audit`) audit the **installed** environment, so upgrades must refresh the lockfile, sync floors, and re-run QA.

`tool.uv.exclude-newer = "7 days"` limits how fresh packages can be unless listed in `exclude-newer-package` overrides.

## Repeatable commands

| Task | Purpose |
|------|---------|
| `task deps:sync-floors` | Align `pyproject.toml` `>=` floors with `uv.lock` (no network) |
| `task deps:upgrade` | `uv lock --upgrade` → sync floors → upgrade again → `uv sync --all-extras` |
| `task deps:upgrade:verify` | `deps:upgrade` then `./scripts/agent.pre-commit.sh --mode full` |

Script: `scripts/sync_pyproject_dep_floors.py` (`--dry-run`, `--check`).

## Steps

1. Run `task deps:upgrade:verify` before merging dependency work (or monthly maintenance).
2. If `pip-audit` reports CVEs, bump floors manually when fix releases are newer than `exclude-newer` allows — add the package to `exclude-newer-package` overrides if needed (see `security-scan-remediation.md`).
3. Commit `pyproject.toml` and `uv.lock` together.

## Gotchas

- Floors only update the `>=` portion of a spec; trailing constraints (for example `pytest>=9.0.3,<9.1`) are preserved.
- **Tavern + pytest:** Prefer keeping the documented upper bound in `pytest` floors. After Tavern 3.6.1+, pytest 9.1.x collection works; re-check e2e collect/run if either package jumps major.
- Local/path dependencies are skipped (not in `uv.lock` as PyPI names).
- `pip-audit` may skip auditing `secretzero` itself (local editable install) — expected.

## Verify

- `task security:scan` exits 0
- `task test` passes
- `./scripts/agent.pre-commit.sh --mode full --quiet` exits 0
