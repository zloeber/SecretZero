"""Vault KV target field merge: one path, many named fields, CAS on v2."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

hvac = pytest.importorskip("hvac")
from hvac.exceptions import InvalidPath, InvalidRequest

from secretzero.providers.vault import VaultAuth, VaultProvider
from secretzero.targets.vault import VaultKVTarget

_PATH = "app/tls/example"
_MOUNT = "kv"


def _target(config: dict[str, Any], client: MagicMock) -> VaultKVTarget:
    auth = VaultAuth({"kind": "token", "url": "https://vault.example.com:8200", "token": "s.test"})
    auth.get_client = lambda: client  # type: ignore[method-assign]
    provider = MagicMock()
    provider.auth = auth
    return VaultKVTarget(provider=provider, config=config)


def _v2_config(**extra: Any) -> dict[str, Any]:
    config: dict[str, Any] = {"path": _PATH, "mount_point": _MOUNT, "version": 2}
    config.update(extra)
    return config


def _v2_response(data: dict[str, Any], version: int) -> dict[str, Any]:
    return {"data": {"data": data, "metadata": {"version": version}}}


def test_store_without_field_replaces_document_with_value_key() -> None:
    client = MagicMock()
    target = _target(_v2_config(), client)

    assert target.store("TLS_CHAIN", "chain-pem") is True

    kwargs = client.secrets.kv.v2.create_or_update_secret.call_args.kwargs
    assert kwargs["path"] == _PATH
    assert kwargs["mount_point"] == _MOUNT
    assert kwargs["secret"] == {"value": "chain-pem"}
    assert "cas" not in kwargs
    client.secrets.kv.v2.read_secret_version.assert_not_called()


def test_retrieve_without_field_returns_full_map() -> None:
    client = MagicMock()
    client.secrets.kv.v2.read_secret_version.return_value = _v2_response(
        {"value": "chain-pem", "other": "kept"}, 3
    )
    target = _target(_v2_config(), client)

    assert target.retrieve("TLS_CHAIN") == {"value": "chain-pem", "other": "kept"}


def test_store_field_creates_with_cas_zero_when_missing() -> None:
    client = MagicMock()
    client.secrets.kv.v2.read_secret_version.side_effect = InvalidPath("missing")
    target = _target(_v2_config(field="chain"), client)

    assert target.store("TLS_CHAIN", "chain-pem") is True

    kwargs = client.secrets.kv.v2.create_or_update_secret.call_args.kwargs
    assert kwargs["secret"] == {"chain": "chain-pem"}
    assert kwargs["cas"] == 0
    assert kwargs["path"] == _PATH
    assert kwargs["mount_point"] == _MOUNT


def test_store_field_merges_existing_map_with_cas() -> None:
    client = MagicMock()
    client.secrets.kv.v2.read_secret_version.return_value = _v2_response(
        {"chain": "chain-pem", "extra": "keep"}, 4
    )
    target = _target(_v2_config(field="key"), client)

    assert target.store("TLS_KEY", "key-pem") is True

    kwargs = client.secrets.kv.v2.create_or_update_secret.call_args.kwargs
    assert kwargs["secret"] == {"chain": "chain-pem", "extra": "keep", "key": "key-pem"}
    assert kwargs["cas"] == 4


def test_store_field_cas_conflict_fails_without_blind_overwrite() -> None:
    client = MagicMock()
    client.secrets.kv.v2.read_secret_version.return_value = _v2_response({"chain": "old"}, 2)
    client.secrets.kv.v2.create_or_update_secret.side_effect = InvalidRequest("check-and-set")
    target = _target(_v2_config(field="key"), client)

    assert target.store("TLS_KEY", "key-pem") is False

    kwargs = client.secrets.kv.v2.create_or_update_secret.call_args.kwargs
    assert kwargs["cas"] == 2
    assert kwargs["secret"]["chain"] == "old"
    assert kwargs["secret"]["key"] == "key-pem"
    assert client.secrets.kv.v2.create_or_update_secret.call_count == 1


def test_store_field_read_error_does_not_create() -> None:
    client = MagicMock()
    client.secrets.kv.v2.read_secret_version.side_effect = RuntimeError("permission denied")
    target = _target(_v2_config(field="chain"), client)

    assert target.store("TLS_CHAIN", "chain-pem") is False
    client.secrets.kv.v2.create_or_update_secret.assert_not_called()


def test_retrieve_field_returns_only_that_value() -> None:
    client = MagicMock()
    client.secrets.kv.v2.read_secret_version.return_value = _v2_response(
        {"chain": "chain-pem", "key": "key-pem"}, 1
    )
    target = _target(_v2_config(field="key"), client)

    assert target.retrieve("TLS_KEY") == "key-pem"


def test_retrieve_missing_field_returns_none() -> None:
    client = MagicMock()
    client.secrets.kv.v2.read_secret_version.return_value = _v2_response({"chain": "chain-pem"}, 1)
    target = _target(_v2_config(field="key"), client)

    assert target.retrieve("TLS_KEY") is None


def test_retrieve_missing_secret_returns_none() -> None:
    client = MagicMock()
    client.secrets.kv.v2.read_secret_version.side_effect = InvalidPath("missing")
    target = _target(_v2_config(field="chain"), client)

    assert target.retrieve("TLS_CHAIN") is None


def test_blank_field_keeps_whole_document_behavior() -> None:
    client = MagicMock()
    target = _target(_v2_config(field="  "), client)

    assert target.store("TLS_CHAIN", "chain-pem") is True
    kwargs = client.secrets.kv.v2.create_or_update_secret.call_args.kwargs
    assert kwargs["secret"] == {"value": "chain-pem"}
    assert "cas" not in kwargs


def test_kv_v1_field_merges_without_cas() -> None:
    client = MagicMock()
    client.secrets.kv.v1.read_secret.return_value = {"data": {"chain": "chain-pem"}}
    target = _target(
        {"path": _PATH, "mount_point": _MOUNT, "version": 1, "field": "key"},
        client,
    )

    assert target.store("TLS_KEY", "key-pem") is True

    kwargs = client.secrets.kv.v1.create_or_update_secret.call_args.kwargs
    assert kwargs["secret"] == {"chain": "chain-pem", "key": "key-pem"}
    assert "cas" not in kwargs


def test_kv_v1_field_creates_when_missing() -> None:
    client = MagicMock()
    client.secrets.kv.v1.read_secret.side_effect = InvalidPath("missing")
    target = _target(
        {"path": _PATH, "mount_point": _MOUNT, "version": 1, "field": "chain"},
        client,
    )

    assert target.store("TLS_CHAIN", "chain-pem") is True
    kwargs = client.secrets.kv.v1.create_or_update_secret.call_args.kwargs
    assert kwargs["secret"] == {"chain": "chain-pem"}


def test_delete_field_rewrites_remaining_map() -> None:
    client = MagicMock()
    client.secrets.kv.v2.read_secret_version.return_value = _v2_response(
        {"chain": "chain-pem", "key": "key-pem"}, 5
    )
    target = _target(_v2_config(field="key"), client)

    assert target.delete("TLS_KEY") is True

    kwargs = client.secrets.kv.v2.create_or_update_secret.call_args.kwargs
    assert kwargs["secret"] == {"chain": "chain-pem"}
    assert kwargs["cas"] == 5
    client.secrets.kv.v2.delete_metadata_and_all_versions.assert_not_called()


def test_delete_last_field_removes_metadata() -> None:
    client = MagicMock()
    client.secrets.kv.v2.read_secret_version.return_value = _v2_response({"key": "key-pem"}, 2)
    target = _target(_v2_config(field="key"), client)

    assert target.delete("TLS_KEY") is True

    client.secrets.kv.v2.create_or_update_secret.assert_not_called()
    client.secrets.kv.v2.delete_metadata_and_all_versions.assert_called_once_with(
        path=_PATH, mount_point=_MOUNT
    )


def test_kv_v1_delete_field_rewrites_remaining_map() -> None:
    client = MagicMock()
    client.secrets.kv.v1.read_secret.return_value = {
        "data": {"chain": "chain-pem", "key": "key-pem"}
    }
    target = _target(
        {"path": _PATH, "mount_point": _MOUNT, "version": 1, "field": "key"},
        client,
    )

    assert target.delete("TLS_KEY") is True

    kwargs = client.secrets.kv.v1.create_or_update_secret.call_args.kwargs
    assert kwargs["secret"] == {"chain": "chain-pem"}
    assert "cas" not in kwargs
    client.secrets.kv.v1.delete_secret.assert_not_called()


def test_kv_v1_delete_last_field_removes_secret() -> None:
    client = MagicMock()
    client.secrets.kv.v1.read_secret.return_value = {"data": {"key": "key-pem"}}
    target = _target(
        {"path": _PATH, "mount_point": _MOUNT, "version": 1, "field": "key"},
        client,
    )

    assert target.delete("TLS_KEY") is True

    client.secrets.kv.v1.create_or_update_secret.assert_not_called()
    client.secrets.kv.v1.delete_secret.assert_called_once_with(path=_PATH, mount_point=_MOUNT)


def test_terraform_export_uses_configured_field_name() -> None:
    from secretzero.models import Secret, TargetConfig
    from secretzero.terraform_export import TerraformProject, _map_target_to_resources

    secret = Secret(name="tls_key", kind="static", config={"value": "placeholder"})
    project = TerraformProject()
    _map_target_to_resources(
        secret,
        TargetConfig(
            provider="vault",
            kind="kv",
            config={"path": _PATH, "mount_point": _MOUNT, "field": "key"},
        ),
        "${var.secret_tls_key}",
        project,
    )
    assert (
        project.resources[0].attributes["data_json"]
        == '${jsonencode({"key" = ${var.secret_tls_key}})}'
    )

    untouched = TerraformProject()
    _map_target_to_resources(
        secret,
        TargetConfig(provider="vault", kind="kv", config={"path": _PATH, "mount_point": _MOUNT}),
        "${var.secret_tls_key}",
        project=untouched,
    )
    assert (
        untouched.resources[0].attributes["data_json"]
        == '${jsonencode({"value" = ${var.secret_tls_key}})}'
    )


def test_delete_without_field_removes_all_versions() -> None:
    client = MagicMock()
    target = _target(_v2_config(), client)

    assert target.delete("TLS_CHAIN") is True

    client.secrets.kv.v2.read_secret_version.assert_not_called()
    client.secrets.kv.v2.delete_metadata_and_all_versions.assert_called_once_with(
        path=_PATH, mount_point=_MOUNT
    )


def test_target_details_document_field() -> None:
    config = VaultProvider.target_details["vault_kv"]["config"]
    assert "field" in config
