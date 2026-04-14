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
last_updated: 2026-04-13
---

# `secretzero web` (network seeding UI)

## Context

- Implementation: [`src/secretzero/network_webui.py`](../../src/secretzero/network_webui.py), dashboard helpers in [`src/secretzero/network_web_dashboard.py`](../../src/secretzero/network_web_dashboard.py) (`build_target_lane_ui` adds per-target **details** rows: e.g. file format + entry key, GitHub repo + Actions secret name + environment, K8s namespace/object + data key, etc.), Jinja templates in [`src/secretzero/network_web_templates_jinja.py`](../../src/secretzero/network_web_templates_jinja.py), CLI in [`src/secretzero/cli.py`](../../src/secretzero/cli.py) (`web_command`).
- After login, **`/dashboard`** lists every secret with targets and lockfile metadata; per-secret **Sync** / **Rotate** (POST `/action/sync-secret`, `/action/rotate-secret`), static **Edit** (`/secret/{name}/edit` → POST `/secret/{name}/apply` with [`_inject_static_values`](../../src/secretzero/agent_webui.py) — merges `config.value` and removes `config.default` so `${ENV}` placeholders under `default` do not shadow the form value). **Structured static** manifests (dict `value` with missing leaves) use the same per-leaf + optional JSON object UX as Vector 2 (`build_pending_static_values_from_form` / `static_secret_edit_template_vars`). A **Session** banner shows process identity (OS user, host, git user, CI actor) — not the bootstrap login token identity. **Sync all** (`/action/sync-all`), **Logout** (`/logout`), **Shutdown** (`/shutdown` — stops the server process after clearing the session cookie; uses a short delayed timer so the response can flush).
- **`--debug`** on `secretzero web` shows a **Debug log** panel at the bottom of the dashboard: JSON summaries of each sync (targets, skip reasons, errors). Never includes raw secret values.
- **Apply and sync** for static secrets runs `SyncEngine.sync(..., force_rotation=True)` so targets are written even when the lockfile already lists them as synced (otherwise sync would skip with “All targets already synced”).
- **Force to target:** when a secret has multiple target lanes and at least one other lane is **synced**, unsynced lanes can show a **Force to target** action (POST `/action/force-sync-target` with `secret_name` + `target_id`). This calls `SyncEngine.sync(secret_names=[...], force_targets={name: frozenset({target_id})})` to re-push one target without forcing every target. CLI: `secretzero sync -s NAME --force-target TARGET_ID`. Partial sync tries **destinations being written first** (including targets not yet in the lockfile), then other tracked targets; if read-back still fails (e.g. GitHub Actions secrets), set the secret’s **uppercase env var** (same name as sync uses) for that run so the value can be supplied without `--force-rotation`.
- Sync uses [`make_sync_engine`](../../src/secretzero/network_web_dashboard.py) (non-interactive `SyncEngine`) against the in-memory manifest + lockfile; not the Vector 2 form batch helper.
- Bootstrap access uses a **one-time** SHA-256 digest exchange, then **HttpOnly** session cookie + **CSRF** on mutating POSTs. Optional TLS: PEM paths or `--tls-self-signed` (SPKI SHA-256 printed for manual trust). Uvicorn is started with a **bounded `timeout_graceful_shutdown`** so HTTPS clients that keep connections alive do not block process exit after **Shut down** from the UI.
- **Rotate** on **`static`** secrets is a link (and POST handler redirect) to **`/secret/{name}/edit`** — rotating a static value means setting it in the form, not calling `force_rotation` sync (which would fail on unresolved `${ENV}` placeholders).

## Steps (when changing behavior)

1. Preserve the zero-leakage rule: never log submitted secret values.
2. Keep cookie `Secure` when HTTPS is enabled; `SameSite=Lax`.
3. After edits, run `task test` (includes `tests/test_network_webui.py`).

## Verify

- [ ] `uv run secretzero web --help` lists host/port/token/TLS options (no stale references to removed flags).
- [ ] Tests in `tests/test_network_webui.py` pass.
