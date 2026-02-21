"""Configuration loading and variable interpolation."""

import re
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, StrictUndefined

from secretzero.models import Secretfile


class ConfigLoader:
    """Load and validate Secretfile configuration with variable interpolation."""

    def __init__(self) -> None:
        """Initialize the config loader."""
        self.jinja_env = Environment(undefined=StrictUndefined)

    def load_file(self, path: Path) -> Secretfile:
        """Load and parse a Secretfile.yml.

        Args:
            path: Path to the Secretfile.yml

        Returns:
            Parsed and validated Secretfile model

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file is invalid
        """
        if not path.exists():
            raise FileNotFoundError(f"Secretfile not found: {path}")

        with open(path) as f:
            raw_data = yaml.safe_load(f)

        if not raw_data:
            raise ValueError("Empty Secretfile")

        # Apply variable interpolation
        variables = raw_data.get("variables", {})
        interpolated_data = self._interpolate_variables(raw_data, variables)

        # Validate with Pydantic model
        return Secretfile(**interpolated_data)

    def _interpolate_variables(self, data: Any, variables: dict[str, Any]) -> Any:
        """Recursively interpolate variables in the configuration.

        Supports Jinja2-style variable interpolation: {{var.name}}

        Args:
            data: The data structure to interpolate
            variables: Dictionary of variables to use for interpolation

        Returns:
            Data with interpolated variables
        """
        if isinstance(data, dict):
            return {
                key: self._interpolate_variables(value, variables) for key, value in data.items()
            }
        elif isinstance(data, list):
            return [self._interpolate_variables(item, variables) for item in data]
        elif isinstance(data, str):
            return self._interpolate_string(data, variables)
        return data

    def _interpolate_string(self, text: str, variables: dict[str, Any]) -> str:
        """Interpolate variables in a string.

        Supports two syntax styles:
        - Jinja2 style: {{var.name}} or {{var['name']}}
        - Shell style: ${VAR_NAME}

        Args:
            text: String that may contain variable references
            variables: Dictionary of variables

        Returns:
            String with variables interpolated
        """
        if not isinstance(text, str):
            return text

        # First, handle shell-style variables: ${VAR_NAME}
        def replace_shell_var(match: Any) -> str:
            var_name = match.group(1)
            return str(variables.get(var_name, match.group(0)))

        text = re.sub(r"\$\{([^}]+)\}", replace_shell_var, text)

        # Then, handle Jinja2-style variables: {{var.name}}
        if "{{" not in text:
            return text

        try:
            # Create Jinja2 template with undefined handler that returns None
            from jinja2 import Undefined

            class SilentUndefined(Undefined):
                def __bool__(self) -> bool:
                    return False

                def __str__(self) -> str:
                    return ""

            env = Environment(undefined=SilentUndefined)
            template = env.from_string(text)
            context = {"var": variables}
            return template.render(context)
        except Exception:
            # If interpolation fails, return original string
            # This allows for graceful degradation
            return text

    def validate_file(self, path: Path) -> tuple[bool, str]:
        """Validate a Secretfile without loading it fully.

        Args:
            path: Path to the Secretfile.yml

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            self.load_file(path)
            return True, "Valid Secretfile"
        except FileNotFoundError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Validation error: {str(e)}"
