"""Tests for Keeper provider and target behavior."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from secretzero.providers.keeper import KeeperAuth, KeeperProvider
from secretzero.sync import SyncEngine
from secretzero.targets.keeper import KeeperRecordTarget


class _FakePasswordRecord:
    def __init__(self, title: str = "DB Password", password: str = "old-secret"):
        self.record_uid = "uid-db-password"
        self.title = title
        self.login = "admin"
        self.password = password
        self.link = ""
        self.notes = ""
        self.custom: list[Any] = []


class _FakeParams:
    def __init__(self) -> None:
        self.user = "admin@example.com"
        self.config = {"server": "keepersecurity.com"}
        self.config_filename = "/tmp/config.json"
        self.session_token = "session-token"
        self.record_cache = {"uid-db-password": {"version": 2}}
        self.environment_variables: dict[str, str] = {}


@pytest.fixture
def fake_params() -> _FakeParams:
    return _FakeParams()


@pytest.fixture
def provider(fake_params: _FakeParams) -> KeeperProvider:
    auth = KeeperAuth({"user": "admin@example.com"})
    auth._params = fake_params  # noqa: SLF001
    auth._logged_in = True  # noqa: SLF001
    keeper = KeeperProvider("keeper", config={"sync_ttl_seconds": 0}, auth=auth)
    keeper._last_sync_at = None  # noqa: SLF001
    return keeper


def test_retrieve_secret_returns_password_field(provider: KeeperProvider) -> None:
    record = _FakePasswordRecord()

    with (
        patch.object(provider, "_ensure_synced"),
        patch.object(provider, "_resolve_locator", return_value=(record, record.record_uid)),
        patch.object(KeeperProvider, "_extract_field", return_value="old-secret"),
    ):
        value = provider.retrieve_secret(
            "db_password",
            record_uid="uid-db-password",
            field="password",
        )

    assert value == "old-secret"


def test_retrieve_secret_structured_returns_json(provider: KeeperProvider) -> None:
    record = _FakePasswordRecord()

    with (
        patch.object(provider, "_ensure_synced"),
        patch.object(provider, "_resolve_locator", return_value=(record, record.record_uid)),
        patch.object(
            KeeperProvider,
            "_extract_record_payload",
            return_value={"login": "admin", "password": "old-secret"},
        ),
    ):
        value = provider.retrieve_secret(
            "db_password",
            record_uid="uid-db-password",
            structured=True,
        )

    assert json.loads(value) == {"login": "admin", "password": "old-secret"}


def test_store_secret_updates_existing_record(provider: KeeperProvider) -> None:
    editable = _FakePasswordRecord()

    with (
        patch.object(provider, "_ensure_synced"),
        patch.object(provider, "_resolve_locator", return_value=(editable, editable.record_uid)),
        patch.object(provider, "_push_record_update") as push_update,
    ):
        result = provider.store_secret(
            "db_password",
            "new-secret",
            record_uid="uid-db-password",
            field="password",
        )

    assert result is True
    assert editable.password == "new-secret"
    push_update.assert_called_once_with(editable)


def test_store_secret_create_if_missing(provider: KeeperProvider) -> None:
    created = _FakePasswordRecord(title="New Record", password="generated")

    with (
        patch.object(provider, "_ensure_synced"),
        patch.object(
            KeeperProvider,
            "_resolve_record",
            side_effect=ValueError("Keeper record not found: New Record"),
        ),
        patch.object(
            provider, "_create_record", return_value=(created, created.record_uid)
        ) as create_record,
        patch.object(provider, "_push_record_update"),
    ):
        result = provider.store_secret(
            "new_record",
            "generated",
            title="New Record",
            create_if_missing=True,
            field="password",
        )

    assert result is True
    create_record.assert_called_once()
    assert provider.last_record_uid == created.record_uid


def test_store_secret_structured_applies_multiple_fields(provider: KeeperProvider) -> None:
    editable = _FakePasswordRecord()

    with (
        patch.object(provider, "_ensure_synced"),
        patch.object(provider, "_resolve_locator", return_value=(editable, editable.record_uid)),
        patch.object(provider, "_push_record_update"),
    ):
        payload = json.dumps(
            {"login": "bot", "password": "secret", "url": "https://example.com"},
            sort_keys=True,
        )
        result = provider.store_secret(
            "service_account",
            payload,
            record_uid="uid-db-password",
            structured=True,
        )

    assert result is True
    assert editable.login == "bot"
    assert editable.password == "secret"
    assert editable.link == "https://example.com"


def test_rotate_secret_delegates_to_store(provider: KeeperProvider) -> None:
    with patch.object(provider, "store_secret", return_value=True) as store_secret:
        assert provider.rotate_secret("db_password", "rotated", record_uid="uid") is True
    store_secret.assert_called_once()


def test_generate_password_uses_commander_generator(provider: KeeperProvider) -> None:
    with patch(
        "keepercommander.commands.record_edit.RecordEditMixin.generate_password",
        return_value="GeneratedPass123!",
    ):
        assert provider.generate_password(length=24) == "GeneratedPass123!"


def test_ambiguous_title_lists_record_uids(
    provider: KeeperProvider, fake_params: _FakeParams
) -> None:
    first = _FakePasswordRecord(title="Duplicate")
    second = _FakePasswordRecord(title="Duplicate")
    second.record_uid = "uid-second"
    fake_params.record_cache = {
        first.record_uid: {"version": 2},
        second.record_uid: {"version": 2},
    }

    with (
        patch.object(provider, "_ensure_synced"),
        patch("keepercommander.commands.base.RecordMixin.resolve_single_record", return_value=None),
        patch(
            "keepercommander.vault.KeeperRecord.load",
            side_effect=[first, second],
        ),
    ):
        with pytest.raises(ValueError, match="Ambiguous Keeper record title"):
            provider._resolve_record(fake_params, record_uid=None, locator="Duplicate")


def test_target_resolve_target_id_uses_last_record_uid() -> None:
    mock_provider = MagicMock()
    mock_provider.name = "keeper"
    mock_provider.last_record_uid = "uid-created"
    target = KeeperRecordTarget(mock_provider, {"title": "Example", "create_if_missing": True})

    assert target.resolve_target_id("example") == "keeper/keeper_record/uid-created"


def test_build_target_id_prefers_record_uid() -> None:
    target = MagicMock()
    target.provider = "keeper"
    target.kind = "keeper_record"
    target.config = {"title": "Example", "record_uid": "uid-123"}

    assert SyncEngine._build_target_id(target) == "keeper/keeper_record/uid-123"


def test_target_store_delegates_to_provider() -> None:
    mock_provider = MagicMock()
    mock_provider.store_secret.return_value = True
    target = KeeperRecordTarget(
        mock_provider,
        {"record_uid": "uid-db-password", "field": "password"},
    )

    assert target.store("db_password", "generated") is True
    mock_provider.store_secret.assert_called_once_with(
        secret_name="db_password",
        secret_value="generated",
        record_uid="uid-db-password",
        path=None,
        title=None,
        name="db_password",
        field="password",
        structured=False,
        fields=None,
        create_if_missing=False,
        record_type="login",
        folder=None,
    )


def test_auth_reports_token_info(fake_params: _FakeParams) -> None:
    auth = KeeperAuth({"user": "admin@example.com"})
    auth._params = fake_params  # noqa: SLF001
    auth._logged_in = True  # noqa: SLF001

    info = auth.get_token_info()

    assert info["user"] == "admin@example.com"
    assert info["token_type"] == "keeper_session"
    assert info["server"] == "keepersecurity.com"


def test_target_requires_locator() -> None:
    with pytest.raises(ValueError, match="requires one of"):
        KeeperRecordTarget(MagicMock(), {})


def test_target_allows_create_if_missing_without_locator() -> None:
    target = KeeperRecordTarget(MagicMock(), {"create_if_missing": True})
    assert target.create_if_missing is True
