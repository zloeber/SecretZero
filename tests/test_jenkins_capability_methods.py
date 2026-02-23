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

        # Mock the auth and client
        mock_auth = MagicMock()
        mock_client = MagicMock()
        mock_client.jenkins_open.return_value = '{"id": "my-secret"}'
        mock_auth.get_client.return_value = mock_client
        provider.auth = mock_auth

        result = provider.retrieve_secret("my-secret")

        assert "[CREDENTIAL EXISTS]" in result or "my-secret" in result.lower()

    def test_store_secret_success(self):
        """Test successful secret storage."""
        config = {
            "url": "https://jenkins.example.com",
            "username": "admin",
            "token": "test-token",
        }
        provider = JenkinsProvider("test-jenkins", config=config)

        # Mock the auth and client
        mock_auth = MagicMock()
        mock_client = MagicMock()
        mock_client.jenkins_open.return_value = None
        mock_auth.get_client.return_value = mock_client
        provider.auth = mock_auth

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

        # Mock the auth and client
        mock_auth = MagicMock()
        mock_client = MagicMock()
        mock_client.jenkins_open.return_value = None
        mock_auth.get_client.return_value = mock_client
        provider.auth = mock_auth

        result = provider.delete_secret("my-secret")

        assert result is True

    def test_store_secret_with_username(self):
        """Test storing a secret with custom username."""
        config = {
            "url": "https://jenkins.example.com",
            "username": "admin",
            "token": "test-token",
        }
        provider = JenkinsProvider("test-jenkins", config=config)

        # Mock the auth and client
        mock_auth = MagicMock()
        mock_client = MagicMock()
        mock_client.jenkins_open.return_value = None
        mock_auth.get_client.return_value = mock_client
        provider.auth = mock_auth

        result = provider.store_secret("my-secret", "secret-value", username="testuser")

        assert result is True
