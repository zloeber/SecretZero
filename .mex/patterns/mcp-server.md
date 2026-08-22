---
name: mcp-server
description: Native MCP server exposing SecretZero orchestration tools with spill guards.
triggers:
  - "mcp server"
  - "secretzero-mcp"
  - "sz_sync"
edges:
  - target: patterns/sz-agent-mode-spill-guard.md
    condition: when adjusting spill-safe behavior for agent clients
last_updated: 2026-08-21
---

# MCP Server

## Context
`src/secretzero/mcp_server.py` exposes stdio MCP tools with CLI/API parity. Business logic lives in `SyncEngine`, `Lockfile`, `DriftDetector`, and `DiscoveryAgent` — do not duplicate orchestration in tool handlers.

## Steps
1. Add or change tools in `create_mcp_server()` via `resolve_mcp_server_cls()` — prefers `mcp.server.MCPServer` (SDK 2.x), falls back to `mcp.server.fastmcp.FastMCP` (SDK 1.x).
2. Route Secretfile loading through `resolve_mcp_paths()` + `_load_secretfile()` for environment/profile parity.
3. Set `sync_client="mcp"` on `SyncEngine` for lockfile provenance.
4. Sanitize all responses with `_sanitize_payload()`; block reveal params via `_reject_reveal_params()`.
5. Keep `SZ_AGENT_MODE=true` default in `ensure_agent_mode()`.
6. Add tests in `tests/test_mcp_server.py`; document client wiring in `docs/mcp-setup.md`.
7. Optional extra: `secretzero[mcp]` (`mcp>=1.27`). Both 1.x and 2.x majors are supported; do not pin `mcp>=2` alone — it conflicts with hosts that depend on `fastmcp` (`mcp<2`).
8. Prefer `secretzero mcp serve` and `secretzero mcp config generate`; keep `secretzero-mcp` as a deprecated wrapper.

## Gotchas
- MCP tools are non-interactive — always `prompt_on_empty=False`.
- Never return `raw_value` from discovery; strip in `_discover_candidates_payload()`.
- SDK 2.x `call_tool` returns `CallToolResult` (`structured_content` / `content`); 1.x may return a `(content, structured)` tuple — `_call_tool` helpers in tests handle both.
- Missing-SDK errors must report the installed `mcp` version when present (avoid a bare "install secretzero[mcp]" when the extra is already installed but the API surface cannot be resolved).
- Do not expose `get --reveal`, `render`, or backup print tools over MCP.

## Verify
- [ ] `pytest tests/test_mcp_server.py` passes
- [ ] `secretzero-mcp --generate-config` emits valid JSON
- [ ] Tool responses contain hashes/metadata only
