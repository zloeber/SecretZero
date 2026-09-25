---
name: vault-env-auth
description: HashiCorp Vault token/ambient auth from VAULT_ADDR and VAULT_TOKEN, plus provider_read from KV and other logical paths.
triggers:
  - "vault"
  - "VAULT_TOKEN"
  - "VAULT_ADDR"
  - "provider_read"
  - "hvac"
edges:
  - target: patterns/add-bundle.md
    condition: when changing Vault provider/target registration
  - target: patterns/schema-doc-parity.md
    condition: when AuthKind or Secretfile auth shape changes
  - target: patterns/secretfile-authoring.md
    condition: when documenting Vault provider blocks in manifests
last_updated: 2026-09-25
---

# Vault environment authentication and KV sources

## Context
The HashiCorp Vault provider (`src/secretzero/providers/vault.py`) authenticates with HVAC and reads/writes KV (and other logical paths). Secretfile `auth` is modeled as `kind` plus `config`, but docs and examples also put `url`/`token` as siblings of `kind`.

## Steps
1. Flatten Secretfile auth with `flatten_vault_auth_config()` before constructing `VaultAuth` (nested `auth.config`, sibling fields, `address` alias, ignore provider `kind: vault`).
2. Treat `token`, `ambient`, and omitted kind as user/token auth: config token, then `VAULT_TOKEN` when set, then `~/.vault-token`, then `~/.vault_token`. Pass the resolved token into the HVAC client.
3. Keep AppRole as `auth.kind: approle` (must be a valid `AuthKind`).
4. `retrieve_secret` must accept `provider_read` extras (`path`, `name`, `mount_point`, `kind`, `engine`, `kv_version`, `**_`) so sync source resolution does not TypeError.
5. Normalize KV v2 paths (`secret/data/...`) and support cubbyhole/generic logical reads.

## Gotchas
- Pydantic `ProviderAuth` must use `extra="allow"` or sibling `url`/`token` fields are dropped before the provider sees them.
- `test_connection` must not read provider `kind: vault` as the auth method.
- `VaultAuth.get_client()` should authenticate lazily; targets call `get_client()` after sync auth but CLI/token-info paths may not.
- Do not log or interpolate plaintext tokens into agent context; keep `${VAULT_TOKEN}` placeholders in docs.

## Verify
- [ ] `tests/test_vault_provider.py` covers env auth, ambient, nested config, provider_read kwargs, KV v1, cubbyhole/generic
- [ ] `kind: approle` validates on `Secretfile`
- [ ] Example `examples/vault-kv-source.yml` documents `auth.kind: ambient` + `provider_read`

## Debug
- Auth failed with env set: dump flattened auth keys (never values); confirm `VAULT_ADDR` is the cluster URL and token is not empty.
- Source TypeError on unexpected kwargs: `retrieve_secret` must swallow `provider_read` extras.
- Wrong KV data: check mount_point and whether the path still includes `/data/`.

## Update Scaffold
- [ ] Update `.mex/ROUTER.md` if Vault auth/source behavior changed
- [ ] Keep `docs/user-guide/providers/vault.md` aligned with env/ambient + provider_read
