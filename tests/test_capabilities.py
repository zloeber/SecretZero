"""Tests for provider capabilities system."""

import pytest

from secretzero.providers.base import BaseProvider, ProviderAuth
from secretzero.providers.capabilities import (
    Capability,
    CapabilityType,
    IProviderWithCapabilities,
    MethodSignature,
    ParameterSchema,
    ProviderCapabilities,
)


class ProviderWithCapabilities(BaseProvider):
    """Test provider with capability methods (renamed to avoid pytest collection)."""

    @property
    def provider_kind(self) -> str:
        """Return provider type identifier."""
        return "test"

    def test_connection(self) -> tuple[bool, str | None]:
        """Test connection."""
        return True, None

    def get_supported_targets(self) -> list[str]:
        """Get supported targets."""
        return ["test_target"]

    def generate_password(self, length: int = 32, special_chars: bool = True) -> str:
        """Generate a secure password.

        Args:
            length: Password length
            special_chars: Include special characters

        Returns:
            Generated password
        """
        return "test_password_123!"

    def retrieve_secret(self, secret_name: str, version: str | None = None) -> str:
        """Retrieve a secret from the provider.

        Args:
            secret_name: Name of secret to retrieve
            version: Optional version to retrieve

        Returns:
            Secret value
        """
        return f"secret_value_for_{secret_name}"

    def store_secret(self, secret_name: str, secret_value: str) -> None:
        """Store a secret in the provider.

        Args:
            secret_name: Name of secret
            secret_value: Value to store
        """
        pass

    def rotate_secret(self, secret_name: str, rotation_days: int = 90) -> dict:
        """Rotate a secret.

        Args:
            secret_name: Name of secret to rotate
            rotation_days: Rotation frequency in days

        Returns:
            Rotation result metadata
        """
        return {"rotated": True, "secret_name": secret_name}

    def delete_secret(self, secret_name: str, permanently: bool = False) -> bool:
        """Delete a secret.

        Args:
            secret_name: Name of secret to delete
            permanently: Permanently delete (no recovery)

        Returns:
            True if deleted successfully
        """
        return True


class TestCapabilityInterface:
    """Tests for capability interface."""

    def test_interface_is_abstract(self):
        """Test that IProviderWithCapabilities is abstract."""
        from abc import ABC

        assert issubclass(IProviderWithCapabilities, ABC)
        with pytest.raises(TypeError):
            # Can't instantiate ABC directly
            IProviderWithCapabilities()  # type: ignore

    def test_base_provider_implements_interface(self):
        """Test that BaseProvider implements IProviderWithCapabilities."""
        assert issubclass(BaseProvider, IProviderWithCapabilities)


