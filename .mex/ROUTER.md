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
last_updated: 2026-04-13
---

# Session Bootstrap

If you haven't already read `AGENTS.md`, read it now — it contains the project identity, non-negotiables, and commands.

Then read this file fully before doing anything else in this session.

## Current Project State
**Working:**
- End-to-end secrets pipeline: `Secretfile.yml` -> `ConfigLoader` -> `SyncEngine` -> targets -> `.gitsecrets.lock`.
- Bundle extensibility for providers/generators/targets via `BundleRegistry` and manifest factories.
- Built-in generators (`random_password`, `random_string`, `static`, `script`, `provider_backed`) and provider-backed targets across AWS/Azure/Vault/GitHub/GitLab/Jenkins/Kubernetes/Infisical.
- Policy/status/drift/terraform command families and comprehensive pytest suite.
- Task-based verification workflow (`lint:fix`, `format`, `schema:update`, `test`, `security:scan`, `test:validations`).
- **`secretzero web`:** one-shot, bindable FastAPI UI over the network (bootstrap token, session + CSRF, optional TLS): dashboard with manifest/lock metadata, per-secret sync/rotate, **per-target “Force to target”** when multiple targets exist and another lane is already synced (`SyncEngine.sync(..., force_targets=...)`), static value edit (forces target writes), optional `--debug` sync log panel, sync-all, logout, shutdown. CLI parity: `secretzero sync -s <name> --force-target <target_id>` (repeatable). See `.mex/patterns/secretzero-web.md`.
- **Vector 2 + network static edit:** localhost agent web form and `secretzero web` static **Edit** support structured static secrets: one password field per missing dict leaf (sorted keys, same as CLI) or optional full JSON object; both surfaces show a **Session** line (OS user, host, git user when present, CI actor when in CI) via `collect_lockfile_sync_identity` — same identity family as lockfile `sync_identity`, not a separate auth “login user”.
- **Static-like generator kinds:** `BaseGenerator.PROMPTS_LIKE_STATIC` and `secret_prompts_like_static()` (`src/secretzero/generators/traits.py`) replace hard-coded `kind == "static"` in agent sync, web dashboards, Vector 2 parsing, and Terraform default export. **`azure_app_reg`** is registered on the Azure bundle (`AzureAppRegGenerator` subclasses `StaticGenerator`); use `kind: azure_app_reg` for Entra app registration–shaped secrets (same config as `static`).
- **Lockfile sync identity:** On each non–dry-run sync that updates secretfile tracking, `.gitsecrets.lock` → `secretfile.sync_identity` records client surface (`cli`, `api`, `agent`, `network_web`), OS user/host/platform, git `user.*` + short `HEAD` at the Secretfile directory, optional env label (`SZ_SYNC_ENVIRONMENT`, `ENVIRONMENT`, `ENV`), and detected CI actor/repo/run URL when present. Each successful target write also appends to `target_provenance` (same snapshot, last 3 per target). See `.mex/patterns/lockfile-sync-identity.md`.
- **Secretfile manifest versioning:** Root `version` is no longer required in `Secretfile.yml`; lockfile tracking now records `secretfile.manifest_spec_version` (currently `1`) in `.gitsecrets.lock` for future manifest migration compatibility.
- **Provider token introspection:** All built-in providers now implement `ProviderAuth.get_token_info()` (or `InfisicalProvider.get_token_info()`) where the upstream API supports it—AWS STS, Azure JWT claims, Vault `lookup-self`, GitLab user, Jenkins `get_whoami`, Kubernetes kubeconfig host/context, Ansible Vault password *mode* (never the password), plus existing GitHub. `BaseProvider.get_actor_info()` merges this into sync `actor` metadata on target writes.
- **Provider identity UI:** `collect_provider_identity_rows()` (`src/secretzero/provider_identity.py`) resolves each `providers:` entry via `get_actor_info()`; shown as a Rich table before `secretzero sync` / `secretzero status` (text), `provider_identity` in JSON, and a **Provider identity** table on the `secretzero web` dashboard manifest header.
- **Agent skill guidance refreshed:** `skills/secretzero/SKILL.md` now includes explicit Secretfile authoring rules that prioritize whole-secret modeling and straightforward template usage.
- **Lockfile write guard:** sync/agent/API flows no longer persist empty skeleton lockfiles; `Lockfile.save()` now skips (and removes) files when state is semantically empty.
- **Provider kind fallback:** When a `providers:` entry omits top-level `kind`, sync and `secretzero init` now treat the YAML key as the provider kind (e.g. `providers.aws` → `aws`). Previously `model_dump()` produced `kind: null` and AWS never registered (`Provider not initialized`).
- **Structured secret hashing:** Lockfile hashing now accepts non-string secret payloads (e.g. JSON objects for multi-field static secrets) via canonical JSON normalization before SHA-256, preventing `'dict' object has no attribute 'encode'` during sync.
- **Example manifest:** `examples/azure-appreg-to-aws-sm.yml` uses a structured static `value` map with YAML `null` leaves so interactive `secretzero sync` prompts once per missing field (sorted keys); `.szvar` / `--var-file` can pre-fill those leaves to skip prompts.
- **Static dict prompting:** `StaticGenerator` now fills dict/object static secrets by prompting for each scalar leaf that is `null`, blank, or a lone `${VAR}` placeholder (nested leaves only; top-level empty string remains a deliberate value). `static_payload_needs_prompt()` drives agent auto-sync classification for structured static secrets.
- **Variable context / lockfile:** `variables_hash` was never persisted, so `variable_context_changed` was always true for manifests with `variables:` (vs `null` in the lock), forcing `ignore_foreign_context_targets` and spurious re-prompts. Missing baseline now means “not changed”; `secretzero sync` calls `track_variable_context` before saving the lockfile so real variable / `.szvar` changes are detected on subsequent runs.
- **CLI rotate filtering:** `secretzero rotate --secret <name>` / `-s` (repeatable) limits rotation to those manifest secrets; same as optional positional `SECRET_NAME`, but do not combine `-s` with the positional.

