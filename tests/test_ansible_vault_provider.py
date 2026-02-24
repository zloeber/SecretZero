"""Tests for the Ansible Vault provider."""

import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_vault_mock(password: str, store: dict | None = None) -> MagicMock:
    """Return a mock Vault instance that encrypts/decrypts in memory.

    The mock stores data in *store* so tests can inspect what was written.
    Encryption is simulated as ``b"ENCRYPTED:" + text.encode()``.
    """
    if store is None:
        store = {}

    mock_vault = MagicMock()

    def _load_raw(content: str) -> bytes:
        prefix = b"ENCRYPTED:"
        if isinstance(content, str):
            content = content.encode()
        if content.startswith(prefix):
            return content[len(prefix):]
        # Allow plain text through (for "unencrypted" fixture data)
        return content

    def _dump_raw(text: str, stream: io.StringIO | None = None) -> str | None:
        if isinstance(text, bytes):
            text = text.decode()
        encrypted = "ENCRYPTED:" + text
        store["last_encrypted"] = encrypted
        if stream is not None:
            stream.write(encrypted)
            return None
        return encrypted

    mock_vault.load_raw.side_effect = _load_raw
    mock_vault.dump_raw.side_effect = _dump_raw

    return mock_vault


# ---------------------------------------------------------------------------
# AnsibleVaultAuth tests
# ---------------------------------------------------------------------------

class TestAnsibleVaultAuth:
    """Tests for AnsibleVaultAuth."""

    def test_auth_with_explicit_password(self):
        """Password supplied directly in config is returned."""
        from secretzero.providers.ansible_vault import AnsibleVaultAuth

        auth = AnsibleVaultAuth({"vault_password": "mysecret"})
        assert auth.get_password() == "mysecret"
        assert auth.authenticate() is True
        assert auth.is_authenticated() is True

    def test_auth_with_env_var(self, monkeypatch):
        """Password is read from the default environment variable."""
        from secretzero.providers.ansible_vault import AnsibleVaultAuth

        monkeypatch.setenv("ANSIBLE_VAULT_PASSWORD", "envpass")
        auth = AnsibleVaultAuth({})
        assert auth.get_password() == "envpass"
        assert auth.authenticate() is True

    def test_auth_with_custom_env_var(self, monkeypatch):
        """Password is read from a custom environment variable."""
        from secretzero.providers.ansible_vault import AnsibleVaultAuth

        monkeypatch.setenv("MY_VAULT_PASS", "custompass")
        auth = AnsibleVaultAuth({"vault_password_env": "MY_VAULT_PASS"})
        assert auth.get_password() == "custompass"
        assert auth.authenticate() is True

    def test_auth_no_password(self, monkeypatch):
        """Returns None / False when no password is available."""
        from secretzero.providers.ansible_vault import AnsibleVaultAuth

        monkeypatch.delenv("ANSIBLE_VAULT_PASSWORD", raising=False)
        auth = AnsibleVaultAuth({})
        assert auth.get_password() is None
        assert auth.authenticate() is False
        assert auth.is_authenticated() is False

    def test_explicit_password_takes_precedence_over_env(self, monkeypatch):
        """Explicit config password wins over environment variable."""
        from secretzero.providers.ansible_vault import AnsibleVaultAuth

        monkeypatch.setenv("ANSIBLE_VAULT_PASSWORD", "envpass")
        auth = AnsibleVaultAuth({"vault_password": "configpass"})
        assert auth.get_password() == "configpass"


# ---------------------------------------------------------------------------
# AnsibleVaultProvider – construction
# ---------------------------------------------------------------------------

