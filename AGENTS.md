# Agent Workflow for SecretZero (Monorepo)

This document guides AI coding agents and human contributors when working on **SecretZero** or using it within any repository.  
SecretZero is a **schema-driven** secrets-as-code tool with multiple integrated components: CLI, REST API (`secretzero-api`), skills framework, Pydantic models, lockfile engine, provider registry, Terraform modules, and documentation.

**Start every session** by reading `.mex/ROUTER.md` for current project state and active patterns.

## Core Principles (Apply Across All Sub-Projects)

- **Schema-driven development is mandatory**: All changes to configuration, validation, or behavior must flow through the Pydantic models in `src/secretzero/models.py` (or equivalent). Run `task schema:update` after any model changes to regenerate `Secretfile.schema.json` and keep CLI, API, skills, and examples in parity.
- **Zero-leakage rule**: Never request, receive, log, store, or allow plaintext secret values into any agent/LLM context, history, logs, or responses.
- **Feature parity**: Ensure new features (especially agentic capabilities) are implemented consistently in the CLI (`secretzero` command), the FastAPI REST API, the skills system, and any related sub-projects (Terraform, docs, .mex patterns).
- Prefer JSON output (`--json` for CLI, appropriate API endpoints) for machine-readable results.
- After model/schema changes, always update:
  - CLI handlers
  - API routers/endpoints
  - Skills documentation
  - Examples (`Secretfile.example.yml`, tests)
  - `.mex/` patterns and `ROUTER.md`

## Unified Agentic Secret-Zero Workflow

The project provides **one primary unified entrypoint** for secure secret bootstrapping that covers the **three agentic vectors** while maintaining full compatibility with all other SecretZero workflows (sync, rotate, drift, policy enforcement, audit, etc.).

**Primary command (CLI):**
```bash
secretzero agent sync --json [--web] [--dry-run] [--verbose]
```

Equivalent API usage (when the REST API is deployed):
- `POST /agent/sync` with JSON body `{ "dry_run", "web", "lockfile?", "sz_agent?" }` (same semantics as the CLI); poll `GET /agent/sync/web/{session_id}` after Vector 2.

### The Three Agentic Vectors

**Vector 1 – Agent instructs human (CLI-guided / human-seeded)**  
Agent receives rendered instructions and relays them to the human. Human performs actions and confirms.  
Best for environments where the human has direct access to consoles or local tools.

**Vector 2 – Secure human input via temporary local web UI**  
Agent triggers `--web` (or API equivalent). A localhost-only, one-time form collects values that are fed directly into the sync engine. Values never enter agent context or logs.

**Vector 3 – Fully automated**  
Provider authentication is sufficient (or `SZ_AGENT=true` is set). The workflow completes end-to-end with no human intervention. Failures are reported clearly in structured output.

**Universal Agent Loop (recommended for all three vectors):**
1. Call `secretzero agent sync --json` (or API equivalent).
2. Act on structured results (`pending_secrets`, `failed_secrets`, status).
3. For Vector 1: Present templated instructions.
4. For Vector 2: Trigger web UI and guide user safely.
5. For Vector 3: Proceed automatically.
6. Re-run until clean.
7. Only continue with downstream tasks once secret-zero state is resolved.

Full details, `agent_instructions` authoring (with templating), top-level `agent:` config, and vector mapping are in `./skills/secretzero/SKILL.md`.

## Schema-Driven Development Mandate

- All configuration, validation rules, and agent behavior are defined in Pydantic models.
- After any model change → run `task schema:update`.
- This automatically keeps:
  - CLI argument parsing and output
  - FastAPI endpoints and OpenAPI spec
  - JSON Schema for IDEs and validation
  - Skills and example files
  - Tests and Terraform modules (where applicable)
- in sync. Never implement behavior directly in CLI or API without updating the core models first.

## Pre-Push / Pre-Merge Checklist (Monorepo-Wide)

Run these from the repository root **before any push or merge request**:

```bash
task lint:fix && task format && task schema:update
task test
task security:scan
task test:validations
```

- If `schema:update`, `lint:fix`, or `format` modifies files, commit the changes and re-run the full checklist.
- Verify feature parity: Test changes through both CLI and API (if the API sub-component is active).
- Update `.mex/ROUTER.md` and any affected patterns in `.mex/patterns/`.

## Other Workflows (Beyond the Three Agentic Vectors)

SecretZero supports many additional workflows that agents should use when appropriate:
- Standard sync/rotate/drift/policy checks
- Provider-specific operations
- Audit log querying
- Graph visualization of secret dependencies
- Terraform integration for infrastructure secrets
- CI/CD secret injection

Always choose the most appropriate workflow; fall back to the unified `agent sync` only for secret-zero bootstrapping scenarios.

## Merge Requests / Pull Requests

- Include a clear description noting impacts on schema, CLI, API, skills, and any other sub-projects.
- Confirm schema-driven changes were validated with `task schema:update` and full tests.
- Reference updated documentation (`AGENTS.md`, `CLAUDE.md`, `SKILL.md`, docs/).

This ensures SecretZero remains secure, consistent, and maintainable across its entire monorepo surface.

