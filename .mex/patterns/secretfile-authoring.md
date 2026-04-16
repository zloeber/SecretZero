---
name: secretfile-authoring
description: Author or refactor `Secretfile.yml` with correct variable/provider structure.
triggers:
  - "secretfile"
  - "variables"
  - "var-file"
  - "provider config"
edges:
  - target: context/architecture.md
    condition: when understanding ConfigLoader and SyncEngine boundaries
  - target: context/setup.md
    condition: when command usage or environment setup is needed
  - target: patterns/add-secret.md
    condition: when authoring includes adding/changing secret entries
last_updated: 2026-04-14
---

# Secretfile Authoring

## Context
This pattern covers edits to `Secretfile.yml` structure (`variables`, `providers`, `templates`, `secrets`, `policies`) and var-file merge usage.

## Provider identity policies (`kind: provider_identity`)

Use root `policies:` entries with `kind: provider_identity` to block `secretzero sync` when a configured provider’s `get_actor_info()` does not match your rules (wrong AWS account, Vault policies, etc.). Policies apply when their `providers:` list overlaps provider aliases used on **in-scope** secret targets, or when a target lists `identity_policies: [policy_name]`. Rules support `glob` / `regex` on scalar fields and `any_glob` / `all_glob` on list fields (e.g. Vault `scopes`). See `$defs.ProviderIdentityPolicy` in `Secretfile.schema.json`.

**Common actor fields** (from built-in providers; always check `secretzero status` / provider identity output for your version):

| Provider kind | Useful `field:` paths |
|---------------|------------------------|
| `aws` | `account`, `arn`, `user`, `region`, `token_type` |
| `vault` | `user`, `scopes`, `url`, `namespace`, `token_type` |
| `azure` | `tenant_id`, `object_id`, `user`, `token_type` (JWT-derived where available) |
| `github` / `gitlab` | `user`, `scopes`, `token_type` |
| `kubernetes` | `cluster_host`, `user`, `token_type` |
| `jenkins` | `user`, `token_type` |

**Narrow AWS account + region example:**
```yaml
policies:
  aws_prod_guard:
    kind: provider_identity
    providers: [aws]
    match: all
    rules:
      - field: account
        glob: "111111111111"
      - field: region
        glob: us-east-1
```

**Discovery-assisted authoring loop (agent-safe):**
1. Inspect current provider identity metadata with `secretzero status --format json`.
2. Capture stable actor fields (`account`, `region`, `arn`, `tenant_id`, etc.) for each provider alias.
3. Draft the most specific `provider_identity` rules first (exact `glob` before broader `regex`).
4. Validate with `secretzero validate -f Secretfile.yml` and `secretzero sync --dry-run`.
5. Only widen matchers when required, and document why.

## Steps
1. Keep top-level sections explicit and valid for Pydantic model parsing.
2. Ensure provider aliases in `providers:` match references in all secret targets.
3. Validate interpolation assumptions with `secretzero render`.
4. Validate schema with `secretzero validate -f Secretfile.yml`.
5. Run `secretzero sync --dry-run` before real sync.

## Gotchas
- `provider_identity` policies are enforced at sync time (CLI, API, agent) after target access checks; they do not run for `secretzero policy` rotation/access checks.
- `${VAR}` interpolation is based on merged variable context in config flow, not implicit shell env substitution.
- Var-file ordering matters; later `--var-file` overrides earlier values.
- A typo in interpolated key paths can silently produce wrong/empty rendered values in downstream config.
- Secretfile root `version` is no longer required; manifest spec versioning is tracked in `.gitsecrets.lock` under `secretfile.manifest_spec_version`.
- Prefer defining whole secrets first; use templates only for stable multi-field credentials that are consumed together.
- Prefer template-level targets over per-field targets unless a field must go to a different destination.

## Verify
- [ ] Render output contains expected provider paths and secret target config.
- [ ] Validation passes without schema/type errors.
- [ ] Dry-run output aligns with intended provider/target routes.

## Debug
- If sync fails after valid render/validate, follow `patterns/debug-sync.md`.

## Update Scaffold
- [ ] Add newly discovered authoring gotchas to this pattern.
