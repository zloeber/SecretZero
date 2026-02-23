"""Jinja2 template target for secret rendering."""

from pathlib import Path
from typing import Any

from secretzero.targets.base import BaseTarget


class TemplateTarget(BaseTarget):
    """Render Jinja2 templates with secret values."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize template target.

        Args:
            config: Configuration with options:
                - template_path: Path to the Jinja2 template file to render
                - output_path: Path to write the rendered template
                - overwrite: Whether to overwrite existing output file (default: True)

        Raises:
            ValueError: If required config options are missing
        """
        super().__init__(config)

        template_path = config.get("template_path")
        output_path = config.get("output_path")

        if not template_path:
            raise ValueError("Template target requires 'template_path' in config")
        if not output_path:
            raise ValueError("Template target requires 'output_path' in config")

        self.template_path = Path(template_path)
        self.output_path = Path(output_path)
        self.overwrite = config.get("overwrite", True)

    def store(self, secret_name: str, secret_value: str) -> bool:
        """Store secret in a rendered template context.

        This method doesn't directly store like FileTarget does. Instead,
        secrets are accumulated in memory and rendered together when all
        secrets for a template are collected.

        Args:
            secret_name: Name/key of the secret
            secret_value: Value of the secret

        Returns:
            True (secrets are stored in context for later rendering)
        """
        # Note: Actual rendering happens in render() method which is called
        # after all secrets are collected. This method returns True to
        # indicate the secret was accepted for the template context.
        return True

    def retrieve(self, secret_name: str) -> str | None:
        """Retrieve a secret from the rendered template output.

        Args:
            secret_name: Name/key of the secret

        Returns:
            None (templates don't retrieve existing secrets)
        """
        return None

    def render(self, secrets: dict[str, str]) -> bool:
        """Render the Jinja2 template with secrets and write output.

        Args:
            secrets: Dictionary of all secrets to use in template context

        Returns:
            True if rendering successful

        Raises:
            ValueError: If template file doesn't exist
            RuntimeError: If rendering fails
        """
        try:
            from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape
        except ImportError:
            raise RuntimeError(
                "Jinja2 is required for template targets. Install with: pip install jinja2"
            )

        if not self.template_path.exists():
            raise ValueError(f"Template file not found: {self.template_path}")

        try:
            # Create Jinja2 environment
            template_dir = self.template_path.parent.absolute()
            template_filename = self.template_path.name

            env = Environment(
                loader=FileSystemLoader(str(template_dir)),
                keep_trailing_newline=True,
                autoescape=select_autoescape(default=False),
            )

            # Load and render template
            template = env.get_template(template_filename)
            rendered_content = template.render(secrets=secrets, **secrets)

            # Create output directory if needed
            self.output_path.parent.mkdir(parents=True, exist_ok=True)

            # Write rendered output
            with open(self.output_path, "w", encoding="utf-8") as f:
                f.write(rendered_content)

            return True

        except TemplateNotFound as e:
            raise ValueError(f"Template not found: {e}")
        except Exception as e:
            raise RuntimeError(f"Template rendering failed: {e}")
