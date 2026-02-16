"""Tests for CLI commands."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from click.testing import CliRunner

from secretzero.cli import main


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI test runner."""
    return CliRunner()


def test_cli_version(runner: CliRunner) -> None:
    """Test CLI version command."""
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_cli_help(runner: CliRunner) -> None:
    """Test CLI help command."""
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "SecretZero" in result.output


def test_init_command(runner: CliRunner) -> None:
    """Test init command creates a Secretfile."""
    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Secretfile.yml"
        result = runner.invoke(main, ["init", "--output", str(output_path)])

        assert result.exit_code == 0
        assert output_path.exists()
        assert "Created Secretfile" in result.output


def test_init_existing_file(runner: CliRunner) -> None:
    """Test init command with existing file."""
    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Secretfile.yml"
        output_path.write_text("existing")

        result = runner.invoke(main, ["init", "--output", str(output_path)])
        assert result.exit_code != 0
        assert "already exists" in result.output


def test_validate_command(runner: CliRunner) -> None:
    """Test validate command."""
    with TemporaryDirectory() as tmpdir:
        secretfile = Path(tmpdir) / "Secretfile.yml"
        secretfile.write_text(
            """
version: '1.0'
variables: {}
providers: {}
secrets: []
templates: {}
"""
        )

        result = runner.invoke(main, ["validate", "--file", str(secretfile)])
        assert result.exit_code == 0
        assert "✓" in result.output


def test_validate_invalid_file(runner: CliRunner) -> None:
    """Test validate command with invalid file."""
    with TemporaryDirectory() as tmpdir:
        secretfile = Path(tmpdir) / "Secretfile.yml"
        secretfile.write_text("invalid: yaml\nno: version")

        result = runner.invoke(main, ["validate", "--file", str(secretfile)])
        assert result.exit_code != 0


def test_validate_nonexistent_file(runner: CliRunner) -> None:
    """Test validate command with non-existent file."""
    result = runner.invoke(main, ["validate", "--file", "nonexistent.yml"])
    assert result.exit_code != 0


def test_secret_types_list(runner: CliRunner) -> None:
    """Test secret-types command lists all types."""
    result = runner.invoke(main, ["secret-types"])
    assert result.exit_code == 0
    assert "random_password" in result.output
    assert "static" in result.output
    assert "file" in result.output


def test_secret_types_detail(runner: CliRunner) -> None:
    """Test secret-types command with type detail."""
    result = runner.invoke(main, ["secret-types", "--type", "random_password", "--verbose"])
    assert result.exit_code == 0
    assert "length" in result.output
    assert "special" in result.output


def test_secret_types_unknown(runner: CliRunner) -> None:
    """Test secret-types command with unknown type."""
    result = runner.invoke(main, ["secret-types", "--type", "unknown"])
    assert result.exit_code == 0
    assert "Unknown type" in result.output


def test_test_command(runner: CliRunner) -> None:
    """Test the test command."""
    with TemporaryDirectory() as tmpdir:
        secretfile = Path(tmpdir) / "Secretfile.yml"
        secretfile.write_text(
            """
version: '1.0'
variables: {}
providers:
  local:
    kind: local
secrets: []
templates: {}
"""
        )

        result = runner.invoke(main, ["test", "--file", str(secretfile)])
        assert result.exit_code == 0
        assert "Testing Provider" in result.output
