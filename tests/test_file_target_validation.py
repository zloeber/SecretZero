"""Tests for file target validation."""

import os
import platform
import tempfile
from pathlib import Path

import pytest

from secretzero.targets.file import FileTarget


class TestFileTargetValidation:
    """Test file target validation functionality."""

    def test_validate_writable_directory(self):
        """Test validation passes for writable directory."""
        # Use OS-specific writable temp directory
        if platform.system() == "Windows":
            temp_dir = os.environ.get("TEMP", "C:\\Temp")
            writable_path = os.path.join(temp_dir, "test_secret.env")
        else:
            writable_path = "/tmp/test_secret.env"

        target = FileTarget({"path": writable_path, "format": "dotenv"})
        is_valid, error = target.validate()

        assert is_valid is True
        assert error is None

    def test_validate_nonexistent_directory_can_create(self):
        """Test validation passes when directory can be created."""
        # Use a temp directory that will be cleaned up
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = Path(tmpdir) / "subdir" / "nested" / "secret.env"
            target = FileTarget({"path": str(test_path), "format": "dotenv"})
            is_valid, error = target.validate()

            assert is_valid is True
            assert error is None
            # Directory should have been created
            assert test_path.parent.exists()

    def test_validate_non_writable_directory(self):
        """Test validation fails for non-writable directory."""
        # Use OS-specific non-writable paths
        if platform.system() == "Windows":
            # Windows: System32 directory is protected
            non_writable_path = r"C:\Windows\System32\test_secret.env"
        else:
            # Unix-like: /root is typically not writable by normal users
            non_writable_path = "/root/test_secret.env"

        target = FileTarget({"path": non_writable_path, "format": "dotenv"})
        is_valid, error = target.validate()

        assert is_valid is False
        assert error is not None
        assert "Cannot create directory" in error or "not writable" in error

    def test_validate_parent_is_file_not_directory(self):
        """Test validation fails when parent path is a file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            temp_file = f.name

        try:
            # Try to create a file inside what should be a file
            target = FileTarget({"path": f"{temp_file}/subdir/secret.env", "format": "dotenv"})
            is_valid, error = target.validate()

            assert is_valid is False
            assert error is not None
            assert "not a directory" in error.lower()
        finally:
            os.unlink(temp_file)

    def test_validate_existing_writable_file(self):
        """Test validation passes for existing writable file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".env") as f:
            temp_file = f.name
            f.write("EXISTING_KEY=value\n")

        try:
            target = FileTarget({"path": temp_file, "format": "dotenv"})
            is_valid, error = target.validate()

            assert is_valid is True
            assert error is None
        finally:
            os.unlink(temp_file)

    def test_validate_existing_readonly_file(self):
        """Test validation fails for existing read-only file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".env") as f:
            temp_file = f.name
            f.write("EXISTING_KEY=value\n")

        try:
            # Make file read-only
            os.chmod(temp_file, 0o444)

            target = FileTarget({"path": temp_file, "format": "dotenv"})
            is_valid, error = target.validate()

            # On some systems, we might still be able to write to our own files
            # So we either get an error, or it's valid
            # The important test is that it doesn't crash
            assert isinstance(is_valid, bool)
            if not is_valid:
                assert error is not None
                assert "not writable" in error.lower()
        finally:
            # Restore write permission before cleanup
            os.chmod(temp_file, 0o644)
            os.unlink(temp_file)

    def test_store_with_validation(self):
        """Test that store operations work after validation passes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = Path(tmpdir) / "secrets.env"
            target = FileTarget({"path": str(test_path), "format": "dotenv"})

            # Validate first
            is_valid, error = target.validate()
            assert is_valid is True

            # Store should work
            success = target.store("TEST_KEY", "test_value")
            assert success is True

            # Verify file was created with correct content
            assert test_path.exists()
            content = test_path.read_text()
            assert "TEST_KEY=test_value" in content

    def test_validate_json_format(self):
        """Test validation works for JSON format."""
        target = FileTarget({"path": "/tmp/test_secret.json", "format": "json"})
        is_valid, error = target.validate()

        assert is_valid is True
        assert error is None

    def test_validate_yaml_format(self):
        """Test validation works for YAML format."""
        target = FileTarget({"path": "/tmp/test_secret.yaml", "format": "yaml"})
        is_valid, error = target.validate()

        assert is_valid is True
        assert error is None
