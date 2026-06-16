"""API request and response models."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ErrorResponse(BaseModel):
    """Error response."""

    error: str
    detail: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ConfigValidationRequest(BaseModel):
    """Request to validate a Secretfile configuration."""

    config: dict[str, Any]


class ConfigValidationResponse(BaseModel):
    """Response from configuration validation."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SecretGenerateRequest(BaseModel):
    """Request to generate a secret."""

    secret_name: str
    dry_run: bool = False
    force: bool = False


class SecretGenerateResponse(BaseModel):
    """Response from secret generation."""

    secret_name: str
    generated: bool
    message: str
    targets_updated: list[str] = Field(default_factory=list)


class SecretListResponse(BaseModel):
    """Response listing secrets."""

    secrets: list[dict[str, Any]]
    count: int


class SecretStatusResponse(BaseModel):
    """Response with secret status."""

    name: str
    exists: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_rotated: datetime | None = None
    rotation_count: int = 0
    targets: list[str] = Field(default_factory=list)


class RotationCheckRequest(BaseModel):
    """Request to check rotation status."""

    secret_name: str | None = None
    dry_run: bool = True


class RotationCheckResponse(BaseModel):
    """Response from rotation check."""

    secrets_checked: int
    secrets_due: list[str] = Field(default_factory=list)
    secrets_overdue: list[str] = Field(default_factory=list)
    results: list[dict[str, Any]] = Field(default_factory=list)


class RotationExecuteRequest(BaseModel):
    """Request to execute rotation."""

    secret_name: str | None = None
    force: bool = False


class RotationExecuteResponse(BaseModel):
    """Response from rotation execution."""

    rotated: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)
    message: str


class PolicyCheckRequest(BaseModel):
    """Request to check policy compliance."""

    fail_on_warning: bool = False


class PolicyCheckResponse(BaseModel):
    """Response from policy check."""

    compliant: bool
    errors: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    info: list[dict[str, Any]] = Field(default_factory=list)


class DriftCheckRequest(BaseModel):
    """Request to check for drift."""

    secret_name: str | None = None


class DriftCheckResponse(BaseModel):
    """Response from drift check."""

    has_drift: bool
    secrets_with_drift: list[str] = Field(default_factory=list)
    details: list[dict[str, Any]] = Field(default_factory=list)


class SyncRequest(BaseModel):
    """Request to sync secrets."""

    dry_run: bool = False
    force: bool = False
    refresh: bool = True
    secret_name: str | None = None
    var_files: list[str] = Field(
        default_factory=list,
        description="Optional .szvar file paths merged into Secretfile variables (later entries win)",
    )
    environment: str | None = Field(
        default=None,
        description="Optional named environment profile from Secretfile.environments.profiles",
    )


class SyncResponse(BaseModel):
    """Response from sync operation."""

    secrets_generated: list[str] = Field(default_factory=list)
    secrets_skipped: list[str] = Field(default_factory=list)
    message: str
    selected_environment: str | None = None
    resolved_var_files: list[str] = Field(default_factory=list)
    resolved_lockfile: str | None = None
    resolved_target_profile: str | None = None


