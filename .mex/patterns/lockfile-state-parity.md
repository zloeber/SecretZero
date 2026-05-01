---
name: lockfile-state-parity
description: Enforce one canonical lockfile sync-state implementation across CLI/web/graph surfaces.
triggers:
  - "lockfile sync state"
  - "sync state parity"
  - "graph synced with"
  - "dashboard sync indicators"
  - "target drift/pending/synced logic"
edges:
  - target: patterns/secretzero-web.md
    condition: when web dashboard or graph rendering changes
  - target: context/conventions.md
    condition: when adding verification checks for parity
last_updated: 2026-04-20
---

# Lockfile State Parity

## Context
Use this pattern whenever you change how target sync state is evaluated or displayed in:
- dashboard rows (`secretzero web`)
- graph edges/labels (`secretzero graph` and web graph tab)
- CLI/status/drift surfaces that reason about lockfile target state

## Rule
Do not duplicate target sync-state logic in renderers. Use shared helpers in `src/secretzero/lockfile_state.py`:
- `target_id(...)`
- `lock_hash_for_target(...)`
- `sync_state_for_target(...)`
- `sync_state_for_secret_target(...)`

## Steps
1. Implement lockfile state logic once in `lockfile_state.py`.
2. Replace surface-specific implementations (dashboard, graph, CLI helpers) with calls to shared helpers.
3. Preserve backward compatibility behavior (legacy file target IDs) only in the shared helper.
4. Add/extend tests that validate synced/pending/drift behavior through helper API.
5. Add at least one consumer-level test (dashboard or graph) to ensure labels/styles still map correctly.

## Verify
- [ ] No duplicated lockfile target-state branching remains outside `lockfile_state.py`.
- [ ] Synced/pending/drift outcomes are identical for dashboard and graph consumers.
- [ ] Legacy file target ID fallback behavior is covered by tests.
- [ ] Consumer tests still verify expected Mermaid edge labels (`|synced|`, `|pending|`, `|drift|`, optional `|unknown|`) and `linkStyle` ordering (generator edges declared before secret→target edges).

## Gotchas
- Graph rendering can hide parity regressions if it reimplements fallback target ID behavior.
- Dashboard lane state can drift from graph state if each surface computes hashes independently.
