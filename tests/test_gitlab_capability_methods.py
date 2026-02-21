"""Test GitLab provider capability methods."""

import pytest
from unittest.mock import MagicMock, patch
from secretzero.providers.gitlab import GitLabProvider


class TestGitLabCapabilityMethods:
    """Test GitLab provider capability methods."""

    def test_generate_password_defaults(self):
        """Test password generation with default settings."""
        config = {
            "token": "glpat-test",
            "project_id": "12345",
        }
        provider = GitLabProvider("test-gitlab", config=config)

        password = provider.generate_password()

        assert isinstance(password, str)
        assert len(password) == 32  # Default length

    def test_generate_password_custom_length(self):
        """Test password generation with custom length."""
        config = {
            "token": "glpat-test",
            "project_id": "12345",
        }
        provider = GitLabProvider("test-gitlab", config=config)

        password = provider.generate_password(length=16)

        assert isinstance(password, str)
        assert len(password) == 16

    def test_retrieve_secret_success(self):
        """Test successful secret retrieval."""
        config = {
            "token": "glpat-test",
            "project_id": "12345",
        }
        provider = GitLabProvider("test-gitlab", config=config)

        # Mock the client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "key": "MY_SECRET",
            "value": "secret-value",
        }
        mock_client.get.return_value = mock_response
        provider.client = mock_client

        result = provider.retrieve_secret("MY_SECRET")

        assert result == "secret-value"

    def test_store_secret_success(self):
        """Test successful secret storage."""
        config = {
            "token": "glpat-test",
            "project_id": "12345",
        }
        provider = GitLabProvider("test-gitlab", config=config)

        # Mock the client
        mock_client = MagicMock()
        mock_client.post.return_value = MagicMock()
        provider.client = mock_client

        result = provider.store_secret("MY_SECRET", "secret-value")

        assert result is True

    def test_delete_secret_success(self):
        """Test successful secret deletion."""
        config = {
            "token": "glpat-test",
            "project_id": "12345",
        }
        provider = GitLabProvider("test-gitlab", config=config)

        # Mock the client
        mock_client = MagicMock()
        mock_client.delete.return_value = MagicMock()
        provider.client = mock_client

        result = provider.delete_secret("MY_SECRET")

        assert result is True

    def test_list_secrets_success(self):
        """Test listing secrets."""
        config = {
            "token": "glpat-test",
            "project_id": "12345",
        }
        provider = GitLabProvider("test-gitlab", config=config)

        # Mock the client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"key": "SECRET1", "value": "value1"},
            {"key": "SECRET2", "value": "value2"},
        ]
        mock_client.get.return_value = mock_response
        provider.client = mock_client

        result = provider.list_secrets()

        assert result == ["SECRET1", "SECRET2"]

    def test_rotate_secret_success(self):
        """Test successful secret rotation."""
        config = {
            "token": "glpat-test",
            "project_id": "12345",
        }
        provider = GitLabProvider("test-gitlab", config=config)

        # Mock the client
        mock_client = MagicMock()
        mock_client.put.return_value = MagicMock()
        provider.client = mock_client

        new_value = provider.rotate_secret("MY_SECRET")

        assert isinstance(new_value, str)
        assert len(new_value) == 32  # Default length

    def test_update_secret_success(self):
        """Test successful secret update."""
        config = {
            "token": "glpat-test",
            "project_id": "12345",
        }
        provider = GitLabProvider("test-gitlab", config=config)

        # Mock the client
        mock_client = MagicMock()
        mock_client.put.return_value = MagicMock()
        provider.client = mock_client

        result = provider.store_secret("MY_SECRET", "new-value")

        assert result is True
