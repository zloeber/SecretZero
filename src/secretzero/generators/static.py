"""Static value generator with validation."""

import re
from typing import Any

from secretzero.generators.base import BaseGenerator


def static_payload_needs_prompt(value: Any, *, nested: bool = False) -> bool:
    """Return True if a static ``value`` / ``default`` still needs interactive input.

    Top-level empty string is treated as an intentional value (no prompt). Empty
    strings inside dict/list values are treated as missing (prompt), matching
    :class:`StaticGenerator` dict handling.
    """
    if isinstance(value, dict):
        return any(static_payload_needs_prompt(v, nested=True) for v in value.values())
    if isinstance(value, list):
        return any(static_payload_needs_prompt(v, nested=True) for v in value)
    if value is None:
        return True
    if isinstance(value, str):
        if re.match(r"^\$\{[^}]+\}$", value):
            return True
        if not value.strip():
            return nested
        return False
    return False


class StaticGenerator(BaseGenerator):
    """Generate static values with optional validation."""

    PROMPTS_LIKE_STATIC = True

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

    def generate(self) -> Any:
        """Generate (return) the static value.

        If ``value`` is a dict, each scalar leaf that is missing, blank, or an
        unresolved ``${VAR}`` placeholder is filled interactively when
        ``prompt_on_empty`` is enabled. Top-level scalar behavior is unchanged
        (a top-level empty string is still a deliberate value and does not prompt).

        Returns:
            The static value (str, dict, or other scalar preserved in dict leaves)

        Raises:
            ValueError: If validation fails or value is required but not provided
        """
        value = self.default_value

        if isinstance(value, dict):
            result, _ = self._generate_dict_value(value)
            return result

        # Check if value is None or looks like an unresolved env var
        # Note: Empty string "" is a valid value and should not be considered "not provided"
        is_not_provided = value is None
        is_unresolved = isinstance(value, str) and bool(re.match(r"^\$\{[^}]+\}$", value))

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
                        ) from e
                    else:
                        raise ValueError(
                            f"Static value is required but not provided. Error: {e}"
                        ) from e
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

        # Validate if pattern is defined (scalar strings only)
        if self.validation_pattern and isinstance(value, str) and value:
            if not re.match(self.validation_pattern, value):
                raise ValueError(
                    f"Value '{value}' does not match validation pattern '{self.validation_pattern}'"
                )

        return value

    def _generate_dict_value(
        self, data: dict[str, Any], show_instructions: bool = True
    ) -> tuple[dict[str, Any], bool]:
        out: dict[str, Any] = {}
        for key in sorted(data.keys()):
            raw = data[key]
            if isinstance(raw, dict):
                nested, show_instructions = self._generate_dict_value(raw, show_instructions)
                out[key] = nested
            elif isinstance(raw, list):
                raise ValueError(
                    "Static generator dict values do not support list entries; "
                    "use only scalars or nested dicts."
                )
            else:
                out[key], show_instructions = self._resolve_dict_leaf(
                    raw, field_key=key, show_instructions=show_instructions
                )
        return out, show_instructions

    def _dict_leaf_needs_prompt(self, value: Any) -> bool:
        return static_payload_needs_prompt(value, nested=True)

    def _resolve_dict_leaf(
        self, value: Any, field_key: str, show_instructions: bool
    ) -> tuple[Any, bool]:
        if not self._dict_leaf_needs_prompt(value):
            return value, show_instructions

        if not self.prompt_on_empty:
            if isinstance(value, str) and re.match(r"^\$\{[^}]+\}$", value):
                raise ValueError(
                    f"Static dict field '{field_key}' contains unresolved environment variable: {value}. "
                    "Set the environment variable or run without --no-prompt flag."
                )
            raise ValueError(
                f"Static dict field '{field_key}' is required but not provided. "
                "Set a value or run without --no-prompt flag."
            )

        base = self.field_description or "Secret"
        label = f"{base} — {field_key}"
        try:
            resolved = self._prompt_for_value(
                prompt_label=label,
                show_instructions=show_instructions,
                apply_validation=False,
            )
        except (ValueError, EOFError) as e:
            raise ValueError(
                f"Static dict field '{field_key}' is required but not provided. Error: {e}"
            ) from e
        return resolved, False

    def _prompt_for_value(
        self,
        *,
        prompt_label: str | None = None,
        show_instructions: bool = True,
        apply_validation: bool = True,
    ) -> str:
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
        if show_instructions:
            instructions = self.get_manual_instructions()
            if instructions:
                self._display_manual_instructions(instructions)

        label = prompt_label if prompt_label is not None else self.field_description
        prompt = "Enter value: "
        if label:
            prompt = f"Enter value for {label}: "

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

                if apply_validation and self.validation_pattern:
                    if not re.match(self.validation_pattern, value):
                        print(f"Value does not match required pattern: {self.validation_pattern}")
                        continue

                return value
            except EOFError:
                raise ValueError("Unable to read input (EOFError)") from None

        raise ValueError(f"Failed to get valid input after {max_retries} attempts")
