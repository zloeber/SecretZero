---
name: setup
description: Dev environment setup and commands. Load when setting up the project for the first time or when environment issues arise.
triggers:
  - "setup"
  - "install"
  - "environment"
  - "getting started"
  - "how do I run"
  - "local development"
edges:
  - target: context/stack.md
    condition: when specific technology versions or library details are needed
  - target: context/architecture.md
    condition: when understanding how components connect during setup
  - target: patterns/debug-sync.md
    condition: when setup succeeds but sync/provider execution fails
last_updated: 2026-04-10
---

# Setup

## Prerequisites
- Python 3.12+.
- `uv` for dependency sync and command execution (project-default workflow).
- `task` CLI for standard lint/test/security/schema pipelines.
- Provider credentials/SDK prereqs for whichever provider bundles you use.

## First-time Setup
1. `git clone https://github.com/zloeber/SecretZero && cd ./SecretZero`
2. `uv sync --all-extras && source ./.venv/bin/activate`
3. `secretzero --version`
4. `task test`
5. `task security:scan`

## Environment Variables
- **Required by command context:** none globally required for local-only targets.
- **Conditionally required (provider use):** `VAULT_TOKEN`/`VAULT_ADDR`, AWS credential vars, `GITHUB_TOKEN`, `GITLAB_TOKEN`, `JENKINS_*`, `AZURE_*`, `KUBECONFIG`.
- **Secret fallback inputs:** uppercase secret names (for example `DB_PASSWORD`) can pre-seed generation fallback paths.
- **Optional app config override:** `SECRETZERO_CONFIG` to point at explicit `secretzero.yml`.

## Common Commands
- `secretzero validate -f Secretfile.yml` — schema/config validation.
- `secretzero render -f Secretfile.yml` — inspect interpolated config.
- `secretzero sync --dry-run` — preview storage actions.
- `secretzero sync` — perform generation/sync and update lockfile.
- `task lint:fix && task format && task schema:update` — local quality + schema maintenance.
- `task test && task security:scan && task test:validations` — full verification pipeline.

## Common Issues
**Unknown generator/target/provider kind:** ensure bundle registration path exists and provider extras are installed.  
**No accessible targets during sync:** authenticate provider credentials and rerun `secretzero sync --dry-run`.  
**Interpolation surprises:** run `secretzero render` and fix variable typos or wrong var-file merge assumptions.  
**Lockfile mismatch after config edits:** rerun `secretzero sync`; use forced rotation only when regeneration is intended.
