"""File-based target for local secret storage."""

import json
from pathlib import Path
from typing import Any

import yaml

from secretzero.targets.base import BaseTarget


class FileTarget(BaseTarget):
    """Store secrets in local files with various formats."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize file target.

        Args:
            config: Configuration with options:
                - path: File path to store secrets
                - format: File format (dotenv, json, yaml, toml)
                - merge: Whether to merge with existing content (default: True)
        """
        super().__init__(config)
        self.path = Path(config.get("path", ".env"))
        self.format = config.get("format", "dotenv")
        self.merge = config.get("merge", True)

    def store(self, secret_name: str, secret_value: str) -> bool:
        """Store a secret in the file.

        Args:
            secret_name: Name/key of the secret
            secret_value: Value to store

        Returns:
            True if successful

        Raises:
            ValueError: If format is unsupported
        """
        # Ensure parent directory exists
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # Read existing content if merging
        existing_data = {}
        if self.merge and self.path.exists():
            existing_data = self._read_file()

        # Update with new secret
        existing_data[secret_name] = secret_value

        # Write to file
        self._write_file(existing_data)

        return True

    def retrieve(self, secret_name: str) -> str | None:
        """Retrieve a secret from the file.

        Args:
            secret_name: Name/key of the secret

        Returns:
            Secret value if found, None otherwise
        """
        if not self.path.exists():
            return None

        data = self._read_file()
        return data.get(secret_name)

    def _read_file(self) -> dict[str, str]:
        """Read and parse file content.

        Returns:
            Dictionary of secret name/value pairs

        Raises:
            ValueError: If format is unsupported
        """
        content = self.path.read_text()

        if self.format == "dotenv":
            return self._parse_dotenv(content)
        elif self.format == "json":
            return json.loads(content) if content else {}
        elif self.format == "yaml":
            return yaml.safe_load(content) or {}
        elif self.format == "toml":
            try:
                import tomli

                return tomli.loads(content)
            except ImportError:
                raise ValueError("tomli package required for TOML support")
        else:
            raise ValueError(f"Unsupported format: {self.format}")

    def _write_file(self, data: dict[str, str]) -> None:
        """Write data to file.

        Args:
            data: Dictionary of secret name/value pairs

        Raises:
            ValueError: If format is unsupported
        """
        if self.format == "dotenv":
            content = self._format_dotenv(data)
        elif self.format == "json":
            content = json.dumps(data, indent=2)
        elif self.format == "yaml":
            content = yaml.dump(data, default_flow_style=False, sort_keys=False)
        elif self.format == "toml":
            try:
                import tomli_w

                content = tomli_w.dumps(data)
            except ImportError:
                raise ValueError("tomli-w package required for TOML support")
        else:
            raise ValueError(f"Unsupported format: {self.format}")

        self.path.write_text(content)

    def _parse_dotenv(self, content: str) -> dict[str, str]:
        """Parse dotenv format content.

        Args:
            content: File content to parse

        Returns:
            Dictionary of key/value pairs
        """
        result = {}
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Split on first = sign
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Remove quotes if present
                if value and value[0] in ('"', "'") and value[-1] == value[0]:
                    value = value[1:-1]

                result[key] = value

        return result

    def _format_dotenv(self, data: dict[str, str]) -> str:
        """Format data as dotenv content.

        Args:
            data: Dictionary of key/value pairs

        Returns:
            Formatted dotenv content
        """
        lines = []
        for key, value in data.items():
            # Quote values with spaces or special characters
            if " " in value or any(c in value for c in ['"', "'", "$", "\\", "\n"]):
                value = f'"{value}"'
            lines.append(f"{key}={value}")

        return "\n".join(lines) + "\n"
