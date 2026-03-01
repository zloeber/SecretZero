"""Test GitHub provider capability methods."""

from unittest.mock import MagicMock, patch

import pytest

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

        # Mock the auth and client
        mock_auth = MagicMock()
        mock_client = MagicMock()
        mock_repo = MagicMock()
        mock_secret = MagicMock()
        mock_secret.name = "MY_SECRET"
        mock_repo.get_secrets.return_value = [mock_secret]
        mock_client.get_repo.return_value = mock_repo
        mock_auth.get_client.return_value = mock_client
        provider.auth = mock_auth

        # GitHub stores secret names, not values
        result = provider.retrieve_secret("MY_SECRET")

        assert "SECRET EXISTS" in result or "MY_SECRET" in result

    def test_store_secret_success(self):
        """Test successful secret storage."""
        config = {
            "token": "ghp_test_token",
            "repository": "owner/repo",
        }
        provider = GitHubProvider("test-github", config=config)

        # Mock the auth and client
        mock_auth = MagicMock()
        mock_client = MagicMock()
        mock_repo = MagicMock()
        mock_repo.create_secret.return_value = None
        mock_client.get_repo.return_value = mock_repo
        mock_auth.get_client.return_value = mock_client
        provider.auth = mock_auth

        result = provider.store_secret("MY_SECRET", "secret-value")

        assert result is True
        mock_repo.create_secret.assert_called_once_with("MY_SECRET", "secret-value")

    def test_delete_secret_success(self):
        """Test successful secret deletion."""
        config = {
            "token": "ghp_test_token",
            "repository": "owner/repo",
        }
        provider = GitHubProvider("test-github", config=config)

        # Mock the auth and client
        mock_auth = MagicMock()
        mock_client = MagicMock()
        mock_repo = MagicMock()
        mock_repo.delete_secret.return_value = None
        mock_client.get_repo.return_value = mock_repo
        mock_auth.get_client.return_value = mock_client
        provider.auth = mock_auth

        result = provider.delete_secret("MY_SECRET")

        assert result is True
        mock_repo.delete_secret.assert_called_once_with("MY_SECRET")
