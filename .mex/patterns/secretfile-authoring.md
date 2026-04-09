---
name: secretfile-authoring
description: Writing and editing Secretfile.yml — variable interpolation, multi-environment setup with .szvar files, and provider configuration patterns.
triggers:
  - "secretfile"
  - "variable"
  - "interpolation"
  - "szvar"
  - "multi-environment"
  - "provider config"
  - "write config"
edges:
  - target: context/architecture.md
    condition: when understanding how ConfigLoader processes the file
  - target: context/decisions.md
    condition: when understanding the variable interpolation design choices
  - target: patterns/add-secret.md
    condition: when adding secrets to the Secretfile being authored
  - target: patterns/debug-sync.md
    condition: when variable interpolation produces unexpected output
last_updated: 2026-04-09
---

# Secretfile Authoring

## Context

`Secretfile.yml` is the declarative manifest. `ConfigLoader` processes it through:
1. YAML parse
2. Variable deep-merge (base `variables:` block + ordered `.szvar` files)
3. Jinja2 interpolation (`{{var.key}}`) and shell-style substitution (`${ENV_VAR}`) — shell runs first
4. Pydantic validation against `Secretfile` model

The output is an immutable `Secretfile` Pydantic model that `SyncEngine` operates on.

## Secretfile Structure

```yaml
version: '1.0'                    # required; must be non-empty string

variables:                         # base variables; overridden by .szvar files
  environment: dev
  region: us-east-1
  project: my-app

metadata:                          # optional; used by policy checks
  project: my-app
  owner: platform-team
  environments: [dev, staging, prod]
  compliance: [soc2]

providers:                         # named provider instances
  local:                           # "local" is the reserved name for file targets
    kind: local
    config: {}
  my_vault:
    kind: vault
    auth:
      kind: token
      config:
        token: ${VAULT_TOKEN}      # shell-style env var substitution
    config:
      url: https://vault.example.com
      mount_point: secret

secrets:                           # list of secret definitions
  - name: db_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: my_vault
        kind: vault_kv
        config:
          path: "{{var.project}}/{{var.environment}}/db_password"

templates: {}                      # named templates for multi-field secrets
policies: {}                       # rotation / compliance / access policies
labels: {}                         # arbitrary labels (informational)
annotations: {}                    # arbitrary annotations (informational)
```

## Variable Interpolation Rules

**Shell-style** (`${VAR_NAME}`) — resolved first, from the merged variables dict (NOT from OS environment):
```yaml
config:
  token: ${VAULT_TOKEN}    # looks up "VAULT_TOKEN" key in variables, falls back to original string
```

**Jinja2-style** (`{{var.key}}` or `{{var['key']}}`) — resolved second, using `var` context object:
```yaml
config:
  path: "{{var.project}}/{{var.environment}}/db_password"
  url: "https://{{var.region}}.vault.example.com"
```

**Silent undefined behaviour** — typos silently become empty strings:
```yaml
# If "environmnet" is not defined, this becomes "/db_password" (empty segment)
path: "{{var.project}}/{{var.environmnet}}/db_password"
```
Always use `secretzero render` after editing to inspect interpolated output.

## Multi-Environment with .szvar Files

Create a base `Secretfile.yml` with shared config and per-environment `.szvar` files:

```yaml
# base.szvar
environment: dev
region: us-east-1
vault_addr: https://vault-dev.example.com
```

```yaml
# prod.szvar
environment: prod
region: us-west-2
vault_addr: https://vault-prod.example.com
```

Usage:
```bash
# Dev sync (loads base variables)
secretzero sync -f Secretfile.yml --var-file base.szvar

# Prod sync (base merged then prod overrides)
secretzero sync -f Secretfile.yml --var-file base.szvar --var-file prod.szvar
```

The lockfile tracks the `var_files` basenames and a hash of the merged variables, so `secretzero status` can detect when the variable context has changed between runs.

## Provider Configuration Patterns

**Ambient auth (SDK default credential chain):**
```yaml
providers:
  aws:
    kind: aws
    auth:
      kind: ambient   # uses AWS default credential chain (env vars, ~/.aws, EC2 metadata)
    config:
      region: us-east-1
```

**Token auth (explicit token):**
```yaml
providers:
  vault:
    kind: vault
    auth:
      kind: token
      config:
        token: ${VAULT_TOKEN}   # from variables block or literal
    config:
      url: https://vault.example.com
      mount_point: secret
      kv_version: "2"           # "1" or "2"
```

**Multiple providers of the same kind:**
```yaml
providers:
  vault_dev:
    kind: vault
    config:
      url: https://vault-dev.example.com
  vault_prod:
    kind: vault
    config:
      url: https://vault-prod.example.com
```

## Gotchas

- **`version:` is required** — missing it causes a Pydantic validation error at parse time. Use `'1.0'` (quoted to avoid YAML treating it as a float).
- **`providers:` key must exist if any target references a non-local provider** — SyncEngine initialises providers from this block; a target referencing `provider: vault` when no `vault:` provider is declared will fail with "provider not initialized".
- **`local` is a reserved provider name** for file/template targets — do not declare a provider named `local` in `providers:`, it is handled implicitly by `SyncEngine`.
- **YAML indentation errors in targets list** — each target must be a list item (`- provider: ...`), not a dict. A missing `-` causes silent parsing of only the first target.
- **Shell-style `${VAR}` resolves from the `variables:` block, NOT OS environment** — to pass an OS env var into a Secretfile, either add it to the `variables:` block as a reference or use `secretzero sync -e KEY=VALUE` (if supported).

## Update Scaffold

- [ ] Update `.mex/ROUTER.md` "Current Project State" if authoring work changes what's working
- [ ] Update any `.mex/context/` files that are now out of date
- [ ] If a new authoring gotcha is discovered, add it to this file
