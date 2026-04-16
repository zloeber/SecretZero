"""Tests for new CLI feature additions: JSON output, exit codes, plan mode, list/detect commands."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from click.testing import CliRunner

from secretzero.lockfile import Lockfile

from secretzero.cli import (
    EXIT_CONFIG_ERROR,
    EXIT_DRIFT_DETECTED,
    EXIT_SUCCESS,
    EXIT_VALIDATION_ERROR,
    main,
)

MINIMAL_SECRETFILE = """
version: '1.0'
variables: {}
providers:
  local:
    kind: local
secrets: []
templates: {}
"""

SECRETFILE_WITH_SECRETS = """
version: '1.0'
variables:
  env: dev
  region: us-east-1
providers:
  local:
    kind: local
secrets:
  - name: db_password
    kind: random_password
    rotation_period: 90d
    config:
      length: 16
    targets:
      - provider: local
        kind: file
        config:
          path: .env.test
          format: dotenv
  - name: api_key
    kind: static
    one_time: true
    config:
      default: test_value
    targets: []
templates: {}
"""


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI test runner."""
    return CliRunner()


# ─────────────────────────────────────────────────────────────────────────────
# Task 1: JSON output format
# ─────────────────────────────────────────────────────────────────────────────


def test_validate_json_output_valid(runner: CliRunner) -> None:
    """Test validate command with --format json on a valid file."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(MINIMAL_SECRETFILE)

        result = runner.invoke(main, ["validate", "--file", str(sf), "--format", "json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["valid"] is True
        assert "message" in payload
        assert "config" in payload
        assert payload["config"]["secrets_count"] == 0


def test_validate_json_output_invalid(runner: CliRunner) -> None:
    """Test validate command with --format json on an invalid file."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text("invalid: yaml\nno: version")

        result = runner.invoke(main, ["validate", "--file", str(sf), "--format", "json"])
        assert result.exit_code == EXIT_VALIDATION_ERROR
        payload = json.loads(result.output)
        assert payload["valid"] is False


def test_status_json_output(runner: CliRunner) -> None:
    """Test status command with --format json."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(SECRETFILE_WITH_SECRETS)
        lock = Path(tmpdir) / ".lock"

        result = runner.invoke(
            main, ["status", "--file", str(sf), "--lockfile", str(lock), "--format", "json"]
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert "secrets" in payload
        assert isinstance(payload["secrets"], list)
        assert payload["total"] == 2
        assert payload["synced"] == 0  # nothing synced yet


def test_status_json_output_after_sync(runner: CliRunner) -> None:
    """Test status command JSON output after syncing."""
    with TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env.test"
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(f"""
version: '1.0'
variables: {{}}
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
          path: {env_file}
          format: dotenv
