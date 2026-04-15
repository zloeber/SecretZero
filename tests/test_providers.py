"""Tests for provider implementations."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from secretzero.providers.base import BaseProvider, ProviderAuth
from secretzero.providers.registry import ProviderRegistry, get_registry


class DummyAuth(ProviderAuth):
    """Dummy auth for testing."""

    def __init__(self, config=None, should_auth=True):
        super().__init__(config)
        self._should_auth = should_auth
        self._is_auth = False

    def authenticate(self) -> bool:
        self._is_auth = self._should_auth
        return self._should_auth

    def is_authenticated(self) -> bool:
        return self._is_auth


class DummyProvider(BaseProvider):
    """Dummy provider for testing."""

    @property
    def provider_kind(self) -> str:
        """Return provider type identifier."""
        return "dummy"

    def test_connection(self) -> tuple[bool, str | None]:
        if self.is_authenticated():
            return True, "Connected"
        return False, "Not authenticated"

    def get_supported_targets(self) -> list[str]:
        return ["dummy_target"]


class TestProviderBase:
    """Tests for base provider classes."""

    def test_provider_auth_initialization(self):
        """Test provider auth initialization."""
        auth = DummyAuth({"key": "value"})
        assert auth.config == {"key": "value"}

    def test_provider_auth_authenticate(self):
        """Test provider authentication."""
        auth = DummyAuth(should_auth=True)
        assert auth.authenticate() is True
        assert auth.is_authenticated() is True

    def test_provider_auth_authenticate_failure(self):
        """Test provider authentication failure."""
        auth = DummyAuth(should_auth=False)
        assert auth.authenticate() is False
        assert auth.is_authenticated() is False

    def test_provider_initialization(self):
        """Test provider initialization."""
        auth = DummyAuth()
        provider = DummyProvider(name="test", config={"key": "value"}, auth=auth)
        assert provider.name == "test"
        assert provider.config == {"key": "value"}
        assert provider.auth == auth

    def test_provider_authenticate(self):
        """Test provider authenticate method."""
        auth = DummyAuth(should_auth=True)
        provider = DummyProvider(name="test", auth=auth)
        assert provider.authenticate() is True
        assert provider.is_authenticated() is True

    def test_provider_test_connection_success(self):
        """Test provider connection test when authenticated."""
        auth = DummyAuth(should_auth=True)
        auth.authenticate()
        provider = DummyProvider(name="test", auth=auth)
        success, message = provider.test_connection()
        assert success is True
        assert "Connected" in message

    def test_provider_test_connection_failure(self):
        """Test provider connection test when not authenticated."""
        auth = DummyAuth(should_auth=False)
        provider = DummyProvider(name="test", auth=auth)
        success, message = provider.test_connection()
        assert success is False
        assert "Not authenticated" in message

    def test_provider_get_supported_targets(self):
        """Test getting supported targets."""
        provider = DummyProvider(name="test")
        targets = provider.get_supported_targets()
        assert targets == ["dummy_target"]

    def test_provider_auth_get_token_info_not_implemented(self):
        """Test that base ProviderAuth.get_token_info raises NotImplementedError."""
        auth = DummyAuth()
        with pytest.raises(NotImplementedError, match="does not support token introspection"):
            auth.get_token_info()

    def test_provider_auth_get_scope_descriptions_default_empty(self):
        """Test that base ProviderAuth.get_scope_descriptions returns empty dict."""
        assert DummyAuth.get_scope_descriptions() == {}

    def test_provider_get_token_info_delegates_to_auth(self):
        """Test that BaseProvider.get_token_info delegates to auth."""
        auth = DummyAuth()
        provider = DummyProvider(name="test", auth=auth)
        # DummyAuth doesn't implement get_token_info, so it should raise
        with pytest.raises(NotImplementedError):
            provider.get_token_info()

    def test_provider_get_token_info_no_auth_raises(self):
        """Test that BaseProvider.get_token_info raises when no auth configured."""
        provider = DummyProvider(name="test", auth=None)
        with pytest.raises(RuntimeError, match="No authentication configured"):
            provider.get_token_info()

    def test_provider_get_scope_descriptions_default_empty(self):
        """Test that BaseProvider.get_scope_descriptions returns empty dict."""
        assert DummyProvider.get_scope_descriptions() == {}


class TestProviderRegistry:
    """Tests for provider registry."""

    def test_registry_initialization(self):
        """Test registry initialization."""
        registry = ProviderRegistry()
        assert registry.list_providers() == []
        assert registry.list_provider_types() == []

    def test_register_provider_class(self):
        """Test registering a provider class."""
        registry = ProviderRegistry()
        registry.register_provider_class("dummy", DummyProvider)
        assert "dummy" in registry.list_provider_types()

    def test_create_provider(self):
        """Test creating a provider instance."""
        registry = ProviderRegistry()
        registry.register_provider_class("dummy", DummyProvider)
        provider = registry.create_provider("dummy", "test_instance", {})
        assert provider is not None
        assert provider.name == "test_instance"

    def test_create_unknown_provider(self):
        """Test creating an unknown provider type."""
        registry = ProviderRegistry()
        provider = registry.create_provider("unknown", "test_instance", {})
        assert provider is None

    def test_get_provider(self):
        """Test getting a provider instance."""
        registry = ProviderRegistry()
        registry.register_provider_class("dummy", DummyProvider)
        created = registry.create_provider("dummy", "test_instance", {})
        retrieved = registry.get_provider("test_instance")
        assert retrieved is created

    def test_get_nonexistent_provider(self):
        """Test getting a nonexistent provider."""
        registry = ProviderRegistry()
        provider = registry.get_provider("nonexistent")
        assert provider is None

    def test_list_providers(self):
        """Test listing provider instances."""
        registry = ProviderRegistry()
        registry.register_provider_class("dummy", DummyProvider)
        registry.create_provider("dummy", "instance1", {})
        registry.create_provider("dummy", "instance2", {})
        providers = registry.list_providers()
        assert len(providers) == 2
        assert "instance1" in providers
        assert "instance2" in providers

    def test_global_registry(self):
        """Test global registry access."""
        registry = get_registry()
        assert isinstance(registry, ProviderRegistry)


# AWS Provider Tests (mocked)
@pytest.mark.parametrize("has_boto3", [True, False])
def test_aws_provider_import(has_boto3):
    """Test AWS provider import with/without boto3."""
    if has_boto3:
        try:
            from secretzero.providers.aws import AWSProvider

            assert AWSProvider is not None
        except ImportError:
            pytest.skip("boto3 not installed")
    else:
        # Can still import the module, just can't use it
        from secretzero.providers.aws import AWSProvider

        assert AWSProvider is not None


def test_aws_auth_ambient():
    """Test AWS ambient authentication (mocked)."""
    try:
        import boto3

        from secretzero.providers.aws import AWSAuth

        with patch("boto3.Session") as mock_session:
            mock_sts = MagicMock()
            mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
            mock_session_instance = MagicMock()
            mock_session_instance.client.return_value = mock_sts
            mock_session.return_value = mock_session_instance

            auth = AWSAuth({"kind": "ambient", "region": "us-east-1"})
            result = auth.authenticate()
            assert result is True
            assert auth.is_authenticated() is True

    except ImportError:
        pytest.skip("boto3 not installed")


def test_aws_provider_test_connection():
    """Test AWS provider connectivity test (mocked)."""
    try:
        import boto3

        from secretzero.providers.aws import AWSAuth, AWSProvider

        with patch("boto3.Session") as mock_session:
            mock_sts = MagicMock()
            mock_sts.get_caller_identity.return_value = {
                "Account": "123456789012",
                "Arn": "arn:aws:iam::123456789012:user/test",
            }
            mock_session_instance = MagicMock()
            mock_session_instance.client.return_value = mock_sts
            mock_session.return_value = mock_session_instance

            auth = AWSAuth({"kind": "ambient", "region": "us-east-1"})
            auth.authenticate()
            provider = AWSProvider(name="aws", auth=auth)

            success, message = provider.test_connection()
            assert success is True
            assert "123456789012" in message

    except ImportError:
        pytest.skip("boto3 not installed")


def test_aws_provider_supported_targets():
    """Test AWS provider supported targets."""
    try:
        from secretzero.providers.aws import AWSProvider

        provider = AWSProvider(name="aws")
        targets = provider.get_supported_targets()
        assert "ssm_parameter" in targets
        assert "secrets_manager" in targets

    except ImportError:
        pytest.skip("boto3 not installed")


def test_aws_auth_get_token_info_includes_region():
    """Token identity should expose resolved AWS region."""
    from secretzero.providers.aws import AWSAuth

    auth = AWSAuth({"kind": "ambient", "region": "us-east-2"})
    mock_sts = MagicMock()
    mock_sts.get_caller_identity.return_value = {
        "Account": "123456789012",
        "Arn": "arn:aws:iam::123456789012:user/tester",
        "UserId": "AIDATEST",
    }
    mock_session = MagicMock()
    mock_session.region_name = "us-west-1"
    mock_session.client.return_value = mock_sts
    auth._session = mock_session

    info = auth.get_token_info()

    assert info["region"] == "us-west-1"
    assert info["account"] == "123456789012"
    assert info["arn"] == "arn:aws:iam::123456789012:user/tester"


# Azure Provider Tests (mocked)
def test_azure_auth_default():
    """Test Azure default authentication (mocked)."""
    try:
        from secretzero.providers.azure import AzureAuth

        with patch("azure.identity.DefaultAzureCredential") as mock_cred:
            mock_cred_instance = MagicMock()
            mock_cred_instance.get_token.return_value = MagicMock()
            mock_cred.return_value = mock_cred_instance

            auth = AzureAuth({"kind": "default"})
            result = auth.authenticate()
            assert result is True

    except ImportError:
        pytest.skip("Azure SDK not installed")


def test_azure_provider_supported_targets():
    """Test Azure provider supported targets."""
    try:
        from secretzero.providers.azure import AzureProvider

        provider = AzureProvider(name="azure")
        targets = provider.get_supported_targets()
        assert "key_vault" in targets

    except ImportError:
        pytest.skip("Azure SDK not installed")


# Vault Provider Tests (mocked)
def test_vault_auth_token():
    """Test Vault token authentication (mocked)."""
    try:
        import hvac

        from secretzero.providers.vault import VaultAuth

        with patch("hvac.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.is_authenticated.return_value = True
            mock_client.return_value = mock_client_instance

            auth = VaultAuth(
                {"kind": "token", "token": "test-token", "url": "http://localhost:8200"}
            )
            result = auth.authenticate()
            assert result is True

    except ImportError:
        pytest.skip("hvac not installed")


def test_vault_provider_supported_targets():
    """Test Vault provider supported targets."""
    try:
        from secretzero.providers.vault import VaultProvider

        provider = VaultProvider(name="vault")
        targets = provider.get_supported_targets()
        assert "kv" in targets

    except ImportError:
        pytest.skip("hvac not installed")
