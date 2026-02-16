"""Base generator class for secret generation."""

import os
from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseGenerator(ABC):
    """Abstract base class for secret generators."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize generator with configuration.

        Args:
            config: Generator configuration dictionary
        """
        self.config = config

    @abstractmethod
    def generate(self) -> str:
        """Generate a secret value.

        Returns:
            Generated secret value as a string
        """
        pass

    def generate_with_fallback(self, env_var_name: Optional[str] = None) -> str:
        """Generate a secret value with environment variable fallback.

        First checks for an environment variable, then falls back to generation.

        Args:
            env_var_name: Optional environment variable name to check first

        Returns:
            Secret value from environment or generated
        """
        if env_var_name:
            env_value = os.environ.get(env_var_name)
            if env_value:
                return env_value

        return self.generate()
