"""Static value generator with validation."""

import re
from typing import Any, Optional

from secretzero.generators.base import BaseGenerator


class StaticGenerator(BaseGenerator):
    """Generate static values with optional validation."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize static generator.

        Args:
            config: Configuration with options:
                - default: Default value to use
                - validation: Optional regex pattern for validation
        """
        super().__init__(config)
        self.default_value = config.get("default", "")
        self.validation_pattern = config.get("validation")

    def generate(self) -> str:
        """Generate (return) the static value.

        Returns:
            The static value

        Raises:
            ValueError: If validation fails
        """
        value = self.default_value

        if self.validation_pattern and value:
            if not re.match(self.validation_pattern, value):
                raise ValueError(
                    f"Value '{value}' does not match validation pattern "
                    f"'{self.validation_pattern}'"
                )

        return value
