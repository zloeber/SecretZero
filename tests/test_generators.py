"""Tests for secret generators."""

import os
import tempfile
from pathlib import Path

import pytest

from secretzero.generators import (
    RandomPasswordGenerator,
    RandomStringGenerator,
    ScriptGenerator,
    StaticGenerator,
)


class TestRandomPasswordGenerator:
    """Test random password generator."""

    def test_basic_generation(self):
        """Test basic password generation."""
        gen = RandomPasswordGenerator({"length": 16})
        password = gen.generate()

        assert len(password) == 16
        assert password  # Not empty

    def test_custom_length(self):
        """Test custom password length."""
        gen = RandomPasswordGenerator({"length": 32})
        password = gen.generate()

        assert len(password) == 32

    def test_character_types(self):
        """Test character type configuration."""
        gen = RandomPasswordGenerator({
            "length": 100,
            "upper": True,
            "lower": True,
            "number": True,
            "special": True,
        })
        password = gen.generate()

        # With 100 chars, we should see all types
        assert any(c.isupper() for c in password)
        assert any(c.islower() for c in password)
        assert any(c.isdigit() for c in password)
        assert any(not c.isalnum() for c in password)

    def test_exclude_characters(self):
        """Test excluding specific characters."""
        gen = RandomPasswordGenerator({
            "length": 100,
            "exclude_characters": '"@/\\`',
        })
        password = gen.generate()

        for char in '"@/\\`':
            assert char not in password

    def test_no_character_types(self):
        """Test error when no character types enabled."""
        gen = RandomPasswordGenerator({
            "upper": False,
            "lower": False,
            "number": False,
            "special": False,
        })

        with pytest.raises(ValueError, match="At least one character type"):
            gen.generate()

    def test_environment_fallback(self):
        """Test environment variable fallback."""
        os.environ["TEST_PASSWORD"] = "env_password_123"

        gen = RandomPasswordGenerator({"length": 16})
        password = gen.generate_with_fallback("TEST_PASSWORD")

        assert password == "env_password_123"

        # Clean up
        del os.environ["TEST_PASSWORD"]


class TestRandomStringGenerator:
    """Test random string generator."""

    def test_basic_generation(self):
        """Test basic string generation."""
        gen = RandomStringGenerator({"length": 16})
        string = gen.generate()

        assert len(string) == 16
        assert string.isalnum()

    def test_alphanumeric(self):
        """Test alphanumeric charset."""
        gen = RandomStringGenerator({"length": 100, "charset": "alphanumeric"})
        string = gen.generate()

        assert string.isalnum()

    def test_alpha_only(self):
        """Test alpha-only charset."""
        gen = RandomStringGenerator({"length": 100, "charset": "alpha"})
        string = gen.generate()

        assert string.isalpha()

    def test_numeric_only(self):
        """Test numeric-only charset."""
        gen = RandomStringGenerator({"length": 100, "charset": "numeric"})
        string = gen.generate()

        assert string.isdigit()

    def test_hex(self):
        """Test hexadecimal charset."""
        gen = RandomStringGenerator({"length": 100, "charset": "hex"})
        string = gen.generate()

        assert all(c in "0123456789abcdef" for c in string)


class TestStaticGenerator:
    """Test static value generator."""

    def test_basic_generation(self):
        """Test basic static value."""
        gen = StaticGenerator({"default": "my_secret_value"})
        value = gen.generate()

        assert value == "my_secret_value"

    def test_validation_success(self):
        """Test successful validation."""
        gen = StaticGenerator({
            "default": "ABC123",
            "validation": r"^[A-Z0-9]+$",
        })
        value = gen.generate()

        assert value == "ABC123"

    def test_validation_failure(self):
        """Test validation failure."""
        gen = StaticGenerator({
            "default": "abc123",
            "validation": r"^[A-Z0-9]+$",
        })

        with pytest.raises(ValueError, match="does not match validation pattern"):
            gen.generate()

    def test_empty_default(self):
        """Test empty default value."""
        gen = StaticGenerator({})
        value = gen.generate()

        assert value == ""

    def test_environment_fallback(self):
        """Test environment variable fallback."""
        os.environ["TEST_STATIC"] = "env_value"

        gen = StaticGenerator({"default": "default_value"})
        value = gen.generate_with_fallback("TEST_STATIC")

        assert value == "env_value"

        # Clean up
        del os.environ["TEST_STATIC"]


class TestScriptGenerator:
    """Test script-based generator."""

    def test_basic_script(self):
        """Test basic script execution."""
        gen = ScriptGenerator({
            "command": "echo",
            "args": ["hello"],
        })
        value = gen.generate()

        assert value == "hello"

    def test_shell_command(self):
        """Test shell command execution."""
        gen = ScriptGenerator({
            "command": "echo 'shell test'",
            "shell": True,
        })
        value = gen.generate()

        assert value == "shell test"

    def test_script_with_output(self):
        """Test script that produces output."""
        # Create a temporary script
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write("#!/bin/bash\necho 'test_secret_123'")
            script_path = f.name

        os.chmod(script_path, 0o755)

        try:
            gen = ScriptGenerator({
                "command": script_path,
            })
            value = gen.generate()

            assert value == "test_secret_123"
        finally:
            os.unlink(script_path)

    def test_no_command(self):
        """Test error when command is missing."""
        gen = ScriptGenerator({})

        with pytest.raises(ValueError, match="Script command is required"):
            gen.generate()

    def test_script_failure(self):
        """Test script execution failure."""
        gen = ScriptGenerator({
            "command": "false",
        })

        with pytest.raises(RuntimeError, match="Script execution failed"):
            gen.generate()

    def test_script_timeout(self):
        """Test script timeout."""
        gen = ScriptGenerator({
            "command": "sleep",
            "args": ["10"],
            "timeout": 1,
        })

        with pytest.raises(RuntimeError, match="timed out"):
            gen.generate()
