"""Provider registry for managing provider instances."""


from secretzero.providers.base import BaseProvider


class ProviderRegistry:
    """Registry for managing provider instances."""

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
        """
        self._provider_classes[provider_type] = provider_class

    def create_provider(
        self, provider_type: str, name: str, config: dict
    ) -> BaseProvider | None:
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
            List of provider type names
        """
        return list(self._provider_classes.keys())


# Global registry instance
_registry = ProviderRegistry()


def get_registry() -> ProviderRegistry:
    """Get the global provider registry.

    Returns:
        Global ProviderRegistry instance
    """
    return _registry