class AuditLogEntry(BaseModel):
    """Audit log entry."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    action: str
    resource: str
    user: str | None = None
    details: dict[str, Any] | None = None
    success: bool = True


class AuditLogResponse(BaseModel):
    """Response with audit logs."""

    entries: list[AuditLogEntry]
    count: int
    page: int = 1
    per_page: int = 50


class SecretDetailResponse(BaseModel):
    """Detailed secret information (show command equivalent)."""

    name: str
    kind: str
    one_time: bool = False
    rotation_period: str | None = None
    targets: list[dict[str, Any]] = Field(default_factory=list)
    exists: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_rotated: datetime | None = None
    rotation_count: int = 0


class ProviderListResponse(BaseModel):
    """Response listing providers from Secretfile."""

    providers: list[dict[str, Any]]
    total: int


class TargetListResponse(BaseModel):
    """Response listing targets from Secretfile."""

    targets: list[dict[str, Any]]
    total: int


class VariableListResponse(BaseModel):
    """Response listing variables from Secretfile."""

    variables: dict[str, Any]
    total: int


class ConfigRenderResponse(BaseModel):
    """Response with rendered Secretfile configuration."""

    config: dict[str, Any]


class SecretTypesResponse(BaseModel):
    """Response listing available secret generator and target types."""

    generators: list[dict[str, str]]
    targets: list[dict[str, str]]


class GraphResponse(BaseModel):
    """Response with graph representation of Secretfile relationships."""

    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


class AppConfigResponse(BaseModel):
    """Effective application configuration (defaults ← config.yml ← Secretfile.config)."""

    config: dict[str, Any] = Field(
        description="Merged app config (llm, discovery, output) as JSON-serializable dict",
    )
    sources: list[str] = Field(
        default_factory=list,
        description="Config sources applied in order (e.g. defaults, config_yml, secretfile)",
    )


class AgentSyncRequest(BaseModel):
    """Request for unified ``agent sync`` (CLI parity)."""

    dry_run: bool = False
    refresh: bool = True
    web: bool = Field(
        default=False,
        description="When True and manual secrets are pending, expose a localhost web URL (Vector 2)",
    )
    lockfile: str | None = Field(
        default=None,
        description="Path to lockfile (default: .gitsecrets.lock next to the Secretfile)",
    )
    var_files: list[str] = Field(
        default_factory=list,
        description="Optional .szvar file paths merged into Secretfile variables (later entries win)",
    )
    environment: str | None = Field(
        default=None,
        description="Optional named environment profile from Secretfile.environments.profiles",
    )
    sz_agent: bool | None = Field(
        default=None,
        description="Override SZ_AGENT for this request; when None, use the server environment",
    )


class AgentSyncResponse(BaseModel):
    """Structured agent sync result (no secret values)."""

    status: str = Field(
        description=(
            "complete | pending_manual | failed | partial | awaiting_web_input "
            "(awaiting_web_input when web_url is returned)"
        )
    )
    synced_secrets: list[str] = Field(default_factory=list)
    already_synced: list[str] = Field(default_factory=list)
    pending_secrets: dict[str, dict[str, Any]] = Field(default_factory=dict)
    failed_secrets: dict[str, str] = Field(default_factory=dict)
    automation_summary: dict[str, int] = Field(default_factory=dict)
    sync_results: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False
    sz_agent: bool = False
    resolved_mode: str = ""
    web_url: str | None = None
    web_session_id: str | None = None
    selected_environment: str | None = None
    resolved_var_files: list[str] = Field(default_factory=list)
    resolved_lockfile: str | None = None
    resolved_target_profile: str | None = None


class AgentWebSessionStatusResponse(BaseModel):
    """Polling status for a Vector 2 web session."""

    done: bool
    error: str | None = None
    result: dict[str, Any] | None = None


class VersionResponse(BaseModel):
    """Version metadata response."""

    name: str
    version: str
    website: str
    backend: str = "api"
    python_version: str | None = None
    platform: str | None = None
    executable: str | None = None
    manifest_spec_version: str | None = None


class CatalogResponse(BaseModel):
    """Full bundle catalog."""

    generators: list[dict[str, Any]] = Field(default_factory=list)
    targets: list[dict[str, Any]] = Field(default_factory=list)
    bundles: list[dict[str, Any]] = Field(default_factory=list)


class DetectRequest(BaseModel):
    directory: str | None = None
    all_keys: bool = False


class DetectResponse(BaseModel):
    detected: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    all_keys: bool = False
    directory: str | None = None


class DiscoverRequest(BaseModel):
    directory: str | None = None
    local_only: bool = True


class DiscoverResponse(BaseModel):
    files_scanned: int = 0
    total_secrets: int = 0
    dry_run: bool = True
    directory: str | None = None
    llm_used: bool = False
    secrets: list[dict[str, Any]] = Field(default_factory=list)


class AgentInstructionsResponse(BaseModel):
    scope: str
    total: int
    secrets: dict[str, Any] = Field(default_factory=dict)
    resolved_lockfile: str | None = None


class AgentListResponse(BaseModel):
    detections: list[dict[str, Any]] = Field(default_factory=list)
    registered_targets: list[str] = Field(default_factory=list)


class AgentAdoptRequest(BaseModel):
    target: str | None = None
    source_dir: str | None = None
    output_dir: str | None = None
    template: bool = False
    preseed_lockfile: bool = False
    dry_run: bool = True
    force: bool = False


class AgentAdoptResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    generated: bool = False
    dry_run: bool = True
    target: str | None = None
    source_dir: str | None = None
    output_dir: str | None = None
    discovered: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    reason: str | None = None
    preseed: dict[str, Any] | None = None
    next_steps: list[str] = Field(default_factory=list)


class ImportCheckRequest(BaseModel):
    environment: str | None = None
    secret_name: str | None = None


class ImportCheckResponse(BaseModel):
    drift_detected: bool
    results: list[dict[str, Any]] = Field(default_factory=list)
    lockfile: str


class CleanLockfileRequest(BaseModel):
    environment: str | None = None
    dry_run: bool = True


class CleanLockfileResponse(BaseModel):
    cleaned: int
    orphaned_entries: list[str] = Field(default_factory=list)
    dry_run: bool = True
    lockfile: str


class IngestPreseedRequest(BaseModel):
    source: str
    environment: str | None = None
    dry_run: bool = True


class IngestPreseedResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    imported: int = 0
    updated: int = 0
    skipped: int = 0
    dry_run: bool = True
    ingest: dict[str, Any] = Field(default_factory=dict)
    lockfile: str | None = None


class SyncExecuteRequest(BaseModel):
    dry_run: bool = True
    force: bool = False
    refresh: bool = True
    secret_name: str | None = None
    environment: str | None = None
    var_files: list[str] = Field(default_factory=list)


class SyncExecuteResponse(BaseModel):
    dry_run: bool = True
    generated: list[str] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    results: dict[str, Any] = Field(default_factory=dict)
    resolved_lockfile: str | None = None
