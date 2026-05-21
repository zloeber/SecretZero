---
name: file-target-tfvars
description: Local file target tfvars format — HCL assignment read/write for Terraform var files
edges:
  - target: ../../src/secretzero/hcl_tfvars.py
  - target: ../../src/secretzero/targets/file.py
last_updated: 2026-05-21
---

# File target `tfvars` format

Use when changing Terraform `.tfvars` support on the local `file` target.

## Scope (v1)

- Flat top-level assignments: `name = "string"`.
- Modules: `hcl_tfvars.py` (parse/format), `hcl_values.py` (quoted literals; shared with `terraform_export`).
- No nested HCL, heredocs, or comment preservation on rewrite.

## Touch points

| Change | Files |
|--------|--------|
| Parser/formatter | `src/secretzero/hcl_tfvars.py` |
| Target dispatch | `src/secretzero/targets/file.py` |
| File source suffix | `src/secretzero/sync.py` (`.tfvars` / `.tfvars.json`) |
| Enum | `FileFormat.TFVARS` in `models.py` |
| Tests | `tests/test_tfvars_file_target.py` |
| Docs | `docs/user-guide/targets/file.md`, `local.md` |

## Manifest

```yaml
config:
  path: terraform/terraform.tfvars
  format: tfvars   # optional when path ends with .tfvars
  merge: true
  key: terraform_variable_name
```

JSON var files: `format: json` + `*.tfvars.json`.
