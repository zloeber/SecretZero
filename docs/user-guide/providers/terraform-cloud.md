# Terraform Cloud Provider

The `terraform_cloud` provider writes secrets to HCP Terraform (Terraform Cloud) and Terraform Enterprise. It can also read non-sensitive variables back.

Sensitive variables are write-only. The API returns `value: null` for them. SecretZero stores those values and does not read them back. `provider_read` works for non-sensitive variables only.

## Install

```bash
uv tool install "secretzero[terraform-cloud]"
```

## Authentication

```bash
export TFE_TOKEN=your_token
export TFE_ORGANIZATION=example-org
```

`TFE_HOSTNAME` selects Terraform Enterprise. The default hostname is `app.terraform.io`.

```yaml
providers:
  tfc:
    kind: terraform_cloud
    auth:
      kind: token
      config:
        token: ${TFE_TOKEN}
        organization: ${TFE_ORGANIZATION}
```

## Workspace variable

`category` is `env` or `terraform`. It defaults to `env`. `sensitive` defaults to true.

```yaml
secrets:
  - name: api_token
    kind: random_string
    config:
      length: 32
    targets:
      - provider: tfc
        kind: tfc_workspace_variable
        config:
          workspace: network-prod
          key: API_TOKEN
          category: env
```

A sensitive update sends only the new value. If `hcl` or `sensitive` does not match the variable that already exists, sync stops and asks you to delete that variable in Terraform Cloud. Sync does not delete it.

## Variable set

An existing variable set keeps its workspace, project, and global assignments. A missing set is created only when `create_set: true`.

```yaml
targets:
  - provider: tfc
    kind: tfc_varset_variable
    config:
      varset: shared-prod
      key: API_TOKEN
      category: env
      create_set: false
```

## Read a non-sensitive variable

```yaml
secrets:
  - name: log_level
    kind: static
    config:
      value: null
    source:
      kind: provider_read
      required: true
      config:
        provider: tfc
        kind: tfc_workspace_variable
        read:
          name: LOG_LEVEL
          workspace: network-prod
          category: env
    targets:
      - provider: local
        kind: file
        config:
          path: .env.local
          format: dotenv
          key: LOG_LEVEL
```

Reading a sensitive variable fails with `sensitive and write-only`.

See [workspace variables](https://developer.hashicorp.com/terraform/cloud-docs/api-docs/workspace-variables) and [variable sets](https://developer.hashicorp.com/terraform/cloud-docs/api-docs/variable-sets).

The example manifest is `examples/terraform-cloud.yml`.
