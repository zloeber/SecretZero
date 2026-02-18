"""Static value generator with validation."""

import re
from typing import Any

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
        self.default_value = config.get("default")
        self.validation_pattern = config.get("validation")

    def generate(self) -> str:
        """Generate (return) the static value.

        If no default value is configured, prompts the user for input interactively.

        Returns:
            The static value

        Raises:
            ValueError: If validation fails
        """
        # If no default, prompt user for input
        if self.default_value is None:
            return self._prompt_for_value()

        value = self.default_value

        if self.validation_pattern and value:
            if not re.match(self.validation_pattern, value):
                raise ValueError(
                    f"Value '{value}' does not match validation pattern '{self.validation_pattern}'"
                )

        return value

    def _prompt_for_value(self) -> str:
        """Prompt user for a value interactively.

        Returns:
            User-provided value

        Raises:
            ValueError: If validation fails after retries
        """
        import getpass

        max_retries = 3

        # Show field description if available
        if self.field_description:
            print(f"\n{self.field_description}")

        for attempt in range(max_retries):
            try:
                # Use getpass if hide_input is enabled, otherwise use regular input
                if self.hide_input:
                    value = getpass.getpass("Enter value: ").strip()
                else:
                    value = input("Enter value: ").strip()

                if not value:
                    print("Value cannot be empty.")
                    continue

                # Validate if pattern is defined
                if self.validation_pattern:
                    if not re.match(self.validation_pattern, value):
                        print(f"Value does not match required pattern: {self.validation_pattern}")
                        continue

                return value
            except EOFError:
                raise ValueError("Unable to read input (EOFError)")

        raise ValueError(f"Failed to get valid input after {max_retries} attempts")
