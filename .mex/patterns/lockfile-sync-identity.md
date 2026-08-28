# Lockfile sync identity

Use when extending **who / where / CI** metadata persisted on sync (not secret values).

## Where it lives

- **Schema:** `LockfileSyncIdentity` and `SecretfileMetadata.sync_identity` in `src/secretzero/lockfile.py`
- **Collection:** `collect_lockfile_sync_identity()` in `src/secretzero/sync_identity.py` (host, user, git config/HEAD at Secretfile parent, CI env — **no tokens**, and no working-directory path)
- **Wiring:** `SyncEngine` (`sync_client`, optional `sync_identity` override, `sync_identity_cwd`) calls `Lockfile.track_secretfile(..., sync_identity=...)` once per run and merges that snapshot with target/provider actor metadata before `record_target_update` for per-target provenance. `secretzero import` uses the same merge with actor `operation: lockfile_import` and `source: target`.

## Verify

- `task test` (includes `tests/test_sync_identity.py`)
- Spot-check `.gitsecrets.lock` → `secretfile.sync_identity` and `secrets[*].target_provenance` after a real sync
