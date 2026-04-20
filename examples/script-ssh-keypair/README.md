# Script SSH Keypair Example

This example shows how to generate an SSH keypair with the `script` generator
and store both keys as a structured template secret.

## What It Does

- Uses `zsh` + `ssh-keygen` to create an Ed25519 keypair.
- Reuses the same generated keypair if files already exist.
- Writes template output to `generated/ssh-keypair.yml`.
- Keeps generated artifacts out of git via local `.gitignore`.

## Files

- `Secretfile.yml` - SecretZero manifest for this example
- `.gitignore` - excludes generated keys and output files

## Usage

Run from repository root:

```bash
secretzero validate -f examples/script-ssh-keypair/Secretfile.yml
secretzero sync --dry-run -f examples/script-ssh-keypair/Secretfile.yml
secretzero sync -f examples/script-ssh-keypair/Secretfile.yml
```

## Output

After `sync`, you should see:

- `examples/script-ssh-keypair/.secrets/deploy_key_ed25519`
- `examples/script-ssh-keypair/.secrets/deploy_key_ed25519.pub`
- `examples/script-ssh-keypair/generated/ssh-keypair.yml`

## Notes

- This is an example for local/development workflows.
- Do not commit generated private keys.
- If you need passphrased keys, replace `-N ""` with your preferred approach.

