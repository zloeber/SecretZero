"""Tests for workstation-local secrets and .gitsecrets.local.lock routing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from secretzero.config import ConfigLoader
from secretzero.local_secrets import LOCAL_LOCKFILE_NAME, load_lockfile_pair, save_lockfile_pair
from secretzero.lockfile import Lockfile, LockfileSyncIdentity
from secretzero.models import Provider, Secret, Secretfile, TargetConfig
from secretzero.sync import SyncEngine


def _mysql_local_secretfile(env_path: Path) -> Secretfile:
    return Secretfile(
        providers={"local": Provider(kind="local")},
        secrets=[
            Secret(
                name="mysql_root_password",
                kind="random_password",
                config={"length": 24, "special": True},
                local=True,
                targets=[
                    TargetConfig(
                        provider="local",
                        kind="file",
                        config={
                            "path": str(env_path),
                            "format": "dotenv",
                            "merge": True,
                        },
                    ),
                ],
            ),
        ],
    )


class TestLocalLockfileRouting:
    def test_local_secret_not_written_to_shared_lockfile(self, tmp_path: Path) -> None:
        env_path = tmp_path / ".env.db"
        global_lock_path = tmp_path / ".gitsecrets.lock"
        secretfile = _mysql_local_secretfile(env_path)

        global_lock = Lockfile()
        local_lock = Lockfile()
        engine = SyncEngine(
            secretfile,
            global_lock,
            local_lockfile=local_lock,
            secretfile_path=tmp_path / "Secretfile.yml",
            secretfile_content="local: true",
            prompt_on_empty=False,
        )

        result = engine.sync(dry_run=False)
        assert result["secrets_stored"] == 1
        assert not global_lock.has_secret("mysql_root_password")
        assert local_lock.has_secret("mysql_root_password")
        assert env_path.exists()

        save_lockfile_pair(global_lock_path, global_lock, local_lock)
        assert (tmp_path / LOCAL_LOCKFILE_NAME).exists()
        shared_payload = json.loads(global_lock_path.read_text())
        assert "mysql_root_password" not in shared_payload.get("secrets", {})

    def test_two_workstations_generate_independent_local_state(self, tmp_path: Path) -> None:
        """Simulate two developers merging the same Secretfile without lockfile conflicts."""
        env_a = tmp_path / "ws-a.env"
        env_b = tmp_path / "ws-b.env"
        global_lock_path = tmp_path / ".gitsecrets.lock"

        secretfile = _mysql_local_secretfile(env_a)

        # Workstation A
        global_lock = Lockfile()
        local_a = Lockfile()
        engine_a = SyncEngine(
            secretfile,
            global_lock,
            local_lockfile=local_a,
            sync_identity=LockfileSyncIdentity(client="cli", hostname="ws-a"),
            prompt_on_empty=False,
        )
        engine_a.sync(dry_run=False)
        hash_a = local_a.get_secret_hash("mysql_root_password")
        save_lockfile_pair(global_lock_path, global_lock, local_a)

        # Workstation B pulls main: same Secretfile, fresh local lockfile
        secretfile_b = _mysql_local_secretfile(env_b)
        global_lock_b, _ = load_lockfile_pair(global_lock_path)
        local_b = Lockfile()
        engine_b = SyncEngine(
            secretfile_b,
            global_lock_b,
            local_lockfile=local_b,
            sync_identity=LockfileSyncIdentity(client="cli", hostname="ws-b"),
            prompt_on_empty=False,
        )
        engine_b.sync(dry_run=False)
        hash_b = local_b.get_secret_hash("mysql_root_password")

        assert hash_a is not None
        assert hash_b is not None
        assert hash_a != hash_b
        assert not global_lock_b.has_secret("mysql_root_password")
        assert local_b.has_secret("mysql_root_password")
        if global_lock_path.exists():
            shared_secrets = json.loads(global_lock_path.read_text()).get("secrets", {})
            assert "mysql_root_password" not in shared_secrets

    def test_local_secret_rejects_cloud_target(self) -> None:
        with pytest.raises(ValueError, match="local-only"):
            Secret(
                name="bad",
                kind="static",
                config={"default": "x"},
                local=True,
                targets=[
                    TargetConfig(
                        provider="aws",
                        kind="secrets_manager",
                        config={"name": "/prod/x"},
                    ),
                ],
            )

    def test_local_flag_supports_variable_interpolation(self, tmp_path: Path) -> None:
        secretfile_path = tmp_path / "Secretfile.yml"
        secretfile_path.write_text(
            """
variables:
  IS_LOCAL_ENV: "true"
providers:
  local:
    kind: local
secrets:
  - name: dev_only
    kind: static
    config:
      default: demo
    local: ${IS_LOCAL_ENV:-false}
    targets:
      - provider: local
        kind: file
        config:
          path: .env.dev
          format: dotenv
templates: {}
""",
            encoding="utf-8",
        )
        config = ConfigLoader().load_file(secretfile_path)
        assert config.secrets[0].local is True
