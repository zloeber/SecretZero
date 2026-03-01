"""Provider registry for managing provider instances."""

from secretzero.providers.base import BaseProvider


class ProviderRegistry:
    """Registry for managing provider instances and provider classes."""

    def __init__(self):
        """Initialize the provider registry."""
        self._providers: dict[str, BaseProvider] = {}
        self._provider_classes: dict[str, type[BaseProvider]] = {}

    def register_provider_class(
        self, provider_type: str, provider_class: type[BaseProvider]
    ) -> None:
        """Register a provider class.

        Args:
            provider_type: Type identifier for the provider
            provider_class: Provider class to register

        Raises:
            ValueError: If provider_type is already registered
        """
        if provider_type in self._provider_classes:
            raise ValueError(f"Provider type '{provider_type}' is already registered")
        self._provider_classes[provider_type] = provider_class

    def get_provider_class(self, provider_type: str) -> type[BaseProvider] | None:
        """Get a provider class by type.

        Args:
            provider_type: Type identifier for the provider

        Returns:
            Provider class or None if not found
        """
        return self._provider_classes.get(provider_type)

    def create_provider(self, provider_type: str, name: str, config: dict) -> BaseProvider | None:
        """Create a provider instance.

        Args:
            provider_type: Type of provider to create
            name: Instance name for the provider
            config: Configuration for the provider

        Returns:
            Provider instance or None if type not registered
        """
        provider_class = self._provider_classes.get(provider_type)
        if not provider_class:
            return None

        provider = provider_class(name=name, config=config)
        self._providers[name] = provider
        return provider

    def get_provider(self, name: str) -> BaseProvider | None:
        """Get a provider instance by name.

        Args:
            name: Provider instance name

        Returns:
            Provider instance or None if not found
        """
        return self._providers.get(name)

    def list_providers(self) -> list[str]:
        """List all registered provider instances.

        Returns:
            List of provider instance names
        """
        return list(self._providers.keys())

    def list_provider_types(self) -> list[str]:
        """List all registered provider types.

        Returns:
            List of provider type names (classes)
        """
        return sorted(list(self._provider_classes.keys()))


def get_registry() -> ProviderRegistry:
    """Get the global provider registry.

    Returns:
        Global ProviderRegistry instance
    """
    return _global_registry


# Initialize and populate global registry with built-in providers
_global_registry = ProviderRegistry()

# Import providers after registry creation to avoid circular imports
# All providers are now registered via BundleManifests in the BundleRegistry.
# Sync them into this legacy ProviderRegistry so that code using
# GLOBAL_PROVIDER_REGISTRY / get_registry() still works.
try:
    from secretzero.bundles import get_bundle_registry as _get_bundle_registry

    _bundle_reg = _get_bundle_registry()
    for _kind in _bundle_reg.list_provider_kinds():
        _cls = _bundle_reg.get_provider_class(_kind)
        if _cls is not None and _kind not in _global_registry._provider_classes:
            try:
                _global_registry.register_provider_class(_kind, _cls)
            except ValueError:
                pass  # already registered
except Exception:
    pass


# Export for convenience (optional)
GLOBAL_PROVIDER_REGISTRY = _global_registry
