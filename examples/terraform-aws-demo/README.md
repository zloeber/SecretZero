# Terraform AWS Demo

Minimal example showing how to use `secretzero terraform` with AWS targets.

## Prerequisites

- SecretZero installed (`secretzero` CLI available)
- Terraform installed (`terraform` command available)
- AWS credentials suitable for managing SSM Parameters / Secrets Manager

## Example Secretfile

This project reuses the repository's `Secretfile.test.yml`, which targets
AWS SSM Parameter Store and Secrets Manager (using LocalStack-friendly
endpoints by default).

## Steps

1. From the repository root, generate Terraform configuration:

   ```bash
   secretzero terraform \
     --file Secretfile.test.yml \
     --output-dir examples/terraform-aws-demo/terraform \
     --format hcl
   ```

2. Change into the Terraform directory:

   ```bash
   cd examples/terraform-aws-demo/terraform
   ```

3. Initialize and review the plan:

   ```bash
   terraform init
   terraform plan
   ```

4. Apply when ready:

   ```bash
   terraform apply
   ```

The generated configuration will create `random_*` resources for your
secrets and provision them into AWS SSM Parameter Store / Secrets Manager
according to the targets defined in `Secretfile.test.yml`.

