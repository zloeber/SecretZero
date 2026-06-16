"""Shared lockfile state helpers for dashboard/graph/CLI surfaces."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from secretzero.lockfile import Lockfile, SecretLockEntry
from secretzero.models import Secret, Secretfile, TargetConfig
from secretzero.secret_definition_hash import hash_secret_definition, stored_definition_hash
from secretzero.sync import SyncEngine


def kind_str(kind: Any) -> str:
    """Return normalized kind string for enum or plain values."""
    if isinstance(kind, Enum):
        return str(kind.value)
    return str(kind)


def target_id(target: TargetConfig) -> str:
    """Canonical target id matching SyncEngine lockfile semantics."""
    return SyncEngine._build_target_id(target)


def lock_hash_for_target(
    entry: SecretLockEntry | None, tid: str, target: TargetConfig
) -> str | None:
    """Resolve per-target hash from lockfile, including legacy file target ids."""
    if not entry or not entry.targets:
        return None
    h = entry.targets.get(tid)
    if h is not None:
        return h
    if kind_str(target.kind) == "file":
        return entry.targets.get(f"{target.provider}/file/")
    return None


def secretfile_tracking_changed(
    lockfile: Lockfile,
    secretfile_path: Path | None,
    secretfile_content: str | None,
) -> bool:
    """True when the on-disk Secretfile differs from the lockfile's tracked copy."""
    if not secretfile_path or secretfile_content is None or lockfile.secretfile is None:
        return False
    return lockfile.secretfile_changed(secretfile_path, secretfile_content)


def definition_drift_for_secret(
    lockfile: Lockfile,
    secret: Secret,
    *,
    secretfile: Secretfile | None = None,
    secretfile_path: Path | None = None,
    secretfile_content: str | None = None,
) -> bool:
    """Return True when the secret definition changed since the last sync.

    Comparison runs only when the file-level Secretfile hash has changed.
    """
    if not secretfile_tracking_changed(lockfile, secretfile_path, secretfile_content):
        return False

    tracked = stored_definition_hash(lockfile, secret)
    if tracked is None:
        return False

    current = hash_secret_definition(secret, secretfile=secretfile)
    return tracked != current


def sync_state_for_target(
    entry: SecretLockEntry | None,
    locked_hash: str | None,
    *,
    definition_drift: bool = False,
) -> str:
    """Return sync state for a target: synced | pending | drift."""
    if definition_drift:
        return "drift"
    if not entry or not entry.hash:
        return "pending"
    if locked_hash is None:
        return "pending"
    if locked_hash == entry.hash:
        return "synced"
    return "drift"


def sync_state_for_secret_target(
    lockfile: Lockfile,
    secret_name: str,
    target: TargetConfig,
    *,
    secret: Secret | None = None,
    secretfile: Secretfile | None = None,
    secretfile_path: Path | None = None,
    secretfile_content: str | None = None,
) -> str:
    """Resolve sync state for a secret/target pair using canonical lockfile logic."""
    definition_drift = False
    if secret is not None:
        definition_drift = definition_drift_for_secret(
            lockfile,
            secret,
            secretfile=secretfile,
            secretfile_path=secretfile_path,
            secretfile_content=secretfile_content,
        )

    entry = lockfile.get_secret_info(secret_name)
    tid = target_id(target)
    locked = lock_hash_for_target(entry, tid, target)
    return sync_state_for_target(entry, locked, definition_drift=definition_drift)
