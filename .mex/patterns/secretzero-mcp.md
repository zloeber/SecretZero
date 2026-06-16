# SecretZero MCP Server

Use when adding or changing the first-party MCP server (`secretzero-mcp`), HttpBackend, or MCP/API parity endpoints.

## Layout

```
src/secretzero/mcp/
  server.py          # stdio entry
  app.py             # FastMCP tool registration
  config.py          # env + CLI flags
  guards.py          # spill guards + mutation allowlists
  agent_ops.py       # agent sync / web / instructions
  mutation_ops.py    # gated sync/rotate/adopt/clean/ingest
  discovery_ops.py   # detect / discover
  backend/local.py   # in-process SDK
  backend/http.py    # secretzero-api client
src/secretzero/api/
  parity_services.py # shared API logic
  parity_routes.py   # /catalog, /detect, /discover, ...
  inventory_routes.py # /inventory/* delegates to LocalBackend on API host
```

## Non-negotiables

- Default `SZ_AGENT_MODE=true` at MCP startup.
- No sampling handlers; discovery via `detect_secrets` / `discover_bindings` only.
- All tool JSON passes through `sanitize_tool_result`.
- Mutations gated by `SZ_MCP_ALLOW_MUTATIONS` (`MUTATION_TOOLS` in `guards.py`).
- CLI + API + MCP feature parity for agent sync vectors.

## Verify

```bash
task test:mcp
uv run python -m pytest tests/test_api_mcp_parity.py -v --no-cov
```

## Docs/skills

After tool surface changes, update:

- `docs/user-guide/mcp.md`
- `skills/secretzero-author/SKILL.md` (Hermes + MCP table)
- `skills/secretzero-agent/SKILL.md` (API/MCP parity note)
- `.mex/ROUTER.md` project state
