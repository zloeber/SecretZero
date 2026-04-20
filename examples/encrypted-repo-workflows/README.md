# Encrypted Repo Workflows Example

This example shows one SecretZero manifest writing the same secrets to three encrypted-in-git backends:

- Ansible Vault (`ansible_vault_file`)
- SOPS (`sops_file`)
- git-crypt (`git_crypt_file`)

It also uses lane-specific `.szvar` files (`dev`, `staging`, `prod`) so each lane writes to distinct encrypted file paths and lockfiles.

## Files

- `Secretfile.yml` - Main manifest
- `dev.szvar` / `staging.szvar` / `prod.szvar` - Lane overrides
- `.gitignore` - Ignores generated lane lockfiles and local `.env.*`

## Prerequisites

Install SecretZero with extras as needed and ensure your encryption tooling is available in PATH:

- `ansible-vault` (python package support for provider)
- `sops` CLI
- `git-crypt` CLI

For Ansible Vault password flow:

```bash
export ANSIBLE_VAULT_PASSWORD='your-password'
```

## Run per lane

```bash
# Dev lane
secretzero sync -f examples/encrypted-repo-workflows/Secretfile.yml --environment dev

# Staging lane
secretzero sync -f examples/encrypted-repo-workflows/Secretfile.yml --environment staging

# Prod lane
secretzero sync -f examples/encrypted-repo-workflows/Secretfile.yml --environment prod
```

## Render and inspect resolved config

```bash
secretzero render \
  -f examples/encrypted-repo-workflows/Secretfile.yml \
  --var-file examples/encrypted-repo-workflows/dev.szvar
```

## Notes

- This example is for workflow shape and lane strategy. Do not commit plaintext output artifacts.
- Keep each lane in separate encrypted files to reduce merge conflicts and blast radius.
