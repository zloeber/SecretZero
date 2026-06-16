"""Register MCP tools and resources for SecretZero."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from secretzero.mcp.backend.protocol import SecretZeroBackend
from secretzero.mcp.config import McpConfig
from secretzero.mcp.guards import assert_tool_allowed, sanitize_error_message, sanitize_tool_result


def create_mcp_app(cfg: McpConfig, backend: SecretZeroBackend) -> FastMCP:
    """Build a FastMCP application with Tier 1 read-only tools."""
    read_only = ToolAnnotations(readOnlyHint=True)
    app = FastMCP(
        "secretzero",
        instructions=(
            "SecretZero secrets-as-code MCP server. Metadata-only by default; "
            "never returns plaintext secret values under SZ_AGENT_MODE."
        ),
    )

    def _ok(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        return sanitize_tool_result(tool_name, payload)

    @app.tool(name="catalog_list", annotations=read_only)
    def catalog_list(
        provider: str | None = None,
        bundle: str | None = None,
        kind: str | None = None,
    ) -> dict[str, Any]:
        """List generator, target, and bundle kinds from the live registry."""
        return _ok(
            "catalog_list", backend.catalog_list(provider=provider, bundle=bundle, kind=kind)
        )

    @app.tool(name="schema_get", annotations=read_only)
    def schema_get() -> dict[str, Any]:
        """Return the JSON Schema for Secretfile.yml."""
        return _ok("schema_get", backend.schema_get())

    @app.tool(name="secretfile_validate", annotations=read_only)
    def secretfile_validate() -> dict[str, Any]:
        """Validate the configured Secretfile manifest."""
        return _ok("secretfile_validate", backend.secretfile_validate())

    @app.tool(name="secrets_list", annotations=read_only)
    def secrets_list(name_filter: str | None = None) -> dict[str, Any]:
        """List secrets defined in the configured Secretfile."""
        return _ok("secrets_list", backend.secrets_list(name_filter=name_filter))

    @app.tool(name="secrets_status", annotations=read_only)
    def secrets_status() -> dict[str, Any]:
        """Return sync status for secrets and targets."""
        return _ok("secrets_status", backend.secrets_status())

    @app.tool(name="providers_list", annotations=read_only)
    def providers_list() -> dict[str, Any]:
        """List configured providers and identity preflight metadata."""
        return _ok("providers_list", backend.providers_list())

    @app.tool(name="targets_list", annotations=read_only)
    def targets_list() -> dict[str, Any]:
        """List all secret targets with spill-safe config redaction."""
        return _ok("targets_list", backend.targets_list())

    @app.tool(name="variables_list", annotations=read_only)
    def variables_list(name_filter: str | None = None) -> dict[str, Any]:
        """List manifest variable names (values redacted under agent mode)."""
        return _ok("variables_list", backend.variables_list(name_filter=name_filter))

    @app.tool(name="detect_secrets", annotations=read_only)
    def detect_secrets(directory: str | None = None, all_keys: bool = False) -> dict[str, Any]:
        """Scan for dotenv-style secret key names without returning values."""
        return _ok(
            "detect_secrets",
            backend.detect_secrets(directory=directory, all_keys=all_keys),
        )

    @app.tool(name="discover_bindings", annotations=read_only)
    def discover_bindings(
        directory: str | None = None,
        local_only: bool = True,
    ) -> dict[str, Any]:
        """Run pattern-based secret discovery and return symbol bindings metadata."""
        return _ok(
            "discover_bindings",
            backend.discover_bindings(directory=directory, local_only=local_only),
        )

    @app.tool(name="version_info", annotations=read_only)
    def version_info(detailed: bool = False) -> dict[str, Any]:
        """Return SecretZero version and runtime metadata."""
        return _ok("version_info", backend.version_info(detailed=detailed))

    @app.tool(name="agent_sync")
    def agent_sync(
        dry_run: bool = False,
        refresh: bool = True,
        web: bool = False,
        sz_agent: bool | None = None,
    ) -> dict[str, Any]:
        """Unified agent bootstrap sync (metadata-only JSON; never returns secret values)."""
        return _ok(
            "agent_sync",
            backend.agent_sync(
                dry_run=dry_run,
                refresh=refresh,
                web=web,
                sz_agent=sz_agent,
            ),
        )

    @app.tool(name="agent_sync_web_start")
    def agent_sync_web_start(dry_run: bool = False, refresh: bool = True) -> dict[str, Any]:
        """Start Vector 2 localhost web form for pending manual secrets."""
        return _ok(
            "agent_sync_web_start",
            backend.agent_sync_web_start(dry_run=dry_run, refresh=refresh),
        )

    @app.tool(name="agent_sync_web_poll", annotations=read_only)
    def agent_sync_web_poll(session_id: str) -> dict[str, Any]:
        """Poll a Vector 2 web session until the operator submits the form."""
        return _ok("agent_sync_web_poll", backend.agent_sync_web_poll(session_id))

    @app.tool(name="agent_instructions", annotations=read_only)
    def agent_instructions(
        show_all: bool = False,
        detailed: bool = False,
        secret_names: list[str] | None = None,
    ) -> dict[str, Any]:
        """Return templated manual steps for pending or all secrets with instructions."""
        return _ok(
            "agent_instructions",
            backend.agent_instructions(
                show_all=show_all,
                detailed=detailed,
                secret_names=secret_names,
            ),
        )

    @app.tool(name="drift_check", annotations=read_only)
    def drift_check(secret_name: str | None = None) -> dict[str, Any]:
        """Report lockfile/target drift without importing values."""
        return _ok("drift_check", backend.drift_check(secret_name=secret_name))

    @app.tool(name="sync_dry_run", annotations=read_only)
    def sync_dry_run(
        secret_name: str | None = None,
        refresh: bool = True,
        force: bool = False,
    ) -> dict[str, Any]:
        """Plan a sync run without writing targets or the lockfile."""
        return _ok(
            "sync_dry_run",
            backend.sync_dry_run(secret_name=secret_name, refresh=refresh, force=force),
        )

    def _mutation(tool_name: str, fn):
        assert_tool_allowed(tool_name)
        return _ok(tool_name, fn())

    @app.tool(name="sync_execute")
    def sync_execute(
        secret_name: str | None = None,
        refresh: bool = True,
        force: bool = False,
    ) -> dict[str, Any]:
        """Execute sync and write targets plus lockfile (requires SZ_MCP_ALLOW_MUTATIONS)."""
        return _mutation(
            "sync_execute",
            lambda: backend.sync_execute(secret_name=secret_name, refresh=refresh, force=force),
        )

    @app.tool(name="rotate_check", annotations=read_only)
    def rotate_check(secret_name: str | None = None) -> dict[str, Any]:
        """List secrets due or overdue for rotation."""
        return _ok("rotate_check", backend.rotate_check(secret_name=secret_name))

    @app.tool(name="rotate_execute")
    def rotate_execute(secret_name: str | None = None, force: bool = False) -> dict[str, Any]:
        """Rotate secrets and sync (requires SZ_MCP_ALLOW_MUTATIONS)."""
        return _mutation(
            "rotate_execute",
            lambda: backend.rotate_execute(secret_name=secret_name, force=force),
        )

    @app.tool(name="agent_adopt")
    def agent_adopt(
        target: str | None = None,
        source_dir: str | None = None,
        output_dir: str | None = None,
        template: bool = False,
        preseed_lockfile: bool = False,
        dry_run: bool = True,
        force: bool = False,
    ) -> dict[str, Any]:
        """Bootstrap SecretZero from Hermes/OpenClaw (dry_run defaults true)."""
        return _mutation(
            "agent_adopt",
            lambda: backend.agent_adopt(
                target=target,
                source_dir=source_dir,
                output_dir=output_dir,
                template=template,
                preseed_lockfile=preseed_lockfile,
                dry_run=dry_run,
                force=force,
            ),
        )

    @app.tool(name="clean_lockfile")
    def clean_lockfile(dry_run: bool = True) -> dict[str, Any]:
        """Remove orphaned lockfile entries (requires SZ_MCP_ALLOW_MUTATIONS when not dry_run)."""
        if not dry_run:
            assert_tool_allowed("clean_lockfile")
        return _ok("clean_lockfile", backend.clean_lockfile(dry_run=dry_run))

    @app.tool(name="ingest_preseed")
    def ingest_preseed(source: str, dry_run: bool = True) -> dict[str, Any]:
        """Import lockfile hashes from a local preseed file path on the API host."""
        if not dry_run:
            assert_tool_allowed("ingest_preseed")
        return _ok(
            "ingest_preseed",
            backend.ingest_preseed(source=source, dry_run=dry_run),
        )

    @app.resource("secretzero://schema", mime_type="application/json")
    def resource_schema() -> str:
        return json.dumps(backend.schema_get(), indent=2)

    @app.resource("secretzero://catalog", mime_type="application/json")
    def resource_catalog() -> str:
        return json.dumps(backend.catalog_list(), indent=2)

    @app.resource("secretzero://inventory", mime_type="application/json")
    def resource_inventory() -> str:
        payload = sanitize_tool_result("secrets_status", backend.secrets_status())
        return json.dumps(payload, indent=2, default=str)

    @app.resource("secretzero://manifest", mime_type="text/yaml")
    def resource_manifest() -> str:
        if cfg.backend != "local":
            return "# Manifest resource requires local backend\n"
        from secretzero.mcp.workspace import load_workspace

        ws = load_workspace(cfg)
        return ws.secretfile_path.read_text(encoding="utf-8")

    @app.resource("secretzero://lockfile", mime_type="application/json")
    def resource_lockfile() -> str:
        if cfg.backend != "local":
            return json.dumps({"error": "Lockfile resource requires local backend"})
        from secretzero.mcp.workspace import load_workspace

        ws = load_workspace(cfg)
        return json.dumps(ws.lockfile.model_dump(mode="json"), indent=2, default=str)

    return app
