"""FastAPI application for SecretZero API."""

from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from secretzero import __version__
from secretzero.api.audit import get_audit_logger
from secretzero.api.auth import RequireAuth
from secretzero.api.schemas import (
    AuditLogResponse,
    ConfigValidationRequest,
    ConfigValidationResponse,
    DriftCheckRequest,
    DriftCheckResponse,
    ErrorResponse,
    HealthResponse,
    PolicyCheckRequest,
    PolicyCheckResponse,
    RotationCheckRequest,
    RotationCheckResponse,
    RotationExecuteRequest,
    RotationExecuteResponse,
    SecretListResponse,
    SecretStatusResponse,
    SyncRequest,
    SyncResponse,
)
from secretzero.config import ConfigLoader
from secretzero.drift import DriftDetector
from secretzero.lockfile import Lockfile
from secretzero.policy import PolicyEngine
from secretzero.rotation import should_rotate_secret
from secretzero.sync import SyncEngine


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
        allow_origins=["*"],  # ⚠️ SECURITY WARNING: Allow all origins (development only)
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
            # Try to load and validate the config
            # For now, we just check if it can be parsed
            errors = []
            warnings = []

            # Basic validation
            if "version" not in request.config:
                errors.append("Missing required field: version")
            if "secrets" not in request.config:
                errors.append("Missing required field: secrets")

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
            config = loader.load_file(config_path)
            lockfile = Lockfile.load(Path(".gitsecrets.lock"))
            sync_engine = SyncEngine(config, lockfile)

            generated = []
            skipped = []

            if request.secret_name:
                # Sync specific secret
                secret = next((s for s in config.secrets if s.name == request.secret_name), None)
                if not secret:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Secret not found: {request.secret_name}",
                    )

                result = sync_engine._sync_secret(secret, request.dry_run, request.force)
                if not request.dry_run and result["generated"] and result["stored"]:
                    generated.append(request.secret_name)
                elif request.dry_run or result["skipped"]:
                    skipped.append(request.secret_name)
                message = f"{'Would generate' if request.dry_run else 'Generated'} secret: {request.secret_name}"
            else:
                # Sync all secrets
                results = sync_engine.sync(dry_run=request.dry_run, force_rotation=request.force)
                for detail in results.get("details", []):
                    if not request.dry_run and detail.get("generated") and detail.get("stored"):
                        generated.append(detail["name"])
                    elif request.dry_run or detail.get("skipped"):
                        skipped.append(detail["name"])
                message = f"{'Would generate' if request.dry_run else 'Generated'} {len(generated)} secret(s), skipped {len(skipped)}"

            # Save lockfile if not dry run
            if not request.dry_run:
                lockfile.save(Path(".gitsecrets.lock"))

            audit_logger.log(
                action="sync",
                resource="secrets",
                details={
                    "dry_run": request.dry_run,
                    "force": request.force,
                    "generated": generated,
                    "skipped": skipped,
                },
            )

            return SyncResponse(
                secrets_generated=generated,
                secrets_skipped=skipped,
                message=message,
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
            sync_engine = SyncEngine(config, lockfile)

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
                        should_rotate, _ = should_rotate_secret(secret, entry)
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

    return app