class TestCapabilityIntrospection:
    """Tests for capability introspection."""

    def test_get_capabilities_returns_correct_types(self):
        """Test that get_capabilities returns ProviderCapabilities."""
        caps = ProviderWithCapabilities.get_capabilities()
        assert isinstance(caps, ProviderCapabilities)
        assert (
            caps.provider_kind == "withcapabilities"
        )  # From class name (lowercase, 'Provider' stripped)
        assert caps.version == "1.0"

    def test_get_capabilities_discovers_generate_methods(self):
        """Test that generate_ methods are discovered."""
        caps = ProviderWithCapabilities.get_capabilities()
        generate_caps = [
            c for c in caps.capabilities if c.capability_type == CapabilityType.GENERATE
        ]
        assert len(generate_caps) == 1
        assert generate_caps[0].method.name == "generate_password"

    def test_get_capabilities_discovers_retrieve_methods(self):
        """Test that retrieve_ methods are discovered."""
        caps = ProviderWithCapabilities.get_capabilities()
        retrieve_caps = [
            c for c in caps.capabilities if c.capability_type == CapabilityType.RETRIEVE
        ]
        assert len(retrieve_caps) == 1
        assert retrieve_caps[0].method.name == "retrieve_secret"

    def test_get_capabilities_discovers_store_methods(self):
        """Test that store_ methods are discovered."""
        caps = ProviderWithCapabilities.get_capabilities()
        store_caps = [c for c in caps.capabilities if c.capability_type == CapabilityType.STORE]
        assert len(store_caps) == 1
        assert store_caps[0].method.name == "store_secret"

    def test_get_capabilities_discovers_rotate_methods(self):
        """Test that rotate_ methods are discovered."""
        caps = ProviderWithCapabilities.get_capabilities()
        rotate_caps = [c for c in caps.capabilities if c.capability_type == CapabilityType.ROTATE]
        assert len(rotate_caps) == 1
        assert rotate_caps[0].method.name == "rotate_secret"

    def test_get_capabilities_discovers_delete_methods(self):
        """Test that delete_ methods are discovered."""
        caps = ProviderWithCapabilities.get_capabilities()
        delete_caps = [c for c in caps.capabilities if c.capability_type == CapabilityType.DELETE]
        assert len(delete_caps) == 1
        assert delete_caps[0].method.name == "delete_secret"

    def test_get_capabilities_extracts_parameters(self):
        """Test that method parameters are extracted."""
        caps = ProviderWithCapabilities.get_capabilities()
        cap = caps.get_capability("generate_password")
        assert cap is not None
        assert "length" in cap.method.parameters
        assert "special_chars" in cap.method.parameters

        length_param = cap.method.parameters["length"]
        assert length_param.default == 32
        assert length_param.required is False

        special_param = cap.method.parameters["special_chars"]
        assert special_param.default is True
        assert special_param.required is False

    def test_get_capabilities_excludes_private_methods(self):
        """Test that private methods are excluded."""
        caps = ProviderWithCapabilities.get_capabilities()
        # Should not include _private methods or methods without capability prefixes
        method_names = [c.method.name for c in caps.capabilities]
        assert not any(name.startswith("_") for name in method_names)

    def test_list_available_methods(self):
        """Test that list_available_methods returns all capability methods."""
        provider = ProviderWithCapabilities(name="test")
        methods = provider.list_available_methods()
        assert "generate_password" in methods
        assert "retrieve_secret" in methods
        assert "store_secret" in methods
        assert "rotate_secret" in methods
        assert "delete_secret" in methods
        assert len(methods) == 5

    def test_get_method_schema(self):
        """Test that get_method_schema returns MethodSignature."""
        provider = ProviderWithCapabilities(name="test")
        schema = provider.get_method_schema("generate_password")
        assert isinstance(schema, MethodSignature)
        assert schema.name == "generate_password"
        assert "length" in schema.parameters
        assert "special_chars" in schema.parameters

    def test_get_method_schema_raises_for_nonexistent_method(self):
        """Test that get_method_schema raises ValueError for unknown methods."""
        provider = ProviderWithCapabilities(name="test")
        with pytest.raises(ValueError, match="Method 'nonexistent_method' not found"):
            provider.get_method_schema("nonexistent_method")


