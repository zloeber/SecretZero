# Agent workflow (pre-push)

Run the following from the repository root **before pushing** branch commits to the remote (`git push`). Fix failures before you push; do not push a branch that still fails these checks.

## Pre-push checklist

Run in order:

```bash
task lint:fix && task format && task schema:update
task test
task security:scan
```

| Step | Command | Purpose |
|------|---------|---------|
| Lint (fix) | `task lint:fix` | Ruff auto-fixes |
| Format | `task format` | Ruff format and Black |
| Schema | `task schema:update` | Regenerates `Secretfile.schema.json` from `secretzero schema export` |
| Tests | `task test` | Full test suite (unit, integration, and anything else the task runs) |
| Security | `task security:scan` | Dependency audit (`pip-audit`) and Bandit on `src/` |

If **`schema:update`** or **`lint:fix`** changes files, commit those changes locally, then run the checklist again (at least `task test` and `task security:scan`) before pushing.

## Merge requests

After a clean pre-push run, push the branch and open or update the merge request. The steps above are what you should rely on before the remote sees your commits.

## Optional

- **`task test:validations`** — Validates example Secretfiles under `./examples` when your change might affect manifest validation.

## Notes

- Tasks assume `uv` and the project `.venv` as configured in `Taskfile.yml`.
- If `schema:update` produces no diff, there is nothing to commit for schema.
