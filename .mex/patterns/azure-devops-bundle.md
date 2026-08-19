---
name: azure-devops-bundle
description: Azure DevOps Services provider bundle for pipeline library secrets.
triggers:
  - "azure devops"
  - "azdo_variable_group"
  - "azdo_pat"
last_updated: 2026-08-19
---

# Azure DevOps Bundle

## Context

Built-in `azure_devops` bundle (separate from `azure` Key Vault):

- Provider: `src/secretzero/providers/azure_devops.py`
- Client: `src/secretzero/providers/azdo_client.py`
- Targets: `src/secretzero/targets/azure_devops.py`
- Generator: `src/secretzero/generators/azdo_pat.py`

Services-only (`dev.azure.com`). Reject on-prem `server`/`collection` config.

## Steps

1. Register via `_get_bundle_manifest()` and `pyproject.toml` entry point.
2. Use helper modules (`azdo_variable_groups.py`, etc.) from targets — no SyncEngine branching.
3. Secret variables: never log plaintext; retrieve returns `None` for `is_secret: true`.
4. Run `task schema:update` after enum changes.

## Verify

- [ ] `pytest tests/test_azdo_*.py` passes
- [ ] Bundle lists all five target kinds + `azdo_pat`
- [ ] `examples/azure-devops-complete.yml` validates
