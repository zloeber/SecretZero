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
try:
    from secretzero.providers.ansible_vault import AnsibleVaultProvider
    from secretzero.providers.aws import AWSProvider
    from secretzero.providers.azure import AzureProvider
    from secretzero.providers.github import GitHubProvider
    from secretzero.providers.gitlab import GitLabProvider
    from secretzero.providers.infisical import InfisicalProvider
    from secretzero.providers.jenkins import JenkinsProvider
    from secretzero.providers.kubernetes import KubernetesProvider
    from secretzero.providers.vault import VaultProvider

    _global_registry.register_provider_class("ansible_vault", AnsibleVaultProvider)
    _global_registry.register_provider_class("aws", AWSProvider)
    _global_registry.register_provider_class("azure", AzureProvider)
    _global_registry.register_provider_class("github", GitHubProvider)
    _global_registry.register_provider_class("gitlab", GitLabProvider)
    _global_registry.register_provider_class("infisical", InfisicalProvider)
    _global_registry.register_provider_class("jenkins", JenkinsProvider)
    _global_registry.register_provider_class("kubernetes", KubernetesProvider)
    _global_registry.register_provider_class("vault", VaultProvider)
except (ImportError, ValueError):
    # Allow graceful degradation if imports fail
    pass


# Export for convenience (optional)
GLOBAL_PROVIDER_REGISTRY = _global_registry
