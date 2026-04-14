"""Tests for target provenance actor enrichment."""

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
