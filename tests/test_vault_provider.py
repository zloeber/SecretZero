"""Tests for HashiCorp Vault authentication and KV/source retrieval."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from secretzero.models import AuthKind, Provider, ProviderAuth, Secretfile
from secretzero.providers.vault import VaultAuth, VaultProvider, flatten_vault_auth_config


def _client_authenticated(token: str = "s.env-token") -> MagicMock:
    client = MagicMock()
    client.is_authenticated.return_value = True
    client.token = token
    return client


class TestFlattenVaultAuthConfig:
    """Secretfile auth shapes must collapse into a flat VaultAuth config."""

    def test_nested_auth_config(self) -> None:
        merged = flatten_vault_auth_config(
            {
                "kind": "vault",
                "auth": {
                    "kind": "token",
                    "config": {
                        "url": "https://vault.example.com:8200",
                        "token": "s.from-config",
                    },
                },
                "config": {},
            }
        )
        assert merged["kind"] == "token"
        assert merged["url"] == "https://vault.example.com:8200"
        assert merged["token"] == "s.from-config"

    def test_sibling_fields_on_auth_block(self) -> None:
        merged = flatten_vault_auth_config(
            {
                "kind": "vault",
                "auth": {
                    "kind": "token",
                    "url": "https://vault.example.com:8200",
                    "token": "s.sibling",
                    "config": {},
                },
            }
        )
        assert merged["url"] == "https://vault.example.com:8200"
        assert merged["token"] == "s.sibling"

    def test_address_alias_and_provider_kind_ignored(self) -> None:
        merged = flatten_vault_auth_config(
            {
                "kind": "vault",
                "auth": {"kind": "ambient", "config": {"address": "https://from-address:8200"}},
            }
        )
        assert merged["kind"] == "ambient"
        assert merged["url"] == "https://from-address:8200"

    def test_empty_provider_dump_stays_empty_for_env_fallback(self) -> None:
        merged = flatten_vault_auth_config({"kind": "vault", "auth": None, "config": {}})
        assert "token" not in merged
        assert merged.get("kind") in (None, "")


class TestVaultAuthEnvironment:
    """User/token auth must succeed from VAULT_ADDR + VAULT_TOKEN."""

    def test_token_kind_uses_env_when_config_omits_credentials(self, monkeypatch) -> None:
        monkeypatch.setenv("VAULT_ADDR", "https://vault.example.com:8200")
        monkeypatch.setenv("VAULT_TOKEN", "s.env-token")
        client = _client_authenticated()
        with patch("hvac.Client", return_value=client) as mock_client:
            auth = VaultAuth({"kind": "token"})
            assert auth.authenticate() is True
        kwargs = mock_client.call_args.kwargs
        assert kwargs["url"] == "https://vault.example.com:8200"
        assert kwargs["token"] == "s.env-token"

    def test_ambient_kind_uses_env(self, monkeypatch) -> None:
        monkeypatch.setenv("VAULT_ADDR", "https://vault.example.com:8200")
        monkeypatch.setenv("VAULT_TOKEN", "s.ambient")
        client = _client_authenticated("s.ambient")
        with patch("hvac.Client", return_value=client) as mock_client:
            auth = VaultAuth({"kind": "ambient"})
            assert auth.authenticate() is True
        assert mock_client.call_args.kwargs["token"] == "s.ambient"

    def test_nested_secretfile_shape_without_env(self, monkeypatch) -> None:
        monkeypatch.delenv("VAULT_ADDR", raising=False)
        monkeypatch.delenv("VAULT_TOKEN", raising=False)
        client = _client_authenticated("s.nested")
        with patch("hvac.Client", return_value=client) as mock_client:
            auth = VaultAuth(
                {
                    "kind": "token",
                    "config": {
                        "url": "https://nested.example.com:8200",
                        "token": "s.nested",
                    },
                }
            )
            assert auth.authenticate() is True
        kwargs = mock_client.call_args.kwargs
        assert kwargs["url"] == "https://nested.example.com:8200"
        assert kwargs["token"] == "s.nested"

    def test_missing_env_token_loads_home_vault_token_file(self, monkeypatch, tmp_path) -> None:
        monkeypatch.delenv("VAULT_TOKEN", raising=False)
        monkeypatch.setenv("VAULT_ADDR", "https://vault.example.com:8200")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        (tmp_path / ".vault_token").write_text("s.from-home\n", encoding="utf-8")
        client = _client_authenticated("s.from-home")
        with patch("hvac.Client", return_value=client) as mock_client:
            auth = VaultAuth({"kind": "token"})
            assert auth.authenticate() is True
        assert mock_client.call_args.kwargs["token"] == "s.from-home"

    def test_vault_login_file_used_when_underscore_file_missing(
        self, monkeypatch, tmp_path
    ) -> None:
        monkeypatch.delenv("VAULT_TOKEN", raising=False)
        monkeypatch.setenv("VAULT_ADDR", "https://vault.example.com:8200")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        (tmp_path / ".vault-token").write_text("s.login-file", encoding="utf-8")
        client = _client_authenticated("s.login-file")
        with patch("hvac.Client", return_value=client) as mock_client:
            auth = VaultAuth({"kind": "ambient"})
            assert auth.authenticate() is True
        assert mock_client.call_args.kwargs["token"] == "s.login-file"

    def test_env_token_wins_over_home_file(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setenv("VAULT_ADDR", "https://vault.example.com:8200")
        monkeypatch.setenv("VAULT_TOKEN", "s.from-env")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        (tmp_path / ".vault_token").write_text("s.from-home", encoding="utf-8")
        client = _client_authenticated("s.from-env")
        with patch("hvac.Client", return_value=client) as mock_client:
            auth = VaultAuth({"kind": "token"})
            assert auth.authenticate() is True
        assert mock_client.call_args.kwargs["token"] == "s.from-env"

    def test_get_client_authenticates_lazily(self, monkeypatch) -> None:
        monkeypatch.setenv("VAULT_ADDR", "https://vault.example.com:8200")
        monkeypatch.setenv("VAULT_TOKEN", "s.lazy")
        client = _client_authenticated("s.lazy")
        with patch("hvac.Client", return_value=client):
            auth = VaultAuth({"kind": "ambient"})
            assert auth.get_client() is client


class TestVaultProviderInitAndConnection:
    """Provider construction from Secretfile dumps must keep env auth usable."""

    def test_provider_from_secretfile_dump_authenticates_via_env(self, monkeypatch) -> None:
        monkeypatch.setenv("VAULT_ADDR", "https://vault.example.com:8200")
        monkeypatch.setenv("VAULT_TOKEN", "s.env-token")
        dump = Provider(
            kind="vault",
            auth=ProviderAuth(kind=AuthKind.AMBIENT, config={}),
        ).model_dump()
        client = _client_authenticated()
        provider = VaultProvider("vault", config=dump)
        with patch("hvac.Client", return_value=client):
            assert provider.authenticate() is True
            ok, message = provider.test_connection()
        assert ok is True
        assert message is not None
        assert "Connected to Vault" in message

    def test_test_connection_does_not_treat_provider_kind_as_auth_kind(self, monkeypatch) -> None:
        monkeypatch.setenv("VAULT_ADDR", "https://vault.example.com:8200")
        monkeypatch.setenv("VAULT_TOKEN", "s.env-token")
        provider = VaultProvider("vault", config={"kind": "vault"})
        client = _client_authenticated()
        client.sys.read_health_status.return_value = {"sealed": False}
        with patch("hvac.Client", return_value=client):
            ok, message = provider.test_connection()
        assert ok is True
        assert message is not None

    def test_supported_targets_include_kv_aliases(self) -> None:
        provider = VaultProvider("vault")
        targets = provider.get_supported_targets()
        assert "kv" in targets
        assert "vault_kv" in targets


class TestVaultRetrieveSecretSources:
    """provider_read / get must read KV mounts and other Vault logical paths."""

    def _provider_with_client(self, client: MagicMock) -> VaultProvider:
        provider = VaultProvider("vault", config={"kind": "vault"})
        provider.auth = VaultAuth({"kind": "token", "token": "s.test"})
        provider.auth._client = client
        return provider

    def test_provider_read_kwargs_kv_v2_field(self) -> None:
        client = _client_authenticated()
        client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"password": "from-kv", "user": "app"}}
        }
        provider = self._provider_with_client(client)
        result = provider.retrieve_secret(
            "ignored",
            path="secret/data/myapp/db",
            field="password",
            mount_point="secret",
            kind="vault_kv",
            profile=None,
        )
        assert result == "from-kv"
        kwargs = client.secrets.kv.v2.read_secret_version.call_args.kwargs
        assert kwargs["path"] == "myapp/db"
        assert kwargs["mount_point"] == "secret"

    def test_kv_v1_engine(self) -> None:
        client = _client_authenticated()
        client.secrets.kv.v1.read_secret.return_value = {"data": {"value": "v1-secret"}}
        provider = self._provider_with_client(client)
        result = provider.retrieve_secret(
            "apps/legacy",
            field="value",
            kv_version=1,
            mount_point="kv",
        )
        assert result == "v1-secret"
        kwargs = client.secrets.kv.v1.read_secret.call_args.kwargs
        assert kwargs["path"] == "apps/legacy"
        assert kwargs["mount_point"] == "kv"

    def test_cubbyhole_and_generic_logical_paths(self) -> None:
        client = _client_authenticated()
        client.read.return_value = {"data": {"value": "from-cubby"}}
        provider = self._provider_with_client(client)

        cubby = provider.retrieve_secret("session-token", engine="cubbyhole", field="value")
        assert cubby == "from-cubby"
        client.read.assert_called_with("cubbyhole/session-token")

        client.read.return_value = {"data": {"token": "from-identity"}}
        generic = provider.retrieve_secret(
            "identity/oidc/token/app",
            engine="generic",
            field="token",
        )
        assert generic == "from-identity"
        client.read.assert_called_with("identity/oidc/token/app")

    def test_json_payload_when_field_omitted(self) -> None:
        client = _client_authenticated()
        client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"value": "secret-value"}}
        }
        provider = self._provider_with_client(client)
        result = provider.retrieve_secret("my-secret")
        import json

        assert json.loads(result)["value"] == "secret-value"


def test_secretfile_accepts_vault_approle_auth_kind() -> None:
    """Documented Vault AppRole auth must validate in the Secretfile model."""
    sf = Secretfile(
        providers={
            "vault": Provider(
                kind="vault",
                auth=ProviderAuth(
                    kind="approle",
                    config={"role_id": "role", "secret_id": "secret"},
                ),
            )
        },
        secrets=[],
    )
    assert sf.providers["vault"].auth is not None
    assert sf.providers["vault"].auth.kind == AuthKind.APPROLE


def test_provider_auth_keeps_documented_sibling_vault_fields() -> None:
    """Examples put url/token next to auth.kind; those fields must survive model_dump."""
    auth = ProviderAuth.model_validate(
        {"kind": "token", "url": "https://vault.example.com:8200", "token": "s.test"}
    )
    dumped = auth.model_dump()
    assert dumped["url"] == "https://vault.example.com:8200"
    assert dumped["token"] == "s.test"


def test_vault_auth_approle_login(monkeypatch) -> None:
    monkeypatch.delenv("VAULT_TOKEN", raising=False)
    client = _client_authenticated("s.approle")
    client.auth.approle.login.return_value = {"auth": {"client_token": "s.approle"}}
    with patch("hvac.Client", return_value=client):
        auth = VaultAuth(
            {
                "kind": "approle",
                "url": "https://vault.example.com:8200",
                "role_id": "role",
                "secret_id": "secret",
            }
        )
        assert auth.authenticate() is True
    client.auth.approle.login.assert_called_once_with(role_id="role", secret_id="secret")
    assert client.token == "s.approle"
