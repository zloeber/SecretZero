"""Gated mutation helpers for MCP LocalBackend."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from secretzero.api.parity_services import (
    api_agent_adopt,
    api_clean_lockfile,
    api_import_check,
    api_ingest_preseed,
    api_rotate_check,
    api_rotate_execute,
    api_sync_execute,
)
from secretzero.mcp.config import McpConfig


def run_sync_dry_run(
    cfg: McpConfig,
    *,
    secret_name: str | None = None,
    refresh: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    return api_sync_execute(
        cfg.secretfile_path,
        dry_run=True,
        force=force,
        refresh=refresh,
        secret_name=secret_name,
        environment=cfg.environment,
    )


def run_sync_execute(
    cfg: McpConfig,
    *,
    secret_name: str | None = None,
    refresh: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    return api_sync_execute(
        cfg.secretfile_path,
        dry_run=False,
        force=force,
        refresh=refresh,
        secret_name=secret_name,
        environment=cfg.environment,
    )


def run_rotate_check(cfg: McpConfig, *, secret_name: str | None = None) -> dict[str, Any]:
    return api_rotate_check(cfg.secretfile_path, secret_name=secret_name)


def run_rotate_execute(
    cfg: McpConfig,
    *,
    secret_name: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    return api_rotate_execute(cfg.secretfile_path, secret_name=secret_name, force=force)


def run_agent_adopt(
    cfg: McpConfig,
    *,
    target: str | None = None,
    source_dir: str | None = None,
    output_dir: str | None = None,
    template: bool = False,
    preseed_lockfile: bool = False,
    dry_run: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    return api_agent_adopt(
        target=target,
        source_dir=source_dir,
        output_dir=output_dir,
        template=template,
        preseed_lockfile=preseed_lockfile,
        dry_run=dry_run,
        force=force,
    )


def run_clean_lockfile(cfg: McpConfig, *, dry_run: bool = True) -> dict[str, Any]:
    return api_clean_lockfile(
        cfg.secretfile_path,
        environment=cfg.environment,
        dry_run=dry_run,
    )


def run_ingest_preseed(
    cfg: McpConfig,
    *,
    source: str,
    dry_run: bool = True,
) -> dict[str, Any]:
    return api_ingest_preseed(
        cfg.secretfile_path,
        source=source,
        environment=cfg.environment,
        dry_run=dry_run,
    )


def run_drift_check(
    cfg: McpConfig,
    *,
    secret_name: str | None = None,
) -> dict[str, Any]:
    return api_import_check(
        cfg.secretfile_path,
        environment=cfg.environment,
        secret_name=secret_name,
    )
