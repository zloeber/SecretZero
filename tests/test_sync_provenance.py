"""Tests for target provenance actor enrichment."""

import json
from pathlib import Path

from secretzero.lockfile import Lockfile, LockfileSyncIdentity
from secretzero.models import Secretfile
from secretzero.sync import SyncEngine


def test_target_provenance_actor_merges_provider_metadata() -> None:
    engine = SyncEngine(
        Secretfile(secrets=[]),
        Lockfile(),
        sync_identity=LockfileSyncIdentity(client="cli", os_user="alice", git_user_name="Alice"),
    )

    merged = engine._target_provenance_actor(  # noqa: SLF001 - intentional unit coverage
        {
            "provider": "aws",
            "username": "session-user",
            "account_id": "123456789012",
        }
    )

    assert merged["client"] == "cli"
    assert merged["os_user"] == "alice"
    assert merged["provider"] == "aws"
    assert merged["username"] == "session-user"
    assert merged["account_id"] == "123456789012"


def test_target_provenance_actor_drops_none_values() -> None:
    engine = SyncEngine(
        Secretfile(secrets=[]),
        Lockfile(),
        sync_identity=LockfileSyncIdentity(client="cli", os_user="alice"),
    )

    merged = engine._target_provenance_actor(  # noqa: SLF001 - intentional unit coverage
        {
            "provider": "aws",
            "username": None,
            "account_id": "123456789012",
            "nested": {"tenant": None, "region": "us-east-1"},
        }
    )

    assert "username" not in merged
    assert merged["nested"] == {"region": "us-east-1"}


def test_saved_target_actor_omits_none_values(tmp_path: Path) -> None:
    lock = Lockfile()
    lock.add_secret("demo", "value", target_id="local/file/.env")
    lock.record_target_update(
        "demo",
        "local/file/.env",
        actor={
            "provider": "local",
            "username": None,
            "nested": {"region": "us-east-1", "id": None},
        },
    )
    out = tmp_path / ".gitsecrets.lock"
    lock.save(out)
    payload = json.loads(out.read_text())
    actor = payload["secrets"]["demo"]["target_provenance"]["local/file/.env"][0]["actor"]
    assert actor == {"provider": "local", "nested": {"region": "us-east-1"}}
