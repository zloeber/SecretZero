---
name: gitnexus-metagit-integration
description: GitNexus overlays, MetaGit registry writes, discovery bindings, blast-radius CLI.
triggers:
  - "gitnexus"
  - "secrets_overlay"
  - "metagit"
  - "discovery_bindings"
  - "blast-radius"
last_updated: 2026-09-22
---

# GitNexus / MetaGit Integration

## Artifacts

| Path | Producer |
|------|----------|
| `.gitnexus/discovery_bindings.json` | `secretzero discover` (non–dry-run with candidates) |
| `.gitnexus/secrets_overlay.json` | `secretzero sync` and `secretzero get`, only when a `.gitnexus` directory already exists (git work-tree index preferred). `SZ_GITNEXUS_OVERLAY=1` creates it. `SZ_NO_GITNEXUS_OVERLAY=1` skips the write. |
| `~/.metagit.yml` (`secretzero.repos`) | Same emit path when `SZ_METAGIT_REGISTRY=1` |

## CLI

- `secretzero gitnexus blast-radius --symbol <FQN>` — runs `gitnexus impact` (or `npx gitnexus`) when available.
- `secretzero rotate --trigger-reindex` — after success, runs `gitnexus analyze --skills` in the Secretfile directory.

## Model

- Per-secret `process_tags` in `Secretfile.yml` flow into the overlay JSON for process filtering in graph tooling.

## Gotchas

- Do not `mkdir` `.gitnexus` from sync, import, get, or other routine CLI commands. The overlay is only useful next to an existing GitNexus index or discovery bindings. `secretzero import` does not emit the overlay.
- `SyncEngine.sync` always sets `secretfile_changed` to a bool. Gate overlay refresh on `bool(secretfile_changed)`, stored secrets, or cleaned orphans — `is not None` is true for every sync.
- When the Secretfile lives in a subdirectory, write `secrets_overlay.json` into the git work-tree `.gitnexus` if that directory already exists. Do not create a second `.gitnexus` beside the manifest.

## Verify

- [ ] `task schema:update` after `process_tags` or overlay schema changes.
- [ ] `tests/test_gitnexus_intel.py` covers overlay and registry helpers.
