"""Tests for Infisical provider."""

import os
from unittest.mock import MagicMock, Mock, patch

import pytest

from secretzero.providers.infisical import InfisicalConfig, InfisicalProvider


@pytest.fixture
def infisical_config() -> InfisicalConfig:
    """Create test Infisical configuration."""
    return InfisicalConfig(
        workspace_id="test-workspace-123",
        project_id="test-project-456",
        environment="dev",
    )


@pytest.fixture
def infisical_provider(infisical_config: InfisicalConfig) -> InfisicalProvider:
    """Create test Infisical provider."""
    return InfisicalProvider(name="infisical_test", config=infisical_config)


class TestInfisicalConfig:
    """Tests for InfisicalConfig model."""

    def test_minimal_valid_config(self) -> None:
        """Test minimal valid configuration."""
        config = InfisicalConfig(workspace_id="ws-123")
        assert config.workspace_id == "ws-123"
        assert config.environment == "dev"
        assert config.api_url == "https://app.infisical.com/api"

    def test_full_config(self) -> None:
        """Test full configuration."""
        config = InfisicalConfig(
            api_url="https://self-hosted.infisical.com/api",
            workspace_id="ws-456",
            project_id="proj-789",
            environment="production",
            timeout=60,
        )
        assert config.api_url == "https://self-hosted.infisical.com/api"
        assert config.environment == "production"
        assert config.timeout == 60

    def test_invalid_timeout(self) -> None:
        """Test validation fails with invalid timeout."""
        with pytest.raises(Exception):
            InfisicalConfig(workspace_id="ws-123", timeout=0)


class TestInfisicalProvider:
    """Tests for InfisicalProvider class."""

    def test_provider_kind(self, infisical_provider: InfisicalProvider) -> None:
        """Test provider returns correct kind."""
        assert infisical_provider.provider_kind == "infisical"

    @patch.dict(os.environ, {"INFISICAL_TOKEN": "test-token"})
    def test_get_token_info(self, infisical_provider: InfisicalProvider) -> None:
        """Token introspection returns workspace context (no secret values)."""
        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"workspace": {"name": "Acme"}}
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            info = infisical_provider.get_token_info()
            assert info["token_type"] == "infisical_token"
            assert info["workspace_id"] == "test-workspace-123"
            assert info["workspace_name"] == "Acme"
            assert info["environment"] == "dev"

    def test_get_auth_token_from_env(self, infisical_provider: InfisicalProvider) -> None:
        """Test retrieving auth token from INFISICAL_TOKEN."""
        with patch.dict(os.environ, {"INFISICAL_TOKEN": "test-token-123"}):
            token = infisical_provider._get_auth_token()
            assert token == "test-token-123"

    def test_get_auth_token_from_service_token(self, infisical_provider: InfisicalProvider) -> None:
        """Test retrieving auth token from INFISICAL_SERVICE_TOKEN."""
        with patch.dict(os.environ, {"INFISICAL_SERVICE_TOKEN": "service-token-456"}):
            token = infisical_provider._get_auth_token()
            assert token == "service-token-456"

    def test_get_auth_token_missing_raises_error(
        self, infisical_provider: InfisicalProvider
    ) -> None:
        """Test error when auth token is missing."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                infisical_provider._get_auth_token()

            assert "authentication required" in str(exc_info.value).lower()

    @patch.dict(os.environ, {"INFISICAL_TOKEN": "test-token"})
    def test_validate_connection_success(
        self,
        infisical_provider: InfisicalProvider,
    ) -> None:
        """Test successful connection validation."""
        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get.return_value.status_code = 200
            mock_client_class.return_value = mock_client

            assert infisical_provider.validate_connection() is True
            mock_client.get.assert_called_once()

    @patch.dict(os.environ, {"INFISICAL_TOKEN": "test-token"})
    def test_validate_connection_failure(
        self,
        infisical_provider: InfisicalProvider,
    ) -> None:
        """Test failed connection validation."""
        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get.return_value.status_code = 401
            mock_client_class.return_value = mock_client

            assert infisical_provider.validate_connection() is False

    @patch.dict(os.environ, {"INFISICAL_TOKEN": "test-token"})
    def test_get_secret_success(
        self,
        infisical_provider: InfisicalProvider,
    ) -> None:
        """Test successful secret retrieval."""
        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get.return_value.json.return_value = {
                "secret": {"secretValue": "my-secret-password"}
            }
            mock_client_class.return_value = mock_client

            result = infisical_provider.get_secret("db_password")

            assert result == "my-secret-password"
            mock_client.get.assert_called_once()

    @patch.dict(os.environ, {"INFISICAL_TOKEN": "test-token"})
    def test_get_secret_not_found(
        self,
        infisical_provider: InfisicalProvider,
    ) -> None:
        """Test error when secret is not found."""
        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_response.raise_for_status.side_effect = Exception("404 Not Found")
            mock_client_class.return_value = mock_client
            mock_client.get.return_value = mock_response

            # Mock the httpx.HTTPError
            import httpx

            http_error = httpx.HTTPError("404 Not Found")
            http_error.response = mock_response
            mock_client.get.return_value.raise_for_status.side_effect = http_error

            with pytest.raises(ValueError) as exc_info:
                infisical_provider.get_secret("nonexistent_secret")

            assert "not found" in str(exc_info.value).lower()

    @patch.dict(os.environ, {"INFISICAL_TOKEN": "test-token"})
    def test_store_secret_success(
        self,
        infisical_provider: InfisicalProvider,
    ) -> None:
        """Test successful secret storage."""
        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post.return_value.status_code = 200
            mock_client_class.return_value = mock_client

            infisical_provider.store_secret("db_password", "new-secret-value")

            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert "db_password" in call_args[0][0]

    @patch.dict(os.environ, {"INFISICAL_TOKEN": "test-token"})
    def test_store_secret_failure(
        self,
        infisical_provider: InfisicalProvider,
    ) -> None:
        """Test error during secret storage."""
        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            import httpx

            http_error = httpx.HTTPError("Server error")
            mock_client.post.side_effect = http_error
            mock_client_class.return_value = mock_client

            with pytest.raises(ValueError) as exc_info:
                infisical_provider.store_secret("db_password", "secret-value")

            assert "failed to store" in str(exc_info.value).lower()

    @patch.dict(os.environ, {"INFISICAL_TOKEN": "test-token"})
    def test_delete_secret_success(
        self,
        infisical_provider: InfisicalProvider,
    ) -> None:
        """Test successful secret deletion."""
        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.delete.return_value.status_code = 200
            mock_client_class.return_value = mock_client

            infisical_provider.delete_secret("db_password")

            mock_client.delete.assert_called_once()

    def test_missing_httpx_raises_error(self, infisical_provider: InfisicalProvider) -> None:
        """Test error when httpx is not installed."""
        with patch.dict(os.environ, {"INFISICAL_TOKEN": "test-token"}):
            with patch("builtins.__import__", side_effect=ImportError("httpx")):
                with pytest.raises(ValueError) as exc_info:
                    # Clear cached client to force reimport
                    infisical_provider._client = None
                    infisical_provider._get_client()

                assert "httpx" in str(exc_info.value).lower()
