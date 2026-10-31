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

## Target ids

Lockfile and `--force-target` ids include the object name, for example `azdo/azdo_variable_group/production-secrets`. A `provider/kind` prefix is enough when the secret has one target of that kind, and the trailing slash is optional:

```bash
secretzero sync -s database_password --force-target azdo/azdo_variable_group
```

`sync --plan` compares the manifest with the lockfile. It does not read the live variable group. `secretzero drift` and a real `sync` are the checks against Azure DevOps.

`secretzero rotate` treats a secret with `rotation_period` and no lockfile entry as due. A fresh clone does not exit 0 with "No secrets need rotation" for those secrets.

## Example

See `examples/azure-devops-complete.yml`.
