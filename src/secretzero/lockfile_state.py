"""Shared lockfile state helpers for dashboard/graph/CLI surfaces."""

from __future__ import annotations

from enum import Enum
from typing import Any

from secretzero.lockfile import Lockfile, SecretLockEntry
from secretzero.models import TargetConfig
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


def sync_state_for_target(entry: SecretLockEntry | None, locked_hash: str | None) -> str:
    """Return sync state for a target: synced | pending | drift."""
    if not entry or not entry.hash:
        return "pending"
    if locked_hash is None:
        return "pending"
    if locked_hash == entry.hash:
        return "synced"
    return "drift"


def sync_state_for_secret_target(lockfile: Lockfile, secret_name: str, target: TargetConfig) -> str:
    """Resolve sync state for a secret/target pair using canonical lockfile logic."""
    entry = lockfile.get_secret_info(secret_name)
    tid = target_id(target)
    locked = lock_hash_for_target(entry, tid, target)
    return sync_state_for_target(entry, locked)
