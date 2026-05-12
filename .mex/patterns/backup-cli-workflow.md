---
name: backup-cli-workflow
description: Change `secretzero backup create` / `backup restore` behavior safely, especially encryption defaults and environment fan-out.
triggers:
  - "backup create"
  - "backup restore"
  - "plain backup"
  - "encrypted backup"
edges:
  - target: "patterns/add-cli-command.md"
    condition: "When changing flags, help text, or CLI output shapes"
  - target: "patterns/secretfile-authoring.md"
    condition: "When backup behavior depends on environment lane config or var-file interpolation"
last_updated: 2026-05-12
---

# Backup CLI Workflow

## Context
`secretzero backup` is environment-sensitive. Backup payloads can depend on lane-specific `.szvar` files, resolved lockfile paths, and target profiles, so treat backup/restore as a per-environment sync workflow rather than a single static file operation.

## Steps
1. Run GitNexus impact on the CLI entrypoints you plan to edit (`backup_create_cmd`, `backup_restore_cmd`) and any helper you need to change.
2. Keep the manifest loading path aligned with the shared CLI helpers so root `--environment`, lane var files, and derived lockfile paths resolve the same way as `sync` and `status`.
3. When no explicit environment is selected and `Secretfile.environments.profiles` exists, iterate every listed lane for backup creation and restoration. Use `--environment` to narrow to one lane.
4. Treat plain backup payloads and encrypted payloads as separate modes. Plain mode should never require SOPS/AGE setup; encrypted mode should require explicit opt-in and be the only path that touches recipient resolution/decryption helpers.
5. Preserve restore compatibility for older single-environment payloads by honoring legacy `meta.environment` data when entry-level environment labels are absent.
6. Add focused CLI tests for default mode, explicit encrypted mode, environment fan-out, environment targeting, and any agent/safety guardrails.

## Gotchas
- A backup file that contains multiple environments cannot be restored through one shared `SyncEngine`; each environment needs its own resolved manifest and lockfile.
- Printing plain backup payloads to stdout is unsafe in automation contexts. Guard `SZ_AGENT` before emitting unencrypted payloads.
- `--age-recipient` and `--age-key-file` only make sense in encrypted mode; leaving them active in plain mode creates confusing partial behavior.
- Backup entry IDs are assigned after entries are aggregated, so multi-environment fan-out must happen before numbering.

## Verify
- Run backup-focused CLI tests that cover plain and encrypted create flows plus restore filtering.
- Run `tests/test_backup.py` when helper functions in `src/secretzero/backup.py` change.
- Check lints on touched files.
- Run the fast pre-commit gate before closing the task.

## Debug
- If restore writes the wrong targets or lockfile, inspect which environment each entry was assigned and whether the restore loop is rebuilding the engine per lane.
- If encrypted mode fails unexpectedly, verify the failure happens only after `--encrypted` is enabled and recipient resolution is not being called in plain mode.
- If plain mode fails in CI/agent contexts, confirm the `SZ_AGENT` guard runs before payload emission.

## Update Scaffold
- [ ] Update `.mex/ROUTER.md` "Current Project State" if backup behavior changed
- [ ] Update any `.mex/context/` files that are now out of date
- [ ] If backup workflow guidance changes again, refresh this pattern and `patterns/INDEX.md`
