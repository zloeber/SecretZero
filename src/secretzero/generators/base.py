"""Base generator class for secret generation."""

import os
from abc import ABC, abstractmethod
from typing import Any


class BaseGenerator(ABC):
    """Abstract base class for secret generators."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize generator with configuration.

        Args:
            config: Generator configuration dictionary
        """
        self.config = config
        self.field_description = None
        self.hide_input = False

    @abstractmethod
    def generate(self) -> str:
        """Generate a secret value.

        Returns:
            Generated secret value as a string
        """
        pass

    def generate_with_fallback(
        self, env_var_name: str | None = None, field_description: str | None = None
    ) -> str:
        """Generate a secret value with environment variable fallback.

        First checks for an environment variable, then falls back to generation.

        Args:
            env_var_name: Optional environment variable name to check first
            field_description: Optional field description for context in prompts

        Returns:
            Secret value from environment or generated
        """
        if field_description:
            self.field_description = field_description

        if env_var_name:
            env_value = os.environ.get(env_var_name)
            if env_value:
                return env_value

        return self.generate()
