"""Tests for Vault provider capability methods."""

import pytest
from unittest.mock import MagicMock, patch

from secretzero.providers.vault import VaultProvider


class TestVaultGeneratePassword:
    """Tests for VaultProvider.generate_password() method."""

    def test_generate_password_defaults(self):
        """Test password generation with default parameters."""
        config = {"url": "http://localhost:8200", "token": "s.test"}
        provider = VaultProvider("test-vault", config=config)

        password = provider.generate_password()

        assert isinstance(password, str)
        assert len(password) == 32
        assert len(set(password)) > 1  # Mix of characters

    def test_generate_password_custom_length(self):
        """Test password generation with custom length."""
        config = {"url": "http://localhost:8200", "token": "s.test"}
        provider = VaultProvider("test-vault", config=config)

        password = provider.generate_password(length=48)

        assert len(password) == 48

    def test_generate_password_no_char_types_selected(self):
        """Test that selecting no character types raises ValueError."""
        config = {"url": "http://localhost:8200", "token": "s.test"}
        provider = VaultProvider("test-vault", config=config)

        with pytest.raises(ValueError, match="At least one character type must be selected"):
            provider.generate_password(
                uppercase=False, lowercase=False, numbers=False, special_chars=False
            )

    def test_generate_password_only_numbers(self):
        """Test password with only numbers."""
        config = {"url": "http://localhost:8200", "token": "s.test"}
        provider = VaultProvider("test-vault", config=config)

        password = provider.generate_password(uppercase=False, lowercase=False, special_chars=False)

        assert password.isdigit()

    def test_generate_password_randomness(self):
        """Test that multiple calls generate different passwords."""
        config = {"url": "http://localhost:8200", "token": "s.test"}
        provider = VaultProvider("test-vault", config=config)

        passwords = [provider.generate_password() for _ in range(10)]
        assert len(set(passwords)) == 10  # All unique


class TestVaultRetrieveSecret:
    """Tests for VaultProvider.retrieve_secret() method."""

    def test_retrieve_secret_success(self):
        """Test successful secret retrieval."""
        config = {"url": "http://localhost:8200", "token": "s.test"}
        provider = VaultProvider("test-vault", config=config)

        # Mock auth and client
        mock_client = MagicMock()
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"value": "secret-value"}}
        }
        mock_client.is_authenticated.return_value = True

        provider.auth = MagicMock()
        provider.auth.is_authenticated.return_value = True
        provider.auth.get_client.return_value = mock_client

        # Patch isinstance specifically in the vault module
        with patch("secretzero.providers.vault.isinstance", return_value=True):
            result = provider.retrieve_secret("my-secret")

        # Vault returns JSON string when no field specified
        import json

        result_data = json.loads(result)
        assert result_data["value"] == "secret-value"

    def test_retrieve_secret_with_version(self):
        """Test secret retrieval with specific version."""
        config = {"url": "http://localhost:8200", "token": "s.test"}
        provider = VaultProvider("test-vault", config=config)

        mock_client = MagicMock()
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"value": "old-secret"}}
        }
        mock_client.is_authenticated.return_value = True

        provider.auth = MagicMock()
        provider.auth.is_authenticated.return_value = True
        provider.auth.get_client.return_value = mock_client

        with patch("secretzero.providers.vault.isinstance", return_value=True):
            result = provider.retrieve_secret("my-secret", version=3)

        # Vault returns JSON string when no field specified
        import json

        result_data = json.loads(result)
        assert result_data["value"] == "old-secret"

    def test_retrieve_secret_not_found(self):
        """Test retrieval when secret doesn't exist."""
        config = {"url": "http://localhost:8200", "token": "s.test"}
        provider = VaultProvider("test-vault", config=config)

        mock_client = MagicMock()
        mock_client.secrets.kv.v2.read_secret_version.side_effect = Exception("Not found")

        provider.auth = MagicMock()
        provider.auth.is_authenticated.return_value = True
        provider.auth.get_client.return_value = mock_client

        with patch("secretzero.providers.vault.isinstance", return_value=True):
            with pytest.raises(ValueError, match="Failed to retrieve secret from Vault:"):
                provider.retrieve_secret("nonexistent")

    def test_retrieve_secret_no_auth(self):
        """Test that missing auth raises ValueError."""
        config = {"url": "http://localhost:8200", "token": "s.test"}
        provider = VaultProvider("test-vault", config=config)

        provider.auth = MagicMock()
        provider.auth.is_authenticated.return_value = False

        with pytest.raises(ValueError, match="Failed to retrieve secret from Vault:"):
            provider.retrieve_secret("my-secret")

    def test_retrieve_secret_with_field(self):
        """Test secret retrieval with specific field."""
        config = {"url": "http://localhost:8200", "token": "s.test"}
        provider = VaultProvider("test-vault", config=config)

        mock_client = MagicMock()
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"password": "secret-pwd"}}
        }
        mock_client.is_authenticated.return_value = True

        provider.auth = MagicMock()
        provider.auth.is_authenticated.return_value = True
        provider.auth.get_client.return_value = mock_client

        with patch("secretzero.providers.vault.isinstance", return_value=True):
            result = provider.retrieve_secret("my-secret", field="password")

        assert result == "secret-pwd"


