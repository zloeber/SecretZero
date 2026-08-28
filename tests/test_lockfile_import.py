"""Tests for lockfile import from local dotenv file targets."""

from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from secretzero.cli import main
from secretzero.config import ConfigLoader
from secretzero.lockfile import Lockfile, LockfileSyncIdentity, SecretfileMetadata
from secretzero.lockfile_import import run_lockfile_import
from secretzero.lockfile_state import sync_state_for_secret_target, target_id
from secretzero.secret_definition_hash import hash_secret_definition
from secretzero.sync import SyncEngine

_SEEDED_VALUE = "seeded-token-value"
_ENV_KEY = "JIRA_API_TOKEN"
_SECRET_NAME = "jira_api_token"


def _write_dotenv_manifest(tmp_path: Path) -> Path:
    env_path = tmp_path / ".env"
    env_path.write_text(f"{_ENV_KEY}={_SEEDED_VALUE}\n", encoding="utf-8")
    sf_path = tmp_path / "Secretfile.yml"
    payload = {
        "providers": {"local": {"kind": "local"}},
        "secrets": [
            {
                "name": _SECRET_NAME,
                "kind": "static",
                "config": {},
                "targets": [
                    {
                        "provider": "local",
                        "kind": "file",
                        "config": {
                            "path": str(env_path),
                            "format": "dotenv",
                            "key": _ENV_KEY,
                        },
                    }
                ],
            }
        ],
    }
    sf_path.write_text(yaml.dump(payload), encoding="utf-8")
    return sf_path


def _load_engine(
    tmp_path: Path, lock: Lockfile, *, secretfile_path: Path | None = None
) -> tuple[SyncEngine, Path]:
    sf_path = secretfile_path or _write_dotenv_manifest(tmp_path)
    config = ConfigLoader().load_file(sf_path)
    engine = SyncEngine(
        config,
        lock,
        secretfile_path=sf_path,
        secretfile_content=sf_path.read_text(encoding="utf-8"),
        hide_input=True,
        prompt_on_empty=False,
        sync_client="cli",
        sync_identity=LockfileSyncIdentity(client="cli", os_user="tester"),
    )
    return engine, sf_path


def _status_for(engine: SyncEngine, lock: Lockfile, sf_path: Path) -> str:
    secret = engine.secretfile.secrets[0]
    return sync_state_for_secret_target(
        lock,
        secret.name,
        secret.targets[0],
        secret=secret,
        secretfile=engine.secretfile,
        secretfile_path=sf_path,
        secretfile_content=sf_path.read_text(encoding="utf-8"),
    )


def _import_actor_for(lock: Lockfile, tid: str) -> dict:
    entry = lock.get_secret_info(_SECRET_NAME)
    assert entry is not None
    history = entry.target_provenance.get(tid) or []
    assert history, "expected import provenance on target"
    return dict(history[-1].actor)


def test_import_from_dotenv_seeds_empty_lockfile_and_status_synced(tmp_path: Path) -> None:
    lock = Lockfile()
    engine, sf_path = _load_engine(tmp_path, lock)
    secret = engine.secretfile.secrets[0]
    tid = target_id(secret.targets[0])

    summary = run_lockfile_import(
        engine,
        secretfile=engine.secretfile,
        secretfile_path=sf_path,
        secretfile_content=sf_path.read_text(encoding="utf-8"),
    )

    assert summary["imported"] == 1
    assert summary["errors"] == 0
    entry = lock.get_secret_info(_SECRET_NAME)
    assert entry is not None
    assert entry.hash == Lockfile._hash_value(_SEEDED_VALUE)
    assert entry.targets[tid] == entry.hash
    assert entry.definition_hash == hash_secret_definition(secret, secretfile=engine.secretfile)
    actor = _import_actor_for(lock, tid)
    assert actor["operation"] == "lockfile_import"
    assert actor["source"] == "target"
    assert actor["os_user"] == "tester"
    assert lock.secretfile is not None
    assert lock.secretfile.sync_identity is not None
    assert lock.secretfile.sync_identity.os_user == "tester"
    assert _status_for(engine, lock, sf_path) == "synced"


