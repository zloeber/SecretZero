# Terraform tfvars file target

Demonstrates `format: tfvars` on the local `file` target.

```bash
secretzero sync -f examples/terraform-tfvars/Secretfile.yml
terraform -chdir=examples/terraform-tfvars/terraform plan -var-file=terraform.tfvars
```

Keep `terraform.tfvars` gitignored; the lockfile stores hashes only.
