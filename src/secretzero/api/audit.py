"""Audit logging for API operations."""

import json
from pathlib import Path
from typing import Any

from secretzero.api.schemas import AuditLogEntry


class AuditLogger:
    """Simple file-based audit logger."""

    def __init__(self, log_file: Path | None = None):
        """Initialize the audit logger.

        Args:
            log_file: Path to the audit log file. Defaults to .secretzero_audit.log
        """
        if log_file is None:
            log_file = Path.cwd() / ".secretzero_audit.log"
        self.log_file = log_file

    def log(
        self,
        action: str,
        resource: str,
        user: str | None = None,
        details: dict[str, Any] | None = None,
        success: bool = True,
    ) -> None:
        """Log an audit event.

        Args:
            action: The action performed (e.g., "sync", "rotate", "policy_check")
            resource: The resource affected (e.g., "secret:api_key")
            user: Optional user identifier
            details: Optional additional details
            success: Whether the operation was successful
        """
        entry = AuditLogEntry(
            action=action,
            resource=resource,
            user=user or "api",
            details=details,
            success=success,
        )

        # Append to log file
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry.model_dump(mode="json")) + "\n")

    def get_logs(
        self,
        limit: int = 100,
        offset: int = 0,
        action: str | None = None,
        resource: str | None = None,
    ) -> list[AuditLogEntry]:
        """Retrieve audit logs.

        Args:
            limit: Maximum number of logs to return
            offset: Number of logs to skip
            action: Filter by action
            resource: Filter by resource

        Returns:
            List of audit log entries
        """
        if not self.log_file.exists():
            return []

        logs = []
        with open(self.log_file) as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    entry = AuditLogEntry(**data)

                    # Apply filters
                    if action and entry.action != action:
                        continue
                    if resource and entry.resource != resource:
                        continue

                    logs.append(entry)
                except (json.JSONDecodeError, ValueError):
                    # Skip invalid entries
                    continue

        # Reverse to get newest first
        logs.reverse()

        # Apply pagination
        return logs[offset : offset + limit]


# Global audit logger instance
_audit_logger: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
