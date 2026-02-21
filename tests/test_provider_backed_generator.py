"""Tests for provider-backed secret generator."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from secretzero.generators.provider_backed import (
    ProviderBackedGenerator,
    ProviderBackedGeneratorConfig,
)
from secretzero.providers.base import BaseProvider
from secretzero.providers.capabilities import CapabilityType, MethodSignature, ParameterSchema


class MockProvider(BaseProvider):
    """Mock provider for testing provider-backed generator."""

    @property
    def provider_kind(self) -> str:
        """Return provider type identifier."""
        return "mock"

    def test_connection(self) -> tuple[bool, str | None]:
        """Test connection."""
        return True, None

    def get_supported_targets(self) -> list[str]:
        """Get supported targets."""
        return []

    def generate_password(self, length: int = 32, special_chars: bool = True) -> str:
        """Generate a secure password."""
        return f"mock_password_{'x' * length}"

    def generate_token(self, length: int = 64) -> str:
        """Generate a security token."""
        return f"token_{'y' * length}"

    def retrieve_secret(self, secret_name: str) -> str:
        """Retrieve secret from store."""
        return f"secret_value_for_{secret_name}"

    def store_metadata(self, secret_name: str, metadata: dict) -> dict:
        """Store and return metadata."""
        return {"name": secret_name, "size": len(metadata)}


class TestProviderBackedGeneratorConfig:
    """Tests for configuration."""

    def test_config_initialization(self):
        """Test configuration initialization."""
        provider = MagicMock()
        config = ProviderBackedGeneratorConfig(
            {"provider": provider, "method": "generate_password"}
        )
        assert config.provider is provider
        assert config.method == "generate_password"
        assert config.method_args == {}

    def test_config_with_method_args(self):
        """Test configuration with method arguments."""
        provider = MagicMock()
        args = {"length": 64, "special_chars": False}
        config = ProviderBackedGeneratorConfig(
            {"provider": provider, "method": "generate_password", "method_args": args}
        )
        assert config.method_args == args

    def test_config_missing_provider(self):
        """Test that config requires provider."""
        with pytest.raises(ValueError, match="requires 'provider'"):
            ProviderBackedGeneratorConfig({"method": "generate_password"})

    def test_config_missing_method(self):
        """Test that config requires method."""
        provider = MagicMock()
        with pytest.raises(ValueError, match="requires 'method'"):
            ProviderBackedGeneratorConfig({"provider": provider})


class TestProviderBackedGeneratorInitialization:
    """Tests for generator initialization."""

    def test_generator_initialization(self):
        """Test generator initialization."""
        provider = MockProvider(name="test")
        gen = ProviderBackedGenerator({"provider": provider, "method": "generate_password"})
        assert gen.gen_config.provider is provider
        assert gen.gen_config.method == "generate_password"

    def test_generator_with_args(self):
        """Test generator initialization with method arguments."""
        provider = MockProvider(name="test")
        args = {"length": 64, "special_chars": False}
        gen = ProviderBackedGenerator(
            {
                "provider": provider,
                "method": "generate_password",
                "method_args": args,
            }
        )
        assert gen.gen_config.method_args == args

    def test_generator_invalid_provider_type(self):
        """Test that provider must implement interface."""
        with pytest.raises(TypeError, match="must implement IProviderWithCapabilities"):
            ProviderBackedGenerator({"provider": "not_a_provider", "method": "generate_password"})

    def test_generator_nonexistent_method(self):
        """Test that method must exist on provider."""
        provider = MockProvider(name="test")
        with pytest.raises(AttributeError, match="has no method 'nonexistent_method'"):
            ProviderBackedGenerator({"provider": provider, "method": "nonexistent_method"})

    def test_generator_non_capability_method(self):
        """Test that method must be a capability method."""

        class BrokenProvider(MockProvider):
            def non_capability_method(self):
                pass

        provider = BrokenProvider(name="test")
        with pytest.raises(ValueError, match="is not a capability method"):
            ProviderBackedGenerator({"provider": provider, "method": "non_capability_method"})


class TestProviderBackedGeneratorGeneration:
    """Tests for secret generation."""

    def test_generate_string_result(self):
        """Test generation with string result."""
        provider = MockProvider(name="test")
        gen = ProviderBackedGenerator({"provider": provider, "method": "generate_password"})
        secret = gen.generate()
        assert isinstance(secret, str)
        assert secret.startswith("mock_password_")

    def test_generate_with_arguments(self):
        """Test generation with method arguments."""
        provider = MockProvider(name="test")
        gen = ProviderBackedGenerator(
            {
                "provider": provider,
                "method": "generate_password",
                "method_args": {"length": 100},
            }
        )
        secret = gen.generate()
        assert isinstance(secret, str)
        assert len(secret) == 14 + 100  # "mock_password_" + 100 x's

    def test_generate_multiple_args(self):
        """Test generation with multiple method arguments."""
        provider = MockProvider(name="test")
        gen = ProviderBackedGenerator(
            {
                "provider": provider,
                "method": "generate_password",
                "method_args": {"length": 64, "special_chars": True},
            }
        )
        secret = gen.generate()
        assert len(secret) == 14 + 64

    def test_generate_fails_on_error(self):
        """Test that errors from provider are captured."""

        class ErrorProvider(MockProvider):
            def generate_password(self, **kwargs):
                raise RuntimeError("Provider error")

        provider = ErrorProvider(name="test")
        gen = ProviderBackedGenerator({"provider": provider, "method": "generate_password"})
        with pytest.raises(RuntimeError, match="Failed to generate secret"):
            gen.generate()

    def test_generate_handles_int_result(self):
        """Test generation with integer result."""
        provider = MagicMock()
        provider.list_available_methods.return_value = ["generate_secret"]
        provider.get_method_schema.return_value = MagicMock()

        class IntProvider(MockProvider):
            def generate_secret(self):
                return 12345

        provider_instance = IntProvider(name="test")

        gen = ProviderBackedGenerator({"provider": provider_instance, "method": "generate_secret"})
        secret = gen.generate()
        assert secret == "12345"

    def test_generate_handles_float_result(self):
        """Test generation with float result."""

        class FloatProvider(MockProvider):
            def generate_secret(self):
                return 123.45

        provider = FloatProvider(name="test")
        gen = ProviderBackedGenerator({"provider": provider, "method": "generate_secret"})
        secret = gen.generate()
        assert secret == "123.45"

    def test_generate_handles_bool_result(self):
        """Test generation with boolean result."""

        class BoolProvider(MockProvider):
            def generate_secret(self):
                return True

        provider = BoolProvider(name="test")
        gen = ProviderBackedGenerator({"provider": provider, "method": "generate_secret"})
        secret = gen.generate()
        assert secret == "True"

    def test_generate_handles_dict_result(self):
        """Test generation with dictionary result."""

        class DictProvider(MockProvider):
            def store_metadata(self, **kwargs):
                return {"name": "test", "size": 42}

        provider = DictProvider(name="test")
        gen = ProviderBackedGenerator({"provider": provider, "method": "store_metadata"})
        secret = gen.generate()
        result = json.loads(secret)
        assert result == {"name": "test", "size": 42}

    def test_generate_fails_on_unsupported_type(self):
        """Test generation fails on unsupported return type."""

        class ListProvider(MockProvider):
            def generate_secret(self):
                return ["list", "result"]

        provider = ListProvider(name="test")
        gen = ProviderBackedGenerator({"provider": provider, "method": "generate_secret"})
        with pytest.raises(TypeError, match="expected str, int, float, bool, or dict"):
            gen.generate()

    def test_generate_with_fallback(self):
        """Test generate_with_fallback method."""
        provider = MockProvider(name="test")
        gen = ProviderBackedGenerator({"provider": provider, "method": "generate_token"})
        secret = gen.generate_with_fallback()
        assert isinstance(secret, str)
        assert secret.startswith("token_")

    def test_generate_with_fallback_env_var(self):
        """Test generate_with_fallback with environment variable."""
        import os

        provider = MockProvider(name="test")
        gen = ProviderBackedGenerator({"provider": provider, "method": "generate_token"})

        # Set environment variable
        os.environ["TEST_SECRET"] = "from_env"
        try:
            secret = gen.generate_with_fallback(env_var_name="TEST_SECRET")
            assert secret == "from_env"
        finally:
            del os.environ["TEST_SECRET"]


class TestProviderBackedGeneratorValidation:
    """Tests for configuration validation."""

    def test_validate_valid_configuration(self):
        """Test validation of valid configuration."""
        provider = MockProvider(name="test")
        gen = ProviderBackedGenerator({"provider": provider, "method": "generate_password"})
        valid, error = gen.validate_configuration()
        assert valid is True
        assert error is None

    def test_validate_missing_provider(self):
        """Test validation fails with missing provider."""
        gen = ProviderBackedGenerator.__new__(ProviderBackedGenerator)
        gen.gen_config = ProviderBackedGeneratorConfig.__new__(ProviderBackedGeneratorConfig)
        gen.gen_config.provider = None
        gen.gen_config.method = "generate_password"
        gen.gen_config.method_args = {}

        valid, error = gen.validate_configuration()
        assert valid is False
        assert "not configured" in error

    def test_validate_nonexistent_method(self):
        """Test validation fails with nonexistent method."""
        provider = MockProvider(name="test")
        gen = ProviderBackedGenerator({"provider": provider, "method": "generate_password"})
        gen.gen_config.method = "nonexistent_method"

        valid, error = gen.validate_configuration()
        assert valid is False
        assert "has no method" in error

    def test_validate_non_capability_method(self):
        """Test validation fails with non-capability method."""

        class BrokenProvider(MockProvider):
            def non_capability_method(self):
                pass

        provider = BrokenProvider(name="test")
        # Use a method that exists
        gen = ProviderBackedGenerator({"provider": provider, "method": "generate_password"})
        gen.gen_config.method = "non_capability_method"

        valid, error = gen.validate_configuration()
        assert valid is False
        assert "not a capability method" in error


class TestProviderBackedGeneratorIntegration:
    """Integration tests with real provider."""

    def test_integration_with_mock_provider(self):
        """Test integration with mock provider."""
        provider = MockProvider(name="vault")
        gen = ProviderBackedGenerator(
            {
                "provider": provider,
                "method": "generate_password",
                "method_args": {"length": 50},
            }
        )

        # Generate multiple secrets
        secret1 = gen.generate()
        secret2 = gen.generate()

        assert isinstance(secret1, str)
        assert isinstance(secret2, str)
        assert len(secret1) == len(secret2)
        assert secret1 == secret2  # Same config produces same result in mock

    def test_integration_multiple_methods(self):
        """Test integration with multiple methods on same provider."""
        provider = MockProvider(name="mock")

        gen1 = ProviderBackedGenerator({"provider": provider, "method": "generate_password"})
        gen2 = ProviderBackedGenerator(
            {"provider": provider, "method": "generate_token", "method_args": {"length": 80}}
        )

        secret1 = gen1.generate()
        secret2 = gen2.generate()

        assert secret1.startswith("mock_password_")
        assert secret2.startswith("token_")
        assert secret1 != secret2


class TestProviderBackedGeneratorMarkers:
    """Tests with various providers that have capability methods."""

    def test_with_provider_having_generate_method(self):
        """Test with provider that has generate methods."""

        class PasswordProvider(MockProvider):
            def generate_password(self, **kwargs):
                return "generated_password"

            def generate_api_key(self, **kwargs):
                return "generated_api_key"

        provider = PasswordProvider(name="test")

        gen_pwd = ProviderBackedGenerator({"provider": provider, "method": "generate_password"})
        gen_key = ProviderBackedGenerator({"provider": provider, "method": "generate_api_key"})

        assert gen_pwd.generate() == "generated_password"
        assert gen_key.generate() == "generated_api_key"

    def test_with_provider_having_retrieve_method(self):
        """Test with provider that has retrieve methods."""

        class VaultProvider(MockProvider):
            def retrieve_secret(self, secret_name: str, **kwargs):
                return f"secret_value_of_{secret_name}"

        provider = VaultProvider(name="vault")
        gen = ProviderBackedGenerator(
            {
                "provider": provider,
                "method": "retrieve_secret",
                "method_args": {"secret_name": "db_password"},
            }
        )

        result = gen.generate()
        assert result == "secret_value_of_db_password"
