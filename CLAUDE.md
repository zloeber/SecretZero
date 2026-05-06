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

Detailed guidance now lives in focused skills:
- `./skills/secretzero-agent/SKILL.md` for unified agentic/runtime workflows and vector handling.
- `./skills/secretzero-author/SKILL.md` for schema-compliant `Secretfile.yml` authoring and safe discovery-driven policy authoring.

### Entra Agent ID guidance

For `kind: entra-agent-blueprint`:
- Treat sponsor/approval blockers as human-in-the-loop flows (`agent sync --web`).
- Never print client secret plaintext from Graph responses.
- Validate required Graph permissions before retrying failed operations:
  - `AgentIdentityBlueprint.Create`
  - `AgentIdentityBlueprint.AddRemoveCreds.All`
  - `AgentIdentityBlueprint.UpdateAuthProperties.All`
  - `Application.ReadWrite.All`
  - `Directory.ReadWrite.All`

## Essential Commands (Schema-Driven)

- `task schema:update` — Regenerate schema after model changes (mandatory for parity).
- `secretzero validate`, `secretzero schema export`
- `secretzero agent sync --json`
- `secretzero sync --dry-run`, `secretzero test`, `secretzero secret-types`

## Pre-Push / Pre-Merge Checklist

Run **in order** from the repository root before any push or merge:

```bash
./scripts/agent.pre-commit.sh --mode full
```

Fix all issues. If schema or lint tasks change files, the script exits with instructions; commit those changes and re-run at least `task test` and `task security:scan`. Verify changes work via both CLI and API where applicable.

## End-of-Work Prompt

At the end of any coding task, run a fast local gate:

```bash
./scripts/agent.pre-commit.sh --mode fast --quiet
```

Before any push/merge, run the full gate:

```bash
./scripts/agent.pre-commit.sh --mode full
```

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

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **SecretZero** (13305 symbols, 18340 relationships, 144 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/SecretZero/context` | Codebase overview, check index freshness |
| `gitnexus://repo/SecretZero/clusters` | All functional areas |
| `gitnexus://repo/SecretZero/processes` | All execution flows |
| `gitnexus://repo/SecretZero/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
