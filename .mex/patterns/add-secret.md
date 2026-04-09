---
name: add-secret
description: Adding a new secret or secret template to Secretfile.yml, including generator config and target routing.
triggers:
  - "add secret"
  - "new secret"
  - "add field"
  - "new template"
  - "secretfile"
edges:
  - target: context/architecture.md
    condition: when understanding how generators and targets connect
  - target: context/conventions.md
    condition: when unsure about naming or structure
  - target: patterns/debug-sync.md
    condition: when the new secret fails to sync
  - target: patterns/secretfile-authoring.md
    condition: when the Secretfile structure, variables, or provider config needs guidance
last_updated: 2026-04-09
---

# Add Secret

## Context

Load `context/architecture.md` — secrets flow from generator → SyncEngine → target → lockfile.
The `Secretfile.yml` is the source of truth. The lockfile (`.gitsecrets.lock`) tracks state.

Two secret flavours exist:
- **Simple secret** — `kind` is a generator kind string (`random_password`, `random_string`, `static`, `script`, `provider_backed`, `github_pat`)
- **Template secret** — `kind: templates.<template_name>` expands to multiple field sub-secrets; template must exist in `templates:` block

## Task: Add a Simple Secret

### Steps

1. Open `Secretfile.yml` (or the relevant var-overridden file for the environment).
2. Add an entry to the `secrets:` list:
```yaml
secrets:
  - name: my_secret          # snake_case; used as lockfile key and env var fallback (MY_SECRET)
    kind: random_password    # generator kind; see GeneratorKind enum in models.py
    config:
      length: 32
      special: true
    one_time: false          # set true to never regenerate once created
    rotation_period: 90d     # optional: d/w/m/y units; triggers check warnings when overdue
    targets:
      - provider: local      # provider name from providers: block (or "local" for file targets)
        kind: file
        config:
          path: .env
          format: dotenv     # dotenv | json | yaml | toml
          merge: true        # merge into existing file vs. overwrite
```
3. If targeting a cloud store, ensure the provider is declared in `providers:` and its optional extra is installed (`pip install secretzero[aws]` etc.).
4. Run `secretzero validate -f Secretfile.yml` — must pass before proceeding.
5. Run `secretzero sync --dry-run` — confirm the secret would be generated and sent to the correct target.
6. Run `secretzero sync` — generates value, stores in target, updates `.gitsecrets.lock`.

### Gotchas

- **Name must be unique across all secrets in the Secretfile.** The lockfile key is the secret name; duplicates silently overwrite each other.
- **`one_time: true` is permanent** — once a value exists in the lockfile the secret will never be regenerated (even with `--force-rotation` unless you delete the lockfile entry manually).
- **Env var fallback is always checked first** — if `MY_SECRET` is set in the environment, that value is used instead of generating. This is intentional (CI seed override), but can cause surprising behaviour if you forget a stale env var is set.
- **File target with `merge: false` will overwrite the entire file** on each sync run — other secrets targeting the same file must also use `merge: true`.
- **`rotation_period` only controls `secretzero check` warnings** — it does NOT trigger automatic rotation. You still need to run `secretzero sync --force-rotation` to actually rotate.

### Verify

- [ ] `secretzero validate` passes with no errors
- [ ] `secretzero sync --dry-run` shows the new secret in the output with the correct target
- [ ] After `secretzero sync`, the secret appears in `secretzero status` output
- [ ] `.gitsecrets.lock` has a new entry with a `hash` (not a plaintext value)
- [ ] The target file/store contains the secret (check the file or cloud console)

## Task: Add a Template Secret

### Steps

1. Define the template in the `templates:` block:
```yaml
templates:
  db_credentials:
    description: Database credentials bundle
    fields:
      username:
        description: Database username
        generator:
          kind: static
          config:
            default: app_user
      password:
        description: Database password
        generator:
          kind: random_password
          config:
            length: 32
            special: true
    targets:
      - provider: local
        kind: file
        config:
          path: config/db.json
          format: json
```
2. Reference the template from a secret:
```yaml
secrets:
  - name: my_db_creds
    kind: templates.db_credentials   # must match templates: key exactly
```
3. Each field (`my_db_creds.username`, `my_db_creds.password`) gets its own lockfile entry.
4. Validate and sync as with simple secrets.

### Gotchas

- **Template field secrets are tracked as `<secret_name>.<field_name>` in lockfile** — e.g., `my_db_creds.password`. Be aware when reading lockfile output.
- **Template targets and field targets are additive** — both `template.targets` and `field.targets` receive the value. This means a field can be stored in multiple places.
- **Template rendering is deferred** — `template` kind targets collect all field values first, then render together at the end of the sync run. This is necessary for Jinja2 template files that reference multiple secrets.

## Update Scaffold

- [ ] Update `.mex/ROUTER.md` "Current Project State" if new secrets change what's working
- [ ] Update any `.mex/context/` files that are now out of date
- [ ] If this is a new task type without a pattern, create one in `.mex/patterns/` and add to `INDEX.md`
