"""Test Jenkins provider capability methods."""

import pytest
from unittest.mock import MagicMock, patch
from secretzero.providers.jenkins import JenkinsProvider


class TestJenkinsCapabilityMethods:
    """Test Jenkins provider capability methods."""

    def test_generate_password_defaults(self):
        """Test password generation with default settings."""
        config = {
            "url": "https://jenkins.example.com",
            "username": "admin",
            "token": "test-token",
        }
        provider = JenkinsProvider("test-jenkins", config=config)

        password = provider.generate_password()

        assert isinstance(password, str)
        assert len(password) == 32  # Default length

    def test_generate_password_custom_length(self):
        """Test password generation with custom length."""
        config = {
            "url": "https://jenkins.example.com",
            "username": "admin",
            "token": "test-token",
        }
        provider = JenkinsProvider("test-jenkins", config=config)

        password = provider.generate_password(length=16)

        assert isinstance(password, str)
        assert len(password) == 16

    def test_retrieve_secret_success(self):
        """Test successful secret retrieval."""
        config = {
            "url": "https://jenkins.example.com",
            "username": "admin",
            "token": "test-token",
        }
        provider = JenkinsProvider("test-jenkins", config=config)

        # Mock the client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"credentials": {"secret": {"plainText": "secret-value"}}}
        mock_client.get.return_value = mock_response
        provider.client = mock_client

        result = provider.retrieve_secret("my-secret")

        assert result == "secret-value"

    def test_store_secret_success(self):
        """Test successful secret storage."""
        config = {
            "url": "https://jenkins.example.com",
            "username": "admin",
            "token": "test-token",
        }
        provider = JenkinsProvider("test-jenkins", config=config)

        # Mock the client
        mock_client = MagicMock()
        mock_client.post.return_value = MagicMock()
        provider.client = mock_client

        result = provider.store_secret("my-secret", "secret-value")

        assert result is True

    def test_delete_secret_success(self):
        """Test successful secret deletion."""
        config = {
            "url": "https://jenkins.example.com",
            "username": "admin",
            "token": "test-token",
        }
        provider = JenkinsProvider("test-jenkins", config=config)

        # Mock the client
        mock_client = MagicMock()
        mock_client.delete.return_value = MagicMock()
        provider.client = mock_client

        result = provider.delete_secret("my-secret")

        assert result is True

    def test_list_secrets_success(self):
        """Test listing secrets."""
        config = {
            "url": "https://jenkins.example.com",
            "username": "admin",
            "token": "test-token",
        }
        provider = JenkinsProvider("test-jenkins", config=config)

        # Mock the client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "credentials": [
                {"id": "secret1"},
                {"id": "secret2"},
            ]
        }
        mock_client.get.return_value = mock_response
        provider.client = mock_client

        result = provider.list_secrets()

        assert result == ["secret1", "secret2"]

    def test_rotate_secret_success(self):
        """Test successful secret rotation."""
        config = {
            "url": "https://jenkins.example.com",
            "username": "admin",
            "token": "test-token",
        }
        provider = JenkinsProvider("test-jenkins", config=config)

        # Mock the client
        mock_client = MagicMock()
        mock_client.put.return_value = MagicMock()
        provider.client = mock_client

        new_value = provider.rotate_secret("my-secret")

        assert isinstance(new_value, str)
        assert len(new_value) == 32  # Default length

    def test_create_credential_success(self):
        """Test creating a new credential."""
        config = {
            "url": "https://jenkins.example.com",
            "username": "admin",
            "token": "test-token",
        }
        provider = JenkinsProvider("test-jenkins", config=config)

        # Mock the client
        mock_client = MagicMock()
        mock_client.post.return_value = MagicMock()
        provider.client = mock_client

        result = provider.store_secret("new-secret", "secret-value", description="Test secret")

        assert result is True
