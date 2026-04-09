# Agent workflow (pre-push)

Run the following from the repository root **before pushing** branch commits to the remote (`git push`). Fix failures before you push; do not push a branch that still fails these checks.

## Pre-push checklist

Before pushing any commits run the following in order and fix any errors that emerge:

```bash
task lint:fix && task format && task schema:update
task test
task security:scan
task test:validations
```

| Step | Command | Purpose |
|------|---------|---------|
| Lint (fix) | `task lint:fix` | Ruff auto-fixes |
| Format | `task format` | Ruff format and Black |
| Schema | `task schema:update` | Regenerates `Secretfile.schema.json` from `secretzero schema export` |
| Tests | `task test` | Full test suite (unit, integration, and anything else the task runs) |
| Security | `task security:scan` | Dependency audit (`pip-audit`) and Bandit on `src/` |
| Integration Tests | `task test:validations` | Validates example Secretfiles under `./examples` |

If **`schema:update`** or **`lint:fix`** changes files, commit those changes locally, then run the checklist again (at least `task test` and `task security:scan`) before pushing.

## Merge requests

After a clean pre-push run, push the branch and open or update the merge request. The steps above are what you should rely on before the remote sees your commits.

## Notes

- Tasks assume `uv` and the project `.venv` as configured in `Taskfile.yml`.
- If `schema:update` produces no diff, there is nothing to commit for schema.

## After Every Task
After completing any task: update `.mex/ROUTER.md` project state and any `.mex/` files that are now out of date. If no pattern existed for the task you just completed, create one in `.mex/patterns/`.

## Navigation
At the start of every session, read `.mex/ROUTER.md` before doing anything else.
For full project context, patterns, and task guidance — everything is there.
