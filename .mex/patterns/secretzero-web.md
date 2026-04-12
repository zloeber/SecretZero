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
    condition: when changing auth, TLS, or templates
last_updated: 2026-04-12
---

# `secretzero web` (network seeding UI)

## Context

- Implementation: [`src/secretzero/network_webui.py`](../../src/secretzero/network_webui.py), Jinja templates in [`src/secretzero/network_web_templates_jinja.py`](../../src/secretzero/network_web_templates_jinja.py), CLI in [`src/secretzero/cli.py`](../../src/secretzero/cli.py) (`web_command`).
- Sync path reuses [`sync_pending_secrets_from_web_form`](../../src/secretzero/agent_webui.py) with the same semantics as Vector 2 localhost forms.
- Bootstrap access uses a **one-time** SHA-256 digest exchange, then **HttpOnly** session cookie + **CSRF** on submit. Optional TLS: PEM paths or `--tls-self-signed` (SPKI SHA-256 printed for manual trust).

## Steps (when changing behavior)

1. Preserve the zero-leakage rule: never log submitted secret values.
2. Keep cookie `Secure` when HTTPS is enabled; `SameSite=Lax`.
3. After edits, run `task test` (includes `tests/test_network_webui.py`).

## Verify

- [ ] `uv run secretzero web --help` lists host/port/token/TLS options.
- [ ] Tests in `tests/test_network_webui.py` pass.