class TestAnsibleVaultProviderInit:
    """Tests for AnsibleVaultProvider initialisation."""

    def test_provider_kind(self):
        """provider_kind should be 'ansible_vault'."""
        from secretzero.providers.ansible_vault import AnsibleVaultProvider

        provider = AnsibleVaultProvider(
            name="test",
            config={"vault_file": "/tmp/vault.yml", "vault_password": "pw"},
        )
        assert provider.provider_kind == "ansible_vault"

    def test_supported_targets(self):
        """get_supported_targets should include 'file'."""
        from secretzero.providers.ansible_vault import AnsibleVaultProvider

        provider = AnsibleVaultProvider(
            name="test",
            config={"vault_file": "/tmp/vault.yml", "vault_password": "pw"},
        )
        assert "file" in provider.get_supported_targets()

    def test_top_level_password_passed_to_auth(self):
        """vault_password at top-level config is forwarded to auth."""
        from secretzero.providers.ansible_vault import AnsibleVaultAuth, AnsibleVaultProvider

        provider = AnsibleVaultProvider(
            name="test",
            config={"vault_file": "/tmp/vault.yml", "vault_password": "toppass"},
        )
        assert isinstance(provider.auth, AnsibleVaultAuth)
        assert provider.auth.get_password() == "toppass"


# ---------------------------------------------------------------------------
# AnsibleVaultProvider – test_connection
# ---------------------------------------------------------------------------

class TestAnsibleVaultProviderConnection:
    """Tests for AnsibleVaultProvider.test_connection()."""

    def test_missing_ansible_vault_library(self):
        """Returns False when ansible-vault is not installed."""
        from secretzero.providers.ansible_vault import AnsibleVaultProvider

        provider = AnsibleVaultProvider(
            name="test",
            config={"vault_file": "/tmp/vault.yml", "vault_password": "pw"},
        )
        with patch.dict("sys.modules", {"ansible_vault": None}):
            success, msg = provider.test_connection()
        assert success is False
        assert "ansible-vault" in msg.lower()

    def test_missing_vault_file_config(self):
        """Returns False when vault_file is not configured."""
        from secretzero.providers.ansible_vault import AnsibleVaultProvider

        provider = AnsibleVaultProvider(
            name="test",
            config={"vault_password": "pw"},
        )
        with patch("ansible_vault.Vault"):
            success, msg = provider.test_connection()
        assert success is False
        assert "vault_file" in msg

    def test_missing_password(self, tmp_path, monkeypatch):
        """Returns False when no vault password is available."""
        from secretzero.providers.ansible_vault import AnsibleVaultProvider

        monkeypatch.delenv("ANSIBLE_VAULT_PASSWORD", raising=False)
        provider = AnsibleVaultProvider(
            name="test",
            config={"vault_file": str(tmp_path / "vault.yml")},
        )
        with patch("ansible_vault.Vault"):
            success, msg = provider.test_connection()
        assert success is False
        assert "password" in msg.lower()

    def test_nonexistent_file_succeeds(self, tmp_path):
        """Returns True for a non-existent vault file (new file will be created on write)."""
        from secretzero.providers.ansible_vault import AnsibleVaultProvider

        vault_path = tmp_path / "new_vault.yml"
        provider = AnsibleVaultProvider(
            name="test",
            config={"vault_file": str(vault_path), "vault_password": "pw"},
        )
        with patch("ansible_vault.Vault"):
            success, msg = provider.test_connection()
        assert success is True

    def test_existing_valid_file_succeeds(self, tmp_path):
        """Returns True when the vault file exists and can be decrypted."""
        from secretzero.providers.ansible_vault import AnsibleVaultProvider

        vault_path = tmp_path / "vault.yml"
        # Write a fake encrypted file that our mock can "decrypt"
        plain = yaml.dump({"key": "val"})
        vault_path.write_text("ENCRYPTED:" + plain)

        provider = AnsibleVaultProvider(
            name="test",
            config={"vault_file": str(vault_path), "vault_password": "pw"},
        )

        mock_vault = _make_vault_mock("pw")
        with patch("ansible_vault.Vault", return_value=mock_vault):
            success, msg = provider.test_connection()
        assert success is True


