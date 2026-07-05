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
secretzero mcp serve --help
secretzero mcp config generate --help
```

The standalone `secretzero-mcp` script remains available for backward compatibility; prefer `secretzero mcp serve`.

## Application config (`config.mcp`)

MCP defaults live in the same app config merge chain as LLM and discovery settings:

**defaults ← `~/.config/secretzero/config.yml` ← Secretfile `config` block**

Example `~/.config/secretzero/config.yml`:

```yaml
mcp:
  workspace: /path/to/your/repo
  client_format: cursor
  sz_agent_mode: true
  discover_local_only: true
  discover_provider: ollama
  serve_args:
    - mcp
    - serve
```

Or in `Secretfile.yml`:

```yaml
config:
  mcp:
    workspace: .
    server_name: secretzero

secrets: []
```

Show effective config: `secretzero config show --format yaml`

## Security defaults

The MCP server enables spill-safe semantics automatically:

| Setting / variable | Default | Purpose |
|--------------------|---------|---------|
| `config.mcp.sz_agent_mode` | `true` | Sets `SZ_AGENT_MODE` in generated host env |
| `SZ_WORKSPACE` / `config.mcp.workspace` | current directory | Project root for Secretfile/lockfile resolution |
| `SECRETZERO_CONFIG` | `Secretfile.yml` | Manifest path relative to workspace |
| `SZ_SANDBOX` | respected | Blocks `sz_sync` / `sz_rotate` writes unless `SZ_ALLOW_SYNC_IN_SANDBOX=true` |

**Reveal is blocked:** no tool accepts `reveal=true` or equivalent flags.

## Tools

| Tool | CLI parity | Description |
|------|------------|-------------|
| `sz_sync` | `secretzero sync --format json` | Reconcile Secretfile with targets |
| `sz_discover` | `secretzero discover --format json` | AI discovery (defaults from `config.mcp`) |
| `sz_status` | `secretzero status --format json` | Lockfile hashes, rotation, sync state |
| `sz_rotate` | `secretzero rotate --format json` | Force rotation policy |
| `sz_drift_check` | `secretzero drift --format json` | External target drift |

All tools support **multi-environment profiles** via the `environment` and `var_files` parameters (same semantics as CLI `--environment` / `--var-file`).

## Generate host client configuration

```bash
cd /path/to/your/project
secretzero mcp config generate --workspace . --format cursor -o .cursor/mcp.json
```

Formats:

```bash
# Cursor (.cursor/mcp.json style)
secretzero mcp config generate --format cursor -o .cursor/mcp.json

# Claude Desktop (merge into claude_desktop_config.json)
secretzero mcp config generate --format claude -o claude_mcp_snippet.json
```

Generated hosts invoke `secretzero mcp serve` (not a separate binary):

```json
{
  "command": "secretzero",
  "args": ["mcp", "serve"],
  "env": {
    "SZ_AGENT_MODE": "true",
    "SZ_WORKSPACE": "/path/to/project"
  }
}
```

Legacy: `secretzero-mcp --generate-config` still works but prints a deprecation notice; use `secretzero mcp config generate` instead. The filename `mcp_config.json` was only ever a suggested **output** path for that generator — the application does not read it at runtime.

## Claude Desktop

1. Install `secretzero[mcp]` so `secretzero` is on `PATH`.
2. Generate config: `secretzero mcp config generate --format claude --workspace /your/repo`
3. Merge the `mcpServers.secretzero` block into:

   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`

4. Restart Claude Desktop.

## Cursor

1. Run `secretzero mcp config generate --format cursor -o .cursor/mcp.json` in your repo.
2. Reload MCP servers in Cursor settings.

## VS Code / GitHub Copilot

Use the generic format and adapt to your client's MCP schema. Point `command` at `secretzero` with args `["mcp", "serve"]` and set `SZ_WORKSPACE` to your repository root.

## Manual stdio test

Use the [MCP Inspector](https://github.com/modelcontextprotocol/inspector):

```bash
npx -y @modelcontextprotocol/inspector secretzero mcp serve
```

Set `SZ_WORKSPACE` in the inspector environment panel when testing against a specific repo.

## Agent workflow notes

- Prefer `sz_status` and `sz_drift_check` before mutating operations.
- Use `sz_discover` for credential inventory — **do not** read `.env` or secret files via IDE/MCP filesystem tools.
- For human-in-the-loop seeding, use `secretzero agent sync --web` (CLI) — the MCP server does not collect plaintext input.
- See `skills/secretzero-agent/SKILL.md` and `AGENTS.md` for the full agent contract.
