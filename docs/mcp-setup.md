# SecretZero MCP Server Setup

SecretZero ships a native [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server that exposes orchestration tools with **metadata-only** responses. Plaintext secret values are never returned to the host LLM.

## Install

```bash
uv tool install -U "secretzero[mcp]"
# or from a checkout:
uv sync --extra mcp && source .venv/bin/activate
```

Verify:

```bash
secretzero-mcp --help
```

## Security defaults

The MCP server enables spill-safe semantics automatically:

| Variable | Default in MCP | Purpose |
|----------|----------------|---------|
| `SZ_AGENT_MODE` | `true` (set if unset) | Blocks reveal/plaintext dumps |
| `SZ_WORKSPACE` | current directory | Project root for Secretfile/lockfile resolution |
| `SECRETZERO_CONFIG` | `Secretfile.yml` | Manifest path relative to workspace |
| `SZ_SANDBOX` | respected | Blocks `sz_sync` / `sz_rotate` writes unless `SZ_ALLOW_SYNC_IN_SANDBOX=true` |

**Reveal is blocked:** no tool accepts `reveal=true` or equivalent flags.

## Tools

| Tool | CLI parity | Description |
|------|------------|-------------|
| `sz_sync` | `secretzero sync --format json` | Reconcile Secretfile with targets |
| `sz_discover` | `secretzero discover --format json` | AI discovery (Ollama by default) |
| `sz_status` | `secretzero status --format json` | Lockfile hashes, rotation, sync state |
| `sz_rotate` | `secretzero rotate --format json` | Force rotation policy |
| `sz_drift_check` | `secretzero drift --format json` | External target drift |

All tools support **multi-environment profiles** via the `environment` and `var_files` parameters (same semantics as CLI `--environment` / `--var-file`).

## Generate client configuration

```bash
cd /path/to/your/project
secretzero-mcp --generate-config --workspace . --output mcp_config.json
```

Formats:

```bash
# Cursor (.cursor/mcp.json style)
secretzero-mcp --generate-config --format cursor -o .cursor/mcp.json

# Claude Desktop (merge into claude_desktop_config.json)
secretzero-mcp --generate-config --format claude -o claude_mcp_snippet.json
```

Example generated entry:

```json
{
  "command": "secretzero-mcp",
  "args": [],
  "env": {
    "SZ_AGENT_MODE": "true",
    "SZ_WORKSPACE": "/path/to/project"
  }
}
```

## Claude Desktop

1. Install `secretzero[mcp]` so `secretzero-mcp` is on `PATH`.
2. Generate config: `secretzero-mcp --generate-config --format claude --workspace /your/repo`
3. Merge the `mcpServers.secretzero` block into:

   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`

4. Restart Claude Desktop.

## Cursor

1. Run `secretzero-mcp --generate-config --format cursor -o .cursor/mcp.json` in your repo (or merge manually).
2. Reload MCP servers in Cursor settings.

## VS Code / GitHub Copilot

Use the generic config and adapt to your client's MCP schema. Point `command` at the `secretzero-mcp` executable and set `SZ_WORKSPACE` to your repository root.

## Manual stdio test

Use the [MCP Inspector](https://github.com/modelcontextprotocol/inspector):

```bash
npx -y @modelcontextprotocol/inspector secretzero-mcp
```

Set `SZ_WORKSPACE` in the inspector environment panel when testing against a specific repo.

## Agent workflow notes

- Prefer `sz_status` and `sz_drift_check` before mutating operations.
- Use `sz_discover` for credential inventory — **do not** read `.env` or secret files via IDE/MCP filesystem tools.
- For human-in-the-loop seeding, use `secretzero agent sync --web` (CLI) — the MCP server does not collect plaintext input.
- See `skills/secretzero-agent/SKILL.md` and `AGENTS.md` for the full agent contract.