# ---------------------------------------------------------------------------
# AnsibleVaultProvider – retrieve_secret
# ---------------------------------------------------------------------------

class TestAnsibleVaultProviderRetrieve:
    """Tests for AnsibleVaultProvider.retrieve_secret()."""

    def _write_encrypted_yaml(self, path: Path, data: dict) -> None:
        """Write a fake-encrypted YAML vault file."""
        plain = yaml.dump(data)
        path.write_text("ENCRYPTED:" + plain)

    def test_retrieve_existing_key(self, tmp_path):
        """Successfully retrieve a secret that is stored in the vault."""
        from secretzero.providers.ansible_vault import AnsibleVaultProvider

        vault_path = tmp_path / "vault.yml"
        self._write_encrypted_yaml(vault_path, {"db_pass": "s3cr3t"})

        provider = AnsibleVaultProvider(
            name="test",
            config={"vault_file": str(vault_path), "vault_password": "pw"},
        )

        mock_vault = _make_vault_mock("pw")
        with patch("ansible_vault.Vault", return_value=mock_vault):
            value = provider.retrieve_secret("db_pass")
        assert value == "s3cr3t"

    def test_retrieve_missing_key_raises(self, tmp_path):
        """Raises ValueError when the requested key is absent."""
        from secretzero.providers.ansible_vault import AnsibleVaultProvider

        vault_path = tmp_path / "vault.yml"
        self._write_encrypted_yaml(vault_path, {"other_key": "val"})

        provider = AnsibleVaultProvider(
            name="test",
            config={"vault_file": str(vault_path), "vault_password": "pw"},
        )

        mock_vault = _make_vault_mock("pw")
        with patch("ansible_vault.Vault", return_value=mock_vault):
            with pytest.raises(ValueError, match="db_pass"):
                provider.retrieve_secret("db_pass")

    def test_retrieve_file_not_found_raises(self, tmp_path):
        """Raises ValueError when the vault file does not exist."""
        from secretzero.providers.ansible_vault import AnsibleVaultProvider

        provider = AnsibleVaultProvider(
            name="test",
            config={"vault_file": str(tmp_path / "missing.yml"), "vault_password": "pw"},
        )

        with patch("ansible_vault.Vault"):
            with pytest.raises(ValueError, match="not found"):
                provider.retrieve_secret("key")

    def test_retrieve_no_vault_file_config_raises(self):
        """Raises ValueError when vault_file is not in the config."""
        from secretzero.providers.ansible_vault import AnsibleVaultProvider

        provider = AnsibleVaultProvider(name="test", config={"vault_password": "pw"})

        with patch("ansible_vault.Vault"):
            with pytest.raises(ValueError, match="vault_file"):
                provider.retrieve_secret("key")


# ---------------------------------------------------------------------------
# AnsibleVaultProvider – store_secret
# ---------------------------------------------------------------------------

