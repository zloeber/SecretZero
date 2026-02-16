"""Base classes for provider implementations."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class ProviderAuth(ABC):
    """Base class for provider authentication."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
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


class BaseProvider(ABC):
    """Base class for all providers."""

    def __init__(
        self,
        name: str,
        config: Optional[Dict[str, Any]] = None,
        auth: Optional[ProviderAuth] = None,
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

    @abstractmethod
    def test_connection(self) -> tuple[bool, Optional[str]]:
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
