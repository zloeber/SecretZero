"""Register MCP/API parity routes on the FastAPI application."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, status

from secretzero.api.auth import RequireAuth
from secretzero.api.parity_services import (
    api_agent_adopt,
    api_agent_instructions,
    api_agent_list,
    api_catalog,
    api_clean_lockfile,
    api_detect,
    api_discover,
    api_import_check,
    api_ingest_preseed,
    api_sync_execute,
    api_version,
)
from secretzero.api.schemas import (
    AgentAdoptRequest,
    AgentAdoptResponse,
    AgentInstructionsResponse,
    AgentListResponse,
    CatalogResponse,
    CleanLockfileRequest,
    CleanLockfileResponse,
    DetectRequest,
    DetectResponse,
    DiscoverRequest,
    DiscoverResponse,
    ImportCheckRequest,
    ImportCheckResponse,
    IngestPreseedRequest,
    IngestPreseedResponse,
    SyncExecuteRequest,
    SyncExecuteResponse,
    VersionResponse,
)
from secretzero.models import Secretfile


def register_parity_routes(app: FastAPI) -> None:
    """Attach parity endpoints used by HttpBackend and MCP tooling."""

    @app.get("/version", response_model=VersionResponse)
    async def get_version(detailed: bool = Query(default=False)):
        """Return SecretZero version metadata."""
        return VersionResponse(**api_version(detailed=detailed))

    @app.get("/catalog", response_model=CatalogResponse)
    async def get_catalog(
        _auth: str = RequireAuth,
        bundle: str | None = Query(default=None),
        provider_kind: str | None = Query(default=None),
        kind: str | None = Query(default=None),
    ):
        """Return the machine-complete bundle catalog."""
        return CatalogResponse(**api_catalog(bundle=bundle, provider_kind=provider_kind, kind=kind))

    @app.post("/detect", response_model=DetectResponse)
    async def post_detect(body: DetectRequest, _auth: str = RequireAuth):
        """Scan for dotenv-style secret key names (metadata only)."""
        config_path = Path(app.state.secretfile_path)
        if not config_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Secretfile not found"
            )
        return DetectResponse(
            **api_detect(config_path, directory=body.directory, all_keys=body.all_keys)
        )

    @app.post("/discover", response_model=DiscoverResponse)
    async def post_discover(body: DiscoverRequest, _auth: str = RequireAuth):
        """Run pattern-based secret discovery (metadata only)."""
        config_path = Path(app.state.secretfile_path)
        if not config_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Secretfile not found"
            )
        return DiscoverResponse(
            **api_discover(config_path, directory=body.directory, local_only=body.local_only)
        )

    @app.get("/agent/instructions", response_model=AgentInstructionsResponse)
    async def get_agent_instructions(
        _auth: str = RequireAuth,
        show_all: bool = Query(default=False),
        detailed: bool = Query(default=False),
        environment: str | None = Query(default=None),
    ):
        """Return agent instruction steps for pending or all secrets."""
        config_path = Path(app.state.secretfile_path)
        if not config_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Secretfile not found"
            )
        return AgentInstructionsResponse(
            **api_agent_instructions(
                config_path,
                environment=environment,
                show_all=show_all,
                detailed=detailed,
            )
        )

    @app.get("/agent/list", response_model=AgentListResponse)
    async def get_agent_list(_auth: str = RequireAuth):
        """Detect local Hermes/OpenClaw installs (metadata only)."""
        return AgentListResponse(**api_agent_list())

    @app.post("/agent/adopt", response_model=AgentAdoptResponse)
    async def post_agent_adopt(body: AgentAdoptRequest, _auth: str = RequireAuth):
        """Bootstrap SecretZero environment from agent install (dry_run defaults true)."""
        return AgentAdoptResponse(**api_agent_adopt(**body.model_dump()))

    @app.post("/import/check", response_model=ImportCheckResponse)
    async def post_import_check(body: ImportCheckRequest, _auth: str = RequireAuth):
        """Report drift between lockfile and live targets."""
        config_path = Path(app.state.secretfile_path)
        if not config_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Secretfile not found"
            )
        try:
            return ImportCheckResponse(
                **api_import_check(
                    config_path,
                    environment=body.environment,
                    secret_name=body.secret_name,
                )
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    @app.post("/clean", response_model=CleanLockfileResponse)
    async def post_clean(body: CleanLockfileRequest, _auth: str = RequireAuth):
        """Remove orphaned lockfile entries."""
        config_path = Path(app.state.secretfile_path)
        if not config_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Secretfile not found"
            )
        return CleanLockfileResponse(
            **api_clean_lockfile(
                config_path,
                environment=body.environment,
                dry_run=body.dry_run,
            )
        )

    @app.post("/ingest/preseed", response_model=IngestPreseedResponse)
    async def post_ingest_preseed(body: IngestPreseedRequest, _auth: str = RequireAuth):
        """Import hashes from a local file matching manifest targets."""
        config_path = Path(app.state.secretfile_path)
        if not config_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Secretfile not found"
            )
        try:
            return IngestPreseedResponse(
                **api_ingest_preseed(
                    config_path,
                    source=body.source,
                    environment=body.environment,
                    dry_run=body.dry_run,
                )
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    @app.post("/sync/execute", response_model=SyncExecuteResponse)
    async def post_sync_execute(body: SyncExecuteRequest, _auth: str = RequireAuth):
        """Execute sync (mutation). Prefer dry_run for planning."""
        config_path = Path(app.state.secretfile_path)
        if not config_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Secretfile not found"
            )
        return SyncExecuteResponse(
            **api_sync_execute(
                config_path,
                dry_run=body.dry_run,
                force=body.force,
                refresh=body.refresh,
                secret_name=body.secret_name,
                environment=body.environment,
                var_files=body.var_files,
            )
        )

    @app.get("/schema/full")
    async def get_full_schema(_auth: str = RequireAuth):
        """Alias for Secretfile JSON Schema (parity with MCP schema_get)."""
        return Secretfile.model_json_schema()
