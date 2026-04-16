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

Full details now live in focused skills:
- `./skills/secretzero-agent/SKILL.md` for unified agentic/runtime workflows and vector handling.
- `./skills/secretzero-author/SKILL.md` for schema-compliant `Secretfile.yml` authoring and safe discovery-driven policy authoring.

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
./scripts/agent.pre-commit.sh --mode full
```

- If `schema:update`, `lint:fix`, or `format` modifies files, the script exits with guidance. Commit those changes and re-run at least `task test` and `task security:scan`.
- Verify feature parity: Test changes through both CLI and API (if the API sub-component is active).
- Update `.mex/ROUTER.md` and any affected patterns in `.mex/patterns/`.

## End-of-Work Prompt

At the end of any coding work, run a fast local gate:

```bash
./scripts/agent.pre-commit.sh --mode fast --quiet
```

Before any push/merge, run the full gate:

```bash
./scripts/agent.pre-commit.sh --mode full
```

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

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **SecretZero** (9587 symbols, 19204 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## When Debugging

1. `gitnexus_query({query: "<error or symptom>"})` — find execution flows related to the issue
2. `gitnexus_context({name: "<suspect function>"})` — see all callers, callees, and process participation
3. `READ gitnexus://repo/SecretZero/process/{processName}` — trace the full execution flow step by step
4. For regressions: `gitnexus_detect_changes({scope: "compare", base_ref: "main"})` — see what your branch changed

## When Refactoring

- **Renaming**: MUST use `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` first. Review the preview — graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run `gitnexus_context({name: "target"})` to see all incoming/outgoing refs, then `gitnexus_impact({target: "target", direction: "upstream"})` to find all external callers before moving code.
- After any refactor: run `gitnexus_detect_changes({scope: "all"})` to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Tools Quick Reference

| Tool | When to use | Command |
|------|-------------|---------|
| `query` | Find code by concept | `gitnexus_query({query: "auth validation"})` |
| `context` | 360-degree view of one symbol | `gitnexus_context({name: "validateUser"})` |
| `impact` | Blast radius before editing | `gitnexus_impact({target: "X", direction: "upstream"})` |
| `detect_changes` | Pre-commit scope check | `gitnexus_detect_changes({scope: "staged"})` |
| `rename` | Safe multi-file rename | `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` |
| `cypher` | Custom graph queries | `gitnexus_cypher({query: "MATCH ..."})` |

## Impact Risk Levels

| Depth | Meaning | Action |
|-------|---------|--------|
| d=1 | WILL BREAK — direct callers/importers | MUST update these |
| d=2 | LIKELY AFFECTED — indirect deps | Should test |
| d=3 | MAY NEED TESTING — transitive | Test if critical path |

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/SecretZero/context` | Codebase overview, check index freshness |
| `gitnexus://repo/SecretZero/clusters` | All functional areas |
| `gitnexus://repo/SecretZero/processes` | All execution flows |
| `gitnexus://repo/SecretZero/process/{name}` | Step-by-step execution trace |

## Self-Check Before Finishing

Before completing any code modification task, verify:
1. `gitnexus_impact` was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. `gitnexus_detect_changes()` confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## Keeping the Index Fresh

After committing code changes, the GitNexus index becomes stale. Re-run analyze to update it:

```bash
npx gitnexus analyze
```

If the index previously included embeddings, preserve them by adding `--embeddings`:

```bash
npx gitnexus analyze --embeddings
```

To check whether embeddings exist, inspect `.gitnexus/meta.json` — the `stats.embeddings` field shows the count (0 means no embeddings). **Running analyze without `--embeddings` will delete any previously generated embeddings.**

> Claude Code users: A PostToolUse hook handles this automatically after `git commit` and `git merge`.

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
