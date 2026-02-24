"""API request and response models."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


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
    secret_name: str | None = None


class SyncResponse(BaseModel):
    """Response from sync operation."""

    secrets_generated: list[str] = Field(default_factory=list)
    secrets_skipped: list[str] = Field(default_factory=list)
    message: str


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
