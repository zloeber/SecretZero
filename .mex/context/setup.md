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
    condition: when a sync or provider error occurs during setup or first run
last_updated: 2026-04-09
---

# Setup

## Prerequisites

- **Python 3.12+** — hard-enforced in `pyproject.toml`; 3.11 and earlier will not work
- **uv** (recommended) or **pip** — `uv` is configured in `pyproject.toml [tool.uv]`
- **git** — version is derived from git tags via `setuptools-scm`
- Provider-specific CLIs as needed (e.g., `aws` CLI for ambient AWS auth, `vault` CLI for Vault token)

## First-time Setup

1. `git clone https://github.com/zloeber/SecretZero && cd SecretZero`
2. `pip install -e .[dev]` — installs the package + all dev dependencies (pytest, ruff, black, mypy)
3. To use a specific provider, also install its extra: `pip install -e .[aws]`, `pip install -e .[vault]`, etc.
4. `secretzero --version` — verify the CLI is installed and working
5. `pytest` — run the full test suite to confirm the environment is healthy

## Environment Variables

**Provider authentication (required when using that provider):**
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_REGION` — AWS ambient auth
- `VAULT_TOKEN` / `VAULT_ADDR` — HashiCorp Vault token auth
- `GITHUB_TOKEN` — GitHub personal access token
- `GITLAB_TOKEN` / `GITLAB_URL` — GitLab token
- `JENKINS_URL` / `JENKINS_USER` / `JENKINS_TOKEN` — Jenkins credentials
- `KUBECONFIG` — Kubernetes config path (ambient auth)
- `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET` / `AZURE_TENANT_ID` — Azure service principal

**Secret fallback (optional per secret):**
- `<SECRET_NAME_UPPERCASE>` — any secret can be seeded via its uppercased name before generation runs (e.g., secret named `db_password` → env var `DB_PASSWORD`)
- Template fields: `<SECRET_NAME_UPPER>_<FIELD_NAME_UPPER>` (e.g., `APP_CREDS_PASSWORD`)

**App configuration (optional):**
- `SECRETZERO_CONFIG` — absolute path to `secretzero.yml` app config, overrides `./secretzero.yml` and `~/.config/secretzero/secretzero.yml`

## Common Commands

- `secretzero create` — scaffold a new `Secretfile.yml` in the current directory
- `secretzero validate -f Secretfile.yml` — validate config structure without generating anything
- `secretzero render` — show the final interpolated config (useful for debugging variables)
- `secretzero sync --dry-run` — show what would be generated/stored without making changes
- `secretzero sync` — generate secrets and store them in configured targets; creates/updates `.gitsecrets.lock`
- `secretzero sync --force-rotation` — regenerate all secrets regardless of lockfile state
- `secretzero sync --name db_password` — sync only the named secret(s)
- `secretzero status` — show lockfile state and rotation due dates
- `secretzero check` — run all policy checks (rotation age, compliance, access)
- `secretzero providers` — list all available providers and their configuration
- `pytest` — run the full test suite
- `ruff check src/` — lint the source
- `black src/` — format the source

## Common Issues

**`ImportError: No module named 'boto3'` during sync:**
The AWS provider's optional dependency is not installed. Run `pip install secretzero[aws]`. The same pattern applies to other providers — check `BaseProvider.required_package` in each provider module for the exact install name.

**`ValueError: Unknown generator kind: 'my_kind'`:**
The generator kind is not registered in `BundleRegistry`. Either the provider package is not installed, its `entry_point` is not registered, or it was not added to `_register_builtin_bundles()` in `bundles/registry.py`. Run `secretzero providers --bundles` to see what is registered.

**`RuntimeError: Cannot sync secrets: No accessible targets found`:**
`SyncEngine` tests provider connectivity before generating any secrets. Check provider auth env vars are set and the provider service is reachable. Use `secretzero validate` first, then `secretzero sync --dry-run` to isolate.

**Lockfile out of sync with Secretfile:**
`secretzero status` will show `secretfile_changed: true` if `Secretfile.yml` content changed since the last sync. Run `secretzero sync` to refresh. For a full reset: delete `.gitsecrets.lock` and re-run `secretzero sync`.

**Variable interpolation silently empty:**
Jinja2 uses `SilentUndefined` — a typo in `{{var.nane}}` produces an empty string, not an error. Use `secretzero render` to inspect the fully-interpolated configuration before syncing.
