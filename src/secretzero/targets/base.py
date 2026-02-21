"""Base target class for secret storage."""

from abc import ABC, abstractmethod
from typing import Any


class BaseTarget(ABC):
    """Abstract base class for secret storage targets."""

    def __init__(
        self,
        provider: Any | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        """Initialize target with configuration.

        Args:
            provider: Optional provider instance for targets that need credentials
            config: Target configuration dictionary
        """
        # Handle backward compatibility: if provider is a dict and config is None,
        # assume old calling convention where only config was passed
        if isinstance(provider, dict) and config is None:
            self.provider = None
            self.config = provider
        else:
            self.provider = provider
            self.config = config or {}

    @abstractmethod
    def store(self, secret_name: str, secret_value: str) -> bool:
        """Store a secret value in the target.

        Args:
            secret_name: Name/key of the secret
            secret_value: Value to store

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def retrieve(self, secret_name: str) -> str | None:
        """Retrieve a secret value from the target.

        Args:
            secret_name: Name/key of the secret

        Returns:
            Secret value if found, None otherwise
        """
        pass
