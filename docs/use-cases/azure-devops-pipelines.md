# Azure DevOps Pipelines

Use SecretZero to manage Azure DevOps Services Library secrets and related pipeline assets from a declarative `Secretfile.yml`.

## Prerequisites

```bash
pip install secretzero[azure-devops]
# or
pip install secretzero[cicd]
```

```bash
export AZDO_PAT=...
export AZDO_ORGANIZATION=myorg   # optional if set in provider config
```

Required PAT scopes typically include Variable Groups (Read/Create/Manage). Secure files, environments, and pipeline variables need their corresponding scopes.

## Minimal Secretfile

```yaml
variables:
  azdo_project: auto

providers:
  azdo:
    kind: azure_devops
    auth:
      kind: token
      config:
        token: ${AZDO_PAT}
        organization: myorg

secrets:
  - name: database_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: azdo
        kind: azdo_variable_group
        config:
          project: auto
          variable_group: production-secrets
          variable_name: DATABASE_PASSWORD
          is_secret: true
          create_if_missing: true
```

## Cross-provider deploy token

Mint a GitLab group service account once and sync the PAT into Azure DevOps:

```yaml
secrets:
  - name: shared_deploy_token
    kind: gitlab_group_service_account
    config:
      provider: gitlab
      group: auto
      service_account_name: secretzero-deploy-bot
      token_name: deploy-token
      scopes: [read_repository, write_repository]
    targets:
      - provider: gitlab
        kind: gitlab_group_variable
        config:
          group: auto
          masked: true
          value_field: token
      - provider: azdo
        kind: azdo_variable_group
        config:
          project: auto
          variable_group: production-secrets
          variable_name: GITLAB_DEPLOY_TOKEN
          is_secret: true
          value_field: token
```

See `examples/azure-devops-complete.yml` and `examples/multi-cicd.yml`.

## Retrieve limitations

Azure DevOps does not return secret variable values via REST after write. Drift and import rely on metadata (existence / secret flags), not plaintext comparison.

## Related

- [Azure DevOps provider](../user-guide/providers/azure-devops.md)
- [Gated live validations](../user-guide/cli/test.md#gated-live-validations)
