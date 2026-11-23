---
name: terraform-cloud-provider
description: HCP Terraform workspace variables and organization variable sets.
triggers:
  - "terraform cloud"
  - "hcp terraform"
  - "tfc_workspace_variable"
  - "tfc_varset_variable"
last_updated: 2026-11-21
---

# Terraform Cloud Provider

## Context

Built-in `terraform_cloud` bundle for HCP Terraform and Terraform Enterprise:

- Provider: `src/secretzero/providers/terraform_cloud.py`
- Client: `src/secretzero/providers/tfc_client.py`
- Targets: `src/secretzero/targets/terraform_cloud.py`
- Design: `docs/superpowers/specs/2026-11-21-terraform-cloud-provider-design.md`

Sensitive variables are write-only. `retrieve()` returns no value. `provider_read` raises when `value` is null.

## Steps

1. Register `_get_bundle_manifest()` in `pyproject.toml` and `_register_builtin_bundles()`.
2. Keep `import requests` inside `TfcClient._session_obj`.
3. Identity is key plus category. Sensitive updates PATCH `value` only.
4. Do not delete a variable when `hcl` or `sensitive` disagrees with the manifest.
5. Do not change assignments on an existing variable set.
6. Append new target-id keys to `SyncEngine._TARGET_ID_KEYS` instead of reordering existing keys.
7. Run `task schema:update` after `TargetKind` changes and `task docs:generate:provider-bundles`.

## Verify

- [ ] `pytest tests/test_tfc_client.py tests/test_terraform_cloud_provider.py tests/test_tfc_targets.py`
- [ ] `secretzero validate -f examples/terraform-cloud.yml`
- [ ] `docs/reference/provider-bundles-auto.md` lists `terraform_cloud`
