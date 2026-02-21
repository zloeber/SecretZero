"""Tests for GitHub token information functionality."""

import os
from unittest.mock import Mock, patch

import pytest

from secretzero.providers.github import GitHubAuth, GitHubProvider


class TestGitHubTokenInfo:
    """Test GitHub token information retrieval."""

    def test_get_token_info_success(self):
        """Test successful token info retrieval."""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "login": "testuser",
            "name": "Test User",
            "email": "test@example.com",
        }
        mock_response.headers = {
            "X-OAuth-Scopes": "repo, workflow, admin:org",
            "X-GitHub-SSO": "OAuth",
        }
        mock_response.raise_for_status = Mock()

        with patch("requests.get", return_value=mock_response):
            auth = GitHubAuth({"token": "ghp_test123"})
            info = auth.get_token_info()

            assert info["user"] == "testuser"
            assert info["name"] == "Test User"
            assert info["email"] == "test@example.com"
            assert "repo" in info["scopes"]
            assert "workflow" in info["scopes"]
            assert "admin:org" in info["scopes"]

    def test_get_token_info_classic_pat(self):
        """Test token info for classic PAT (no OAuth scopes)."""
        # Classic PATs don't return X-OAuth-Scopes header
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "login": "testuser",
            "name": "Test User",
            "email": None,
        }
        mock_response.headers = {
            "X-GitHub-SSO": "PAT",
        }
        mock_response.raise_for_status = Mock()

        with patch("requests.get", return_value=mock_response):
            auth = GitHubAuth({"token": "ghp_test123"})
            info = auth.get_token_info()

            assert info["user"] == "testuser"
            assert info["name"] == "Test User"
            assert info["email"] is None
            assert info["scopes"] == []  # Classic PATs don't return scopes
            assert info["token_type"] == "PAT"

    def test_get_token_info_from_env(self):
        """Test token info retrieval using environment variable."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "login": "envuser",
            "name": "Env User",
        }
        mock_response.headers = {
            "X-OAuth-Scopes": "repo",
        }
        mock_response.raise_for_status = Mock()

        with patch("requests.get", return_value=mock_response):
            with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_env_token"}):
                auth = GitHubAuth({})  # No token in config
                info = auth.get_token_info()

                assert info["user"] == "envuser"
                assert "repo" in info["scopes"]

    def test_get_token_info_no_token(self):
        """Test error when no token is available."""
        auth = GitHubAuth({})

        with patch.dict(os.environ, {}, clear=True):  # Clear GITHUB_TOKEN
            with pytest.raises(RuntimeError, match="No GitHub token found"):
                auth.get_token_info()

    def test_get_token_info_api_error(self):
        """Test handling of API errors."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = Exception("Unauthorized")

        with patch("requests.get", return_value=mock_response):
            auth = GitHubAuth({"token": "invalid_token"})

            with pytest.raises(RuntimeError, match="Failed to get token info"):
                auth.get_token_info()

    def test_get_token_info_custom_api_url(self):
        """Test token info with custom GitHub Enterprise URL."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "login": "enterpriseuser",
        }
        mock_response.headers = {
            "X-OAuth-Scopes": "repo",
        }
        mock_response.raise_for_status = Mock()

        with patch("requests.get", return_value=mock_response) as mock_get:
            auth = GitHubAuth(
                {
                    "token": "ghp_enterprise",
                    "api_url": "https://github.enterprise.com/api/v3",
                }
            )
            info = auth.get_token_info()

            # Verify correct API URL was used
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "https://github.enterprise.com/api/v3/user" in str(call_args)

            assert info["user"] == "enterpriseuser"

    def test_get_token_permissions_provider(self):
        """Test get_token_permissions method on provider."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "login": "testuser",
        }
        mock_response.headers = {
            "X-OAuth-Scopes": "repo, workflow",
        }
        mock_response.raise_for_status = Mock()

        with patch("requests.get", return_value=mock_response):
            auth = GitHubAuth({"token": "ghp_test"})
            provider = GitHubProvider("github", auth=auth)

            info = provider.get_token_permissions()

            assert info["user"] == "testuser"
            assert "repo" in info["scopes"]
            assert "workflow" in info["scopes"]

    def test_get_token_permissions_no_auth(self):
        """Test error when provider has no auth configured."""
        provider = GitHubProvider("github", auth=None)

        with pytest.raises(RuntimeError, match="No authentication configured"):
            provider.get_token_permissions()

    def test_scope_parsing(self):
        """Test proper parsing of scope header."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"login": "testuser"}
        mock_response.headers = {
            # Test various formats: spaces, no spaces, trailing commas
            "X-OAuth-Scopes": "repo, workflow,admin:org  ,  read:user,",
        }
        mock_response.raise_for_status = Mock()

        with patch("requests.get", return_value=mock_response):
            auth = GitHubAuth({"token": "ghp_test"})
            info = auth.get_token_info()

            # Should have 4 scopes, properly trimmed
            assert len(info["scopes"]) == 4
            assert "repo" in info["scopes"]
            assert "workflow" in info["scopes"]
            assert "admin:org" in info["scopes"]
            assert "read:user" in info["scopes"]
            # Empty string from trailing comma should be filtered out
            assert "" not in info["scopes"]
