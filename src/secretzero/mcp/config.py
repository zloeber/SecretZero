"""MCP server configuration from environment and CLI flags."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


def _truthy(raw: str | None) -> bool:
    if raw is None:
        return False
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _parse_argv(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="secretzero-mcp", add_help=True)
    parser.add_argument(
        "--backend",
        choices=("local", "http"),
        default=None,
        help="Backend mode: local in-process SDK or http API bridge",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to Secretfile.yml (local backend)",
    )
    parser.add_argument(
        "--lockfile",
        default=None,
        help="Lockfile path override",
    )
    parser.add_argument(
        "--environment",
        "-e",
        default=None,
        help="Environment lane name",
    )
    parser.add_argument(
        "--workspace-root",
        default=None,
        help="Path jail root for detect/discover (defaults to Secretfile parent)",
    )
    parser.add_argument(
        "--api-url",
        default=None,
        help="secretzero-api base URL (http backend)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key for http backend",
    )
    return parser.parse_args(argv)


@dataclass(frozen=True)
class McpConfig:
    """Resolved MCP server configuration."""

    backend: Literal["local", "http"]
    secretfile_path: Path
    lockfile_path: str | None
    environment: str | None
    workspace_root: Path
    api_url: str | None
    api_key: str | None
    allow_mutations: bool
    allow_reveal: bool
    force_agent_mode: bool
    sz_agent: bool


def load_mcp_config(argv: list[str] | None = None) -> McpConfig:
    """Load MCP configuration from CLI flags and environment variables."""
    args = _parse_argv(argv or [])

    backend_raw = args.backend or os.environ.get("SZ_MCP_BACKEND", "local")
    backend = backend_raw.strip().lower()
    if backend not in ("local", "http"):
        raise ValueError(f"Invalid SZ_MCP_BACKEND: {backend_raw!r} (expected local or http)")

    config_raw = args.config or os.environ.get("SECRETZERO_CONFIG", "Secretfile.yml")
    secretfile_path = Path(config_raw).expanduser()
    if not secretfile_path.is_absolute():
        secretfile_path = (Path.cwd() / secretfile_path).resolve()

    lockfile_path = args.lockfile or os.environ.get("SECRETZERO_LOCKFILE")
    environment = args.environment or os.environ.get("SECRETZERO_ENVIRONMENT")

    workspace_raw = args.workspace_root or os.environ.get("SZ_MCP_WORKSPACE_ROOT")
    if workspace_raw:
        workspace_root = Path(workspace_raw).expanduser().resolve()
    else:
        workspace_root = secretfile_path.parent.resolve()

    api_url = args.api_url or os.environ.get("SECRETZERO_API_URL")
    api_key = args.api_key or os.environ.get("SECRETZERO_API_KEY")

    if backend == "http":
        if not api_url:
            raise ValueError("http backend requires SECRETZERO_API_URL or --api-url")
        if not api_key:
            raise ValueError("http backend requires SECRETZERO_API_KEY or --api-key")

    spill_guard_off = _truthy(os.environ.get("SZ_MCP_SPILL_GUARD"))
    force_agent_mode = not spill_guard_off

    return McpConfig(
        backend=backend,  # type: ignore[arg-type]
        secretfile_path=secretfile_path,
        lockfile_path=lockfile_path,
        environment=environment,
        workspace_root=workspace_root,
        api_url=api_url.rstrip("/") if api_url else None,
        api_key=api_key,
        allow_mutations=_truthy(os.environ.get("SZ_MCP_ALLOW_MUTATIONS")),
        allow_reveal=_truthy(os.environ.get("SZ_MCP_ALLOW_REVEAL")),
        force_agent_mode=force_agent_mode,
        sz_agent=_truthy(os.environ.get("SZ_AGENT")),
    )
