# SecretZero MCP Server

SecretZero ships a first-party MCP server (`secretzero-mcp`) for agent hosts (Cursor, Claude Code, Hermes, etc.). It exposes metadata-only tools with spill guards enabled by default.

## Install

```bash
uv tool install -U "secretzero[mcp]"
# or from a clone:
uv sync --extra mcp
```

## Local stdio (default)

Point your MCP host at the repo or install:

```json
{
  "mcpServers": {
    "secretzero": {
      "command": "uv",
      "args": ["run", "--extra", "mcp", "secretzero-mcp"],
      "env": {
        "SECRETZERO_CONFIG": "/absolute/path/to/Secretfile.yml",
        "SZ_AGENT_MODE": "true"
      }
    }
  }
}
```

## Remote HTTP bridge

Run `secretzero-api` on the machine that holds the Secretfile. The MCP process on the agent host calls the API:

```json
{
  "mcpServers": {
    "secretzero": {
      "command": "uvx",
      "args": ["--from", "secretzero[mcp]", "secretzero-mcp"],
      "env": {
        "SZ_MCP_BACKEND": "http",
        "SECRETZERO_API_URL": "https://secretzero.internal:8000",
        "SECRETZERO_API_KEY": "${env:SECRETZERO_API_KEY}",
        "SZ_AGENT_MODE": "true"
      }
    }
  }
}
```

On the API host:

```bash
export SECRETZERO_CONFIG=/path/to/Secretfile.yml
export SECRETZERO_API_KEY=...
secretzero-api
```

## Agent bootstrap loop

1. `agent_sync` (metadata JSON)
2. If manual values needed → `agent_sync_web_start` → relay `web_url` to the operator
3. `agent_sync_web_poll` until `done`
4. Repeat until `pending_secrets` and `failed_secrets` are empty

## Mutations

Tier 3 tools (`sync_execute`, `rotate_execute`, `agent_adopt`, `clean_lockfile`, `ingest_preseed`) require:

```bash
export SZ_MCP_ALLOW_MUTATIONS=true
```

Plaintext reveal tools are not exposed by default.

## Verification

```bash
task test:mcp
```

See also: `skills/secretzero-agent/SKILL.md`, `skills/secretzero-author/SKILL.md`.