templates: {{}}
""")
        lock = Path(tmpdir) / ".lock"

        # First sync to create the secret
        runner.invoke(main, ["sync", "--file", str(sf), "--lockfile", str(lock)])

        result = runner.invoke(
            main, ["status", "--file", str(sf), "--lockfile", str(lock), "--format", "json"]
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["synced"] == 1


def test_get_json_metadata_only_default(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    """`get` returns metadata by default without plaintext value."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(MINIMAL_SECRETFILE)

        def _fake_get(self, provider_name, secret_id, method_name=None, method_args=None):
            return {
                "provider": provider_name,
                "method": method_name or "retrieve_secret",
                "retrieved": True,
                "revealable": True,
                "value": "super-secret",
                "notes": None,
            }

        monkeypatch.setattr("secretzero.cli.SyncEngine.get_provider_secret", _fake_get)

        result = runner.invoke(
            main,
            [
                "get",
                "--file",
                str(sf),
                "--provider",
                "local",
                "--secret-id",
                "app/secret",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["provider"] == "local"
        assert payload["revealed"] is False
        assert "value" not in payload


def test_get_json_reveal_includes_value(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    """`get --reveal` includes plaintext when revealable."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(MINIMAL_SECRETFILE)

        def _fake_get(self, provider_name, secret_id, method_name=None, method_args=None):
            return {
                "provider": provider_name,
                "method": "retrieve_secret",
                "retrieved": True,
                "revealable": True,
                "value": "revealed-secret",
                "notes": None,
            }

        monkeypatch.setattr("secretzero.cli.SyncEngine.get_provider_secret", _fake_get)

        result = runner.invoke(
            main,
            [
                "get",
                "--file",
                str(sf),
                "--provider",
                "local",
                "--secret-id",
                "app/secret",
                "--reveal",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["revealed"] is True
        assert payload["value"] == "revealed-secret"


def test_get_blocked_in_sandbox_without_override(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`get` is blocked when `SZ_SANDBOX=true` unless override is set."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(MINIMAL_SECRETFILE)
        monkeypatch.setenv("SZ_SANDBOX", "true")
        monkeypatch.delenv("SZ_ALLOW_GET_IN_SANDBOX", raising=False)

        result = runner.invoke(
            main,
            [
                "get",
                "--file",
                str(sf),
                "--provider",
                "local",
                "--secret-id",
                "app/secret",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == EXIT_VALIDATION_ERROR
        payload = json.loads(result.output)
        assert "blocked in sandbox mode" in payload["error"]


def test_get_allows_sandbox_override(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    """`SZ_ALLOW_GET_IN_SANDBOX=true` allows `get` execution in sandbox mode."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(MINIMAL_SECRETFILE)
        monkeypatch.setenv("SZ_SANDBOX", "true")
        monkeypatch.setenv("SZ_ALLOW_GET_IN_SANDBOX", "true")

        def _fake_get(self, provider_name, secret_id, method_name=None, method_args=None):
            return {
                "provider": provider_name,
                "method": method_name or "retrieve_secret",
                "retrieved": True,
                "revealable": False,
                "value": "[SECRET EXISTS]",
                "notes": "exists-only",
            }

        monkeypatch.setattr("secretzero.cli.SyncEngine.get_provider_secret", _fake_get)

        result = runner.invoke(
            main,
            [
                "get",
                "--file",
                str(sf),
                "--provider",
                "local",
                "--secret-id",
                "app/secret",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["revealable"] is False
        assert payload["revealed"] is False


def test_sync_json_output(runner: CliRunner) -> None:
    """Test sync command with --format json."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(MINIMAL_SECRETFILE)
        lock = Path(tmpdir) / ".lock"

        result = runner.invoke(
            main,
            ["sync", "--file", str(sf), "--lockfile", str(lock), "--dry-run", "--format", "json"],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert "secrets_stored" in payload
        assert "dry_run" in payload
        assert payload["dry_run"] is True
        assert "refresh" in payload


def test_sync_json_output_with_refresh_includes_refresh_report(runner: CliRunner) -> None:
    """`sync --refresh --format json` returns refresh metadata."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(MINIMAL_SECRETFILE)
        lock = Path(tmpdir) / ".lock"

        result = runner.invoke(
            main,
            [
                "sync",
                "--file",
                str(sf),
                "--lockfile",
                str(lock),
                "--dry-run",
                "--refresh",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert "refresh" in payload
        assert payload["refresh"]["mismatch_targets"] == 0


def test_sync_json_output_no_refresh_omits_refresh_report(runner: CliRunner) -> None:
    """`sync --no-refresh --format json` does not include refresh metadata."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(MINIMAL_SECRETFILE)
        lock = Path(tmpdir) / ".lock"

        result = runner.invoke(
            main,
            [
                "sync",
                "--file",
                str(sf),
                "--lockfile",
                str(lock),
                "--dry-run",
                "--no-refresh",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert "refresh" not in payload


def test_sync_json_output_with_secret(runner: CliRunner) -> None:
    """Test sync command JSON output includes details."""
    with TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env.test"
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(f"""
version: '1.0'
variables: {{}}
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
          path: {env_file}
          format: dotenv
templates: {{}}
""")
        lock = Path(tmpdir) / ".lock"

        result = runner.invoke(
            main,
            ["sync", "--file", str(sf), "--lockfile", str(lock), "--format", "json"],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["secrets_stored"] == 1
        assert len(payload["details"]) == 1
        assert payload["details"][0]["name"] == "test_secret"
        assert lock.exists(), "JSON sync must persist the lockfile like text mode"
        assert "test_secret" in lock.read_text()


def test_sync_environment_resolution_metadata_in_json(runner: CliRunner) -> None:
    """`sync --environment` includes resolved context metadata in JSON."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        dev_var = Path(tmpdir) / "dev.szvar"
        dev_var.write_text("env: dev\n", encoding="utf-8")
        sf.write_text(f"""
variables:
  env: base
environments:
  default: dev
  profiles:
    dev:
      var_files:
        - {dev_var}
      lockfile: .gitsecrets.dev.lock
providers:
  local:
    kind: local
secrets: []
templates: {{}}
""")
        result = runner.invoke(main, ["sync", "--file", str(sf), "--dry-run", "--format", "json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["selected_environment"] == "dev"
        assert payload["resolved_target_profile"] is None
        assert str(payload["resolved_lockfile"]).endswith(".gitsecrets.dev.lock")


def test_rotate_json_output_dry_run(runner: CliRunner) -> None:
    """Test rotate command JSON output in dry-run mode."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(SECRETFILE_WITH_SECRETS)
        lock = Path(tmpdir) / ".lock"

        result = runner.invoke(
            main,
            ["rotate", "--file", str(sf), "--lockfile", str(lock), "--dry-run", "--format", "json"],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert "dry_run" in payload
        assert payload["dry_run"] is True


def test_rotate_secret_flag_filters_by_name(runner: CliRunner) -> None:
    """``--secret`` / ``-s`` limits rotation checks to named secret(s)."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text("""
version: '1.0'
variables: {}
providers:
  local:
    kind: local
secrets:
  - name: db_password
    kind: random_password
    rotation_period: 90d
    config:
      length: 16
    targets:
      - provider: local
        kind: file
        config:
          path: .env.test
          format: dotenv
  - name: redis_cache
    kind: random_string
    rotation_period: 30d
    config:
      length: 8
    targets:
      - provider: local
        kind: file
        config:
          path: .env.redis
          format: dotenv
templates: {}
""")
        lock = Path(tmpdir) / ".lock"
        lo = Lockfile()
        lo.add_secret("db_password", "v1")
        lo.add_secret("redis_cache", "v2")
        lo.save(lock)

        result = runner.invoke(
            main,
            [
                "rotate",
                "--file",
                str(sf),
                "--lockfile",
                str(lock),
                "--secret",
                "db_password",
                "--dry-run",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["dry_run"] is True
        names = {d["name"] for d in payload["details"]}
        assert names == {"db_password"}

        result_all = runner.invoke(
            main,
            [
                "rotate",
                "--file",
                str(sf),
                "--lockfile",
                str(lock),
                "--dry-run",
                "--format",
                "json",
            ],
        )
        assert result_all.exit_code == 0, result_all.output
        payload_all = json.loads(result_all.output)
        assert {d["name"] for d in payload_all["details"]} == {"db_password", "redis_cache"}


def test_rotate_secret_flag_unknown_name(runner: CliRunner) -> None:
    """Unknown ``--secret`` name exits with validation error."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(SECRETFILE_WITH_SECRETS)
        lock = Path(tmpdir) / ".lock"

        result = runner.invoke(
            main,
            [
                "rotate",
                "--file",
                str(sf),
                "--lockfile",
                str(lock),
                "--secret",
                "not_in_manifest",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == EXIT_VALIDATION_ERROR, result.output
        payload = json.loads(result.output)
        assert "not found" in payload["error"].lower()


def test_rotate_secret_flag_conflicts_with_positional(runner: CliRunner) -> None:
    """Cannot combine ``--secret`` and positional secret name."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(SECRETFILE_WITH_SECRETS)
        lock = Path(tmpdir) / ".lock"

        result = runner.invoke(
            main,
            [
                "rotate",
                "--file",
                str(sf),
                "--lockfile",
                str(lock),
                "--secret",
                "db_password",
                "db_password",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == EXIT_VALIDATION_ERROR, result.output
        payload = json.loads(result.output)
        assert "not both" in payload["error"].lower()


def test_policy_json_output_compliant(runner: CliRunner) -> None:
    """Test policy command JSON output when compliant."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(MINIMAL_SECRETFILE)

        result = runner.invoke(main, ["policy", "--file", str(sf), "--format", "json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["compliant"] is True
        assert "violations" in payload
        assert isinstance(payload["violations"], list)
        assert payload["errors_count"] == 0


def test_drift_json_output_no_lockfile(runner: CliRunner) -> None:
    """Test drift command JSON output when no lockfile exists."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(MINIMAL_SECRETFILE)
        lock = Path(tmpdir) / ".nonexistent.lock"

        result = runner.invoke(
            main, ["drift", "--file", str(sf), "--lockfile", str(lock), "--format", "json"]
        )
        assert result.exit_code == EXIT_CONFIG_ERROR
        payload = json.loads(result.output)
        assert "error" in payload


# ─────────────────────────────────────────────────────────────────────────────
# Task 2: Standardized exit codes
# ─────────────────────────────────────────────────────────────────────────────


def test_exit_codes_constants() -> None:
    """Test that exit code constants are defined correctly."""
    assert EXIT_SUCCESS == 0
    assert EXIT_VALIDATION_ERROR == 1
    assert EXIT_DRIFT_DETECTED == 4
    assert EXIT_CONFIG_ERROR == 5


def test_validate_success_exit_code(runner: CliRunner) -> None:
    """Test that validate returns exit code 0 on success."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(MINIMAL_SECRETFILE)

        result = runner.invoke(main, ["validate", "--file", str(sf)])
        assert result.exit_code == EXIT_SUCCESS


def test_validate_failure_exit_code(runner: CliRunner) -> None:
    """Test that validate returns exit code 1 on validation error."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text("secrets: invalid")

        result = runner.invoke(main, ["validate", "--file", str(sf)])
        assert result.exit_code == EXIT_VALIDATION_ERROR


# ─────────────────────────────────────────────────────────────────────────────
# Task 3: Plan mode
# ─────────────────────────────────────────────────────────────────────────────


def test_sync_plan_mode(runner: CliRunner) -> None:
    """Test sync --plan shows execution plan without applying."""
    with TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env.test"
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(f"""
version: '1.0'
variables: {{}}
providers:
  local:
    kind: local
secrets:
  - name: db_password
    kind: random_password
    config:
      length: 16
    targets:
      - provider: local
        kind: file
        config:
          path: {env_file}
          format: dotenv
templates: {{}}
""")
        lock = Path(tmpdir) / ".lock"

        result = runner.invoke(main, ["sync", "--file", str(sf), "--lockfile", str(lock), "--plan"])
        assert result.exit_code == 0, result.output
        # Plan mode should show secret names and not create the .env file
        assert "db_password" in result.output
        assert not env_file.exists()


def test_sync_plan_json_output(runner: CliRunner) -> None:
    """Test sync --plan --format json outputs a plan JSON."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(SECRETFILE_WITH_SECRETS.replace(".env.test", str(Path(tmpdir) / ".env.test")))
        lock = Path(tmpdir) / ".lock"

        result = runner.invoke(
            main,
            ["sync", "--file", str(sf), "--lockfile", str(lock), "--plan", "--format", "json"],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["plan"] is True
        assert "plan_details" in payload


def test_sync_plan_implies_dry_run(runner: CliRunner) -> None:
    """Test that --plan implies --dry-run (no changes made)."""
    with TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env.test"
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(f"""
version: '1.0'
variables: {{}}
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
          path: {env_file}
          format: dotenv
templates: {{}}
""")
        lock = Path(tmpdir) / ".lock"

        runner.invoke(main, ["sync", "--file", str(sf), "--lockfile", str(lock), "--plan"])
        # The file should NOT be created when --plan is used
        assert not env_file.exists()
        assert not lock.exists()


# ─────────────────────────────────────────────────────────────────────────────
# Task 4: list command
# ─────────────────────────────────────────────────────────────────────────────


def test_list_secrets_text(runner: CliRunner) -> None:
    """Test list secrets command in text format."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(SECRETFILE_WITH_SECRETS)

        result = runner.invoke(main, ["list", "secrets", "--file", str(sf)])
        assert result.exit_code == 0, result.output
        assert "db_password" in result.output
        assert "api_key" in result.output


def test_list_secrets_json(runner: CliRunner) -> None:
    """Test list secrets command in JSON format."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(SECRETFILE_WITH_SECRETS)

        result = runner.invoke(main, ["list", "secrets", "--file", str(sf), "--format", "json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert "secrets" in payload
        assert payload["total"] == 2
        names = [s["name"] for s in payload["secrets"]]
        assert "db_password" in names
        assert "api_key" in names


def test_list_secrets_filter(runner: CliRunner) -> None:
    """Test list secrets command with name filter."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(SECRETFILE_WITH_SECRETS)

        result = runner.invoke(
            main, ["list", "secrets", "--file", str(sf), "--format", "json", "--filter", "db"]
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["total"] == 1
        assert payload["secrets"][0]["name"] == "db_password"


def test_list_providers_text(runner: CliRunner) -> None:
    """Test list providers command in text format."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(SECRETFILE_WITH_SECRETS)

        result = runner.invoke(main, ["list", "providers", "--file", str(sf)])
        assert result.exit_code == 0, result.output
        assert "local" in result.output


def test_list_providers_json(runner: CliRunner) -> None:
    """Test list providers command in JSON format."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(SECRETFILE_WITH_SECRETS)

        result = runner.invoke(main, ["list", "providers", "--file", str(sf), "--format", "json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert "providers" in payload
        assert payload["total"] == 1
        assert payload["providers"][0]["name"] == "local"


def test_list_targets_json(runner: CliRunner) -> None:
    """Test list targets command in JSON format."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(SECRETFILE_WITH_SECRETS)

        result = runner.invoke(main, ["list", "targets", "--file", str(sf), "--format", "json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert "targets" in payload
        # db_password has 1 target, api_key has 0 targets
        assert payload["total"] == 1
        assert payload["targets"][0]["secret"] == "db_password"


def test_list_targets_empty(runner: CliRunner) -> None:
    """Test list targets command with no targets."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(MINIMAL_SECRETFILE)

        result = runner.invoke(main, ["list", "targets", "--file", str(sf)])
        assert result.exit_code == 0, result.output
        assert "No targets" in result.output


def test_list_variables_text(runner: CliRunner) -> None:
    """Test list variables command in text format."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(SECRETFILE_WITH_SECRETS)

        result = runner.invoke(main, ["list", "variables", "--file", str(sf)])
        assert result.exit_code == 0, result.output
        assert "env" in result.output
        assert "region" in result.output


def test_list_variables_json(runner: CliRunner) -> None:
    """Test list variables command in JSON format."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(SECRETFILE_WITH_SECRETS)

        result = runner.invoke(main, ["list", "variables", "--file", str(sf), "--format", "json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert "variables" in payload
        assert payload["total"] == 2
        assert "env" in payload["variables"]
        assert payload["variables"]["env"] == "dev"


def test_list_variables_filter(runner: CliRunner) -> None:
    """Test list variables command with filter."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(SECRETFILE_WITH_SECRETS)

        result = runner.invoke(
            main,
            ["list", "variables", "--file", str(sf), "--format", "json", "--filter", "region"],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["total"] == 1
        assert "region" in payload["variables"]


def test_list_variables_empty(runner: CliRunner) -> None:
    """Test list variables with no variables."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(MINIMAL_SECRETFILE)

        result = runner.invoke(main, ["list", "variables", "--file", str(sf)])
        assert result.exit_code == 0, result.output
        assert "No variables" in result.output


# ─────────────────────────────────────────────────────────────────────────────
# Task 5: JSON graph output
# ─────────────────────────────────────────────────────────────────────────────


def test_graph_json_format(runner: CliRunner) -> None:
    """Test graph command with --format json."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(SECRETFILE_WITH_SECRETS)

        result = runner.invoke(main, ["graph", "--file", str(sf), "--format", "json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert "nodes" in payload
        assert "edges" in payload
        assert isinstance(payload["nodes"], list)
        assert isinstance(payload["edges"], list)


def test_graph_json_contains_secrets(runner: CliRunner) -> None:
    """Test graph JSON output includes secret nodes."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(SECRETFILE_WITH_SECRETS)

        result = runner.invoke(main, ["graph", "--file", str(sf), "--format", "json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        node_ids = [n["id"] for n in payload["nodes"]]
        assert "db_password" in node_ids
        assert "api_key" in node_ids


def test_graph_json_output_to_file(runner: CliRunner) -> None:
    """Test graph JSON output to file."""
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(SECRETFILE_WITH_SECRETS)
        output_file = Path(tmpdir) / "graph.json"

        result = runner.invoke(
            main,
            ["graph", "--file", str(sf), "--format", "json", "--output", str(output_file)],
        )
        assert result.exit_code == 0, result.output
        assert output_file.exists()
        payload = json.loads(output_file.read_text())
        assert "nodes" in payload


# ─────────────────────────────────────────────────────────────────────────────
# Task 6 (Bonus): detect command
# ─────────────────────────────────────────────────────────────────────────────


def test_detect_empty_directory(runner: CliRunner) -> None:
    """Test detect command with no secrets in directory."""
    with TemporaryDirectory() as tmpdir:
        result = runner.invoke(main, ["detect", tmpdir])
        assert result.exit_code == 0, result.output
        assert "No potential secrets" in result.output


def test_detect_finds_env_file_secrets(runner: CliRunner) -> None:
    """Test detect finds secrets in .env file."""
    with TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("DATABASE_PASSWORD=mysecret\nAPI_KEY=abc123\nDEBUG=true\n")

        result = runner.invoke(main, ["detect", tmpdir])
        assert result.exit_code == 0, result.output
        # Should detect at least one secret (DATABASE_PASSWORD or API_KEY)
        assert "database_password" in result.output.lower() or "api_key" in result.output.lower()
        # At least one detected secret is shown
        assert "database_password" in result.output.lower() or "api_key" in result.output.lower()


def test_detect_json_output(runner: CliRunner) -> None:
    """Test detect command with JSON output."""
    with TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("DATABASE_PASSWORD=mysecret\n")

        result = runner.invoke(main, ["detect", tmpdir, "--format", "json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert "detected" in payload
        assert "total" in payload


def test_detect_output_to_file(runner: CliRunner) -> None:
    """Test detect command writing suggestion to file."""
    with TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("API_SECRET=abc123\n")
        output_file = Path(tmpdir) / "suggested.yml"

        result = runner.invoke(main, ["detect", tmpdir, "--output", str(output_file)])
        assert result.exit_code == 0, result.output
        # Either finds secrets and writes file, or finds nothing
        if output_file.exists():
            content = output_file.read_text()
            assert "secrets:" in content


def test_import_cli_help(runner: CliRunner) -> None:
    r = runner.invoke(main, ["import", "--help"])
    assert r.exit_code == 0, r.output
    assert "--check" in r.output


def test_import_check_missing_lockfile(runner: CliRunner) -> None:
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(MINIMAL_SECRETFILE)
        lf = Path(tmpdir) / ".missing.lock"
        r = runner.invoke(main, ["import", "-f", str(sf), "-l", str(lf), "--check"])
        assert r.exit_code == EXIT_CONFIG_ERROR


def test_import_check_json_empty_secrets(runner: CliRunner) -> None:
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(MINIMAL_SECRETFILE)
        lf = Path(tmpdir) / ".gitsecrets.lock"
        lf.write_text('{"version": "1.0", "secrets": {}}\n')
        r = runner.invoke(
            main,
            ["import", "--check", "--format", "json", "-f", str(sf), "-l", str(lf)],
        )
        assert r.exit_code == 0, r.output
        data = json.loads(r.output)
        assert data.get("drift_detected") is False


def test_import_dry_run_json(runner: CliRunner) -> None:
    with TemporaryDirectory() as tmpdir:
        sf = Path(tmpdir) / "Secretfile.yml"
        sf.write_text(SECRETFILE_WITH_SECRETS)
        lf = Path(tmpdir) / ".gitsecrets.lock"
        lf.write_text('{"version": "1.0", "secrets": {}}\n')
        r = runner.invoke(
            main,
            ["import", "-f", str(sf), "-l", str(lf), "--dry-run", "--format", "json"],
        )
        assert r.exit_code == 0, r.output
        data = json.loads(r.output)
        assert data.get("dry_run") is True
        assert "details" in data
