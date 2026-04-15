"""Configuration loading and variable interpolation."""

import re
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, StrictUndefined, select_autoescape

from secretzero.models import Secret, Secretfile


class ConfigLoader:
    """Load and validate Secretfile configuration with variable interpolation."""

    def __init__(self) -> None:
        """Initialize the config loader."""
        self.jinja_env = Environment(
            undefined=StrictUndefined,
            autoescape=select_autoescape(default=False, default_for_string=False),
        )

    def load_var_file(self, path: Path) -> dict[str, Any]:
        """Load a .szvar variable file.

        Args:
            path: Path to the .szvar file

        Returns:
            Dictionary of variables loaded from the file

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file is invalid YAML
        """
        if not path.exists():
            raise FileNotFoundError(f"Variable file not found: {path}")

        with open(path) as f:
            var_data = yaml.safe_load(f)

        if not isinstance(var_data, dict):
            raise ValueError(f"Variable file must contain a dictionary: {path}")

        return var_data

    def merge_variables(
        self, base_vars: dict[str, Any], override_vars: dict[str, Any]
    ) -> dict[str, Any]:
        """Deep merge variables with override taking precedence.

        Args:
            base_vars: Base variables dictionary
            override_vars: Override variables dictionary (takes precedence)

        Returns:
            Merged variables dictionary
        """
        result = base_vars.copy()

        for key, value in override_vars.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # Recursively merge nested dictionaries
                result[key] = self.merge_variables(result[key], value)
            else:
                # Override value
                result[key] = value

        return result

    def load_file(self, path: Path, var_files: list[Path] | None = None) -> Secretfile:
        """Load and parse a Secretfile.yml with optional variable files.

        Args:
            path: Path to the Secretfile.yml
            var_files: Optional list of .szvar files to merge with variables

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

        # Start with base variables from Secretfile
        variables = raw_data.get("variables", {})

        # Merge in variables from .szvar files (later files take precedence)
        if var_files:
            for var_file in var_files:
                override_vars = self.load_var_file(var_file)
                variables = self.merge_variables(variables, override_vars)

        # Apply variable interpolation
        interpolated_data = self._interpolate_variables(raw_data, variables)

        # Update the variables in the data to reflect merged values
        interpolated_data["variables"] = variables

        # Validate with Pydantic model
        secretfile = Secretfile(**interpolated_data)
        from secretzero.policy import validate_secretfile_policy_shapes

        validate_secretfile_policy_shapes(secretfile)
        return secretfile

    def _interpolate_variables(
        self,
        data: Any,
        variables: dict[str, Any],
        *,
        in_agent_instructions: bool = False,
    ) -> Any:
        """Recursively interpolate variables in the configuration.

        Supports Jinja2-style variable interpolation: {{var.name}}

        Strings under ``agent_instructions`` are left unchanged so per-secret templates
        (e.g. ``{{ secret_name }}``) can be rendered later by :meth:`AgentInstructions.render_for_secret`.

        Args:
            data: The data structure to interpolate
            variables: Dictionary of variables to use for interpolation

        Returns:
            Data with interpolated variables
        """
        if isinstance(data, dict):
            return {
                key: self._interpolate_variables(
                    value,
                    variables,
                    in_agent_instructions=in_agent_instructions or key == "agent_instructions",
                )
                for key, value in data.items()
            }
        elif isinstance(data, list):
            return [
                self._interpolate_variables(
                    item, variables, in_agent_instructions=in_agent_instructions
                )
                for item in data
            ]
        elif isinstance(data, str):
            if in_agent_instructions:
                return data
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

            env = Environment(
                undefined=SilentUndefined,
                autoescape=select_autoescape(default=False, default_for_string=False),
            )
            template = env.from_string(text)
            context = {"var": variables}
            return template.render(context)
        except Exception:
            # If interpolation fails, return original string
            # This allows for graceful degradation
            return text

    def validate_file(self, path: Path, var_files: list[Path] | None = None) -> tuple[bool, str]:
        """Validate a Secretfile without loading it fully.

        Args:
            path: Path to the Secretfile.yml
            var_files: Optional list of .szvar files to validate with

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            self.load_file(path, var_files=var_files)
            return True, "Valid Secretfile"
        except FileNotFoundError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Validation error: {str(e)}"


def _target_template_context(secret: Secret) -> dict[str, Any]:
    """Build a flat-ish dict for ``target`` in agent instruction templates."""
    if not secret.targets:
        return {}
    t0 = secret.targets[0]
    kind_val = getattr(t0.kind, "value", t0.kind)
    ctx: dict[str, Any] = {"provider": t0.provider, "kind": kind_val}
    ctx.update(t0.config)
    return ctx


def render_template_with_agent_context(
    text: str,
    *,
    variables: dict[str, Any],
    secret_name: str,
    secret: Secret,
) -> str:
    """Interpolate a string with Secretfile ``variables`` plus agent context.

    Supports shell-style ``${VAR}``, Jinja ``{{ var.name }}`` (same as :class:`ConfigLoader`),
    plus ``{{ secret_name }}`` and ``target`` (first secret target: kind, provider, config keys).
    """
    if not isinstance(text, str):
        return str(text)

    def replace_shell_var(match: Any) -> str:
        var_name = match.group(1)
        return str(variables.get(var_name, match.group(0)))

    out = re.sub(r"\$\{([^}]+)\}", replace_shell_var, text)

    if "{{" not in out:
        return out

    try:
        from jinja2 import Environment, Undefined, select_autoescape

        class SilentUndefined(Undefined):
            def __bool__(self) -> bool:
                return False

            def __str__(self) -> str:
                return ""

        env = Environment(
            undefined=SilentUndefined,
            autoescape=select_autoescape(default=False, default_for_string=False),
        )
        template = env.from_string(out)
        context = {
            "var": variables,
            "secret_name": secret_name,
            "target": _target_template_context(secret),
        }
        return template.render(context)
    except Exception:
        return out
