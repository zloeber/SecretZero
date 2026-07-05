"""Helpers for workstation-local secrets and lockfile routing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from secretzero.lockfile import Lockfile
from secretzero.models import Secret, TargetConfig

LOCAL_LOCKFILE_NAME = ".gitsecrets.local.lock"

_LOCAL_FILE_TARGET_KINDS = frozenset({"file", "template"})


def local_lockfile_path(global_lockfile_path: Path) -> Path:
    """Return the machine-local lockfile path adjacent to the shared lockfile."""
    return global_lockfile_path.parent / LOCAL_LOCKFILE_NAME


def coerce_local_flag(value: Any) -> bool:
    """Coerce interpolated YAML values into a boolean local flag."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "on"}
    return bool(value)


def is_local_secret(secret: Secret) -> bool:
    """Return True when *secret* should use the machine-local lockfile."""
    return coerce_local_flag(getattr(secret, "local", False))


def is_local_file_target(target: TargetConfig) -> bool:
    """Return True when *target* is an allowed local-only sink."""
    kind = getattr(target.kind, "value", target.kind)
    return str(target.provider) == "local" and str(kind) in _LOCAL_FILE_TARGET_KINDS


def validate_local_secret_targets(secret: Secret) -> None:
    """Raise when a local secret targets a disallowed provider/kind."""
    if not is_local_secret(secret):
        return
    if coerce_local_flag(getattr(secret, "local_allow_cloud", False)):
        return
    for target in secret.targets:
        if not is_local_file_target(target):
            kind = getattr(target.kind, "value", target.kind)
            raise ValueError(
                f"Secret '{secret.name}' is local-only but target "
                f"{target.provider}/{kind} is not allowed. "
                "Use local/file or local/template targets, or set local_allow_cloud: true."
            )


def resolve_lockfile_for_secret(
    global_lockfile: Lockfile,
    local_lockfile: Lockfile | None,
    secret: Secret,
) -> Lockfile:
    """Return the lockfile backing *secret* (global vs machine-local)."""
    if local_lockfile is not None and is_local_secret(secret):
        return local_lockfile
    return global_lockfile


def load_lockfile_pair(global_path: Path) -> tuple[Lockfile, Lockfile]:
    """Load shared and machine-local lockfiles for a manifest directory."""
    return Lockfile.load(global_path), Lockfile.load(local_lockfile_path(global_path))


def save_lockfile_pair(
    global_path: Path,
    global_lockfile: Lockfile,
    local_lockfile: Lockfile,
) -> None:
    """Persist shared and machine-local lockfiles."""
    global_lockfile.save(global_path)
    local_lockfile.save(local_lockfile_path(global_path))


def stamp_local_lockfile_host(local_lockfile: Lockfile, *, sync_identity: dict[str, Any]) -> None:
    """Record host identity in local lockfile metadata (audit trail, no secret values)."""
    host_meta = {
        k: sync_identity[k]
        for k in ("hostname", "host_fqdn", "os_user", "platform")
        if sync_identity.get(k) is not None
    }
    if host_meta:
        local_lockfile.metadata["local_host"] = host_meta
