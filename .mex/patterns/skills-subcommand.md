---
name: skills-subcommand
description: Implement or extend the secretzero skills CLI for bundled agent skill install.
last_updated: 2026-06-11
---

# Skills subcommand

## What it does

`secretzero skills` installs bundled agent skills from package data into supported IDE/agent skill directories (parity with metagit-cli `skills`).

Commands:

- `secretzero skills list` — bundled skill names
- `secretzero skills show [name]` — print `SKILL.md`
- `secretzero skills install` — copy skills to detected or explicit targets

## Source layout

- Authoring: repo-root `skills/<name>/SKILL.md` (public skills only)
- Package data: `src/secretzero/data/skills/` (sync from `skills/` when adding or updating bundled skills)
- Installer: `src/secretzero/skills/installer.py`
- CLI: `src/secretzero/cli_skills.py`

## Packaging

`pyproject.toml` includes `[tool.setuptools.package-data] secretzero = ["data/**/*"]`.

Run `task skills:sync` (or `uv run python scripts/sync_bundled_skills.py`) before building wheels. `task cli:build` and CI `build-tests` run sync automatically and assert the wheel contains `data/skills/`.

**Do not** ignore `src/secretzero/data/` in `.gitignore` — only root-level `/data/` is ignored so package data is committed and published wheels include bundled skills.

`DATA_PATH` in `secretzero.__init__` resolves bundled skills; override with `SECRETZERO_SKILLS_SOURCE_ROOT` for tests.

## Adding a new bundled skill

1. Add `skills/<new-skill>/SKILL.md` at repo root.
2. Copy into `src/secretzero/data/skills/<new-skill>/`.
3. Update `scripts/download-secretzero-skills.zsh` if the skill should be in the remote download set.
4. Extend tests in `tests/test_skills_installer.py` / `tests/test_cli_skills.py` if behavior changes.

## Tests

```bash
uv run python -m pytest tests/test_skills_installer.py tests/test_cli_skills.py -q
```