def test_import_unchanged_refreshes_definition_hash_and_status_synced(tmp_path: Path) -> None:
    sf_path = _write_dotenv_manifest(tmp_path)
    config = ConfigLoader().load_file(sf_path)
    secret = config.secrets[0]
    tid = target_id(secret.targets[0])

    lock = Lockfile()
    lock.add_secret(_SECRET_NAME, _SEEDED_VALUE, target_id=tid, definition_hash="stale-definition")
    lock.secretfile = SecretfileMetadata(
        filename="Secretfile.yml",
        hash=Lockfile._hash_value("previous-secretfile\n"),
        synced_at="2026-01-01T00:00:00+00:00",
    )
    engine, sf_path = _load_engine(tmp_path, lock, secretfile_path=sf_path)

    assert _status_for(engine, lock, sf_path) == "drift"

    summary = run_lockfile_import(
        engine,
        secretfile=engine.secretfile,
        secretfile_path=sf_path,
        secretfile_content=sf_path.read_text(encoding="utf-8"),
    )

    assert summary["unchanged"] == 1
    assert summary["imported"] == 0
    assert summary["updated"] == 0
    entry = lock.get_secret_info(_SECRET_NAME)
    assert entry is not None
    assert entry.definition_hash == hash_secret_definition(secret, secretfile=engine.secretfile)
    actor = _import_actor_for(lock, tid)
    assert actor["operation"] == "lockfile_import"
    assert actor["source"] == "target"
    assert actor["os_user"] == "tester"
    assert lock.secretfile is not None
    assert lock.secretfile.sync_identity is not None
    assert lock.secretfile.sync_identity.os_user == "tester"
    assert _status_for(engine, lock, sf_path) == "synced"


def test_import_updates_stale_per_target_hash_and_status_synced(tmp_path: Path) -> None:
    lock = Lockfile()
    engine, sf_path = _load_engine(tmp_path, lock)
    secret = engine.secretfile.secrets[0]
    tid = target_id(secret.targets[0])
    lock.add_secret(_SECRET_NAME, _SEEDED_VALUE, target_id=tid)
    entry = lock.get_secret_info(_SECRET_NAME)
    assert entry is not None
    entry.targets[tid] = "stale-target-hash"
    lock.secretfile = SecretfileMetadata(
        filename="Secretfile.yml",
        hash=Lockfile._hash_value(sf_path.read_text(encoding="utf-8")),
        synced_at="2026-01-01T00:00:00+00:00",
    )

    assert _status_for(engine, lock, sf_path) == "drift"

    summary = run_lockfile_import(
        engine,
        secretfile=engine.secretfile,
        secretfile_path=sf_path,
        secretfile_content=sf_path.read_text(encoding="utf-8"),
    )

    assert summary["updated"] == 1
    entry = lock.get_secret_info(_SECRET_NAME)
    assert entry is not None
    assert entry.targets[tid] == entry.hash
    actor = _import_actor_for(lock, tid)
    assert actor["operation"] == "lockfile_import"
    assert actor["source"] == "target"
    assert _status_for(engine, lock, sf_path) == "synced"


def test_import_cli_then_status_reports_synced(tmp_path: Path) -> None:
    sf_path = _write_dotenv_manifest(tmp_path)
    config = ConfigLoader().load_file(sf_path)
    secret = config.secrets[0]
    tid = target_id(secret.targets[0])
    lock_path = tmp_path / ".gitsecrets.lock"
    lock = Lockfile()
    lock.add_secret(_SECRET_NAME, _SEEDED_VALUE, target_id=tid, definition_hash="stale-definition")
    lock.secretfile = SecretfileMetadata(
        filename="Secretfile.yml",
        hash=Lockfile._hash_value("previous-secretfile\n"),
        synced_at="2026-01-01T00:00:00+00:00",
    )
    lock.save(lock_path)

    runner = CliRunner()
    imported = runner.invoke(
        main,
        ["import", "-f", str(sf_path), "-l", str(lock_path), "--format", "json"],
    )
    assert imported.exit_code == 0, imported.output

    persisted = Lockfile.load(lock_path)
    actor = _import_actor_for(persisted, tid)
    assert actor["operation"] == "lockfile_import"
    assert actor["source"] == "target"

    status = runner.invoke(main, ["status", "-f", str(sf_path), "-l", str(lock_path)])
    assert status.exit_code == 0, status.output
    assert "synced:1 pending:0" in status.output
