"""Test Azure provider capability methods."""

import pytest
from unittest.mock import MagicMock, patch
from secretzero.providers.azure import AzureProvider


class TestAzureCapabilityMethods:
    """Test Azure provider capability methods."""

    def test_generate_password_defaults(self):
        """Test password generation with default settings."""
        config = {
            "vault_url": "https://test-vault.vault.azure.net",
            "tenant_id": "test-tenant",
            "client_id": "test-client",
        }
        provider = AzureProvider("test-azure", config=config)

        password = provider.generate_password()

        assert isinstance(password, str)
        assert len(password) == 32  # Default length

    def test_generate_password_custom_length(self):
        """Test password generation with custom length."""
        config = {
            "vault_url": "https://test-vault.vault.azure.net",
            "tenant_id": "test-tenant",
            "client_id": "test-client",
        }
        provider = AzureProvider("test-azure", config=config)

        password = provider.generate_password(length=16)

        assert isinstance(password, str)
        assert len(password) == 16

    def test_generate_password_with_special_chars(self):
        """Test password generation with special characters."""
        config = {
            "vault_url": "https://test-vault.vault.azure.net",
            "tenant_id": "test-tenant",
            "client_id": "test-client",
        }
        provider = AzureProvider("test-azure", config=config)

        password = provider.generate_password(length=32, special_chars=True)

        assert isinstance(password, str)
        assert len(password) == 32
        # Should contain at least one special character
        special = set("!@#$%^&*()-_=+[]{}|;:,.<>?")
        assert any(c in special for c in password)

    @patch("azure.keyvault.secrets.SecretClient")
    def test_retrieve_secret_success(self, mock_secret_client_class):
        """Test successful secret retrieval."""
        config = {
            "vault_url": "https://test-vault.vault.azure.net",
            "tenant_id": "test-tenant",
            "client_id": "test-client",
        }
        provider = AzureProvider("test-azure", config=config)

        # Mock the credential
        mock_credential = MagicMock()
        provider.auth = MagicMock()
        provider.auth.get_client.return_value = mock_credential

        # Mock the SecretClient
        mock_client = MagicMock()
        mock_secret = MagicMock()
        mock_secret.value = "secret-value"
        mock_client.get_secret.return_value = mock_secret
        mock_secret_client_class.return_value = mock_client

        result = provider.retrieve_secret("my-secret")

        assert result == "secret-value"
        mock_client.get_secret.assert_called_once_with("my-secret")
        mock_secret_client_class.assert_called_once_with(
            vault_url="https://test-vault.vault.azure.net", credential=mock_credential
        )

    @patch("azure.keyvault.secrets.SecretClient")
    def test_store_secret_success(self, mock_secret_client_class):
        """Test successful secret storage."""
        config = {
            "vault_url": "https://test-vault.vault.azure.net",
            "tenant_id": "test-tenant",
            "client_id": "test-client",
        }
        provider = AzureProvider("test-azure", config=config)

        # Mock the credential
        mock_credential = MagicMock()
        provider.auth = MagicMock()
        provider.auth.get_client.return_value = mock_credential

        # Mock the SecretClient
        mock_client = MagicMock()
        mock_secret_client_class.return_value = mock_client

        result = provider.store_secret("my-secret", "secret-value")

        assert result is True
        mock_client.set_secret.assert_called_once_with("my-secret", "secret-value", tags=None)

    @patch("azure.keyvault.secrets.SecretClient")
    def test_rotate_secret_success(self, mock_secret_client_class):
        """Test successful secret rotation."""
        config = {
            "vault_url": "https://test-vault.vault.azure.net",
            "tenant_id": "test-tenant",
            "client_id": "test-client",
        }
        provider = AzureProvider("test-azure", config=config)

        # Mock the credential
        mock_credential = MagicMock()
        provider.auth = MagicMock()
        provider.auth.get_client.return_value = mock_credential

        # Mock the SecretClient
        mock_client = MagicMock()
        mock_secret_client_class.return_value = mock_client

        new_value = "new-secret-value"
        result = provider.rotate_secret("my-secret", new_value)

        assert result is True
        mock_client.set_secret.assert_called_once_with("my-secret", new_value)

    @patch("azure.keyvault.secrets.SecretClient")
    def test_delete_secret_success(self, mock_secret_client_class):
        """Test successful secret deletion."""
        config = {
            "vault_url": "https://test-vault.vault.azure.net",
            "tenant_id": "test-tenant",
            "client_id": "test-client",
        }
        provider = AzureProvider("test-azure", config=config)

        # Mock the credential
        mock_credential = MagicMock()
        provider.auth = MagicMock()
        provider.auth.get_client.return_value = mock_credential

        # Mock the SecretClient
        mock_client = MagicMock()
        mock_delete_op = MagicMock()
        mock_delete_op.wait.return_value = None
        mock_client.begin_delete_secret.return_value = mock_delete_op
        mock_secret_client_class.return_value = mock_client

        result = provider.delete_secret("my-secret")

        assert result is True
        mock_client.begin_delete_secret.assert_called_once_with("my-secret")
        mock_client.purge_deleted_secret.assert_called_once_with("my-secret")