class TestAnsibleVaultProviderStore:
    """Tests for AnsibleVaultProvider.store_secret()."""

    def test_store_creates_new_file(self, tmp_path):
        """store_secret creates the vault file when it doesn't exist yet."""
        from secretzero.providers.ansible_vault import AnsibleVaultProvider

        vault_path = tmp_path / "new_vault.yml"
        provider = AnsibleVaultProvider(
            name="test",
            config={"vault_file": str(vault_path), "vault_password": "pw"},
        )

        mock_vault = _make_vault_mock("pw")
        with patch("ansible_vault.Vault", return_value=mock_vault):
            result = provider.store_secret("api_key", "abc123")

        assert result is True
        assert vault_path.exists()
        # Verify the mock was asked to encrypt something containing "api_key"
        assert "api_key" in mock_vault.dump_raw.call_args[0][0]

    def test_store_merges_with_existing(self, tmp_path):
        """store_secret preserves existing keys when adding a new one."""
        from secretzero.providers.ansible_vault import AnsibleVaultProvider

        vault_path = tmp_path / "vault.yml"
        # Pre-populate vault with one key
        existing = {"old_key": "old_val"}
        vault_path.write_text("ENCRYPTED:" + yaml.dump(existing))

        provider = AnsibleVaultProvider(
            name="test",
            config={"vault_file": str(vault_path), "vault_password": "pw"},
        )

        mock_vault = _make_vault_mock("pw")
        with patch("ansible_vault.Vault", return_value=mock_vault):
            provider.store_secret("new_key", "new_val")

        written_plain = mock_vault.dump_raw.call_args[0][0]
        stored = yaml.safe_load(written_plain)
        assert stored["old_key"] == "old_val"
        assert stored["new_key"] == "new_val"

    def test_store_updates_existing_key(self, tmp_path):
        """store_secret overwrites the value of an existing key."""
        from secretzero.providers.ansible_vault import AnsibleVaultProvider

        vault_path = tmp_path / "vault.yml"
        vault_path.write_text("ENCRYPTED:" + yaml.dump({"mykey": "oldval"}))

        provider = AnsibleVaultProvider(
            name="test",
            config={"vault_file": str(vault_path), "vault_password": "pw"},
        )

        mock_vault = _make_vault_mock("pw")
        with patch("ansible_vault.Vault", return_value=mock_vault):
            provider.store_secret("mykey", "newval")

        written_plain = mock_vault.dump_raw.call_args[0][0]
        stored = yaml.safe_load(written_plain)
        assert stored["mykey"] == "newval"

    def test_store_no_vault_file_config_raises(self):
        """Raises ValueError when vault_file is missing from config."""
        from secretzero.providers.ansible_vault import AnsibleVaultProvider

        provider = AnsibleVaultProvider(name="test", config={"vault_password": "pw"})

        with patch("ansible_vault.Vault"):
            with pytest.raises(ValueError, match="vault_file"):
                provider.store_secret("key", "val")


# ---------------------------------------------------------------------------
# AnsibleVaultProvider – delete_secret
# ---------------------------------------------------------------------------

class TestAnsibleVaultProviderDelete:
    """Tests for AnsibleVaultProvider.delete_secret()."""

    def test_delete_existing_key(self, tmp_path):
        """delete_secret removes the key and returns True."""
        from secretzero.providers.ansible_vault import AnsibleVaultProvider

        vault_path = tmp_path / "vault.yml"
        vault_path.write_text("ENCRYPTED:" + yaml.dump({"a": "1", "b": "2"}))

        provider = AnsibleVaultProvider(
            name="test",
            config={"vault_file": str(vault_path), "vault_password": "pw"},
        )

        mock_vault = _make_vault_mock("pw")
        with patch("ansible_vault.Vault", return_value=mock_vault):
            result = provider.delete_secret("a")

        assert result is True
        written_plain = mock_vault.dump_raw.call_args[0][0]
        stored = yaml.safe_load(written_plain)
        assert "a" not in stored
        assert stored["b"] == "2"

    def test_delete_missing_key_returns_false(self, tmp_path):
        """delete_secret returns False when key is not present."""
        from secretzero.providers.ansible_vault import AnsibleVaultProvider

        vault_path = tmp_path / "vault.yml"
        vault_path.write_text("ENCRYPTED:" + yaml.dump({"a": "1"}))

        provider = AnsibleVaultProvider(
            name="test",
            config={"vault_file": str(vault_path), "vault_password": "pw"},
        )

        mock_vault = _make_vault_mock("pw")
        with patch("ansible_vault.Vault", return_value=mock_vault):
            result = provider.delete_secret("nonexistent")

        assert result is False

    def test_delete_file_not_found_raises(self, tmp_path):
        """Raises ValueError when the vault file does not exist."""
        from secretzero.providers.ansible_vault import AnsibleVaultProvider

        provider = AnsibleVaultProvider(
            name="test",
            config={"vault_file": str(tmp_path / "missing.yml"), "vault_password": "pw"},
        )

        with patch("ansible_vault.Vault"):
            with pytest.raises(ValueError, match="not found"):
                provider.delete_secret("key")


