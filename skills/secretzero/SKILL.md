---
name: secretzero
description: Use when Secretfile.yml sits at a repository root, or when running SecretZero sync, human-in-the-loop secret seeding, or schema-compliant Secretfile authoring. Use to bootstrap new projects, agents, or other processes which require initial secrets to be generated or seeded.
---

# SecretZero for coding agents

Operate from the **repository root** where `Secretfile.yml` lives unless the manifest uses another path (then pass `-f` / `--file` consistently).

## Install

- **Requires Python 3.12+** and a recent [`uv`](https://docs.astral.sh/uv/) (or use `pip` equivalently).
- Minimal CLI:

  ```bash
  uv tool install secretzero
  ```

- Add extras matching the manifest’s providers (examples from the project docs). If uncertain then install 'all':

  ```bash
  uv tool install secretzero[aws]
  uv tool install secretzero[azure]
  uv tool install secretzero[vault]
  uv tool install secretzero[kubernetes]
  uv tool install secretzero[cicd]
  uv tool install secretzero[all]
  ```

- Confirm the tool is on `PATH`: `secretzero --help`

## Process a root manifest (baseline)

Run in order when onboarding a project that already has `Secretfile.yml`:

1. `secretzero validate` — structural validation (default file: `Secretfile.yml`). Use `--var-file path.szvar` when the repo uses variable files.
2. `secretzero init --install` — install declared provider/Python extras where supported.
3. `secretzero test` — check provider connectivity when configured.
4. `secretzero sync --dry-run` — full-engine preview (interactive prompts possible for manual secrets).

Default lockfile is **`.gitsecrets.lock`** when the manifest is `Secretfile.yml`. If you use `-f other.yml`, SecretZero derives a matching lockfile name from the stem unless you set `-l` explicitly.

Use **Agent mode** in the IDE so you can execute these commands, read output, and iterate without asking the user to copy-paste logs.

## Human-in-the-loop seeding (`secretzero agent sync`)

Use this path when you want **automated secrets synced first** and **structured guidance** for anything that needs a human (sign-ups, admin approval, OAuth, third-party consoles).

- **Read-oriented / automation-friendly output:**

  ```bash
  secretzero agent sync --json
  ```

  Parse the JSON: `synced_secrets`, `already_synced`, `pending_secrets` (each value includes `summary`, `steps`, `prerequisites`, etc.), and `failed_secrets`. Secrets that cannot auto-sync and lack `agent_instructions` appear under `failed_secrets` with an explicit error — fix the Secretfile (add `agent_instructions`) and re-run.

- **Dry run:** `secretzero agent sync --dry-run` (or add `--dry-run` with `--json`).

- **After the human completes external steps:** run `secretzero agent sync --interactive` so the user can supply values for pending items (only when a real TTY is available — not in headless automation). Alternatively use full `secretzero sync` if that matches the repo’s documented workflow.

**Agent loop (recommended):**

1. Run `secretzero agent sync --json` from the repo root.
2. For each entry in `pending_secrets`, present `summary` and `steps` to the human; wait for them to finish browser/account work.
3. Re-run `agent sync` until `pending_secrets` is empty or only contains items blocked on permissions.
4. If `failed_secrets` is non-empty, correct the manifest and validate again.

**Authoring expectation:** manual or semi-manual secrets should define `agent_instructions` (see schema export and examples below) so `agent sync` returns steps instead of hard failures.

## Writing schema-compliant `Secretfile.yml`

Use the CLI as the source of truth (Pydantic models back the schema).

| Goal | Command |
|------|---------|
| Export JSON Schema for editors / review | `secretzero schema export -o Secretfile.schema.json` (use `-o -` for stdout) |
| Validate YAML | `secretzero validate` or `secretzero validate --format json` |
| Scaffold a new file | `secretzero create --template-type basic` (also `aws`, `azure`, `vault`, `kubernetes`) |
| List generator kinds and options | `secretzero secret-types` and `secretzero secret-types --type <kind> --verbose` |

Workflow for agents:

1. Discover required secrets from the codebase (env vars, configs, deployment manifests).
2. Map each to a generator or `kind: static` and list targets (`kind: file`, cloud secret stores, CI providers, etc.).
3. For any secret that is not fully generatable in CI, add **`agent_instructions`** with a `summary` and ordered `steps` (`action`, `description`; optional `params` as a **mapping** if needed).
4. Run `secretzero validate`; fix errors against `secretzero schema export` or `--format json` validation output.
5. Only then run `secretzero agent sync` / `secretzero sync`.

Keep variable substitution consistent (`variables` section and `.szvar` files) and validate with the same `--var-file` flags the user will use in production.

## Common mistakes

- Running `agent sync` **without** `agent_instructions` on non-automatic secrets — yields `failed_secrets` instead of guided steps.
- Validating without **`.szvar`** files that the manifest depends on — use the same `-v` / `--var-file` inputs as `sync`.
- Forgetting provider extras — `secretzero init --install` or install the matching `secretzero[...]` extra.

## Quick reference

```bash
secretzero validate
secretzero agent sync --json
secretzero schema export -o Secretfile.schema.json
secretzero secret-types --verbose
```
