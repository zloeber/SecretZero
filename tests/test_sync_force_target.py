"""Tests for per-target forced re-sync (``force_targets`` / ``--force-target``)."""

import json
from pathlib import Path

import pytest

from secretzero.config import ConfigLoader
from secretzero.lockfile import Lockfile
from secretzero.sync import SyncEngine


@pytest.fixture
def secretfile_two_file_targets(tmp_path: Path) -> Path:
    """One secret, two local file targets (different paths)."""
    a = tmp_path / "a.env"
    b = tmp_path / "b.env"
    a.write_text("shared_secret=abcdefgh\n")
    b.write_text("shared_secret=abcdefgh\n")
    p = tmp_path / "Secretfile.yml"
    p.write_text(f"""
version: '1.0'
providers:
  local:
    kind: local
secrets:
  - name: shared_secret
    kind: random_string
    config:
      length: 8
    targets:
      - provider: local
        kind: file
        config:
          path: {a}
          format: dotenv
      - provider: local
        kind: file
        config:
          path: {b}
          format: dotenv
""")
    return p


def test_sync_skips_when_all_targets_tracked(
    secretfile_two_file_targets: Path, tmp_path: Path
) -> None:
    loader = ConfigLoader()
    config = loader.load_file(secretfile_two_file_targets)
    sec = config.secrets[0]
    id_a = SyncEngine._build_target_id(sec.targets[0])
    id_b = SyncEngine._build_target_id(sec.targets[1])
    lock_path = tmp_path / "t.lock"
    # Both targets synced with same hash as current value would imply — minimal lock: both ids present
    lock_path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "secrets": {
                    "shared_secret": {
                        "hash": "H",
                        "created_at": "2020-01-01T00:00:00Z",
                        "updated_at": "2020-01-01T00:00:00Z",
                        "targets": {
                            id_a: "H",
                            id_b: "H",
                        },
                    }
                },
            }
        )
    )
    lock = Lockfile.load(lock_path)
    eng = SyncEngine(config, lock)
    r = eng.sync(dry_run=True, secret_names=["shared_secret"])
    assert r["details"][0].get("skipped") is True
    assert "already synced" in (r["details"][0].get("reason") or "")


def test_force_target_repushes_despite_tracked(
    secretfile_two_file_targets: Path, tmp_path: Path
) -> None:
    loader = ConfigLoader()
    config = loader.load_file(secretfile_two_file_targets)
    sec = config.secrets[0]
    id_a = SyncEngine._build_target_id(sec.targets[0])
    id_b = SyncEngine._build_target_id(sec.targets[1])
    lock_path = tmp_path / "t.lock"
    lock_path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "secrets": {
                    "shared_secret": {
                        "hash": "H",
                        "created_at": "2020-01-01T00:00:00Z",
                        "updated_at": "2020-01-01T00:00:00Z",
                        "targets": {
                            id_a: "H",
                            id_b: "H",
                        },
                    }
                },
            }
        )
    )
    lock = Lockfile.load(lock_path)
    eng = SyncEngine(config, lock)
    tid_a = id_a
    r = eng.sync(
        dry_run=True,
        secret_names=["shared_secret"],
        force_targets={"shared_secret": frozenset([tid_a])},
    )
    detail = r["details"][0]
    assert detail.get("skipped") is not True
    assert detail.get("dry_run") is True
    assert len(detail["targets"]) >= 1
    assert detail["targets"][0].get("status") == "would_store"


def test_partial_sync_reads_untracked_destination_before_tracked(
    secretfile_two_file_targets: Path, tmp_path: Path
) -> None:
    """When only one target is lockfile-tracked but unreadable, read from the other file."""
    loader = ConfigLoader()
    config = loader.load_file(secretfile_two_file_targets)
    sec = config.secrets[0]
    id_a = SyncEngine._build_target_id(sec.targets[0])
    id_b = SyncEngine._build_target_id(sec.targets[1])
    a_path = sec.targets[0].config["path"]
    b_path = sec.targets[1].config["path"]
    Path(a_path).write_text("\n")  # tracked but no key — retrieve fails
    Path(b_path).write_text("shared_secret=on_disk_b\n")

    lock_path = tmp_path / "t.lock"
    lock_path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "secrets": {
                    "shared_secret": {
                        "hash": "H",
                        "created_at": "2020-01-01T00:00:00Z",
                        "updated_at": "2020-01-01T00:00:00Z",
                        "targets": {id_a: "H"},
                    }
                },
            }
        )
    )
    lock = Lockfile.load(lock_path)
    eng = SyncEngine(config, lock)
    r = eng.sync(dry_run=True, secret_names=["shared_secret"])
    detail = r["details"][0]
    assert detail.get("skipped") is not True
    assert detail.get("retrieved_from_existing") is True


def test_force_target_uses_env_when_retrieve_fails(
    secretfile_two_file_targets: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Non-retrievable targets (simulated) + env var still allow force-target dry-run."""
    monkeypatch.setenv("SHARED_SECRET", "env_value_for_force")
    loader = ConfigLoader()
    config = loader.load_file(secretfile_two_file_targets)
    sec = config.secrets[0]
    id_a = SyncEngine._build_target_id(sec.targets[0])
    id_b = SyncEngine._build_target_id(sec.targets[1])
    lock_path = tmp_path / "t.lock"
    lock_path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "secrets": {
                    "shared_secret": {
                        "hash": "H",
                        "created_at": "2020-01-01T00:00:00Z",
                        "updated_at": "2020-01-01T00:00:00Z",
                        "targets": {
                            id_a: "H",
                            id_b: "H",
                        },
                    }
                },
            }
        )
    )
    lock = Lockfile.load(lock_path)
    eng = SyncEngine(config, lock)
    monkeypatch.setattr(eng, "_retrieve_from_target", lambda _name, _tc: None)
    r = eng.sync(
        dry_run=True,
        secret_names=["shared_secret"],
        force_targets={"shared_secret": frozenset([id_a])},
    )
    detail = r["details"][0]
    assert detail.get("skipped") is not True
    assert detail.get("dry_run") is True
    assert detail["targets"][0].get("status") == "would_store"
