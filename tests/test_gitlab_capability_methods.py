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
            "project": "12345",  # Changed from project_id to project
        }
        provider = GitLabProvider("test-gitlab", config=config)

        # Mock the auth and client
        mock_auth = MagicMock()
        mock_client = MagicMock()
        mock_project = MagicMock()
        mock_variable = MagicMock()
        mock_variable.value = "secret-value"
        mock_project.variables.get.return_value = mock_variable
        mock_client.projects.get.return_value = mock_project
        mock_auth.get_client.return_value = mock_client
        provider.auth = mock_auth

        result = provider.retrieve_secret("MY_SECRET")

        assert result == "secret-value"

    def test_store_secret_success(self):
        """Test successful secret storage."""
        config = {
            "token": "glpat-test",
            "project": "12345",  # Changed from project_id to project
        }
        provider = GitLabProvider("test-gitlab", config=config)

        # Mock the auth and client
        mock_auth = MagicMock()
        mock_client = MagicMock()
        mock_project = MagicMock()
        mock_variable = MagicMock()
        mock_project.variables.create.return_value = mock_variable
        mock_client.projects.get.return_value = mock_project
        mock_auth.get_client.return_value = mock_client
        provider.auth = mock_auth

        result = provider.store_secret("MY_SECRET", "secret-value")

        assert result is True

    def test_delete_secret_success(self):
        """Test successful secret deletion."""
        config = {
            "token": "glpat-test",
            "project": "12345",  # Changed from project_id to project
        }
        provider = GitLabProvider("test-gitlab", config=config)

        # Mock the auth and client
        mock_auth = MagicMock()
        mock_client = MagicMock()
        mock_project = MagicMock()
        mock_variable = MagicMock()
        mock_project.variables.delete.return_value = None
        mock_client.projects.get.return_value = mock_project
        mock_auth.get_client.return_value = mock_client
        provider.auth = mock_auth

        result = provider.delete_secret("MY_SECRET")

        assert result is True