class TestProviderCapabilitiesModel:
    """Tests for ProviderCapabilities model."""

    def test_provider_capabilities_model(self):
        """Test basic ProviderCapabilities model."""
        sig = MethodSignature(
            name="generate_password",
            description="Generate a password",
            return_type="str",
            parameters={"length": ParameterSchema(type="int", required=False, default=32)},
        )
        cap = Capability(
            capability_type=CapabilityType.GENERATE,
            method=sig,
            requires_auth=True,
            supported_targets=[],
        )
        caps = ProviderCapabilities(provider_kind="test", version="1.0", capabilities=[cap])
        assert caps.provider_kind == "test"
        assert len(caps.capabilities) == 1

    def test_get_capability_by_name(self):
        """Test get_capability method."""
        sig = MethodSignature(
            name="generate_password",
            description="Generate a password",
            return_type="str",
            parameters={},
        )
        cap = Capability(capability_type=CapabilityType.GENERATE, method=sig, requires_auth=True)
        caps = ProviderCapabilities(provider_kind="test", version="1.0", capabilities=[cap])
        result = caps.get_capability("generate_password")
        assert result == cap

    def test_get_capability_returns_none_for_missing(self):
        """Test get_capability returns None for missing methods."""
        caps = ProviderCapabilities(provider_kind="test", version="1.0", capabilities=[])
        result = caps.get_capability("nonexistent")
        assert result is None

    def test_has_capability(self):
        """Test has_capability method."""
        sig = MethodSignature(
            name="generate_password", description="", return_type="str", parameters={}
        )
        cap = Capability(capability_type=CapabilityType.GENERATE, method=sig)
        caps = ProviderCapabilities(provider_kind="test", version="1.0", capabilities=[cap])
        # has_capability checks by CapabilityType, not method name
        assert caps.has_capability(CapabilityType.GENERATE) is True
        assert caps.has_capability(CapabilityType.RETRIEVE) is False
        # To check for specific method, use get_capability
        assert caps.get_capability("generate_password") is not None
        assert caps.get_capability("nonexistent") is None

    def test_list_methods_by_type(self):
        """Test list_methods_by_type method."""
        gen_sig = MethodSignature(
            name="generate_password", description="", return_type="str", parameters={}
        )
        ret_sig = MethodSignature(
            name="retrieve_secret", description="", return_type="str", parameters={}
        )
        caps = ProviderCapabilities(
            provider_kind="test",
            version="1.0",
            capabilities=[
                Capability(capability_type=CapabilityType.GENERATE, method=gen_sig),
                Capability(capability_type=CapabilityType.RETRIEVE, method=ret_sig),
            ],
        )
        generate_methods = caps.list_methods_by_type(CapabilityType.GENERATE)
        assert generate_methods == ["generate_password"]

        retrieve_methods = caps.list_methods_by_type(CapabilityType.RETRIEVE)
        assert retrieve_methods == ["retrieve_secret"]


class TestRealProviderCapabilities:
    """Tests for real provider implementations."""

    def test_dummy_provider_has_capabilities(self):
        """Test that test provider has no capability methods by default."""
        from secretzero.providers.base import BaseProvider

        class MinimalProvider(BaseProvider):
            @property
            def provider_kind(self) -> str:
                return "minimal"

            def test_connection(self) -> tuple[bool, str | None]:
                return True, None

            def get_supported_targets(self) -> list[str]:
                return []

        caps = MinimalProvider.get_capabilities()
        assert isinstance(caps, ProviderCapabilities)
        assert caps.provider_kind == "minimal"  # From class name (lowercase, 'Provider' stripped)
        assert len(caps.capabilities) == 0  # No capability methods defined

    def test_aws_provider_has_capabilities(self):
        """Test that AWS provider has capabilities."""
        try:
            from secretzero.providers.aws import AWSProvider

            caps = AWSProvider.get_capabilities()
            assert isinstance(caps, ProviderCapabilities)
            assert caps.provider_kind == "aws"  # From class name (lowercase, 'Provider' stripped)
            # AWS provider should have 5 capability methods: generate_password, retrieve_secret, store_secret, rotate_secret, delete_secret
            assert len(caps.capabilities) == 5
            assert caps.get_capability("generate_password") is not None
            assert caps.get_capability("retrieve_secret") is not None
            assert caps.get_capability("store_secret") is not None
            assert caps.get_capability("rotate_secret") is not None
            assert caps.get_capability("delete_secret") is not None
        except ImportError:
            pytest.skip("AWS provider dependencies not installed")

    def test_vault_provider_has_capabilities(self):
        """Test that Vault provider has capabilities."""
        try:
            from secretzero.providers.vault import VaultProvider

            caps = VaultProvider.get_capabilities()
            assert isinstance(caps, ProviderCapabilities)
            assert caps.provider_kind == "vault"  # From class name (lowercase, 'Provider' stripped)
            # Vault provider should have 6 capability methods: generate_password, generate_api_token, retrieve_secret, store_secret, rotate_secret, delete_secret
            assert len(caps.capabilities) == 6
            assert caps.get_capability("generate_password") is not None
            assert caps.get_capability("generate_api_token") is not None
            assert caps.get_capability("retrieve_secret") is not None
            assert caps.get_capability("store_secret") is not None
            assert caps.get_capability("rotate_secret") is not None
            assert caps.get_capability("delete_secret") is not None
        except ImportError:
            pytest.skip("Vault provider dependencies not installed")
