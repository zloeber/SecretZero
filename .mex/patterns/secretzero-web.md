---
name: secretzero-web
description: Network-facing one-shot web UI for manual secret seeding (`secretzero web`).
triggers:
  - "secretzero web"
  - "network web UI"
edges:
  - target: patterns/add-cli-command.md
    condition: when extending CLI flags or help text
  - target: src/secretzero/network_webui.py
    condition: when changing auth, TLS, routes, or templates
  - target: src/secretzero/network_web_dashboard.py
    condition: when changing dashboard rows, manifest metadata, or SyncEngine wiring
last_updated: 2026-04-12
---

# `secretzero web` (network seeding UI)

## Context

- Implementation: [`src/secretzero/network_webui.py`](../../src/secretzero/network_webui.py), dashboard helpers in [`src/secretzero/network_web_dashboard.py`](../../src/secretzero/network_web_dashboard.py), Jinja templates in [`src/secretzero/network_web_templates_jinja.py`](../../src/secretzero/network_web_templates_jinja.py), CLI in [`src/secretzero/cli.py`](../../src/secretzero/cli.py) (`web_command`).
- After login, **`/dashboard`** lists every secret with targets and lockfile metadata; per-secret **Sync** / **Rotate** (POST `/action/sync-secret`, `/action/rotate-secret`), static **Edit** (`/secret/{name}/edit` → POST `/secret/{name}/apply` with [`_inject_static_values`](../../src/secretzero/agent_webui.py)), **Sync all** (`/action/sync-all`), **Logout** (`/logout`), **Shutdown** (`/shutdown` — stops the server process after clearing the session cookie; uses a short delayed timer so the response can flush).
- Sync uses [`make_sync_engine`](../../src/secretzero/network_web_dashboard.py) (non-interactive `SyncEngine`) against the in-memory manifest + lockfile; not the Vector 2 form batch helper.
- Bootstrap access uses a **one-time** SHA-256 digest exchange, then **HttpOnly** session cookie + **CSRF** on mutating POSTs. Optional TLS: PEM paths or `--tls-self-signed` (SPKI SHA-256 printed for manual trust).

## Steps (when changing behavior)

1. Preserve the zero-leakage rule: never log submitted secret values.
2. Keep cookie `Secure` when HTTPS is enabled; `SameSite=Lax`.
3. After edits, run `task test` (includes `tests/test_network_webui.py`).

## Verify

- [ ] `uv run secretzero web --help` lists host/port/token/TLS options (no stale references to removed flags).
- [ ] Tests in `tests/test_network_webui.py` pass.
