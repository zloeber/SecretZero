---
name: agent-adopt
description: Agent runtime adopt/list workflows for Hermes, OpenClaw, and future claw-like installs.
triggers:
  - "agent adopt"
  - "agent list"
  - "agent backup"
  - "hermes adopt"
  - "openclaw adopt"
edges:
  - target: patterns/add-cli-command.md
    condition: when changing CLI flags or output shapes
  - target: patterns/sz-agent-mode-spill-guard.md
    condition: when touching agent-safe JSON or spill guards
  - target: patterns/docs-entrypoint-parity.md
    condition: when updating README/skills onboarding
last_updated: 2026-05-27
---

# Agent Adopt Workflow

## Context

`secretzero agent list` and `secretzero agent adopt` (alias `agent backup`) bootstrap SecretZero
environments from local agent installs. This is **not** `secretzero backup create` (encrypted value DR).

Implementation lives under `src/secretzero/integrations/`.

## Steps

1. Add or extend an adapter in `integrations/<target>/` with `catalog.yaml` + `adapter.py`.
2. Register the adapter in `integrations/registry.py` with autodetect order.
3. Keep scans **presence-only** — never attach secret values to result models or JSON.
4. Generated manifests use `default: null` on static secrets; target paths point at agent `.env` (absolute when GitOps output dir differs from install root).
5. `--preseed-lockfile` must call `run_lockfile_import` via the ingest-preseed path (hash-only).
6. Update skills (`secretzero-agent-adopt`), README `agent-entrypoint` comment, and ROUTER.md together.

## Gotchas

- `agent backup` wording collides mentally with `secretzero backup create` — document the distinction in help and skills.
- Re-adopt merges new catalog matches into an existing Secretfile unless `--force`.
- `--force` rebuilds from scratch (drops merge behavior).
- Autodetect failure must not write partial artifacts.
- Default `--output-dir` is the resolved agent install path.

## Verify

- Run `tests/test_agent_adopt.py`.
- Confirm JSON output never contains fixture secret strings.
- Run fast pre-commit gate.

## Update Scaffold

- [ ] Update `.mex/ROUTER.md` when adopt behavior changes
- [ ] Keep `docs/superpowers/specs/2026-05-27-agent-adopt-design.md` aligned
