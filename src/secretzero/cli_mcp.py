"""CLI commands for the SecretZero MCP server and host client configuration."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from secretzero.mcp_server import generate_mcp_config, run_stdio_server


@click.group("mcp")
def mcp_group() -> None:
    """Run the MCP server or generate host client configuration.

    The stdio server exposes metadata-only tools (``sz_sync``, ``sz_discover``,
    ``sz_status``, ``sz_rotate``, ``sz_drift_check``). Configure defaults via
    ``config.mcp`` in ``~/.config/secretzero/config.yml`` or the Secretfile
    ``config`` block.
    """


@mcp_group.command("serve")
def serve() -> None:
    """Start the SecretZero MCP server on stdio (for Cursor, Claude Desktop, etc.)."""
    try:
        run_stdio_server()
    except ImportError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


@mcp_group.group("config")
def mcp_config_group() -> None:
    """Generate MCP host client configuration snippets."""


@mcp_config_group.command("generate")
@click.option(
    "--file",
    "-f",
    type=click.Path(),
    default="Secretfile.yml",
    help="Secretfile used to merge project ``config.mcp`` settings",
)
@click.option(
    "--workspace",
    type=click.Path(),
    default=None,
    help="Repository root (overrides config.mcp.workspace and SZ_WORKSPACE)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Write JSON to this path (default: stdout only)",
)
@click.option(
    "--format",
    "format_name",
    type=click.Choice(["generic", "cursor", "claude"]),
    default=None,
    help="Host config shape (default from config.mcp.client_format)",
)
@click.option(
    "--command",
    default=None,
    help="Override MCP server executable in generated config",
)
def config_generate(
    file: str,
    workspace: str | None,
    output: str | None,
    format_name: str | None,
    command: str | None,
) -> None:
    """Emit MCP client configuration for AI hosts.

    Defaults come from effective app config (``config.mcp``): defaults ←
    ``~/.config/secretzero/config.yml`` ← Secretfile ``config`` block.
    """
    secretfile_path = Path(file)
    output_path = Path(output) if output else None
    workspace_path = Path(workspace).resolve() if workspace else None

    payload = generate_mcp_config(
        workspace=workspace_path,
        output_path=output_path,
        command=command,
        format_name=format_name,
        secretfile_path=secretfile_path if secretfile_path.exists() else None,
    )
    if output_path is None:
        click.echo(json.dumps(payload, indent=2))


def run_legacy_entrypoint() -> None:
    """Backward-compatible entry point for the ``secretzero-mcp`` script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="SecretZero MCP server (stdio) — prefer: secretzero mcp serve",
    )
    parser.add_argument(
        "--generate-config",
        action="store_true",
        help="Deprecated: use `secretzero mcp config generate`",
    )
    parser.add_argument("--output", "-o", type=Path, default=None)
    parser.add_argument("--workspace", type=Path, default=None)
    parser.add_argument(
        "--format",
        choices=["generic", "cursor", "claude"],
        default=None,
    )
    parser.add_argument("--command", default=None)
    args, _unknown = parser.parse_known_args()

    if args.generate_config:
        click.echo(
            "Note: --generate-config is deprecated; use `secretzero mcp config generate`.",
            err=True,
        )
        payload = generate_mcp_config(
            workspace=args.workspace,
            output_path=args.output,
            command=args.command,
            format_name=args.format,
        )
        click.echo(json.dumps(payload, indent=2))
        return

    try:
        run_stdio_server()
    except ImportError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
