---
name: gitnexus-metagit-integration
description: GitNexus overlays, MetaGit registry writes, discovery bindings, blast-radius CLI.
triggers:
  - "gitnexus"
  - "secrets_overlay"
  - "metagit"
  - "discovery_bindings"
  - "blast-radius"
last_updated: 2026-05-06
---

# GitNexus / MetaGit Integration

## Artifacts

| Path | Producer |
|------|----------|
| `.gitnexus/discovery_bindings.json` | `secretzero discover` (non–dry-run with candidates) |
| `.gitnexus/secrets_overlay.json` | `secretzero sync`, `secretzero get` (unless `SZ_NO_GITNEXUS_OVERLAY`) |
| `~/.metagit.yml` (`secretzero.repos`) | Same emit path when `SZ_METAGIT_REGISTRY=1` |

## CLI

- `secretzero gitnexus blast-radius --symbol <FQN>` — runs `gitnexus impact` (or `npx gitnexus`) when available.
- `secretzero rotate --trigger-reindex` — after success, runs `gitnexus analyze --skills` in the Secretfile directory.

## Model

- Per-secret `process_tags` in `Secretfile.yml` flow into the overlay JSON for process filtering in graph tooling.

## Verify

- [ ] `task schema:update` after `process_tags` or overlay schema changes.
- [ ] `tests/test_gitnexus_intel.py` covers overlay and registry helpers.
