---
name: security-scan-remediation
description: Reproduce and fix `task security:scan` failures, especially dependency audit drift and pre-commit enforcement.
triggers:
  - "security:scan"
  - "pip-audit"
  - "bandit"
  - "dependency vulnerability"
edges:
  - target: "context/setup.md"
    condition: "When scan failures may be caused by environment/bootstrap drift"
  - target: "patterns/add-cli-command.md"
    condition: "When security findings come from CLI behavior changes"
last_updated: 2026-06-05
---

# Security Scan Remediation

## Context
`task security:scan` is the canonical Python security gate for this repo. It must run against the locked dependency set, not whichever packages happen to be installed already, or `pip-audit` can report stale versions after the lockfile is updated.

## Steps
1. Reproduce with `task security:scan` before changing anything.
2. If `pip-audit` reports versions that disagree with `uv.lock`, compare the live environment (`uv run python` / `uv tree`) against the lockfile to confirm stale-install drift.
3. Update dependency floors in `pyproject.toml` and refresh `uv.lock` when the vulnerability is a real package issue.
4. Make `task security:scan` sync the frozen environment before running audit tools so standalone scans match CI/pre-commit behavior.
5. Keep the pre-commit gate wired to `task security:scan` rather than duplicating `pip-audit`/`bandit` commands by hand.
6. Re-run `task security:scan`, then run the fast pre-commit gate.

## Gotchas
- `uv tree` reflects the resolved lockfile; `uv run pip-audit` audits the currently installed environment. Those can diverge until `uv sync` runs.
- Fixing only `uv.lock` is not enough if the task does not bootstrap the environment first.
- If the pre-commit script shells out to raw audit commands instead of `task security:scan`, the two gates can drift again later.

## Verify
- `task security:scan` exits 0.
- `./scripts/agent.pre-commit.sh --mode fast --quiet` exits 0.
- `uv tree` and `uv run python` agree on the audited package versions for the vulnerable dependencies you changed.
- No new lints are introduced in task/shell files you touched.

## Debug
- If `pip-audit` still reports the old versions after a lock update, inspect installed package versions before and after `uv sync --frozen --all-extras`.
- If Bandit fails while `pip-audit` passes, fix or justify the reported source issue separately; do not treat them as one class of failure.
- If pre-commit still misses the scan, confirm the gate path calls `task security:scan` rather than stale inline commands.

## Update Scaffold
- [ ] Update `.mex/ROUTER.md` when security gate behavior changes
- [ ] Update `context/setup.md` if the recommended verification command flow changed
- [ ] Keep this pattern aligned with `Taskfile.yml` and `scripts/agent.pre-commit.sh`
