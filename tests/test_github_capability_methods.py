"""Test GitHub provider capability methods."""

import pytest
from unittest.mock import MagicMock, patch
from secretzero.providers.github import GitHubProvider


class TestGitHubCapabilityMethods:
    """Test GitHub provider capability methods."""

    def test_generate_password_defaults(self):
        """Test password generation with default settings."""
        config = {
            "token": "ghp_test_token",
            "repository": "owner/repo",
        }
        provider = GitHubProvider("test-github", config=config)

        password = provider.generate_password()

        assert isinstance(password, str)
        assert len(password) == 32  # Default length

    def test_generate_password_custom_length(self):
        """Test password generation with custom length."""
        config = {
            "token": "ghp_test_token",
            "repository": "owner/repo",
        }
        provider = GitHubProvider("test-github", config=config)

        password = provider.generate_password(length=16)

        assert isinstance(password, str)
        assert len(password) == 16

    def test_retrieve_secret_success(self):
        """Test successful secret retrieval."""
        config = {
            "token": "ghp_test_token",
            "repository": "owner/repo",
        }
        provider = GitHubProvider("test-github", config=config)

        # Mock the client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"name": "MY_SECRET"}
        mock_client.get.return_value = mock_response
        provider.client = mock_client

        # GitHub stores secret names, not values
        result = provider.retrieve_secret("MY_SECRET")

        assert result == "MY_SECRET"

    def test_store_secret_success(self):
        """Test successful secret storage."""
        config = {
            "token": "ghp_test_token",
            "repository": "owner/repo",
        }
        provider = GitHubProvider("test-github", config=config)

        # Mock the client and encryption
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"key": "public-key", "key_id": "key-123"}
        mock_client.get.return_value = mock_response
        mock_client.put.return_value = MagicMock()
        provider.client = mock_client

        with patch("secretzero.providers.github.Public") as mock_public:
            mock_box = MagicMock()
            mock_box.encrypt.return_value = b"encrypted-value"
            mock_public.return_value = mock_box

            result = provider.store_secret("MY_SECRET", "secret-value")

        assert result is True

    def test_delete_secret_success(self):
        """Test successful secret deletion."""
        config = {
            "token": "ghp_test_token",
            "repository": "owner/repo",
        }
        provider = GitHubProvider("test-github", config=config)

        # Mock the client
        mock_client = MagicMock()
        mock_client.delete.return_value = MagicMock()
        provider.client = mock_client

        result = provider.delete_secret("MY_SECRET")

        assert result is True

    def test_list_secrets_success(self):
        """Test listing secrets."""
        config = {
            "token": "ghp_test_token",
            "repository": "owner/repo",
        }
        provider = GitHubProvider("test-github", config=config)

        # Mock the client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "secrets": [
                {"name": "SECRET1"},
                {"name": "SECRET2"},
            ]
        }
        mock_client.get.return_value = mock_response
        provider.client = mock_client

        result = provider.list_secrets()

        assert result == ["SECRET1", "SECRET2"]

    def test_rotate_secret_success(self):
        """Test successful secret rotation."""
        config = {
            "token": "ghp_test_token",
            "repository": "owner/repo",
        }
        provider = GitHubProvider("test-github", config=config)

        # Mock the client and encryption
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"key": "public-key", "key_id": "key-123"}
        mock_client.get.return_value = mock_response
        mock_client.put.return_value = MagicMock()
        provider.client = mock_client

        with patch("secretzero.providers.github.Public") as mock_public:
            mock_box = MagicMock()
            mock_box.encrypt.return_value = b"encrypted-value"
            mock_public.return_value = mock_box

            new_value = provider.rotate_secret("MY_SECRET")

        assert isinstance(new_value, str)
        assert len(new_value) == 32  # Default length
