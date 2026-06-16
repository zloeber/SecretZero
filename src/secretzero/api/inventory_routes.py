"""HTTP inventory endpoints delegating to LocalBackend on the API host."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, status

from secretzero.api.auth import RequireAuth
from secretzero.mcp.backend.local import LocalBackend
from secretzero.mcp.config import McpConfig


def _local_backend(app: FastAPI, environment: str | None = None) -> LocalBackend:
    config_path = Path(app.state.secretfile_path)
    if not config_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Secretfile not found")
    cfg = McpConfig(
        backend="local",
        secretfile_path=config_path,
        lockfile_path=None,
        environment=environment,
        workspace_root=config_path.parent,
        api_url=None,
        api_key=None,
        allow_mutations=False,
        allow_reveal=False,
        force_agent_mode=True,
        sz_agent=False,
    )
    return LocalBackend(cfg)


def register_inventory_routes(app: FastAPI) -> None:
    @app.get("/inventory/status")
    async def inventory_status(
        _auth: str = RequireAuth, environment: str | None = Query(default=None)
    ):
        return _local_backend(app, environment).secrets_status()

    @app.get("/inventory/secrets")
    async def inventory_secrets(
        _auth: str = RequireAuth,
        name_filter: str | None = Query(default=None),
        environment: str | None = Query(default=None),
    ):
        return _local_backend(app, environment).secrets_list(name_filter=name_filter)

    @app.get("/inventory/providers")
    async def inventory_providers(
        _auth: str = RequireAuth, environment: str | None = Query(default=None)
    ):
        return _local_backend(app, environment).providers_list()

    @app.get("/inventory/targets")
    async def inventory_targets(
        _auth: str = RequireAuth, environment: str | None = Query(default=None)
    ):
        return _local_backend(app, environment).targets_list()

    @app.get("/inventory/variables")
    async def inventory_variables(
        _auth: str = RequireAuth,
        name_filter: str | None = Query(default=None),
        environment: str | None = Query(default=None),
    ):
        return _local_backend(app, environment).variables_list(name_filter=name_filter)

    @app.get("/manifest/validate")
    async def manifest_validate(
        _auth: str = RequireAuth, environment: str | None = Query(default=None)
    ):
        return _local_backend(app, environment).secretfile_validate()
