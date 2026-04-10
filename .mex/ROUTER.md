---
name: router
description: Session bootstrap and navigation hub. Read at the start of every session before any task. Contains project state, routing table, and behavioural contract.
edges:
  - target: context/architecture.md
    condition: when working on system design, integrations, or understanding how components connect
  - target: context/stack.md
    condition: when working with specific technologies, libraries, or making tech decisions
  - target: context/conventions.md
    condition: when writing new code, reviewing code, or unsure about project patterns
  - target: context/decisions.md
    condition: when making architectural choices or understanding why something is built a certain way
  - target: context/setup.md
    condition: when setting up the dev environment or running the project for the first time
  - target: patterns/INDEX.md
    condition: when starting a task — check the pattern index for a matching pattern file
last_updated: 2026-04-09
---

# Session Bootstrap

If you haven't already read `AGENTS.md`, read it now — it contains the project identity, non-negotiables, and commands.

Then read this file fully before doing anything else in this session.

## Current Project State

**Working:**
- Docs pipeline exports and publishes a raw `Secretfile.schema.json` at site root (`/Secretfile.schema.json`); `task docs:build` / `docs:serve` run the same export; generated `docs/Secretfile.schema.json` is gitignored
- Agent anchors aligned: `CLAUDE.md` and `.cursorrules` now mirror `AGENTS.md` pre-push workflow and operational checklist
- Core sync pipeline: Secretfile.yml → ConfigLoader → SyncEngine → generators → targets → lockfile
- Built-in generators: `random_password`, `random_string`, `static`, `script`, `provider_backed`, `github_pat`
- Built-in targets: `file`, `template` (local); `ssm_parameter`, `secrets_manager`, `vault_kv`, `azure_keyvault`, `kubernetes_secret`, `github_secret`, `gitlab_variable`, `jenkins_credential` (via provider bundles)
- All built-in providers: AWS, Azure, Vault, GitHub, GitLab, Jenkins, Kubernetes, AnsibleVault, Infisical
- Variable interpolation (Jinja2 + shell-style) and `.szvar` multi-environment override files
- Lockfile tracking: SHA-256 hashes, rotation history, per-target provenance
- Policy engine: rotation / compliance / access policies
- CLI: `create`, `init`, `validate`, `render`, `sync`, `status`, `check`, `drift`, `graph`, `format`, `terraform`, `providers`
- Optional FastAPI REST API (`secretzero-api`)
- Bundle extension system via Python entry_points

**Not yet built:**
- Automatic/scheduled rotation (rotation period only triggers warnings via `check`; actual rotation requires manual `--force-rotation`)
- Web UI (API server exists, but no browser frontend)
- Native CI/CD pipeline integrations (e.g., GitHub Actions action, GitLab CI template)

**Known issues:**
- MkDocs + pymdownx + Pygments 2.19+: `pymdownx.highlight` must set `auto_title: true` (or equivalent) so Pygments never receives `filename=None` (would break builds on pages like `api-getting-started.md`)
- Jinja2 variable typos silently produce empty strings (SilentUndefined); always run `secretzero render` to catch before sync
- Partial sync fails gracefully when an existing secret's value cannot be retrieved from tracked targets — requires `--force-rotation` to recover
- `.szvar` shell-style `${VAR}` resolves from the `variables:` dict, NOT the OS environment — this surprises users expecting OS env var injection

## Routing Table

Load the relevant file based on the current task. Always load `context/architecture.md` first if not already in context this session.

| Task type | Load |
|-----------|------|
| Understanding how the system works | `context/architecture.md` |
| Working with a specific technology | `context/stack.md` |
| Writing or reviewing code | `context/conventions.md` |
| Making a design decision | `context/decisions.md` |
| Setting up or running the project | `context/setup.md` |
| Adding a secret to a Secretfile | `patterns/add-secret.md` |
| Writing or editing a Secretfile.yml | `patterns/secretfile-authoring.md` |
| Adding a provider, generator, or target | `patterns/add-bundle.md` |
| Diagnosing a sync failure | `patterns/debug-sync.md` |
| Any specific task | Check `patterns/INDEX.md` for a matching pattern |

## Behavioural Contract

For every task, follow this loop:

1. **CONTEXT** — Load the relevant context file(s) from the routing table above. Check `patterns/INDEX.md` for a matching pattern. If one exists, follow it. Narrate what you load: "Loading architecture context..."
2. **BUILD** — Do the work. If a pattern exists, follow its Steps. If you are about to deviate from an established pattern, say so before writing any code — state the deviation and why.
3. **VERIFY** — Load `context/conventions.md` and run the Verify Checklist item by item. State each item and whether the output passes. Do not summarise — enumerate explicitly.
4. **DEBUG** — If verification fails or something breaks, check `patterns/INDEX.md` for a debug pattern. Follow it. Fix the issue and re-run VERIFY.
5. **GROW** — After completing the task:
   - If no pattern exists for this task type, create one in `patterns/` using the format in `patterns/README.md`. Add it to `patterns/INDEX.md`. Flag it: "Created `patterns/<name>.md` from this session."
   - If a pattern exists but you deviated from it or discovered a new gotcha, update it with what you learned.
   - If any `context/` file is now out of date because of this work, update it surgically — do not rewrite entire files.
   - Update the "Current Project State" section above if the work was significant.
