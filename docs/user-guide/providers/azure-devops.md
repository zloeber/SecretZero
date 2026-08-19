# Azure DevOps Provider

The `azure_devops` bundle targets **Azure DevOps Services** (`dev.azure.com`) only.

## Authentication

```yaml
providers:
  azdo:
    kind: azure_devops
    auth:
      kind: token
      config:
        token: ${AZDO_PAT}
        organization: myorg
```

Environment variables:

- `AZDO_PAT` (primary)
- `AZURE_DEVOPS_EXT_PAT` (fallback)
- `AZDO_ORGANIZATION`

## Targets

| Kind | Purpose |
|------|---------|
| `azdo_variable_group` | Library secret variables |
| `azdo_pipeline_variable` | Pipeline definition variables |
| `azdo_environment_variable` | Environment-scoped secrets |
| `azdo_secure_file` | Encrypted secure files |
| `azdo_keyvault_variable_group` | Key Vault–linked variable group name mapping |

## Generators

| Kind | Purpose |
|------|---------|
| `azdo_pat` | Mint automation PATs when org policy allows |

## Retrieve limitations

Azure DevOps does not return secret variable values via REST after write. `retrieve()` is metadata-only for secret targets.

## Example

See `examples/azure-devops-complete.yml`.
