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


def test_sync_dry_run(runner: CliRunner) -> None:
    """Test sync command with dry-run."""
    with TemporaryDirectory() as tmpdir:
        secretfile = Path(tmpdir) / "Secretfile.yml"
        secretfile.write_text(
            """
version: '1.0'
variables: {}
providers:
  local:
    kind: local
secrets:
  - name: test_secret
    kind: random_password
    config:
      length: 16
    targets:
      - provider: local
        kind: file
        config:
          path: .env.test
          format: dotenv
templates: {}
"""
        )

        result = runner.invoke(
            main,
            ["sync", "--file", str(secretfile), "--lockfile", str(Path(tmpdir) / ".lock"), "--dry-run"],
        )
        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        assert "would generate" in result.output or "would_store" in result.output


def test_sync_actual(runner: CliRunner) -> None:
    """Test actual sync command."""
    with TemporaryDirectory() as tmpdir:
        secretfile = Path(tmpdir) / "Secretfile.yml"
        lockfile = Path(tmpdir) / ".lock"
        env_file = Path(tmpdir) / ".env.test"

        secretfile.write_text(
            """
version: '1.0'
variables: {}
providers:
  local:
    kind: local
secrets:
  - name: test_secret
    kind: random_password
    config:
      length: 16
    targets:
      - provider: local
        kind: file
        config:
          path: """ + str(env_file) + """
          format: dotenv
templates: {}
"""
        )

        result = runner.invoke(
            main,
            ["sync", "--file", str(secretfile), "--lockfile", str(lockfile)],
        )
        assert result.exit_code == 0
        assert "✓" in result.output
        assert lockfile.exists()
        assert env_file.exists()


def test_sync_one_time_secret(runner: CliRunner) -> None:
    """Test sync with one-time secret."""
    with TemporaryDirectory() as tmpdir:
        secretfile = Path(tmpdir) / "Secretfile.yml"
        lockfile = Path(tmpdir) / ".lock"

        secretfile.write_text(
            """
version: '1.0'
variables: {}
providers: {}
secrets:
  - name: one_time_secret
    kind: static
    one_time: true
    config:
      default: "secret_value"
    targets: []
templates: {}
"""
        )

        # First sync - should generate
        result1 = runner.invoke(
            main,
            ["sync", "--file", str(secretfile), "--lockfile", str(lockfile)],
        )
        assert result1.exit_code == 0
        assert "Generated: 1" in result1.output

        # Second sync - should skip
        result2 = runner.invoke(
            main,
            ["sync", "--file", str(secretfile), "--lockfile", str(lockfile)],
        )
        assert result2.exit_code == 0
        assert "Skipped: 1" in result2.output
        assert "One-time secret already exists" in result2.output


def test_show_command(runner: CliRunner) -> None:
    """Test show command."""
    with TemporaryDirectory() as tmpdir:
        secretfile = Path(tmpdir) / "Secretfile.yml"
        lockfile = Path(tmpdir) / ".lock"

        secretfile.write_text(
            """
version: '1.0'
variables: {}
providers: {}
secrets:
  - name: test_secret
    kind: random_password
    rotation_period: 90d
    config:
      length: 16
    targets: []
templates: {}
"""
        )

        # First sync to create the secret
        runner.invoke(
            main,
            ["sync", "--file", str(secretfile), "--lockfile", str(lockfile)],
        )

        # Show the secret
        result = runner.invoke(
            main,
            ["show", "test_secret", "--file", str(secretfile), "--lockfile", str(lockfile)],
        )
        assert result.exit_code == 0
        assert "test_secret" in result.output
        assert "random_password" in result.output
        assert "90d" in result.output


def test_show_nonexistent_secret(runner: CliRunner) -> None:
    """Test show command with non-existent secret."""
    with TemporaryDirectory() as tmpdir:
        secretfile = Path(tmpdir) / "Secretfile.yml"
        lockfile = Path(tmpdir) / ".lock"

        secretfile.write_text(
            """
version: '1.0'
variables: {}
providers: {}
secrets: []
templates: {}
"""
        )

        result = runner.invoke(
            main,
            ["show", "nonexistent", "--file", str(secretfile), "--lockfile", str(lockfile)],
        )
        assert result.exit_code != 0
        assert "not found" in result.output

