"""FastAPI application for SecretZero API."""

import inspect
import os
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from secretzero import __version__, generators, targets
from secretzero.agent import (
    AgentSecretSynchronizer,
    build_agent_sync_json_payload,
    env_sz_agent,
    resolve_resolved_mode_label,
)
from secretzero.agent_webui import start_web_session_server, web_session_registry
from secretzero.api.audit import get_audit_logger
from secretzero.api.auth import RequireAuth
from secretzero.api.schemas import (
    AgentSyncRequest,
    AgentSyncResponse,
    AgentWebSessionStatusResponse,
    AppConfigResponse,
    AuditLogResponse,
    ConfigRenderResponse,
    ConfigValidationRequest,
    ConfigValidationResponse,
    DriftCheckRequest,
    DriftCheckResponse,
    ErrorResponse,
    GraphResponse,
    HealthResponse,
    PolicyCheckRequest,
    PolicyCheckResponse,
    ProviderListResponse,
    RotationCheckRequest,
    RotationCheckResponse,
    RotationExecuteRequest,
    RotationExecuteResponse,
    SecretDetailResponse,
    SecretListResponse,
    SecretStatusResponse,
    SecretTypesResponse,
    SyncRequest,
    SyncResponse,
    TargetListResponse,
    VariableListResponse,
)
from secretzero.cli_config import get_effective_config
from secretzero.config import ConfigLoader
from secretzero.drift import DriftDetector
from secretzero.environment_resolution import apply_target_profile, resolve_environment_context
from secretzero.lockfile import Lockfile
from secretzero.models import AgentMode, Secretfile
from secretzero.policy import PolicyEngine
from secretzero.rotation import should_rotate_secret
from secretzero.sync import SyncEngine


def _class_name_to_snake_case(name: str, suffix: str) -> str:
    """Convert a class name to snake_case type name, removing a suffix.

    Args:
        name: Class name (e.g., SSMParameterTarget)
        suffix: Suffix to remove (e.g., Target, Generator)

    Returns:
        snake_case type name (e.g., ssm_parameter)
    """
    # Remove the suffix
    if name.endswith(suffix):
        name = name[: -len(suffix)]

    # Insert underscores before uppercase letters that follow lowercase letters or digits
    s1 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    # Insert underscores before uppercase letters that are followed by lowercase letters
    # when preceded by multiple uppercase letters (handles acronyms like SSM, KV)
    s2 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s1)
    return s2.lower()


