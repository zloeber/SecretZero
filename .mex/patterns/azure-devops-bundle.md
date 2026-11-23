---
name: azure-devops-bundle
description: Azure DevOps Services provider bundle for pipeline library secrets.
triggers:
  - "azure devops"
  - "azdo_variable_group"
  - "azdo_pat"
last_updated: 2026-11-20
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
5. Target ids include `variable_group`, `pipeline`, `environment`, `file_name`, or `vault_name`. Keep the empty `provider/kind/` alias only when that kind appears once, so older lockfiles stay tracked.
6. Variable group **writes** (`azdo_variable_group` upsert and `azdo_keyvault_variable_group` create) use `AzdoClient.organization_url()`. List/get by `groupName` stays on `project_url()`. A project-scoped `PUT`/`POST` returns HTTP 400: "Project information name is not valid for variable group."
7. That same 400 also happens on an organization-scoped `PUT` when the project-scoped GET returned `variableGroupProjectReferences: null` (typical for groups created outside SecretZero). `upsert_variable_group_secret()` fills a single reference for `project` only when the field is missing or empty, and leaves an existing list unchanged so multi-project groups stay shared.
8. `AzureDevOpsProvider.provider_kind` must stay a `@property`. `BaseProvider.get_actor_info()` stores `self.provider_kind` in lockfile provenance; a plain method makes `Lockfile.model_dump(mode="json")` fail with `Unable to serialize unknown type: <class 'method'>` after a successful store.

## Verify

- [ ] `pytest tests/test_azdo_*.py` passes
- [ ] Bundle lists all five target kinds + `azdo_pat`
- [ ] `examples/azure-devops-complete.yml` validates
