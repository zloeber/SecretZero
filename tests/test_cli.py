"""Tests for CLI commands."""

import json
from datetime import UTC, datetime
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
    assert "version" in result.output.lower()


def test_cli_help(runner: CliRunner) -> None:
    """Test CLI help command."""
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "SecretZero" in result.output


def test_create_command(runner: CliRunner) -> None:
    """Test create command creates a Secretfile."""
    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Secretfile.yml"
        result = runner.invoke(main, ["create", "--output", str(output_path)])

        assert result.exit_code == 0
        assert output_path.exists()
        assert "Created Secretfile" in result.output


def test_create_existing_file(runner: CliRunner) -> None:
    """Test create command with existing file."""
    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "Secretfile.yml"
        output_path.write_text("existing")

        result = runner.invoke(main, ["create", "--output", str(output_path)])
        assert result.exit_code != 0
        assert "already exists" in result.output


def test_validate_command(runner: CliRunner) -> None:
    """Test validate command."""
    with TemporaryDirectory() as tmpdir:
        secretfile = Path(tmpdir) / "Secretfile.yml"
        secretfile.write_text("""
version: '1.0'
variables: {}
providers: {}
secrets: []
templates: {}
""")

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


def test_schema_export_stdout(runner: CliRunner) -> None:
    """Test schema export to stdout."""
    result = runner.invoke(main, ["schema", "export"])
    assert result.exit_code == 0

    payload = json.loads(result.output)
    assert payload.get("title") == "Secretfile"
    assert "properties" in payload


def test_schema_export_file(runner: CliRunner) -> None:
    """Test schema export to file."""
    with TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "secretfile.schema.json"
        result = runner.invoke(main, ["schema", "export", "--output", str(output_path)])

        assert result.exit_code == 0
        assert output_path.exists()

        payload = json.loads(output_path.read_text())
        assert payload.get("title") == "Secretfile"


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
        secretfile.write_text("""
version: '1.0'
variables: {}
providers:
  local:
    kind: local
secrets: []
templates: {}
""")

        result = runner.invoke(main, ["test", "--file", str(secretfile)])
        assert result.exit_code == 0
        assert "Testing Provider" in result.output


