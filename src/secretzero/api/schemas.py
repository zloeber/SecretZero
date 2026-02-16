"""API request and response models."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    """Error response."""

    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ConfigValidationRequest(BaseModel):
    """Request to validate a Secretfile configuration."""

    config: Dict[str, Any]


class ConfigValidationResponse(BaseModel):
    """Response from configuration validation."""

    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


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
    targets_updated: List[str] = Field(default_factory=list)


class SecretListResponse(BaseModel):
    """Response listing secrets."""

    secrets: List[Dict[str, Any]]
    count: int


class SecretStatusResponse(BaseModel):
    """Response with secret status."""

    name: str
    exists: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_rotated: Optional[datetime] = None
    rotation_count: int = 0
    targets: List[str] = Field(default_factory=list)


class RotationCheckRequest(BaseModel):
    """Request to check rotation status."""

    secret_name: Optional[str] = None
    dry_run: bool = True


class RotationCheckResponse(BaseModel):
    """Response from rotation check."""

    secrets_checked: int
    secrets_due: List[str] = Field(default_factory=list)
    secrets_overdue: List[str] = Field(default_factory=list)
    results: List[Dict[str, Any]] = Field(default_factory=list)


class RotationExecuteRequest(BaseModel):
    """Request to execute rotation."""

    secret_name: Optional[str] = None
    force: bool = False


class RotationExecuteResponse(BaseModel):
    """Response from rotation execution."""

    rotated: List[str] = Field(default_factory=list)
    failed: List[str] = Field(default_factory=list)
    message: str


class PolicyCheckRequest(BaseModel):
    """Request to check policy compliance."""

    fail_on_warning: bool = False


class PolicyCheckResponse(BaseModel):
    """Response from policy check."""

    compliant: bool
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    info: List[Dict[str, Any]] = Field(default_factory=list)


class DriftCheckRequest(BaseModel):
    """Request to check for drift."""

    secret_name: Optional[str] = None


class DriftCheckResponse(BaseModel):
    """Response from drift check."""

    has_drift: bool
    secrets_with_drift: List[str] = Field(default_factory=list)
    details: List[Dict[str, Any]] = Field(default_factory=list)


class SyncRequest(BaseModel):
    """Request to sync secrets."""

    dry_run: bool = False
    force: bool = False
    secret_name: Optional[str] = None


class SyncResponse(BaseModel):
    """Response from sync operation."""

    secrets_generated: List[str] = Field(default_factory=list)
    secrets_skipped: List[str] = Field(default_factory=list)
    message: str


class AuditLogEntry(BaseModel):
    """Audit log entry."""

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    action: str
    resource: str
    user: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    success: bool = True


class AuditLogResponse(BaseModel):
    """Response with audit logs."""

    entries: List[AuditLogEntry]
    count: int
    page: int = 1
    per_page: int = 50
