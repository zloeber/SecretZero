# SecretZero – Guidance for Claude (and Other Coding Agents)

## Project Overview

SecretZero is a **declarative, schema-driven** secrets-as-code solution. It centers on `Secretfile.yml` manifests and includes multiple integrated components: Python CLI, FastAPI REST API, provider registry, lockfile engine, skills framework, Terraform support, and comprehensive documentation.

The project is structured as a **monorepo** (managed via `Taskfile.yml`, `pyproject.toml`, and supporting Node/Docker configs). All major behavior must maintain **feature parity** across CLI, API, skills, and other sub-projects.

## Non-Negotiables

- **Schema-driven development**: All features, validation, and agent behavior must originate from the Pydantic models. After model changes, always run `task schema:update` to propagate updates to CLI, API, JSON Schema, examples, and tests.
- **Zero-leakage rule**: Never request, receive, log, store, or allow plaintext secrets into any context, history, or responses.
- **Feature parity**: New capabilities (especially agentic features) must work consistently via CLI flags, API endpoints, and skills.
- Prefer structured JSON output for agent consumption.
- Use Rich for CLI output and FastAPI best practices for the API layer.

## Unified Agentic Secret-Zero Workflow

Use the **single unified entrypoint** for all secret bootstrapping:

**CLI:**
```bash
secretzero agent sync --json [--web] [--dry-run]
```

**API equivalent:** Use the corresponding `/agent/sync` (or proxy/metadata) endpoint when the REST API is deployed.

This command intelligently supports the **three agentic vectors**:

- **Vector 1 (Agent instructs human)**: Relay templated instructions from `pending_secrets`.
- **Vector 2 (Secure web UI)**: Use `--web`; guide the human to the temporary localhost form (values never enter agent context).
- **Vector 3 (Fully automated)**: Enable via `SZ_AGENT=true` + provider auth; runs end-to-end without intervention.

**Recommended loop**: Call the command/API → parse structured results → act (instruct human, trigger web UI, or proceed) → repeat until `pending_secrets` and `failed_secrets` are empty.

Detailed guidance, `agent_instructions` (with templating support), top-level `agent:` config, and vector mapping live in `./skills/secretzero/SKILL.md`.

## Essential Commands (Schema-Driven)

- `task schema:update` — Regenerate schema after model changes (mandatory for parity).
- `secretzero validate`, `secretzero schema export`
- `secretzero agent sync --json`
- `secretzero sync --dry-run`, `secretzero test`, `secretzero secret-types`

## Pre-Push / Pre-Merge Checklist

Run **in order** from the repository root before any push or merge:

```bash
task lint:fix && task format && task schema:update
task test
task security:scan
task test:validations
```

Fix all issues. If schema or lint tasks change files, commit them and re-run the checklist. Verify changes work via both CLI and API where applicable.

## Other Workflows

In addition to the three agentic vectors, SecretZero includes:
- Standard sync, rotate, drift detection, policy checks
- Audit logging and graph visualization
- Provider-specific and Terraform-integrated operations
- CI/CD secret injection

Choose the right workflow for the task; default to the unified `agent sync` only for secret-zero bootstrapping.

## After Every Task or Major Change

- Update `.mex/ROUTER.md` and relevant `.mex/` patterns.
- Ensure documentation (`AGENTS.md`, `CLAUDE.md`, `SKILL.md`, docs/) reflects the changes.
- Maintain schema-driven consistency across the monorepo.

Follow these rules to keep SecretZero secure, consistent, and highly usable by both humans and AI agents across all its components.
