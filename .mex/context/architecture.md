---
name: architecture
description: How the major pieces of this project connect and flow. Load when working on system design, integrations, or understanding how components interact.
triggers:
  - "architecture"
  - "system design"
  - "how does X connect to Y"
  - "integration"
  - "flow"
edges:
  - target: context/stack.md
    condition: when specific technology details are needed
  - target: context/decisions.md
    condition: when understanding why the architecture is structured this way
  - target: patterns/add-bundle.md
    condition: when adding a new provider, generator, or target to the system
  - target: patterns/debug-sync.md
    condition: when a sync failure occurs and the flow needs to be traced
last_updated: 2026-04-09
---

# Architecture

## System Overview

User writes `Secretfile.yml` (+ optional `.szvar` override files) →
`ConfigLoader` reads YAML, merges `.szvar` variables, applies Jinja2 + shell-style
interpolation (`{{var.name}}` / `${VAR_NAME}`), validates against the `Secretfile`
Pydantic model →
`SyncEngine` initialises by loading `BundleRegistry` (singleton, entry_points-discovered)
and the on-disk `Lockfile` (`.gitsecrets.lock`) →
For each `Secret`, `SyncEngine` looks up the generator kind in `BundleRegistry`,
instantiates it, calls `generate_with_fallback(env_var_name)` (env var checked first) →
Generated value is dispatched to each configured `Target` via `BundleRegistry` target
class lookup; provider authentication happens lazily per target →
`Lockfile` records SHA-256 hash, timestamps, per-target provenance; saved as `.gitsecrets.lock` →
Template secrets (`kind: templates.<name>`) expand to multiple field sub-secrets, each
with independent generators and targets →
`PolicyEngine` validates rotation/compliance/access rules on `check` / `status` commands.

## Key Components

- **ConfigLoader** (`src/secretzero/config.py`) — loads Secretfile.yml + `.szvar` files, deep-merges variables, applies Jinja2 + shell-style interpolation, validates via Pydantic. Entry point for all config.
- **BundleRegistry** (`src/secretzero/bundles/registry.py`) — singleton mapping kind strings (`"aws"`, `"random_password"`, `"vault_kv"`) to generator/target/provider classes. Auto-discovered from Python `entry_points` under group `"secretzero.providers"`. All built-in providers register via `_get_bundle_manifest()` factory in each provider module.
- **SyncEngine** (`src/secretzero/sync.py`) — orchestrates all sync operations: validates provider connectivity, generates secrets, stores in targets, updates the lockfile. Template rendering is deferred until all secrets are synced.
- **Lockfile** (`src/secretzero/lockfile.py`) — Pydantic model tracking SHA-256 hashes (never plaintext values), creation/update timestamps, rotation count, and per-target provenance (last 3 updates per target). Serialised to `.gitsecrets.lock`.
- **BaseProvider** + built-in providers (`src/secretzero/providers/`) — AWS, Azure, Vault, GitHub, GitLab, Jenkins, Kubernetes, AnsibleVault, Infisical. Each exposes `test_connection()`, `authenticate()`, capability methods prefixed `generate_`/`retrieve_`/`store_`/`rotate_`/`delete_`.
- **BaseGenerator** + built-in generators (`src/secretzero/generators/`) — `random_password`, `random_string`, `static`, `script`, `provider_backed`, `github_pat`. All subclass `BaseGenerator` and must implement `generate()`.
- **BaseTarget** + built-in targets (`src/secretzero/targets/`) — `file`, `template` (built-in); `ssm_parameter`, `secrets_manager`, `vault_kv`, `azure_keyvault`, `kubernetes_secret`, `github_secret`, `gitlab_variable`, `jenkins_credential` (registered via BundleManifests). All subclass `BaseTarget` and must implement `store()` and `retrieve()`.
- **PolicyEngine** (`src/secretzero/policy.py`) — validates `RotationPolicy`, `CompliancePolicy`, `AccessPolicy` rules defined in the `policies:` block of Secretfile.yml.
- **CLI** (`src/secretzero/cli.py`) — Click-based CLI entry point (`secretzero`). Key commands: `create`, `init`, `validate`, `render`, `sync`, `status`, `check`, `rotate`, `drift`, `graph`, `format`, `terraform`, `providers`.
- **REST API** (`src/secretzero/api/`) — optional FastAPI server (`secretzero-api` entry point); provides programmatic access to sync/status operations.

## External Dependencies

- **HashiCorp Vault** (via `hvac`, optional extra `vault`) — KV v1/v2 secret storage; `VaultKVTarget` uses `vault_kv` kind.
- **AWS SSM + Secrets Manager** (via `boto3`, optional extra `aws`) — parameter store (`ssm_parameter`) and secrets manager (`secrets_manager`) targets.
- **Azure Key Vault** (via `azure-identity` + `azure-keyvault-secrets`, optional extra `azure`) — `azure_keyvault` target.
- **GitHub** (via `PyGithub` + `PyNaCl`, optional extra `github`) — `github_secret` target and `github_pat` generator.
- **GitLab / Jenkins / Kubernetes** (optional extras `gitlab`, `jenkins`, `kubernetes`) — CI/CD secret targets.
- **Infisical** (via `httpx`, optional extra `infisical`) — hosted secrets manager provider.
- **Python entry_points** (`importlib.metadata`) — third-party bundle discovery at startup.

## What Does NOT Exist Here

- No background job processing — all operations are on-demand CLI or API calls; no daemons or schedulers.
- No secret value storage in the lockfile or anywhere on disk — only SHA-256 hashes are persisted; plain values live only in memory during a sync run.
- No web UI — the `secretzero-api` FastAPI server is a REST interface for programmatic/agent use, not a browser UI.
- No provider hard-coding — `SyncEngine` never has `if provider == "aws"` branches; everything routes through `BundleRegistry`.