def create_app(secretfile_path: str = "Secretfile.yml") -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        secretfile_path: Path to the Secretfile configuration

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="SecretZero API",
        description="REST API for SecretZero secrets orchestration and lifecycle management",
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS middleware - DEVELOPMENT ONLY
    # TODO: Configure restrictive CORS policy for production
    # For production, set allow_origins to specific domains:
    # allow_origins=["https://yourdomain.com"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.environ.get("SECRETZERO_ALLOWED_ORIGINS", "http://localhost:8000").split(
            ","
        ),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store configuration path
    app.state.secretfile_path = secretfile_path

    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        """Handle all uncaught exceptions."""
        audit_logger = get_audit_logger()
        audit_logger.log(
            action="error",
            resource=str(request.url),
            details={"error": str(exc)},
            success=False,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error="Internal server error",
                detail=str(exc),
            ).model_dump(),
        )

    @app.get("/", response_model=dict[str, str])
    async def root():
        """Root endpoint."""
        return {
            "message": "SecretZero API",
            "version": __version__,
            "docs": "/docs",
        }

    @app.get("/health", response_model=HealthResponse)
    async def health():
        """Health check endpoint."""
        return HealthResponse(version=__version__)

    @app.post("/config/validate", response_model=ConfigValidationResponse)
    async def validate_config(
        request: ConfigValidationRequest,
        _auth: str = RequireAuth,
    ):
        """Validate a Secretfile configuration."""
        audit_logger = get_audit_logger()

        try:
            errors: list[str] = []
            warnings = []

            try:
                from secretzero.policy import validate_secretfile_policy_shapes

                sf = Secretfile.model_validate(request.config)
                validate_secretfile_policy_shapes(sf)
            except ValidationError as exc:
                errors.extend(
                    [
                        f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}"
                        for err in exc.errors()
                    ]
                )
            except ValueError as exc:
                errors.append(str(exc))

            valid = len(errors) == 0

            audit_logger.log(
                action="validate_config",
                resource="config",
                details={"valid": valid, "errors": errors},
                success=valid,
            )

            return ConfigValidationResponse(
                valid=valid,
                errors=errors,
                warnings=warnings,
            )
        except Exception as e:
            audit_logger.log(
                action="validate_config",
                resource="config",
                details={"error": str(e)},
                success=False,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Configuration validation failed: {str(e)}",
            )

    @app.get("/secrets", response_model=SecretListResponse)
    async def list_secrets(_auth: str = RequireAuth):
        """List all secrets from the Secretfile."""
        audit_logger = get_audit_logger()

        try:
            config_path = Path(app.state.secretfile_path)
            if not config_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Secretfile not found: {config_path}",
                )

            loader = ConfigLoader()
            config = loader.load_file(config_path)

            secrets = []
            for secret in config.secrets:
                secrets.append(
                    {
                        "name": secret.name,
                        "kind": secret.kind,
                        "rotation_period": secret.rotation_period,
                        "targets": [t.kind for t in secret.targets],
                    }
                )

            audit_logger.log(
                action="list_secrets",
                resource="secrets",
                details={"count": len(secrets)},
            )

            return SecretListResponse(secrets=secrets, count=len(secrets))
        except HTTPException:
            raise
        except Exception as e:
            audit_logger.log(
                action="list_secrets",
                resource="secrets",
                details={"error": str(e)},
                success=False,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list secrets: {str(e)}",
            )

    @app.get("/secrets/{secret_name}/status", response_model=SecretStatusResponse)
    async def get_secret_status(secret_name: str, _auth: str = RequireAuth):
        """Get the status of a specific secret."""
        audit_logger = get_audit_logger()

        try:
            lockfile = Lockfile.load(Path(".gitsecrets.lock"))
            entry = lockfile.get_secret_info(secret_name)

            if entry is None:
                audit_logger.log(
                    action="get_secret_status",
                    resource=f"secret:{secret_name}",
                    details={"exists": False},
                )
                return SecretStatusResponse(name=secret_name, exists=False)

            audit_logger.log(
                action="get_secret_status",
                resource=f"secret:{secret_name}",
                details={"exists": True},
            )

            return SecretStatusResponse(
                name=secret_name,
                exists=True,
                created_at=entry.created_at,
                updated_at=entry.updated_at,
                last_rotated=entry.last_rotated,
                rotation_count=entry.rotation_count,
                targets=list(entry.targets.keys()),
            )
        except Exception as e:
            audit_logger.log(
                action="get_secret_status",
                resource=f"secret:{secret_name}",
                details={"error": str(e)},
                success=False,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get secret status: {str(e)}",
            )

    @app.post("/sync", response_model=SyncResponse)
    async def sync_secrets(request: SyncRequest, _auth: str = RequireAuth):
        """Sync secrets (generate and store)."""
        audit_logger = get_audit_logger()

        try:
            config_path = Path(app.state.secretfile_path)
            if not config_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Secretfile not found: {config_path}",
                )

            loader = ConfigLoader()
            base_config = loader.load_file(config_path)
            runtime_var_files = [Path(vf) for vf in request.var_files]
            env_ctx = resolve_environment_context(
                secretfile=base_config,
                secretfile_path=config_path,
                environment=request.environment,
                runtime_var_files=runtime_var_files,
                runtime_lockfile=None,
            )
            config = loader.load_file(config_path, var_files=env_ctx.resolved_var_files or None)
            config = apply_target_profile(config, env_ctx.resolved_target_profile)
            lockfile = Lockfile.load(env_ctx.resolved_lockfile)
            secretfile_content = config_path.read_text()
            sync_engine = SyncEngine(
                config,
                lockfile,
                secretfile_path=config_path,
                secretfile_content=secretfile_content,
                sync_client="api",
            )

            generated = []
            skipped = []
            secret_names = None

            if request.secret_name:
                secret = next((s for s in config.secrets if s.name == request.secret_name), None)
                if not secret:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Secret not found: {request.secret_name}",
                    )
                secret_names = [request.secret_name]

            results = sync_engine.sync(
                dry_run=request.dry_run,
                force_rotation=request.force,
                secret_names=secret_names,
                refresh=request.refresh,
            )
            for detail in results.get("details", []):
                if not request.dry_run and detail.get("generated") and detail.get("stored"):
                    generated.append(detail["name"])
                elif request.dry_run or detail.get("skipped"):
                    skipped.append(detail["name"])

            if request.secret_name:
                message = (
                    f"{'Would generate' if request.dry_run else 'Generated'} secret: "
                    f"{request.secret_name}"
                )
            else:
                message = (
                    f"{'Would generate' if request.dry_run else 'Generated'} "
                    f"{len(generated)} secret(s), skipped {len(skipped)}"
                )

            # Save lockfile if not dry run
            if not request.dry_run:
                lockfile.save(env_ctx.resolved_lockfile)

            audit_logger.log(
                action="sync",
                resource="secrets",
                details={
                    "dry_run": request.dry_run,
                    "force": request.force,
                    "refresh": request.refresh,
                    "generated": generated,
                    "skipped": skipped,
                },
            )

            return SyncResponse(
                secrets_generated=generated,
                secrets_skipped=skipped,
                message=message,
                selected_environment=env_ctx.selected_environment,
                resolved_var_files=[str(p) for p in env_ctx.resolved_var_files],
                resolved_lockfile=str(env_ctx.resolved_lockfile),
                resolved_target_profile=env_ctx.resolved_target_profile,
            )
        except HTTPException:
            raise
        except Exception as e:
            audit_logger.log(
                action="sync",
                resource="secrets",
                details={"error": str(e)},
                success=False,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Sync failed: {str(e)}",
            )

    @app.post("/agent/sync", response_model=AgentSyncResponse)
    async def agent_sync_endpoint(body: AgentSyncRequest, _auth: str = RequireAuth):
        """Unified agent sync (CLI parity): structured JSON, optional localhost web URL for Vector 2."""
        audit_logger = get_audit_logger()

        try:
            config_path = Path(app.state.secretfile_path)
            if not config_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Secretfile not found: {config_path}",
                )

            secretfile_content = config_path.read_text()
            loader = ConfigLoader()
            base_secretfile = loader.load_file(config_path)
            env_ctx = resolve_environment_context(
                secretfile=base_secretfile,
                secretfile_path=config_path,
                environment=body.environment,
                runtime_var_files=[Path(vf) for vf in body.var_files],
                runtime_lockfile=body.lockfile,
            )
            lockfile_path = env_ctx.resolved_lockfile
            secretfile = loader.load_file(config_path, var_files=env_ctx.resolved_var_files or None)
            secretfile = apply_target_profile(secretfile, env_ctx.resolved_target_profile)
            lock = Lockfile.load(lockfile_path)

            sz_eff = body.sz_agent if body.sz_agent is not None else env_sz_agent()
            agent_cfg = secretfile.effective_agent_config()
            use_web = (body.web or agent_cfg.mode == AgentMode.WEB) and not sz_eff

            syncer = AgentSecretSynchronizer(
                secretfile,
                lock,
                dry_run=body.dry_run,
                secretfile_path=config_path,
                secretfile_content=secretfile_content,
            )
            result = syncer.sync(sz_agent=sz_eff, refresh=body.refresh)

            resolved = resolve_resolved_mode_label(secretfile, cli_web=body.web, sz_agent=sz_eff)
            payload = build_agent_sync_json_payload(
                result,
                dry_run=body.dry_run,
                sz_agent=sz_eff,
                resolved_mode=resolved,
            )
            payload["selected_environment"] = env_ctx.selected_environment
            payload["resolved_var_files"] = [str(p) for p in env_ctx.resolved_var_files]
            payload["resolved_lockfile"] = str(env_ctx.resolved_lockfile)
            payload["resolved_target_profile"] = env_ctx.resolved_target_profile

            if use_web and result.pending_secrets and not body.dry_run:
                sess = web_session_registry.create(list(result.pending_secrets.keys()))
                url, _port = start_web_session_server(
                    session_id=sess.session_id,
                    pending_secret_names=list(result.pending_secrets.keys()),
                    secretfile=secretfile,
                    lockfile=lock,
                    lockfile_path=lockfile_path,
                    secretfile_path=config_path,
                    secretfile_content=secretfile_content,
                    dry_run=body.dry_run,
                    port_min=agent_cfg.web_port_min,
                    port_max=agent_cfg.web_port_max,
                    registry=web_session_registry,
                )
                payload["web_url"] = url
                payload["web_session_id"] = sess.session_id
                payload["status"] = "awaiting_web_input"

            if not body.dry_run:
                lock.save(lockfile_path)

            audit_logger.log(
                action="agent_sync",
                resource="agent_sync",
                details={
                    "dry_run": body.dry_run,
                    "web": body.web,
                    "refresh": body.refresh,
                    "status": payload["status"],
                    "pending_count": len(result.pending_secrets),
                    "failed_count": len(result.failed_secrets),
                },
                success=True,
            )

            return AgentSyncResponse(**payload)
        except HTTPException:
            raise
        except Exception as e:
            audit_logger.log(
                action="agent_sync",
                resource="agent_sync",
                details={"error": str(e)},
                success=False,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Agent sync failed: {str(e)}",
            )

    @app.get("/agent/sync/web/{session_id}", response_model=AgentWebSessionStatusResponse)
    async def agent_sync_web_status(session_id: str, _auth: str = RequireAuth):
        """Poll completion for a Vector 2 web session (no secret values)."""
        sess = web_session_registry.get(session_id)
        if sess is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Unknown web session",
            )
        return AgentWebSessionStatusResponse(
            done=sess.done,
            error=sess.error,
            result=sess.result_payload,
        )

    @app.post("/rotation/check", response_model=RotationCheckResponse)
    async def check_rotation(request: RotationCheckRequest, _auth: str = RequireAuth):
        """Check which secrets need rotation."""
        audit_logger = get_audit_logger()

        try:
            config_path = Path(app.state.secretfile_path)
            if not config_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Secretfile not found: {config_path}",
                )

            loader = ConfigLoader()
            config = loader.load_file(config_path)
            lockfile = Lockfile.load(Path(".gitsecrets.lock"))

            secrets_to_check = []
            if request.secret_name:
                secret = next((s for s in config.secrets if s.name == request.secret_name), None)
                if not secret:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Secret not found: {request.secret_name}",
                    )
                secrets_to_check = [secret]
            else:
                secrets_to_check = config.secrets

            due = []
            overdue = []
            results = []

            for secret in secrets_to_check:
                entry = lockfile.get_secret_info(secret.name)
                if entry and secret.rotation_period:
                    should_rotate, status_msg = should_rotate_secret(secret, entry)
                    results.append(
                        {
                            "name": secret.name,
                            "should_rotate": should_rotate,
                            "status": status_msg,
                        }
                    )
                    if should_rotate:
                        if "overdue" in status_msg.lower():
                            overdue.append(secret.name)
                        else:
                            due.append(secret.name)

            audit_logger.log(
                action="check_rotation",
                resource="secrets",
                details={
                    "secrets_checked": len(secrets_to_check),
                    "secrets_due": len(due),
                    "secrets_overdue": len(overdue),
                },
            )

            return RotationCheckResponse(
                secrets_checked=len(secrets_to_check),
                secrets_due=due,
                secrets_overdue=overdue,
                results=results,
            )
        except HTTPException:
            raise
        except Exception as e:
            audit_logger.log(
                action="check_rotation",
                resource="secrets",
                details={"error": str(e)},
                success=False,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Rotation check failed: {str(e)}",
            )

    @app.post("/rotation/execute", response_model=RotationExecuteResponse)
    async def execute_rotation(request: RotationExecuteRequest, _auth: str = RequireAuth):
        """Execute secret rotation."""
        audit_logger = get_audit_logger()

        try:
            config_path = Path(app.state.secretfile_path)
            if not config_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Secretfile not found: {config_path}",
                )

            loader = ConfigLoader()
            config = loader.load_file(config_path)
            lockfile = Lockfile.load(Path(".gitsecrets.lock"))
            secretfile_content = config_path.read_text()
            sync_engine = SyncEngine(
                config,
                lockfile,
                secretfile_path=config_path,
                secretfile_content=secretfile_content,
                sync_client="api",
            )

            rotated = []
            failed = []

            secrets_to_rotate = []
            if request.secret_name:
                secret = next((s for s in config.secrets if s.name == request.secret_name), None)
                if not secret:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Secret not found: {request.secret_name}",
                    )
                secrets_to_rotate = [secret]
            else:
                # Find all secrets that need rotation
                for secret in config.secrets:
                    entry = lockfile.get_secret_info(secret.name)
                    if entry and secret.rotation_period:
                        should_rotate, _ = should_rotate_secret(
                            secret.rotation_period,
                            entry.last_rotated,
                            entry.created_at,
                        )
                        if should_rotate or request.force:
                            secrets_to_rotate.append(secret)

            for secret in secrets_to_rotate:
                try:
                    result = sync_engine._sync_secret(secret, dry_run=False, force_rotation=True)
                    if result["generated"]:
                        rotated.append(secret.name)
                    else:
                        failed.append(secret.name)
                except Exception:
                    failed.append(secret.name)

            # Save lockfile
            lockfile.save(Path(".gitsecrets.lock"))

            message = f"Rotated {len(rotated)} secret(s)"
            if failed:
                message += f", {len(failed)} failed"

            audit_logger.log(
                action="execute_rotation",
                resource="secrets",
                details={
                    "force": request.force,
                    "rotated": rotated,
                    "failed": failed,
                },
            )

            return RotationExecuteResponse(
                rotated=rotated,
                failed=failed,
                message=message,
            )
        except HTTPException:
            raise
        except Exception as e:
            audit_logger.log(
                action="execute_rotation",
                resource="secrets",
                details={"error": str(e)},
                success=False,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Rotation execution failed: {str(e)}",
            )

    @app.post("/policy/check", response_model=PolicyCheckResponse)
    async def check_policy(request: PolicyCheckRequest, _auth: str = RequireAuth):
        """Check policy compliance."""
        audit_logger = get_audit_logger()

        try:
            config_path = Path(app.state.secretfile_path)
            if not config_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Secretfile not found: {config_path}",
                )

            loader = ConfigLoader()
            config = loader.load_file(config_path)

            # Create policy engine
            engine = PolicyEngine(config)
            violations = engine.validate_all()

            errors = []
            warnings = []
            info = []

            for violation in violations:
                entry = {
                    "secret": violation.secret_name,
                    "policy": violation.policy_name,
                    "message": violation.message,
                    "severity": violation.severity,
                }

                if violation.severity == "error":
                    errors.append(entry)
                elif violation.severity == "warning":
                    warnings.append(entry)
                else:
                    info.append(entry)

            compliant = len(errors) == 0 and (not request.fail_on_warning or len(warnings) == 0)

            audit_logger.log(
                action="check_policy",
                resource="secrets",
                details={
                    "compliant": compliant,
                    "errors": len(errors),
                    "warnings": len(warnings),
                },
            )

            return PolicyCheckResponse(
                compliant=compliant,
                errors=errors,
                warnings=warnings,
                info=info,
            )
        except HTTPException:
            raise
        except Exception as e:
            audit_logger.log(
                action="check_policy",
                resource="secrets",
                details={"error": str(e)},
                success=False,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Policy check failed: {str(e)}",
            )

    @app.post("/drift/check", response_model=DriftCheckResponse)
    async def check_drift(request: DriftCheckRequest, _auth: str = RequireAuth):
        """Check for configuration drift."""
        audit_logger = get_audit_logger()

        try:
            config_path = Path(app.state.secretfile_path)
            if not config_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Secretfile not found: {config_path}",
                )

            # loader = ConfigLoader()
            # config = loader.load_file(config_path)
            lockfile_path = Path(".gitsecrets.lock")
            detector = DriftDetector(config_path, lockfile_path)

            # Check drift
            drift_results = detector.check_drift(request.secret_name)

            secrets_with_drift = []
            details = []

            for drift_status in drift_results:
                if drift_status.has_drift:
                    secrets_with_drift.append(drift_status.secret_name)
                    details.append(
                        {
                            "secret": drift_status.secret_name,
                            "message": drift_status.message,
                            "details": drift_status.details,
                        }
                    )

            has_drift = len(secrets_with_drift) > 0

            audit_logger.log(
                action="check_drift",
                resource="secrets",
                details={
                    "has_drift": has_drift,
                    "secrets_with_drift": secrets_with_drift,
                },
            )

            return DriftCheckResponse(
                has_drift=has_drift,
                secrets_with_drift=secrets_with_drift,
                details=details,
            )
        except HTTPException:
            raise
        except Exception as e:
            audit_logger.log(
                action="check_drift",
                resource="secrets",
                details={"error": str(e)},
                success=False,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Drift check failed: {str(e)}",
            )

    @app.get("/audit/logs", response_model=AuditLogResponse)
    async def get_audit_logs(
        limit: int = 50,
        offset: int = 0,
        action: str | None = None,
        resource: str | None = None,
        _auth: str = RequireAuth,
    ):
        """Get audit logs."""
        audit_logger = get_audit_logger()

        try:
            logs = audit_logger.get_logs(
                limit=limit,
                offset=offset,
                action=action,
                resource=resource,
            )

            return AuditLogResponse(
                entries=logs,
                count=len(logs),
                page=offset // limit + 1,
                per_page=limit,
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve audit logs: {str(e)}",
            )

    @app.get("/list/providers", response_model=ProviderListResponse)
    async def list_providers(_auth: str = RequireAuth):
        """List all providers configured in the Secretfile."""
        audit_logger = get_audit_logger()

        try:
            config_path = Path(app.state.secretfile_path)
            if not config_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Secretfile not found: {config_path}",
                )

            loader = ConfigLoader()
            config = loader.load_file(config_path)

            providers = [
                {
                    "name": name,
                    "kind": p.kind,
                    "auth_kind": p.auth.kind if p.auth else None,
                    "fallback_generator": p.fallback_generator,
                }
                for name, p in config.providers.items()
            ]

            audit_logger.log(
                action="list_providers",
                resource="providers",
                details={"count": len(providers)},
            )

            return ProviderListResponse(providers=providers, total=len(providers))
        except HTTPException:
            raise
        except Exception as e:
            audit_logger.log(
                action="list_providers",
                resource="providers",
                details={"error": str(e)},
                success=False,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list providers: {str(e)}",
            )

    @app.get("/list/targets", response_model=TargetListResponse)
    async def list_targets(_auth: str = RequireAuth):
        """List all target destinations across all secrets in the Secretfile."""
        audit_logger = get_audit_logger()

        try:
            config_path = Path(app.state.secretfile_path)
            if not config_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Secretfile not found: {config_path}",
                )

            loader = ConfigLoader()
            config = loader.load_file(config_path)

            all_targets = []
            for secret in config.secrets:
                for t in secret.targets:
                    all_targets.append(
                        {
                            "secret": secret.name,
                            "provider": t.provider,
                            "kind": t.kind,
                            "config": t.config,
                        }
                    )

            audit_logger.log(
                action="list_targets",
                resource="targets",
                details={"count": len(all_targets)},
            )

            return TargetListResponse(targets=all_targets, total=len(all_targets))
        except HTTPException:
            raise
        except Exception as e:
            audit_logger.log(
                action="list_targets",
                resource="targets",
                details={"error": str(e)},
                success=False,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list targets: {str(e)}",
            )

    @app.get("/list/variables", response_model=VariableListResponse)
    async def list_variables(_auth: str = RequireAuth):
        """List all variables defined in the Secretfile."""
        audit_logger = get_audit_logger()

        try:
            config_path = Path(app.state.secretfile_path)
            if not config_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Secretfile not found: {config_path}",
                )

            loader = ConfigLoader()
            config = loader.load_file(config_path)

            variables = dict(config.variables)

            audit_logger.log(
                action="list_variables",
                resource="variables",
                details={"count": len(variables)},
            )

            return VariableListResponse(variables=variables, total=len(variables))
        except HTTPException:
            raise
        except Exception as e:
            audit_logger.log(
                action="list_variables",
                resource="variables",
                details={"error": str(e)},
                success=False,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list variables: {str(e)}",
            )

    @app.get("/config/render", response_model=ConfigRenderResponse)
    async def render_config(_auth: str = RequireAuth):
        """Render the Secretfile configuration with variables interpolated."""
        audit_logger = get_audit_logger()

        try:
            config_path = Path(app.state.secretfile_path)
            if not config_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Secretfile not found: {config_path}",
                )

            loader = ConfigLoader()
            config = loader.load_file(config_path)

            config_dict = config.model_dump(mode="python", exclude_none=True)

            audit_logger.log(
                action="render_config",
                resource="config",
                details={},
            )

            return ConfigRenderResponse(config=config_dict)
        except HTTPException:
            raise
        except Exception as e:
            audit_logger.log(
                action="render_config",
                resource="config",
                details={"error": str(e)},
                success=False,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to render config: {str(e)}",
            )

    @app.get("/config", response_model=AppConfigResponse)
    async def get_app_config(_auth: str = RequireAuth):
        """Return effective application config (defaults ← config.yml ← Secretfile.config)."""
        config_path = Path(app.state.secretfile_path)
        result = get_effective_config(secretfile_path=config_path)
        return AppConfigResponse(
            config=result.config.model_dump(),
            sources=result.sources,
        )

    @app.get("/schema")
    async def get_schema():
        """Export JSON Schema for Secretfile.yml."""
        return Secretfile.model_json_schema()

    @app.get("/secret-types", response_model=SecretTypesResponse)
    async def get_secret_types():
        """List all available secret generator and target types."""
        generator_types = []
        for name in dir(generators):
            if name.endswith("Generator") and not name.startswith("_"):
                obj = getattr(generators, name)
                if inspect.isclass(obj) and obj != generators.BaseGenerator:
                    type_name = _class_name_to_snake_case(name, "Generator")
                    description = (obj.__doc__ or "").strip().split("\n")[0]
                    generator_types.append({"type": type_name, "description": description})

        target_types = []
        for name in dir(targets):
            if name.endswith("Target") and not name.startswith("_"):
                obj = getattr(targets, name)
                if inspect.isclass(obj) and obj != targets.BaseTarget:
                    type_name = _class_name_to_snake_case(name, "Target")
                    description = (obj.__doc__ or "").strip().split("\n")[0]
                    target_types.append({"type": type_name, "description": description})

        return SecretTypesResponse(
            generators=sorted(generator_types, key=lambda x: x["type"]),
            targets=sorted(target_types, key=lambda x: x["type"]),
        )

    @app.get("/graph", response_model=GraphResponse)
    async def get_graph(_auth: str = RequireAuth):
        """Generate a graph representation of Secretfile relationships."""
        audit_logger = get_audit_logger()

        try:
            config_path = Path(app.state.secretfile_path)
            if not config_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Secretfile not found: {config_path}",
                )

            loader = ConfigLoader()
            config = loader.load_file(config_path)

            nodes = []
            edges = []
            for secret in config.secrets:
                nodes.append(
                    {
                        "id": secret.name,
                        "type": "secret",
                        "kind": secret.kind,
                        "one_time": secret.one_time,
                        "rotation_period": secret.rotation_period,
                    }
                )
                edges.append(
                    {
                        "from": secret.kind,
                        "to": secret.name,
                        "label": "generates",
                    }
                )
                for target in secret.targets:
                    target_id = f"{target.provider}/{target.kind}"
                    if not any(n["id"] == target_id for n in nodes):
                        nodes.append(
                            {
                                "id": target_id,
                                "type": "target",
                                "provider": target.provider,
                                "kind": target.kind,
                            }
                        )
                    edges.append({"from": secret.name, "to": target_id, "label": "stored_in"})

            audit_logger.log(
                action="get_graph",
                resource="config",
                details={"nodes": len(nodes), "edges": len(edges)},
            )

            return GraphResponse(nodes=nodes, edges=edges)
        except HTTPException:
            raise
        except Exception as e:
            audit_logger.log(
                action="get_graph",
                resource="config",
                details={"error": str(e)},
                success=False,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate graph: {str(e)}",
            )

    @app.get("/secrets/{secret_name}", response_model=SecretDetailResponse)
    async def get_secret_detail(secret_name: str, _auth: str = RequireAuth):
        """Get detailed information about a specific secret."""
        audit_logger = get_audit_logger()

        try:
            config_path = Path(app.state.secretfile_path)
            if not config_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Secretfile not found: {config_path}",
                )

            loader = ConfigLoader()
            config = loader.load_file(config_path)

            secret = next((s for s in config.secrets if s.name == secret_name), None)
            if not secret:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Secret not found: {secret_name}",
                )

            targets = [
                {"provider": t.provider, "kind": t.kind, "config": t.config} for t in secret.targets
            ]

            lockfile = Lockfile.load(Path(".gitsecrets.lock"))
            entry = lockfile.get_secret_info(secret_name)

            audit_logger.log(
                action="get_secret_detail",
                resource=f"secret:{secret_name}",
                details={"exists": entry is not None},
            )

            return SecretDetailResponse(
                name=secret.name,
                kind=secret.kind,
                one_time=secret.one_time,
                rotation_period=secret.rotation_period,
                targets=targets,
                exists=entry is not None,
                created_at=entry.created_at if entry else None,
                updated_at=entry.updated_at if entry else None,
                last_rotated=entry.last_rotated if entry else None,
                rotation_count=entry.rotation_count if entry else 0,
            )
        except HTTPException:
            raise
        except Exception as e:
            audit_logger.log(
                action="get_secret_detail",
                resource=f"secret:{secret_name}",
                details={"error": str(e)},
                success=False,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get secret detail: {str(e)}",
            )

    return app
