"""Base classes for provider implementations."""

import inspect
from abc import ABC, abstractmethod
from typing import Any, get_type_hints

from secretzero.providers.capabilities import (
    Capability,
    CapabilityType,
    IProviderWithCapabilities,
    MethodSignature,
    ParameterSchema,
    ProviderCapabilities,
)


class ProviderAuth(ABC):
    """Base class for provider authentication."""

    #: Environment variable that carries the authentication token.
    #: Subclasses should override (e.g. ``ENV_TOKEN = "GITHUB_TOKEN"``).
    ENV_TOKEN: str = ""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize authentication with configuration.

        Args:
            config: Authentication configuration dictionary
        """
        self.config = config or {}

    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate with the provider.

        Returns:
            True if authentication successful, False otherwise
        """
        pass

    @abstractmethod
    def is_authenticated(self) -> bool:
        """Check if currently authenticated.

        Returns:
            True if authenticated, False otherwise
        """
        pass

    def get_client(self) -> Any:
        """Get authenticated client for the provider.

        Returns:
            Authenticated client instance or None
        """
        return None

    def get_token_info(self) -> dict[str, Any]:
        """Return information about the current authentication token.

        Providers that support token introspection should override this method
        to return details such as user identity, scopes/permissions, and token
        type.

        Returns:
            Dictionary with at least:
                - user: Identity associated with the token
                - scopes: List of permission scopes granted
                - token_type: Kind of token (e.g. 'PAT', 'OAuth')

        Raises:
            NotImplementedError: If the provider does not support token introspection.
        """
        raise NotImplementedError(f"{type(self).__name__} does not support token introspection")

    @classmethod
    def get_scope_descriptions(cls) -> dict[str, str]:
        """Return a mapping of scope/permission names to human-readable descriptions.

        Providers that expose OAuth-style scopes should override this method.

        Returns:
            Dictionary mapping scope name to description string.
        """
        return {}