# ---------------------------------------------------------------------------
# AnsibleVaultProvider – alternative formats
# ---------------------------------------------------------------------------

class TestAnsibleVaultProviderFormats:
    """Tests for json and dotenv format support."""

    def test_json_format_round_trip(self, tmp_path):
        """Secrets can be stored and retrieved using JSON format."""
        from secretzero.providers.ansible_vault import AnsibleVaultProvider

        vault_path = tmp_path / "vault.json"
        provider = AnsibleVaultProvider(
            name="test",
            config={"vault_file": str(vault_path), "vault_password": "pw", "format": "json"},
        )

        mock_vault = _make_vault_mock("pw")
        with patch("ansible_vault.Vault", return_value=mock_vault):
            provider.store_secret("token", "abc")

        # Verify plaintext is valid JSON
        written_plain = mock_vault.dump_raw.call_args[0][0]
        stored = json.loads(written_plain)
        assert stored["token"] == "abc"

        # Now read back
        vault_path.write_text("ENCRYPTED:" + written_plain)
        mock_vault2 = _make_vault_mock("pw")
        with patch("ansible_vault.Vault", return_value=mock_vault2):
            value = provider.retrieve_secret("token")
        assert value == "abc"

    def test_dotenv_format_round_trip(self, tmp_path):
        """Secrets can be stored and retrieved using dotenv format."""
        from secretzero.providers.ansible_vault import AnsibleVaultProvider

        vault_path = tmp_path / "vault.env"
        provider = AnsibleVaultProvider(
            name="test",
            config={"vault_file": str(vault_path), "vault_password": "pw", "format": "dotenv"},
        )

        mock_vault = _make_vault_mock("pw")
        with patch("ansible_vault.Vault", return_value=mock_vault):
            provider.store_secret("MY_KEY", "myvalue")

        written_plain = mock_vault.dump_raw.call_args[0][0]
        assert "MY_KEY=myvalue" in written_plain

        # Read back
        vault_path.write_text("ENCRYPTED:" + written_plain)
        mock_vault2 = _make_vault_mock("pw")
        with patch("ansible_vault.Vault", return_value=mock_vault2):
            value = provider.retrieve_secret("MY_KEY")
        assert value == "myvalue"

    def test_unsupported_format_raises(self, tmp_path):
        """store_secret raises ValueError for an unsupported format."""
        from secretzero.providers.ansible_vault import AnsibleVaultProvider

        vault_path = tmp_path / "vault.toml"
        provider = AnsibleVaultProvider(
            name="test",
            config={"vault_file": str(vault_path), "vault_password": "pw", "format": "toml"},
        )

        mock_vault = _make_vault_mock("pw")
        with patch("ansible_vault.Vault", return_value=mock_vault):
            with pytest.raises(ValueError, match="Unsupported format"):
                provider.store_secret("key", "val")


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------

def test_ansible_vault_registered_in_global_registry():
    """AnsibleVaultProvider is registered in the global provider registry."""
    from secretzero.providers.registry import get_registry

    registry = get_registry()
    provider_types = registry.list_provider_types()
    assert "ansible_vault" in provider_types


def test_registry_can_create_ansible_vault_provider():
    """Global registry can instantiate an AnsibleVaultProvider."""
    from secretzero.providers.ansible_vault import AnsibleVaultProvider
    from secretzero.providers.registry import get_registry

    registry = get_registry()
    provider = registry.create_provider(
        "ansible_vault",
        "my_vault",
        {"vault_file": "/tmp/test.yml", "vault_password": "pw"},
    )
    assert provider is not None
    assert isinstance(provider, AnsibleVaultProvider)
