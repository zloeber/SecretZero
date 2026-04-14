# secretzero terraform

Generate Terraform manifests from a Secretfile.

## Synopsis

```bash
secretzero terraform [OPTIONS]
```

## Description

The `terraform` command translates your SecretZero `Secretfile.yml` into a
Terraform configuration. It uses bundle-provided Terraform metadata to
declare providers and maps supported generators/targets to Terraform
resources (for example AWS SSM Parameters and Secrets Manager secrets).

Generated configuration can be written as HCL2 (`.tf`) or Terraform JSON
(`.tf.json`) and then used with standard Terraform workflows (`terraform init`,
`terraform plan`, `terraform apply`).

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--file`, `-f` | path | `Secretfile.yml` | Path to Secretfile |
| `--var-file`, `-v` | path (repeatable) | – | `.szvar` variable file(s) to merge before export |
| `--output-dir`, `-o` | path | `terraform-out` | Directory to write generated Terraform files |
| `--format` | choice | `hcl` | Terraform output format: `hcl` or `json` |
| `--include-static-secrets/--no-include-static-secrets` | flag | `--no-include-static-secrets` | Whether to include default values for static-secret Terraform variables (not recommended for production) |
| `--dry-run` | flag | `false` | Show a summary of what would be generated without writing files |

## Supported mappings (initial)

The first version of `secretzero terraform` focuses on common patterns:

- **Generators**
  - `random_password` → `random_password` resource (hashicorp/random)
  - `random_string` → `random_string` resource (hashicorp/random)
  - `static` (and static-like bundle kinds) → sensitive Terraform variables
- **Targets**
  - `provider: aws`, `kind: ssm_parameter` → `aws_ssm_parameter`
  - `provider: aws`, `kind: secrets_manager` → `aws_secretsmanager_secret` + `aws_secretsmanager_secret_version`
  - `provider: azure`, `kind: azure_keyvault` / `key_vault` → `azurerm_key_vault_secret` (requires `azure_key_vault_id` variable)
  - `provider: vault`, `kind: vault_kv` / `kv` → `vault_kv_secret_v2`

Bundles that declare a `terraform_provider` field on their `BundleManifest`
automatically contribute **required_providers** entries and `provider` blocks.

Targets and generators without an explicit mapping are currently skipped;
they must be modeled manually in Terraform if needed.

## Examples

### 1. Dry run (no files written)

```bash
secretzero terraform --file Secretfile.yml --dry-run
```

Example output:

```text
Terraform generation plan (dry run)

  Secrets: 3
  Providers: 2
  Resources: 5

Required providers:
  • aws (source: hashicorp/aws) (version: ~> 5.0)
  • random (source: hashicorp/random) (version: ~> 3.0)

Use --format hcl|json and remove --dry-run to write Terraform files.
```

### 2. Generate HCL (.tf) configuration

```bash
secretzero terraform \
  --file Secretfile.yml \
  --output-dir terraform \
  --format hcl
```

This writes `terraform/main.tf` containing:

- `terraform.required_providers` block
- `provider` blocks for bundles that declare `terraform_provider`
- `resource` blocks for supported generators/targets

You can then run:

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

### 3. Generate Terraform JSON (.tf.json)

```bash
secretzero terraform \
  --file Secretfile.yml \
  --output-dir terraform-json \
  --format json
```

This writes `terraform-json/main.tf.json` with a JSON representation of
the same configuration, suitable for tooling that prefers JSON.

## Security considerations

- **Static secrets**: Terraform export now always creates sensitive input
  variables for static/static-like secrets. By default, these variables have
  no `default` value, so plaintext is not embedded in generated files.
  Enabling `--include-static-secrets` adds static defaults to those variables,
  which may embed sensitive values directly into version-controlled Terraform
  files and state; use with caution.
- **State files**: Secrets stored via Terraform-managed resources will
  typically appear in Terraform state. Use remote, encrypted state backends
  and restrict access appropriately.
- **Partial coverage**: Not all SecretZero generators/targets have
  Terraform equivalents. Review generated configuration and complement it
  with hand-written Terraform as needed.

## Related topics

- [Secretfile configuration](../configuration/secretfile.md)
- [Targets overview](../targets/index.md)
- [Bundle reference](../bundles/index.md)
- [Terraform Cloudflare deployment example](../../../terraform/README.md)

