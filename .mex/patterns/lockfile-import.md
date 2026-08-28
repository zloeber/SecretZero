---
name: lockfile-import
description: Lockfile import from live targets must keep status, definition hashes, and provenance aligned.
triggers:
  - "secretzero import"
  - "lockfile import"
  - "run_lockfile_import"
  - "ingest preseed"
edges:
  - target: patterns/lockfile-state-parity.md
    condition: when changing how import results appear in status/web/graph
  - target: patterns/lockfile-sync-identity.md
    condition: when changing import actor or secretfile.sync_identity
  - target: patterns/debug-sync.md
    condition: when import succeeds but status still shows pending
last_updated: 2026-08-28
---

# Lockfile Import

## Context
`secretzero import` (`run_lockfile_import`) reads values from configured targets and updates `.gitsecrets.lock` hashes. It does not write targets. Compact `secretzero status` does not re-read target files; it uses `sync_state_for_secret_target()`.

## Steps
1. Retrieve values from targets and hash them (`Lockfile._hash_value`).
2. Treat a secret as current only when **secret-level hash and each matched per-target hash** equal the retrieved value.
3. On that current path, still refresh `definition_hash` (same as sync skip) and append target provenance.
4. Provenance actor must merge sync identity with `operation: lockfile_import` and `source: target`.
5. After a full (unscoped) import that imported/updated/unchanged any secret, call `track_secretfile(..., sync_identity=...)`.

## Gotchas
- Import "unchanged (hash_and_targets_current)" used to check only secret-level hash + target **keys**. Status can still show pending/drift when per-target hashes or `definition_hash` are stale, or when Secretfile file-level tracking is stale.
- Compact status paints both `pending` and `drift` as the red pending lane.
- Do not put plaintext values in lockfile metadata, tests, or logs. Provenance is operation/source/identity only.

## Verify
- [ ] `uv run pytest tests/test_lockfile_import.py`
- [ ] After import, `secretzero status` shows synced for those file targets.
- [ ] `.gitsecrets.lock` `target_provenance` last actor has `operation: lockfile_import` and `source: target`.