def test_sync_dry_run(runner: CliRunner) -> None:
    """Test sync command with dry-run."""
    with TemporaryDirectory() as tmpdir:
        secretfile = Path(tmpdir) / "Secretfile.yml"
        secretfile.write_text("""
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
""")

        result = runner.invoke(
            main,
            [
                "sync",
                "--file",
                str(secretfile),
                "--lockfile",
                str(Path(tmpdir) / ".lock"),
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        assert "would generate" in result.output.lower() or "would store" in result.output.lower()


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
          path: """
            + str(env_file)
            + """
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

        secretfile.write_text("""
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
""")

        # First sync - should generate
        result1 = runner.invoke(
            main,
            ["sync", "--file", str(secretfile), "--lockfile", str(lockfile)],
        )
        assert result1.exit_code == 0
        # Check for successful storage in the output
        assert (
            "Success: 1 secret(s) stored" in result1.output
            or "Stored" in result1.output
            or "one_time_secret" in result1.output
        )

        # Second sync - should skip
        result2 = runner.invoke(
            main,
            ["sync", "--file", str(secretfile), "--lockfile", str(lockfile)],
        )
        assert result2.exit_code == 0
        assert "Skipped" in result2.output
        assert (
            "one-time secret already" in result2.output.lower()
            or "skipped: 1" in result2.output.lower()
        )


def test_sync_clean_orphaned_entries(runner: CliRunner) -> None:
    """Test sync --clean removes orphaned lockfile entries."""
    with TemporaryDirectory() as tmpdir:
        secretfile = Path(tmpdir) / "Secretfile.yml"
        lockfile_path = Path(tmpdir) / "test.lock"
        output_file = Path(tmpdir) / "secret.txt"

        # Create secretfile with one secret
        secretfile.write_text(f"""
version: "1.0"
secrets:
  - name: current_secret
    kind: random_password
    config:
      length: 16
    targets:
      - provider: local
        kind: file
        config:
          path: {output_file}
""")

        # Create lockfile with current_secret and orphaned entries
        from datetime import UTC, datetime

        from secretzero.lockfile import Lockfile, SecretLockEntry

        lock = Lockfile()
        now = datetime.now(UTC).isoformat()

        # Add current secret
        lock.secrets["current_secret"] = SecretLockEntry(
            hash="abc123", created_at=now, updated_at=now
        )

        # Add orphaned entries (secrets that don't exist in Secretfile)
        lock.secrets["old_secret_1"] = SecretLockEntry(
            hash="def456", created_at=now, updated_at=now
        )
        lock.secrets["old_secret_2"] = SecretLockEntry(
            hash="ghi789", created_at=now, updated_at=now
        )

        lock.save(lockfile_path)

        # Verify lockfile has 3 entries
        loaded_lock = Lockfile.load(lockfile_path)
        assert len(loaded_lock.secrets) == 3

        # Run sync with --clean flag
        result = runner.invoke(
            main, ["sync", "--file", str(secretfile), "--lockfile", str(lockfile_path), "--clean"]
        )
        if result.exit_code != 0:
            print(f"Exit code: {result.exit_code}")
            print(f"Output: {result.output}")
            if result.exception:
                import traceback

                traceback.print_exception(
                    type(result.exception), result.exception, result.exception.__traceback__
                )
        assert result.exit_code == 0

        # Verify orphaned entries were removed
        cleaned_lock = Lockfile.load(lockfile_path)
        assert len(cleaned_lock.secrets) == 1
        assert "current_secret" in cleaned_lock.secrets
        assert "old_secret_1" not in cleaned_lock.secrets
        assert "old_secret_2" not in cleaned_lock.secrets

        # Check output mentions cleaning
        assert "Cleaned" in result.output or "cleaned" in result.output


def test_sync_clean_dry_run(runner: CliRunner) -> None:
    """Test sync --clean --dry-run doesn't actually remove entries."""
    with TemporaryDirectory() as tmpdir:
        secretfile = Path(tmpdir) / "Secretfile.yml"
        lockfile_path = Path(tmpdir) / "test.lock"
        output_file = Path(tmpdir) / "secret.txt"

        # Create secretfile with one secret
        secretfile.write_text(f"""
version: "1.0"
secrets:
  - name: current_secret
    kind: random_password
    config:
      length: 16
    targets:
      - provider: local
        kind: file
        config:
          path: {output_file}
""")

        # Create lockfile with orphaned entries
        from datetime import UTC, datetime

        from secretzero.lockfile import Lockfile, SecretLockEntry

        lock = Lockfile()
        now = datetime.now(UTC).isoformat()

        lock.secrets["current_secret"] = SecretLockEntry(
            hash="abc123", created_at=now, updated_at=now
        )
        lock.secrets["orphaned_secret"] = SecretLockEntry(
            hash="def456", created_at=now, updated_at=now
        )

        lock.save(lockfile_path)

        # Run sync with --clean and --dry-run
        result = runner.invoke(
            main,
            [
                "sync",
                "--file",
                str(secretfile),
                "--lockfile",
                str(lockfile_path),
                "--clean",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0

        # Verify orphaned entry is still present (dry run)
        cleaned_lock = Lockfile.load(lockfile_path)
        assert len(cleaned_lock.secrets) == 2
        assert "orphaned_secret" in cleaned_lock.secrets

        # Check output mentions what would be cleaned
        assert "Would remove" in result.output or "dry run" in result.output.lower()


def test_show_command(runner: CliRunner) -> None:
    """Test show command."""
    with TemporaryDirectory() as tmpdir:
        secretfile = Path(tmpdir) / "Secretfile.yml"
        lockfile = Path(tmpdir) / ".lock"

        secretfile.write_text("""
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
""")

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

        secretfile.write_text("""
version: '1.0'
variables: {}
providers: {}
secrets: []
templates: {}
""")

        result = runner.invoke(
            main,
            ["show", "nonexistent", "--file", str(secretfile), "--lockfile", str(lockfile)],
        )
        assert result.exit_code != 0
        assert "not found" in result.output


def test_audit_command_no_log_file(runner: CliRunner) -> None:
    """Test audit command when no log file exists."""
    with TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "audit.log"
        result = runner.invoke(main, ["audit", "--log-file", str(log_path)])
        assert result.exit_code == 0
        assert "No audit log entries" in result.output or "not found" in result.output


def test_audit_command_with_log_file(runner: CliRunner) -> None:
    """Test audit command reads from an existing log file."""
    with TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "audit.log"
        # Write a sample audit log entry
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "action": "sync",
            "resource": "secrets",
            "user": "api",
            "details": {"count": 2},
            "success": True,
        }
        log_path.write_text(json.dumps(entry) + "\n")

        result = runner.invoke(main, ["audit", "--log-file", str(log_path)])
        assert result.exit_code == 0
        assert "sync" in result.output
        assert "secrets" in result.output


def test_audit_command_json_format(runner: CliRunner) -> None:
    """Test audit command with JSON output format."""
    with TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "audit.log"
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "action": "rotate",
            "resource": "secret:api_key",
            "user": "api",
            "details": {},
            "success": True,
        }
        log_path.write_text(json.dumps(entry) + "\n")

        result = runner.invoke(main, ["audit", "--log-file", str(log_path), "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "entries" in data
        assert "count" in data
        assert data["count"] == 1
        assert data["entries"][0]["action"] == "rotate"


def test_audit_command_filter_by_action(runner: CliRunner) -> None:
    """Test audit command filters by action."""
    with TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "audit.log"
        entries = [
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "action": "sync",
                "resource": "secrets",
                "user": "api",
                "details": {},
                "success": True,
            },
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "action": "rotate",
                "resource": "secrets",
                "user": "api",
                "details": {},
                "success": True,
            },
        ]
        log_path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")

        result = runner.invoke(
            main, ["audit", "--log-file", str(log_path), "--action", "sync", "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 1
        assert data["entries"][0]["action"] == "sync"


def test_terraform_command_dry_run(runner: CliRunner) -> None:
    """Test terraform command in dry-run mode."""
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        secretfile_src = Path(__file__).resolve().parents[1] / "Secretfile.test.yml"
        secretfile_dest = tmp_path / "Secretfile.yml"
        secretfile_dest.write_text(secretfile_src.read_text())

        output_dir = tmp_path / "tf-out"

        result = runner.invoke(
            main,
            [
                "terraform",
                "--file",
                str(secretfile_dest),
                "--output-dir",
                str(output_dir),
                "--format",
                "json",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        assert "Terraform generation plan" in result.output


def test_terraform_command_writes_files(runner: CliRunner) -> None:
    """Test terraform command writes configuration files."""
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        secretfile_src = Path(__file__).resolve().parents[1] / "Secretfile.test.yml"
        secretfile_dest = tmp_path / "Secretfile.yml"
        secretfile_dest.write_text(secretfile_src.read_text())

        output_dir = tmp_path / "tf-out"

        result = runner.invoke(
            main,
            [
                "terraform",
                "--file",
                str(secretfile_dest),
                "--output-dir",
                str(output_dir),
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        main_tf_json = output_dir / "main.tf.json"
        assert main_tf_json.exists()
        data = json.loads(main_tf_json.read_text())
        assert "terraform" in data or "resource" in data