class TestVaultStoreSecret:
    """Tests for VaultProvider.store_secret() method."""

    def test_store_secret_success(self):
        """Test successful secret storage."""
        config = {"url": "http://localhost:8200", "token": "s.test"}
        provider = VaultProvider("test-vault", config=config)

        mock_client = MagicMock()
        mock_client.secrets.kv.v2.create_or_update_secret.return_value = {
            "metadata": {"version": 1}
        }
        mock_client.is_authenticated.return_value = True

        provider.auth = MagicMock()
        provider.auth.is_authenticated.return_value = True
        provider.auth.get_client.return_value = mock_client

        with patch("secretzero.providers.vault.isinstance", return_value=True):
            result = provider.store_secret("my-secret", "secret-value")

        assert result is True

    def test_store_secret_with_cas(self):
        """Test secret storage with CAS (check-and-set)."""
        config = {"url": "http://localhost:8200", "token": "s.test"}
        provider = VaultProvider("test-vault", config=config)

        mock_client = MagicMock()
        mock_client.secrets.kv.v2.create_or_update_secret.return_value = {
            "metadata": {"version": 2}
        }
        mock_client.is_authenticated.return_value = True

        provider.auth = MagicMock()
        provider.auth.is_authenticated.return_value = True
        provider.auth.get_client.return_value = mock_client

        with patch("secretzero.providers.vault.isinstance", return_value=True):
            result = provider.store_secret("my-secret", "new-value", cas=1)

        assert result is True

    def test_store_secret_failure(self):
        """Test secret storage failure."""
        config = {"url": "http://localhost:8200", "token": "s.test"}
        provider = VaultProvider("test-vault", config=config)

        mock_client = MagicMock()
        mock_client.secrets.kv.v2.create_or_update_secret.side_effect = Exception(
            "Permission denied"
        )

        provider.auth = MagicMock()
        provider.auth.is_authenticated.return_value = True
        provider.auth.get_client.return_value = mock_client

        with patch("secretzero.providers.vault.isinstance", return_value=True):
            with pytest.raises(ValueError, match="Failed to store secret in Vault:"):
                provider.store_secret("my-secret", "secret-value")