class BaseProvider(IProviderWithCapabilities):
    """Base class for all providers with capability support."""

    #: Human-readable name shown in CLI listings (e.g. "Amazon Web Services").
    display_name: str = ""

    #: Short description shown in CLI listings.
    description: str = ""

    #: ``(import_name, pip_install_name)`` for the required third-party
    #: package, e.g. ``("boto3", "secretzero[aws]")``.  ``None`` if the
    #: provider has no extra dependencies.
    required_package: tuple[str, str] | None = None

    #: The :class:`ProviderAuth` subclass used by this provider.
    #: Subclasses should override this so CLI/tooling can inspect
    #: auth-level metadata (e.g. ``ENV_TOKEN``) without instantiation.
    auth_class: type[ProviderAuth] = ProviderAuth

    #: Supported authentication method names and descriptions, e.g.
    #: ``{"token": "Use a personal access token", "ambient": "SDK chain"}``.
    auth_methods: dict[str, str] = {}

    #: Configuration options shown in CLI help, e.g.
    #: ``{"region": "AWS region (default: us-east-1)"}``.
    config_options: dict[str, str] = {}

    #: Example YAML snippet shown in ``secretzero providers --provider <kind>``.
    config_example: str = ""

    #: Mapping of target kind → detail dict for CLI display.
    #: Each value has ``description``, ``config`` (dict[str, str]), and ``example`` (str).
    target_details: dict[str, dict[str, Any]] = {}

    @classmethod
    def get_provider_detail(cls) -> dict[str, Any]:
        """Return a self-describing detail dict used by CLI ``providers`` commands.

        The returned dict has keys ``description``, ``auth_methods``,
        ``config``, ``example``, ``target_details`` — all sourced from
        class-level attributes so bundles self-register their docs.

        Returns:
            Provider detail dictionary.
        """
        return {
            "description": cls.display_name or cls.description,
            "auth_methods": dict(cls.auth_methods),
            "config": dict(cls.config_options),
            "example": cls.config_example,
            "target_details": dict(cls.target_details),
        }

    def __init__(
        self,
        name: str,
        config: dict[str, Any] | None = None,
        auth: ProviderAuth | None = None,
    ):
        """Initialize provider.

        Args:
            name: Provider name
            config: Provider configuration
            auth: Provider authentication instance
        """
        self.name = name
        self.config = config or {}
        self.auth = auth
        self._authenticated = False

    @property
    @abstractmethod
    def provider_kind(self) -> str:
        """Return provider type identifier.

        Returns:
            Provider kind string (e.g., 'vault', 'aws', 'github')
        """
        pass

    @abstractmethod
    def test_connection(self) -> tuple[bool, str | None]:
        """Test provider connectivity.

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        pass

    def authenticate(self) -> bool:
        """Authenticate with the provider.

        Returns:
            True if authentication successful, False otherwise
        """
        if self.auth:
            self._authenticated = self.auth.authenticate()
            return self._authenticated
        return False

    def is_authenticated(self) -> bool:
        """Check if provider is authenticated.

        Returns:
            True if authenticated, False otherwise
        """
        if self.auth:
            return self.auth.is_authenticated()
        return self._authenticated

    @abstractmethod
    def get_supported_targets(self) -> list[str]:
        """Get list of supported target types for this provider.

        Returns:
            List of target type names
        """
        pass

    def get_actor_info(self) -> dict[str, Any]:
        """Return information about the currently authenticated actor/user.

        Default implementation returns a minimal structure based on the
        provider kind and, when available, the authentication token info.
        Provider implementations are encouraged to override this method
        to return richer identity data (usernames, emails, account IDs,
        etc.) where the underlying API supports it.

        Returns:
            Dictionary containing at least:
                - provider: Provider kind string (e.g. ``\"aws\"``, ``\"github\"``)
                - provider_name: Configured provider instance name
            Additional keys may be included by subclasses.
        """
        info: dict[str, Any] = {
            "provider": self.provider_kind,
            "provider_name": getattr(self, "name", None),
        }

        if self.auth is not None:
            try:
                token_info = self.auth.get_token_info()
            except NotImplementedError:
                token_info = None
            except Exception:
                token_info = None

            if isinstance(token_info, dict):
                # Do not overwrite core keys unless explicitly provided
                for key, value in token_info.items():
                    if key not in info:
                        info[key] = value

        return info

    @classmethod
    def get_capabilities(cls) -> ProviderCapabilities:
        """Declare all capabilities this provider offers.

        Default implementation uses introspection to find methods starting with
        'generate_', 'retrieve_', 'store_', 'rotate_', or 'delete_'.

        Override this method for custom capability declarations.

        Returns:
            ProviderCapabilities describing all methods and their signatures
        """
        capabilities = []

        # Find all methods with capability prefixes
        capability_prefixes = {
            "generate": CapabilityType.GENERATE,
            "retrieve": CapabilityType.RETRIEVE,
            "store": CapabilityType.STORE,
            "rotate": CapabilityType.ROTATE,
            "delete": CapabilityType.DELETE,
        }

        for method_name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            if method_name.startswith("_"):
                continue  # Skip private methods

            # Check if method matches a capability prefix
            capability_type = None
            for prefix, cap_type in capability_prefixes.items():
                if method_name.startswith(f"{prefix}_"):
                    capability_type = cap_type
                    break

            if capability_type is None:
                continue  # Not a capability method

            try:
                sig = inspect.signature(method)
                type_hints = get_type_hints(method)

                # Build parameter schema
                params = {}
                for param_name, param in sig.parameters.items():
                    if param_name in ("self", "cls"):
                        continue

                    param_type = type_hints.get(param_name, Any)
                    param_type_str = str(param_type).replace("typing.", "")

                    params[param_name] = ParameterSchema(
                        type=param_type_str,
                        required=param.default == inspect.Parameter.empty,
                        default=None if param.default == inspect.Parameter.empty else param.default,
                        description=f"Parameter {param_name}",
                    )

                return_type = type_hints.get("return", Any)
                return_type_str = str(return_type).replace("typing.", "")

                method_sig = MethodSignature(
                    name=method_name,
                    description=method.__doc__ or f"{capability_type.value.capitalize()} operation",
                    return_type=return_type_str,
                    parameters=params,
                )

                capabilities.append(
                    Capability(
                        capability_type=capability_type,
                        method=method_sig,
                        requires_auth=True,
                        supported_targets=[],  # Empty means all targets
                    )
                )
            except Exception:
                # Skip methods that fail introspection
                continue

        # Get provider kind from instance property or class name
        # Try to instantiate temporarily to get provider_kind (if it doesn't require args)
        provider_kind = cls.__name__.lower().replace("provider", "").strip()
        try:
            # Try to get from a dummy instance (if class can be instantiated without args)
            # This is just for introspection, not for actual use
            pass  # Use class name for now since providers need auth/config
        except Exception:
            pass

        return ProviderCapabilities(
            provider_kind=provider_kind, version="1.0", capabilities=capabilities
        )

    def list_available_methods(self) -> list[str]:
        """List all callable capability methods on this provider instance.

        Returns:
            List of method names available after authentication
        """
        methods = []
        capability_prefixes = ["generate_", "retrieve_", "store_", "rotate_", "delete_"]

        for method_name in dir(self):
            if method_name.startswith("_"):
                continue
            method = getattr(self, method_name, None)
            if callable(method):
                if any(method_name.startswith(prefix) for prefix in capability_prefixes):
                    methods.append(method_name)

        return methods

    def get_method_schema(self, method_name: str) -> MethodSignature:
        """Get schema for a specific method.

        Args:
            method_name: Name of method to inspect

        Returns:
            MethodSignature with parameter and return types

        Raises:
            ValueError: If method not found
        """
        capabilities = self.get_capabilities()
        capability = capabilities.get_capability(method_name)

        if capability is None:
            raise ValueError(f"Method '{method_name}' not found in {self.provider_kind} provider")

        return capability.method

    def get_token_info(self) -> dict[str, Any]:
        """Return information about the current authentication token.

        Delegates to the underlying :class:`ProviderAuth` instance. Providers
        whose auth class implements ``get_token_info`` will return meaningful
        data; others will raise :class:`NotImplementedError`.

        Returns:
            Dictionary with token details (see :meth:`ProviderAuth.get_token_info`).

        Raises:
            RuntimeError: If no authentication is configured.
            NotImplementedError: If the auth class does not support introspection.
        """
        if not self.auth:
            raise RuntimeError("No authentication configured")
        return self.auth.get_token_info()

    @classmethod
    def get_scope_descriptions(cls) -> dict[str, str]:
        """Return scope/permission descriptions for this provider's auth layer.

        Returns:
            Mapping of scope name to human-readable description.
        """
        return {}
