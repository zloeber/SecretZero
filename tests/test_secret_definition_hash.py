"""Tests for per-secret definition hashing and drift detection."""

from pathlib import Path

from secretzero.lockfile import Lockfile, SecretfileMetadata
from secretzero.lockfile_state import (
    definition_drift_for_secret,
    secretfile_tracking_changed,
    sync_state_for_secret_target,
)
from secretzero.models import Secret, Secretfile, TargetConfig
from secretzero.secret_definition_hash import hash_secret_definition, stored_definition_hash


def _secret(**overrides) -> Secret:
    base = {
        "name": "api_key",
        "kind": "random_password",
        "config": {"length": 32},
        "targets": [
            TargetConfig(provider="local", kind="file", config={"path": ".env"}),
        ],
    }
    base.update(overrides)
    return Secret(**base)


def test_hash_secret_definition_stable_for_same_definition() -> None:
    secret = _secret()
    assert hash_secret_definition(secret) == hash_secret_definition(secret)


def test_hash_secret_definition_changes_when_target_changes() -> None:
    secret_a = _secret()
    secret_b = _secret(
        targets=[
            TargetConfig(provider="local", kind="file", config={"path": ".env.prod"}),
        ]
    )
    assert hash_secret_definition(secret_a) != hash_secret_definition(secret_b)


def test_stored_definition_hash_reads_parent_or_template_field() -> None:
    lock = Lockfile()
    lock.add_secret("api_key", "value", definition_hash="abc")
    secret = _secret()
    assert stored_definition_hash(lock, secret) == "abc"

    lock.add_secret("db.password", "value", definition_hash="tpl")
    template_secret = Secret(name="db", kind="templates.db", config={}, targets=[])
    assert stored_definition_hash(lock, template_secret) == "tpl"


def test_definition_drift_only_when_secretfile_changed() -> None:
    secret = _secret()
    path = Path("Secretfile.yml")
    original = "original: true\n"
    changed = "original: false\n"

    lock = Lockfile()
    lock.add_secret("api_key", "value", definition_hash=hash_secret_definition(secret))
    lock.secretfile = SecretfileMetadata(
        filename="Secretfile.yml",
        hash=Lockfile._hash_value(original),
        synced_at="2026-01-01T00:00:00+00:00",
    )

    assert not secretfile_tracking_changed(lock, path, original)
    assert not definition_drift_for_secret(
        lock,
        secret,
        secretfile_path=path,
        secretfile_content=original,
    )

    modified = _secret(config={"length": 24})
    assert secretfile_tracking_changed(lock, path, changed)
    assert not definition_drift_for_secret(
        lock,
        modified,
        secretfile_path=path,
        secretfile_content=original,
    )
    assert definition_drift_for_secret(
        lock,
        modified,
        secretfile_path=path,
        secretfile_content=changed,
    )


def test_definition_drift_false_when_only_unrelated_secretfile_changes() -> None:
    secret = _secret()
    path = Path("Secretfile.yml")
    lock = Lockfile()
    lock.add_secret("api_key", "value", definition_hash=hash_secret_definition(secret))
    lock.secretfile = SecretfileMetadata(
        filename="Secretfile.yml",
        hash=Lockfile._hash_value("v1\n"),
        synced_at="2026-01-01T00:00:00+00:00",
    )

    assert not definition_drift_for_secret(
        lock,
        secret,
        secretfile_path=path,
        secretfile_content="v2\n",
    )


def test_sync_state_marks_definition_drift() -> None:
    secret = _secret()
    target = secret.targets[0]
    path = Path("Secretfile.yml")
    original = "v1\n"
    changed = "v2\n"

    lock = Lockfile()
    lock.add_secret("api_key", "value", target_id="local/file/.env")
    lock.record_definition_hash("api_key", hash_secret_definition(secret))
    lock.secretfile = SecretfileMetadata(
        filename="Secretfile.yml",
        hash=Lockfile._hash_value(original),
        synced_at="2026-01-01T00:00:00+00:00",
    )

    assert (
        sync_state_for_secret_target(
            lock,
            secret.name,
            target,
            secret=secret,
            secretfile_path=path,
            secretfile_content=original,
        )
        == "synced"
    )

    modified = _secret(config={"length": 16})
    assert (
        sync_state_for_secret_target(
            lock,
            secret.name,
            target,
            secret=modified,
            secretfile_path=path,
            secretfile_content=changed,
        )
        == "drift"
    )