class TestVaultRotateSecret:
    """Tests for VaultProvider.rotate_secret() method."""

    def test_rotate_secret_success(self):
        """Test successful secret rotation."""
        config = {"url": "http://localhost:8200", "token": "s.test"}
        provider = VaultProvider("test-vault", config=config)

        mock_client = MagicMock()
        mock_client.secrets.kv.v2.create_or_update_secret.return_value = {
            "metadata": {"version": 2}
        }
        mock_client.is_authenticated.return_value = True

        provider.auth = MagicMock()
        provider.auth.is_authenticated.return_value = True
        provider.auth.get_client.return_value = mock_client

        with patch("secretzero.providers.vault.isinstance", return_value=True):
            result = provider.rotate_secret("my-secret", "new-value")

        assert result is True

    def test_rotate_secret_not_found(self):
        """Test rotation of non-existent secret."""
        config = {"url": "http://localhost:8200", "token": "s.test"}
        provider = VaultProvider("test-vault", config=config)

        mock_client = MagicMock()
        mock_client.secrets.kv.v2.create_or_update_secret.side_effect = Exception("Not found")

        provider.auth = MagicMock()
        provider.auth.is_authenticated.return_value = True
        provider.auth.get_client.return_value = mock_client

        with patch("secretzero.providers.vault.isinstance", return_value=True):
            with pytest.raises(ValueError, match="Failed to rotate secret in Vault:"):
                provider.rotate_secret("nonexistent", "new-value")


class TestVaultDeleteSecret:
    """Tests for VaultProvider.delete_secret() method."""

    def test_delete_secret_success(self):
        """Test successful secret deletion."""
        config = {"url": "http://localhost:8200", "token": "s.test"}
        provider = VaultProvider("test-vault", config=config)

        mock_client = MagicMock()
        mock_client.secrets.kv.v2.delete_secret_metadata.return_value = {}
        mock_client.is_authenticated.return_value = True

        provider.auth = MagicMock()
        provider.auth.is_authenticated.return_value = True
        provider.auth.get_client.return_value = mock_client

        with patch("secretzero.providers.vault.isinstance", return_value=True):
            result = provider.delete_secret("my-secret")

        assert result is True

    def test_delete_secret_specific_versions(self):
        """Test deletion of specific secret versions."""
        config = {"url": "http://localhost:8200", "token": "s.test"}
        provider = VaultProvider("test-vault", config=config)

        mock_client = MagicMock()
        mock_client.secrets.kv.v2.delete_secret_versions.return_value = {}
        mock_client.is_authenticated.return_value = True

        provider.auth = MagicMock()
        provider.auth.is_authenticated.return_value = True
        provider.auth.get_client.return_value = mock_client

        with patch("secretzero.providers.vault.isinstance", return_value=True):
            result = provider.delete_secret("my-secret", versions=[1, 2, 3])

        assert result is True

    def test_delete_secret_not_found(self):
        """Test deletion of non-existent secret."""
        config = {"url": "http://localhost:8200", "token": "s.test"}
        provider = VaultProvider("test-vault", config=config)

        mock_client = MagicMock()
        mock_client.secrets.kv.v2.delete_secret_metadata.side_effect = Exception("Not found")

        provider.auth = MagicMock()
        provider.auth.is_authenticated.return_value = True
        provider.auth.get_client.return_value = mock_client

        with patch("secretzero.providers.vault.isinstance", return_value=True):
            with pytest.raises(ValueError, match="Failed to delete secret from Vault:"):
                provider.delete_secret("nonexistent")


class TestVaultCapabilityIntegration:
    """Integration tests for Vault provider capabilities."""

    def test_vault_capabilities_discoverable(self):
        """Test that Vault provider capabilities are discoverable."""
        capabilities = VaultProvider.get_capabilities()

        assert capabilities.provider_kind == "vault"
        assert len(capabilities.capabilities) >= 5

        capability_names = [cap.method.name for cap in capabilities.capabilities]
        assert "generate_password" in capability_names
        assert "retrieve_secret" in capability_names
        assert "store_secret" in capability_names

    def test_vault_generate_method_discoverable(self):
        """Test that generate_password is discoverable."""
        capabilities = VaultProvider.get_capabilities()
        gen_cap = capabilities.get_capability("generate_password")

        assert gen_cap is not None
        assert gen_cap.method.description is not None

    def test_vault_retrieve_method_discoverable(self):
        """Test that retrieve_secret is discoverable."""
        capabilities = VaultProvider.get_capabilities()
        ret_cap = capabilities.get_capability("retrieve_secret")

        assert ret_cap is not None
        assert ret_cap.method.parameters is not None
