"""Provider-backed secret generator for SecretZero.

This generator delegates secret generation to a provider that has native
generation capabilities (e.g., Vault's password generation, AWS IAM
credential generation, etc.).
"""

from typing import Any

from secretzero.generators.base import BaseGenerator
from secretzero.providers.base import BaseProvider
from secretzero.providers.capabilities import CapabilityType, IProviderWithCapabilities


class ProviderBackedGeneratorConfig:
    """Configuration for provider-backed generator."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize configuration.

        Args:
            config: Configuration dictionary with:
                - provider: Provider instance or registry key
                - method: Method name to call on provider
                - method_args: Arguments to pass to method (default: {})
        """
        self.provider = config.get("provider")
        self.method = config.get("method")
        self.method_args = config.get("method_args", {})

        if not self.provider:
            raise ValueError("provider_backed generator requires 'provider' configuration")
        if not self.method:
            raise ValueError("provider_backed generator requires 'method' configuration")


class ProviderBackedGenerator(BaseGenerator):
    """Generator that delegates to a provider's capability method.

    .. rubric:: Bundle provider injection protocol

    The sync engine inspects ``PROVIDER_CONFIG_KEY`` and ``PROVIDER_INJECTION_KEY``
    class attributes to inject the resolved provider instance into the config
    before instantiation.  For this generator both keys are ``"provider"``,
    meaning the string provider name in ``config["provider"]`` is *replaced*
    in-place with the actual provider instance.

    This allows using provider-native operations for secret generation:
    - Vault's password/certificate generation
    - AWS IAM credential generation
    - Azure service principal creation
    - etc.

    Example configuration:
        generator: provider_backed
        generator_config:
          provider: vault_instance
          method: generate_password
          method_args:
            length: 32
            special_chars: true
    """

    #: Key in the generator config dict that holds the provider *name* string.
    #: Used by the sync engine to resolve the provider instance.
    PROVIDER_CONFIG_KEY: str = "provider"

    #: Key under which the sync engine injects the resolved provider *instance*.
    #: For this generator the string name is replaced in-place.
    PROVIDER_INJECTION_KEY: str = "provider"

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize provider-backed generator.

        Args:
            config: Configuration dictionary

        Raises:
            ValueError: If provider or method not configured
            TypeError: If provider doesn't support the method
        """
        super().__init__(config)
        self.gen_config = ProviderBackedGeneratorConfig(config)

        # Validate provider implements capabilities
        provider = self.gen_config.provider
        if not isinstance(provider, (BaseProvider, IProviderWithCapabilities)):
            raise TypeError(
                f"Provider must implement IProviderWithCapabilities, got {type(provider)}"
            )

        # Validate method exists
        if not hasattr(provider, self.gen_config.method):
            raise AttributeError(
                f"Provider {provider.__class__.__name__} has no method '{self.gen_config.method}'"
            )

        # Validate method is a capability method
        available_methods = provider.list_available_methods()
        if self.gen_config.method not in available_methods:
            raise ValueError(
                f"Method '{self.gen_config.method}' is not a capability method on {provider.__class__.__name__}. "
                f"Available: {', '.join(available_methods)}"
            )

    def generate(self) -> str:
        """Generate a secret using the provider method.

        Returns:
            Generated secret value from the provider

        Raises:
            RuntimeError: If provider method fails
            TypeError: If method return value is not a string
        """
        provider = self.gen_config.provider
        method = getattr(provider, self.gen_config.method)
        args = self.gen_config.method_args or {}

        try:
            result = method(**args)
        except Exception as e:
            raise RuntimeError(
                f"Failed to generate secret using {self.gen_config.method}: {e}"
            ) from e

        # Convert result to string if needed
        if isinstance(result, str):
            return result
        if isinstance(result, (int, float, bool)):
            return str(result)
        if isinstance(result, dict):
            # For dict results, return JSON string or specific field
            import json

            return json.dumps(result)

        raise TypeError(
            f"Provider method {self.gen_config.method} returned {type(result)}, "
            f"expected str, int, float, bool, or dict"
        )

    def validate_configuration(self) -> tuple[bool, str | None]:
        """Validate generator configuration.

        Returns:
            Tuple of (valid: bool, error_message: Optional[str])
        """
        try:
            provider = self.gen_config.provider
            if not provider:
                return False, "Provider is not configured"

            if not isinstance(provider, (BaseProvider, IProviderWithCapabilities)):
                return False, "Provider must implement IProviderWithCapabilities"

            method = self.gen_config.method
            if not hasattr(provider, method):
                return False, f"Provider has no method '{method}'"

            available = provider.list_available_methods()
            if method not in available:
                return False, f"Method '{method}' is not a capability method"

            # Try to get method schema to validate it exists and is callable
            schema = provider.get_method_schema(method)
            if not schema:
                return False, f"Could not get schema for method '{method}'"

            return True, None
        except Exception as e:
            return False, str(e)
