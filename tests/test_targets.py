"""Tests for secret storage targets."""

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from secretzero.targets import FileTarget


class TestFileTarget:
    """Test file-based target."""

    def test_dotenv_format(self):
        """Test dotenv format storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "path": str(Path(tmpdir) / ".env"),
                "format": "dotenv",
                "merge": False,
            }
            target = FileTarget(config)

            # Store secret
            success = target.store("MY_SECRET", "secret_value_123")
            assert success

            # Retrieve secret
            value = target.retrieve("MY_SECRET")
            assert value == "secret_value_123"

    def test_dotenv_config_key_override_preserves_casing(self):
        """config.key is the file/env key; manifest secret name may differ in casing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            config = {
                "path": str(env_path),
                "format": "dotenv",
                "merge": False,
                "key": "PYPI_PROD_API_TOKEN",
            }
            target = FileTarget(config)
            assert target.store("pypi_prod_api_token", "pypi-token-value")

            text = env_path.read_text()
            assert "PYPI_PROD_API_TOKEN=" in text
            assert "pypi_prod_api_token=" not in text

            assert target.retrieve("pypi_prod_api_token") == "pypi-token-value"

    def test_dotenv_with_quotes(self):
        """Test dotenv format with quoted values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "path": str(Path(tmpdir) / ".env"),
                "format": "dotenv",
            }
            target = FileTarget(config)

            # Store secret with spaces
            target.store("MY_SECRET", "value with spaces")

            # Read and verify
            content = Path(config["path"]).read_text()
            assert 'MY_SECRET="value with spaces"' in content

    def test_json_format(self):
        """Test JSON format storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "path": str(Path(tmpdir) / "secrets.json"),
                "format": "json",
            }
            target = FileTarget(config)

            # Store secret
            target.store("api_key", "abc123")

            # Retrieve secret
            value = target.retrieve("api_key")
            assert value == "abc123"

            # Verify JSON structure
            data = json.loads(Path(config["path"]).read_text())
            assert data["api_key"] == "abc123"

    def test_yaml_format(self):
        """Test YAML format storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "path": str(Path(tmpdir) / "secrets.yml"),
                "format": "yaml",
            }
            target = FileTarget(config)

            # Store secret
            target.store("db_password", "password123")

            # Retrieve secret
            value = target.retrieve("db_password")
            assert value == "password123"

            # Verify YAML structure
            data = yaml.safe_load(Path(config["path"]).read_text())
            assert data["db_password"] == "password123"

    def test_merge_existing_file(self):
        """Test merging with existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / ".env"

            # Create existing file
            file_path.write_text("EXISTING_VAR=existing_value\n")

            config = {
                "path": str(file_path),
                "format": "dotenv",
                "merge": True,
            }
            target = FileTarget(config)

            # Store new secret
            target.store("NEW_SECRET", "new_value")

            # Both should exist
            assert target.retrieve("EXISTING_VAR") == "existing_value"
            assert target.retrieve("NEW_SECRET") == "new_value"

    def test_overwrite_existing_file(self):
        """Test overwriting existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / ".env"

            # Create existing file
            file_path.write_text("EXISTING_VAR=existing_value\n")

            config = {
                "path": str(file_path),
                "format": "dotenv",
                "merge": False,
            }
            target = FileTarget(config)

            # Store new secret (should overwrite)
            target.store("NEW_SECRET", "new_value")

            # Only new secret should exist
            assert target.retrieve("EXISTING_VAR") is None
            assert target.retrieve("NEW_SECRET") == "new_value"

    def test_update_existing_secret(self):
        """Test updating an existing secret."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "path": str(Path(tmpdir) / "secrets.json"),
                "format": "json",
            }
            target = FileTarget(config)

            # Store initial value
            target.store("api_key", "old_value")
            assert target.retrieve("api_key") == "old_value"

            # Update value
            target.store("api_key", "new_value")
            assert target.retrieve("api_key") == "new_value"

    def test_retrieve_nonexistent_file(self):
        """Test retrieving from non-existent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "path": str(Path(tmpdir) / "nonexistent.env"),
                "format": "dotenv",
            }
            target = FileTarget(config)

            value = target.retrieve("MY_SECRET")
            assert value is None

    def test_retrieve_nonexistent_secret(self):
        """Test retrieving non-existent secret."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "path": str(Path(tmpdir) / ".env"),
                "format": "dotenv",
            }
            target = FileTarget(config)

            target.store("SECRET1", "value1")
            value = target.retrieve("NONEXISTENT")
            assert value is None

    def test_create_parent_directories(self):
        """Test that parent directories are created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "path": str(Path(tmpdir) / "subdir" / "secrets" / ".env"),
                "format": "dotenv",
            }
            target = FileTarget(config)

            # Should not raise error
            target.store("MY_SECRET", "value")

            # Verify file exists
            assert Path(config["path"]).exists()

    def test_dotenv_parse_comments(self):
        """Test parsing dotenv with comments."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / ".env"
            file_path.write_text("""
# Comment line
SECRET1=value1
# Another comment
SECRET2=value2
""")

            config = {
                "path": str(file_path),
                "format": "dotenv",
            }
            target = FileTarget(config)

            assert target.retrieve("SECRET1") == "value1"
            assert target.retrieve("SECRET2") == "value2"

    def test_multiple_secrets_json(self):
        """Test storing multiple secrets in JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "path": str(Path(tmpdir) / "secrets.json"),
                "format": "json",
            }
            target = FileTarget(config)

            # Store multiple secrets
            target.store("secret1", "value1")
            target.store("secret2", "value2")
            target.store("secret3", "value3")

            # Retrieve all
            assert target.retrieve("secret1") == "value1"
            assert target.retrieve("secret2") == "value2"
            assert target.retrieve("secret3") == "value3"