**Not yet built:**
- Autonomous/scheduled secret rotation service (rotation is operator-invoked).
- Fully automated release/deployment orchestration from scaffold itself.

**Unified agent sync:** Implemented — `secretzero agent sync --json [--web] [--verbose]` and `POST /agent/sync` share `AgentSecretSynchronizer`; Vector 2 web UI and `GET /agent/sync/web/{session_id}` for polling; Tavern E2E under `tests/e2e/` (`task test:e2e`).

**Known issues:**
- `secretzero sync --format json` previously skipped writing the lockfile; fixed — JSON sync now persists `.gitsecrets.lock` when not `--dry-run` (same rules as text output).
- Interpolation mistakes can appear as empty rendered values and require `secretzero render` to diagnose.
- Missing provider extras cause runtime unknown-kind/missing-dependency errors.
- Partial sync can skip if previous value retrieval from existing targets fails.
- Docs/schema/build workflows rely on keeping generated schema in sync.

## Routing Table

Load the relevant file based on the current task. Always load `context/architecture.md` first if not already in context this session.

| Task type | Load |
|-----------|------|
| Understanding how the system works | `context/architecture.md` |
| Working with a specific technology | `context/stack.md` |
| Writing or reviewing code | `context/conventions.md` |
| Making a design decision | `context/decisions.md` |
| Setting up or running the project | `context/setup.md` |
| Adding or modifying secrets in manifests | `patterns/add-secret.md` |
| Editing Secretfile structure/variables/providers | `patterns/secretfile-authoring.md` |
| Adding providers/generators/targets | `patterns/add-bundle.md` |
| Adding CLI commands/options | `patterns/add-cli-command.md` |
| Debugging sync failures | `patterns/debug-sync.md` |
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
