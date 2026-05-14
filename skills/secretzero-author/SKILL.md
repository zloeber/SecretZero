---
name: secretzero-author
description: |
  Use when authoring, reviewing, or discovering `Secretfile.yml` manifests.
  Focuses on schema-compliant manifest quality, safe contextless discovery,
  environment-aware `.szvar` separation, and policy-bound provider targets.
  When work touches `.env`, local `file` targets, or spill-safe agent CLI,
  also load `skills/secretzero-handle/SKILL.md`.
---

# SecretZero Author Skill

Use this skill whenever the task is to create or improve `Secretfile.yml` and related `.szvar` files.

## Mission

Produce high-quality, json-schema compliant SecretZero manifests that:

- Pass `secretzero validate` with zero issues.
- Keep secret discovery safe and contextless (no secret values requested or echoed).
- Intelligently break out environment variance into `.szvar` files.
- Bind provider-backed targets to least-privilege identity policies for AWS/Azure/other authenticated environments.

## Safety Rules (Non-Negotiable)

- Never ask for, copy, log, or output plaintext secret values.
- Discovery must use metadata only (`status`, `test`, provider identity fields), not secret retrieval.
- Do not run `secretzero get --reveal` in agent sessions.
- If provider identity evidence is missing, mark policy confidence as low and require human confirmation.

## Install / Verify

Preferred:

```bash
uv tool install -U "secretzero[all]"
```

Other valid options:

```bash
uv tool install -U secretzero
uv tool install -U "secretzero[aws]"
uv tool install -U "secretzero[azure]"
pip install -U "secretzero[all]"
```

Verify:

```bash
secretzero --help
secretzero validate --help
```

## Authoring Workflow

1. **Load schema context**
   - Treat `Secretfile.schema.json` and `src/secretzero/models.py` as source of truth.
2. **Model whole secrets first**
   - One logical secret per `secrets[]` entry unless a true multi-field bundle is needed.
3. **Select generator intentionally**
   - Prefer `random_password`, `random_string`, `static` (or static-like kinds) before script/api complexity.
4. **Map explicit targets**
   - Every secret has clear targets unless intentionally deferred.
5. **Break out environment variance**
   - Keep structural defaults in `Secretfile.yml`.
   - Move lane-specific values to `*.szvar` files (`dev.szvar`, `staging.szvar`, `prod.szvar`).
6. **Apply identity guardrails**
   - Add `kind: provider_identity` policies and attach with `identity_policies` where needed.
7. **Validate in loop**
   - `secretzero validate`
   - `secretzero render` (if interpolation/templating is used)
   - `secretzero sync --dry-run --var-file <lane>.szvar`

## Environment Breakout Heuristics (`.szvar`)

Prefer `.szvar` breakout when values differ by deployment lane:

- Target names/paths (`/${env}/...`)
- Regions, accounts, tenants, namespaces
- Role/session specific selectors
- Non-structural per-lane toggles

Keep in manifest:

- Secret definitions (`name`, `kind`, generator config shape)
- Provider aliases and auth mode intent
- Policy object structure

Pattern:

```yaml
variables:
  env: dev
  aws_region: us-east-1
```

`dev.szvar`:

```yaml
env: dev
aws_region: us-east-1
```

`prod.szvar`:

```yaml
env: prod
aws_region: us-west-2
```

## Contextless Secret Discovery (Safe Mode)

Use only discovery commands that return metadata:

```bash
secretzero status --format json
secretzero test --verbose --format json
secretzero secret-types --verbose
```

Derive policy candidates from actor/auth metadata (account, region, arn, tenant_id, subscription_id, namespace, etc.), never from secret contents.

## Target Policy Binding Guidance

- **AWS**: constrain `account` and `region` first; optionally constrain role/arn patterns.
- **Azure**: constrain `tenant_id` and, when available, `subscription_id`.
- **Other providers**: bind to strongest stable identity fields exposed by `get_actor_info()`.
- Avoid broad `*` or permissive regex unless explicitly approved.

Example:

```yaml
policies:
  aws_prod_identity:
    kind: provider_identity
    providers: [aws]
    match: all
    rules:
      - field: account
        glob: "111111111111"
      - field: region
        glob: us-east-1
```

## Definition of Done

- `Secretfile.yml` is schema compliant and readable.
- `secretzero validate` exits cleanly.
- `.szvar` files cover lane variance without duplicating manifest structure.
- Provider-backed targets are bound to least-privilege identity policies where supported.
- No plaintext secret material appears in prompts, logs, files, or responses.
