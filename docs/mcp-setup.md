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

## Modality parity

MCP is **not** a full replacement for the CLI, REST API, or `secretzero web`. It is a **fifth modality** scoped for agent hosts: metadata-only orchestration over stdio with spill guards enabled by default.

For the operations it exposes, MCP calls the **same core engines** as CLI/API (`SyncEngine`, `DriftDetector`, `DiscoveryAgent`, `Lockfile`, environment profile resolution). Responses are sanitized; business logic is not reimplemented in tool handlers.

### Covered on MCP (aligned semantics)

| MCP tool | CLI | API | Notes |
|----------|-----|-----|-------|
| `sz_sync` | `secretzero sync --format json` | `POST /sync` | Non-interactive (`prompt_on_empty=False`); supports `dry_run`, `secrets`, `environment`, `var_files`, `refresh` |
| `sz_status` | `secretzero status --format json` | `GET /secrets`, `GET /secrets/{name}/status` | Includes lockfile hashes, per-target sync state, provider identity, sync readiness |
| `sz_rotate` | `secretzero rotate --format json` | `POST /rotation/check`, `POST /rotation/execute` | Supports `force`, `dry_run`, per-secret filter |
| `sz_drift_check` | `secretzero drift --format json` | `POST /drift/check` | Requires existing lockfile |
| `sz_discover` | `secretzero discover --format json` | — | Defaults from `config.mcp`; never returns candidate values |

Shared across these paths: multi-environment `environment` / `var_files`, local+shared lockfile merge, `sync_client="mcp"` provenance, and `SZ_AGENT_MODE` spill contract.

### Intentionally not on MCP (by design)

| Capability | CLI | API | Web | Why not MCP |
|------------|-----|-----|-----|-------------|
| **Agent bootstrap / seeding** (`agent sync`, Vector 2 `--web`) | ✅ | `POST /agent/sync` | one-shot form | Requires human-in-the-loop or structured bootstrap output; MCP has no plaintext input channel |
| **Plaintext retrieval** (`get --reveal`, `render`, backup `--print`) | ✅ (guarded) | partial | dashboard edit | Zero-leakage rule for LLM-connected hosts |
| **Interactive prompts** (missing static fields) | ✅ | — | ✅ | MCP is non-interactive |
| **`secretzero web` dashboard** | ✅ | — | ✅ | Separate bindable UI modality (sync, rotate, import, graph, manifest views) |

Use CLI or API for bootstrap loops; use MCP for ongoing metadata-only maintenance after secrets are seeded.

### Available on CLI/API but not yet on MCP

These use the same backends and may be added later; today agents should fall back to CLI subprocess or REST API:

| Capability | CLI | API |
|------------|-----|-----|
| Validate manifest | `secretzero validate` | `POST /config/validate` |
| Policy check | `secretzero policy` | `POST /policy/check` |
| Lockfile import / preseed | `secretzero import`, `ingest preseed` | — |
| Provider connectivity test | `secretzero test` | — |
| Catalog / list providers & targets | `secretzero catalog`, `list *` | `GET /list/*`, `GET /secret-types` |
| Agent instructions report | `secretzero agent instructions` | — |
| Per-target force sync | `sync --force-target` | — (CLI + web today) |
| Graph / Terraform export | `graph`, `terraform` | `GET /graph` |
| Backup / restore | `secretzero backup` | — |
| Audit log query | — | `GET /audit/logs` |

### Recommended agent workflow

1. **Bootstrap (CLI/API only):** `secretzero agent sync --json` until `pending_secrets` and `failed_secrets` are empty; use `--web` for Vector 2 human input.
2. **Ongoing ops (MCP or CLI):** `sz_status` → `sz_sync` / `sz_rotate` / `sz_drift_check` as needed.
3. **Authoring (MCP + CLI):** `sz_discover` for inventory; edit `Secretfile.yml`; `secretzero validate` via CLI; dry-run with `sz_sync(dry_run=true)`.

See also `skills/secretzero-agent/SKILL.md` for the MCP gap callout on bootstrap.

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
