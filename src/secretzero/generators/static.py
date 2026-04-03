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
                - default: Default value to use (or 'value' for backwards compatibility)
                - validation: Optional regex pattern for validation
                - prompt_on_empty: Whether to prompt for value if empty (default: True)
        """
        super().__init__(config)
        # Support both 'default' and 'value' keys for backwards compatibility
        # Use 'default' if it exists (even if empty string), otherwise fall back to 'value'
        if "default" in config:
            self.default_value = config["default"]
        else:
            self.default_value = config.get("value")
        self.validation_pattern = config.get("validation")
        self.prompt_on_empty = config.get("prompt_on_empty", True)

    def generate(self) -> str:
        """Generate (return) the static value.

        If no default value is configured or value is unresolved (e.g., ${VAR}),
        prompts for manual input if prompting is enabled.

        Returns:
            The static value

        Raises:
            ValueError: If validation fails or value is required but not provided
        """
        value = self.default_value

        # Check if value is None or looks like an unresolved env var
        # Note: Empty string "" is a valid value and should not be considered "not provided"
        is_not_provided = value is None
        is_unresolved = isinstance(value, str) and re.match(r"^\$\{[^}]+\}$", value)

        if is_not_provided or is_unresolved:
            if self.prompt_on_empty:
                # Prompt user for value
                try:
                    value = self._prompt_for_value()
                except (ValueError, EOFError) as e:
                    if is_unresolved:
                        raise ValueError(
                            f"Static value contains unresolved environment variable: {value}. "
                            f"Set the environment variable or provide a value. Error: {e}"
                        )
                    else:
                        raise ValueError(f"Static value is required but not provided. Error: {e}")
            else:
                # Prompting disabled (CI mode)
                if is_unresolved:
                    raise ValueError(
                        f"Static value contains unresolved environment variable: {value}. "
                        "Set the environment variable or run without --no-prompt flag."
                    )
                else:
                    raise ValueError(
                        "Static value is required but not provided. "
                        "Set a value or run without --no-prompt flag."
                    )

        # Validate if pattern is defined
        if self.validation_pattern and value:
            if not re.match(self.validation_pattern, value):
                raise ValueError(
                    f"Value '{value}' does not match validation pattern '{self.validation_pattern}'"
                )

        return value

    def _prompt_for_value(self) -> str:
        """Prompt user for a value interactively.

        If manual instructions are available (from ``manual_instructions`` or
        ``get_manual_instructions()``), they are displayed before the prompt so
        the user knows where to find the secret value.

        Returns:
            User-provided value

        Raises:
            ValueError: If validation fails after retries
        """
        import getpass

        max_retries = 3

        # Display manual instructions before prompting, if available
        instructions = self.get_manual_instructions()
        if instructions:
            self._display_manual_instructions(instructions)

        # Build prompt with field description if available
        prompt = "Enter value: "
        if self.field_description:
            prompt = f"Enter value for {self.field_description}: "

        for attempt in range(max_retries):
            try:
                # Use getpass if hide_input is enabled, otherwise use regular input
                if self.hide_input:
                    value = getpass.getpass(prompt).strip()
                else:
                    value = input(prompt).strip()

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
