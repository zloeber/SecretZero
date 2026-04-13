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
                - key: Optional key/name used in the file (dotenv variable name, JSON key, etc.).
                  If set, overrides the manifest secret name for storage and retrieval so casing
                  and spelling can differ from ``Secret.name`` (e.g. ``PYPI_PROD_API_TOKEN``).
        """
        super().__init__(config)
        self.path = Path(config.get("path", ".env"))
        self.format = config.get("format", "dotenv")
        self.merge = config.get("merge", True)

    def _entry_key(self, secret_name: str) -> str:
        """Key used in the file: ``config.key`` when set, else the manifest secret name."""
        override = self.config.get("key")
        if override is not None and str(override).strip() != "":
            return str(override).strip()
        return secret_name

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

        # Update with new secret (optional config.key overrides manifest name for the on-disk key)
        entry_key = self._entry_key(secret_name)
        existing_data[entry_key] = secret_value

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
        entry_key = self._entry_key(secret_name)
        return data.get(entry_key)

    def validate(self) -> tuple[bool, str | None]:
        """Validate that the file path is writable.

        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Check if parent directory exists or can be created
            parent_dir = self.path.parent

            if not parent_dir.exists():
                # Try to check if we can create it
                try:
                    parent_dir.mkdir(parents=True, exist_ok=True)
                except (PermissionError, OSError) as e:
                    return False, f"Cannot create directory '{parent_dir}': {e}"

            # Check if parent directory is writable
            if not parent_dir.is_dir():
                return False, f"Path '{parent_dir}' exists but is not a directory"

            if not parent_dir.exists():
                return False, f"Directory '{parent_dir}' does not exist"

            # Test write permissions
            test_file = parent_dir / f".secretzero_write_test_{id(self)}"
            try:
                test_file.touch()
                test_file.unlink()
            except (PermissionError, OSError) as e:
                return False, f"Directory '{parent_dir}' is not writable: {e}"

            # If file exists, check if it's writable
            if self.path.exists():
                if not self.path.is_file():
                    return False, f"Path '{self.path}' exists but is not a file"
                if not self.path.stat().st_mode & 0o200:  # Check write permission
                    return False, f"File '{self.path}' exists but is not writable"

            return True, None

        except Exception as e:
            return False, f"Validation failed: {e}"

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
