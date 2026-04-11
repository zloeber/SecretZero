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
    condition: when adding new providers, generators, or targets
  - target: patterns/debug-sync.md
    condition: when tracing where sync failures happen in the pipeline
last_updated: 2026-04-10
---

# Architecture

## System Overview
`Secretfile.yml` (+ optional `--var-file` `.szvar` files) is loaded by `ConfigLoader` and interpolated.
The loaded config is validated into a `Secretfile` Pydantic model.
`SyncEngine` initializes `BundleRegistry`, loads providers, and validates target access.
Each secret is resolved by generator kind through `BundleRegistry`, then generated via `generate_with_fallback()`.
Generated values are stored into target kinds (`file`, `template`, cloud targets) via registry lookups.
`Lockfile` (`.gitsecrets.lock`) records only hash/provenance metadata and sync state.
Template targets collect values during sync and render in a deferred final pass.
`status`, `check`, `drift`, and `terraform` commands consume config + lockfile state for reporting/export.

## Key Components
- **`ConfigLoader` (`src/secretzero/config.py`)** — loads/merges YAML and interpolates variables; depends on `pyyaml` and Jinja2.
- **`SyncEngine` (`src/secretzero/sync.py`)** — orchestrates generation, storage, partial sync retrieval, and template rendering; depends on `BundleRegistry` and `Lockfile`.
- **`BundleRegistry` (`src/secretzero/bundles/registry.py`)** — central dispatch map for providers/generators/targets and entry-point bundle discovery.
- **`Lockfile` (`src/secretzero/lockfile.py`)** — tracks per-secret hashes, target provenance, and change metadata without storing values.
- **CLI (`src/secretzero/cli.py`)** — command surface (`validate`, `sync`, `status`, `check`, `drift`, `terraform`, etc.) for daily operations.

## External Dependencies
- **AWS (`boto3`)** — supports SSM parameter + Secrets Manager providers/targets.
- **Vault (`hvac`)** — supports token-auth secret retrieval/storage in Vault KV.
- **Azure (`azure-identity`, `azure-keyvault-secrets`)** — supports Azure Key Vault target/provider paths.
- **GitHub/GitLab/Jenkins/Kubernetes SDKs** — provider-specific targets for CI/CD and cluster secret delivery.
- **FastAPI/Uvicorn** — optional `secretzero-api` service layer for programmatic operations.

## What Does NOT Exist Here
- No plaintext secret persistence in lockfile or docs artifacts.
- No scheduler/daemon for automatic rotation; rotation is operator-driven (`sync --force-rotation`).
- No browser UI; API is optional, but project is centered on CLI workflows.
- No provider-specific branching in `SyncEngine`; dispatch is registry-driven.
