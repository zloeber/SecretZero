"""Tests for canonical lockfile sync-state helpers."""

from secretzero.lockfile import Lockfile
from secretzero.lockfile_state import (
    lock_hash_for_target,
    sync_state_for_secret_target,
    sync_state_for_target,
    target_id,
)
from secretzero.models import TargetConfig


def test_sync_state_for_secret_target_synced_drift_pending() -> None:
    lockfile = Lockfile()
    synced_target = TargetConfig(provider="local", kind="file", config={"path": ".env.synced"})
    drift_target = TargetConfig(provider="local", kind="file", config={"path": ".env.drift"})
    pending_target = TargetConfig(provider="local", kind="file", config={"path": ".env.pending"})

    lockfile.add_secret("api_key", "value", target_id=target_id(synced_target))
    entry = lockfile.get_secret_info("api_key")
    assert entry is not None
    entry.targets[target_id(drift_target)] = "different-hash"

    assert sync_state_for_secret_target(lockfile, "api_key", synced_target) == "synced"
    assert sync_state_for_secret_target(lockfile, "api_key", drift_target) == "drift"
    assert sync_state_for_secret_target(lockfile, "api_key", pending_target) == "pending"


def test_lock_hash_for_target_supports_legacy_file_target_id() -> None:
    lockfile = Lockfile()
    file_target = TargetConfig(provider="local", kind="file", config={"path": ".env"})
    lockfile.add_secret("db_password", "value")
    entry = lockfile.get_secret_info("db_password")
    assert entry is not None
    entry.targets["local/file/"] = entry.hash

    resolved = lock_hash_for_target(entry, target_id(file_target), file_target)
    assert resolved == entry.hash


def test_sync_state_for_target_definition_drift() -> None:
    lockfile = Lockfile()
    lockfile.add_secret("api_key", "value", target_id="local/file/.env")
    entry = lockfile.get_secret_info("api_key")
    assert entry is not None
    assert sync_state_for_target(entry, entry.hash, definition_drift=True) == "drift"
