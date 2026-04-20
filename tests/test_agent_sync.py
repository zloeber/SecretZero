"""Tests for agent-guided secret synchronisation."""

import json
from datetime import UTC
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from secretzero.agent import (
    AgentSecretSynchronizer,
    AgentSyncResult,
    detect_automation_level,
    secret_supports_automatic_generation,
)
from secretzero.cli import main
from secretzero.models import (
    AgentInstructions,
    AgentInstructionStep,
    AutomationLevel,
    Secret,
    Secretfile,
    TargetConfig,
    TargetKind,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_secretfile(secrets: list[Secret]) -> Secretfile:
    """Build a minimal Secretfile containing the given secrets."""
    return Secretfile(
        version="1.0",
        secrets=secrets,
    )


def _make_secret(
    name: str,
    kind: str,
    config: dict | None = None,
    agent_instructions: AgentInstructions | None = None,
) -> Secret:
    return Secret(
        name=name,
        kind=kind,
        config=config or {},
        agent_instructions=agent_instructions,
    )


# ---------------------------------------------------------------------------
# Model validation
# ---------------------------------------------------------------------------


class TestAgentInstructionsModel:
    """Unit tests for AgentInstructions Pydantic model."""

    def test_minimal_valid_model(self) -> None:
        """AgentInstructions can be created with only required fields."""
        instructions = AgentInstructions(
            summary="Do something",
            steps=[AgentInstructionStep(action="Act", description="Why")],
        )
        assert instructions.summary == "Do something"
        assert len(instructions.steps) == 1

    def test_full_model(self) -> None:
        """AgentInstructions accepts all optional fields."""
        instructions = AgentInstructions(
            summary="Full example",
            steps=[
                AgentInstructionStep(
                    action="curl https://example.com",
                    description="Fetch token",
                    params={"key": "value"},
                    required=False,
                )
            ],
            prerequisites=["Must have account"],
            automation_hint="Fully automated",
            estimated_time="1 minute",
            fallback="Do it manually",
            required_tools=["curl", "jq"],
            documentation_url="https://docs.example.com",
        )
        assert instructions.prerequisites == ["Must have account"]
        assert instructions.required_tools == ["curl", "jq"]
        assert instructions.steps[0].params == {"key": "value"}
        assert instructions.steps[0].required is False

    def test_step_required_defaults_to_true(self) -> None:
        """AgentInstructionStep.required defaults to True."""
        step = AgentInstructionStep(action="Do", description="Because")
        assert step.required is True

    def test_optional_fields_default_to_none(self) -> None:
        """Optional AgentInstructions fields default to None."""
        instructions = AgentInstructions(summary="x", steps=[])
        assert instructions.prerequisites is None
        assert instructions.automation_hint is None
        assert instructions.estimated_time is None
        assert instructions.fallback is None
        assert instructions.required_tools is None
        assert instructions.documentation_url is None


class TestSecretModelWithAgentInstructions:
    """Verify that agent_instructions integrates with the Secret model."""

    def test_secret_without_instructions(self) -> None:
        """Secret.agent_instructions defaults to None."""
        secret = Secret(name="pwd", kind="random_password")
        assert secret.agent_instructions is None

    def test_secret_with_instructions(self) -> None:
        """Secret.agent_instructions is stored and retrieved correctly."""
        instructions = AgentInstructions(
            summary="Sign up",
            steps=[AgentInstructionStep(action="Visit URL", description="Go there")],
        )
        secret = Secret(name="api_key", kind="static", agent_instructions=instructions)
        assert secret.agent_instructions is not None
        assert secret.agent_instructions.summary == "Sign up"


# ---------------------------------------------------------------------------
# detect_automation_level
# ---------------------------------------------------------------------------


class TestDetectAutomationLevel:
    """Unit tests for detect_automation_level()."""

    def test_random_password_is_fully_automated(self) -> None:
        secret = _make_secret("pwd", "random_password")
        assert detect_automation_level(secret) == AutomationLevel.FULLY_AUTOMATED

    def test_random_string_is_fully_automated(self) -> None:
        secret = _make_secret("s", "random_string")
        assert detect_automation_level(secret) == AutomationLevel.FULLY_AUTOMATED

    def test_static_without_instructions_is_manual_only(self) -> None:
        secret = _make_secret("k", "static")
        assert detect_automation_level(secret) == AutomationLevel.MANUAL_ONLY

    @pytest.mark.parametrize(
        "hint,expected",
        [
            ("Fully automated via CLI", AutomationLevel.FULLY_AUTOMATED),
            ("Manual only – requires browser", AutomationLevel.MANUAL_ONLY),
            ("Requires admin approval", AutomationLevel.REQUIRES_APPROVAL),
            ("Semi-automated: agent polls, user approves", AutomationLevel.SEMI_AUTOMATED),
            (None, AutomationLevel.SEMI_AUTOMATED),  # no hint → semi-automated default
        ],
    )
    def test_automation_hint_parsing(self, hint: str | None, expected: AutomationLevel) -> None:
        instructions = AgentInstructions(
            summary="Test",
            steps=[],
            automation_hint=hint,
        )
        secret = _make_secret("s", "static", agent_instructions=instructions)
        assert detect_automation_level(secret) == expected


# ---------------------------------------------------------------------------
# AgentSecretSynchronizer
# ---------------------------------------------------------------------------


class TestAgentSecretSynchronizer:
    """Unit tests for AgentSecretSynchronizer."""

    def test_auto_secrets_land_in_synced_secrets(self) -> None:
        """Random-password secrets are synced automatically (dry_run=True)."""
        from secretzero.lockfile import Lockfile

        sf = _make_secretfile([_make_secret("pwd", "random_password")])
        lock = Lockfile()
        sync = AgentSecretSynchronizer(sf, lock, dry_run=True)
        result = sync.sync()
        assert "pwd" in result.synced_secrets
        assert len(result.pending_secrets) == 0
        assert len(result.failed_secrets) == 0

    def test_random_string_is_auto_synced(self) -> None:
        from secretzero.lockfile import Lockfile

        sf = _make_secretfile([_make_secret("tok", "random_string")])
        lock = Lockfile()
        result = AgentSecretSynchronizer(sf, lock, dry_run=True).sync()
        assert "tok" in result.synced_secrets

    def test_static_with_value_is_auto_synced(self) -> None:
        from secretzero.lockfile import Lockfile

        sf = _make_secretfile([_make_secret("k", "static", config={"value": "secret123"})])
        lock = Lockfile()
        result = AgentSecretSynchronizer(sf, lock, dry_run=True).sync()
        assert "k" in result.synced_secrets

    def test_static_dict_fully_set_is_auto_synced(self) -> None:
        from secretzero.lockfile import Lockfile

        sf = _make_secretfile(
            [
                _make_secret(
                    "k",
                    "static",
                    config={
                        "value": {
                            "tenant_id": "t1",
                            "client_id": "c1",
                            "client_secret": "s1",
                        }
                    },
                )
            ]
        )
        lock = Lockfile()
        result = AgentSecretSynchronizer(sf, lock, dry_run=True).sync()
        assert "k" in result.synced_secrets

    def test_static_dict_with_null_goes_to_pending(self) -> None:
        """Structured static with missing leaves is not auto-synced."""
        from secretzero.lockfile import Lockfile

        instructions = AgentInstructions(
            summary="Provide Entra credentials",
            steps=[AgentInstructionStep(action="Azure Portal", description="Copy IDs")],
        )
        sf = _make_secretfile(
            [
                _make_secret(
                    "entra",
                    "static",
                    config={"value": {"tenant_id": None, "client_id": "x", "client_secret": ""}},
                    agent_instructions=instructions,
                )
            ]
        )
        lock = Lockfile()
        result = AgentSecretSynchronizer(sf, lock, dry_run=True).sync()
        assert "entra" in result.pending_secrets
        assert "entra" not in result.synced_secrets

    def test_static_without_value_with_instructions_goes_to_pending(self) -> None:
        """Static secret with no value but with instructions ends up in pending."""
        from secretzero.lockfile import Lockfile

        instructions = AgentInstructions(
            summary="Manual setup required",
            steps=[AgentInstructionStep(action="Visit site", description="Sign up")],
        )
        sf = _make_secretfile([_make_secret("api_key", "static", agent_instructions=instructions)])
        lock = Lockfile()
        result = AgentSecretSynchronizer(sf, lock, dry_run=True).sync()
        assert "api_key" in result.pending_secrets
        assert result.pending_secrets["api_key"].summary == "Manual setup required"

    def test_sz_agent_moves_manual_to_failed(self) -> None:
        """SZ_AGENT semantics report manual secrets as failed, not pending."""
        from secretzero.lockfile import Lockfile

        instructions = AgentInstructions(
            summary="Manual setup required",
            steps=[AgentInstructionStep(action="Visit site", description="Sign up")],
        )
        sf = _make_secretfile([_make_secret("api_key", "static", agent_instructions=instructions)])
        lock = Lockfile()
        result = AgentSecretSynchronizer(sf, lock, dry_run=True).sync(sz_agent=True)
        assert "api_key" in result.failed_secrets
        assert "api_key" not in result.pending_secrets
        assert result.status == "failed"

    def test_agent_instructions_render_for_secret(self) -> None:
        """render_for_secret injects secret_name, var, and target context."""
        instructions = AgentInstructions(
            summary="Configure {{ secret_name }} for {{ var.project }}",
            steps=[
                AgentInstructionStep(
                    action="sync",
                    description="kind={{ target.kind }}",
                )
            ],
        )
        secret = Secret(
            name="my_key",
            kind="static",
            config={},
            targets=[
                TargetConfig(provider="local", kind=TargetKind.FILE, config={"path": "./out.env"})
            ],
            agent_instructions=instructions,
        )
        sf = _make_secretfile([secret])
        sf.variables["project"] = "demo"
        rendered = instructions.render_for_secret(
            variables=sf.variables,
            secret_name=secret.name,
            secret=secret,
        )
        assert rendered.summary == "Configure my_key for demo"
        assert "file" in rendered.steps[0].description

    def test_static_without_value_or_instructions_goes_to_failed(self) -> None:
        """Static secret with no value and no instructions ends up in failed."""
        from secretzero.lockfile import Lockfile

        sf = _make_secretfile([_make_secret("bare", "static")])
        lock = Lockfile()
        result = AgentSecretSynchronizer(sf, lock, dry_run=True).sync()
        assert "bare" in result.failed_secrets

    def test_mixed_secrets(self) -> None:
        """Mixed auto, pending, and failed secrets are correctly classified."""
        from secretzero.lockfile import Lockfile

        instructions = AgentInstructions(summary="Manual", steps=[])
        secrets = [
            _make_secret("auto1", "random_password"),
            _make_secret("auto2", "random_string"),
            _make_secret("manual1", "static", agent_instructions=instructions),
            _make_secret("failed1", "static"),  # no value, no instructions
        ]
        sf = _make_secretfile(secrets)
        lock = Lockfile()
        result = AgentSecretSynchronizer(sf, lock, dry_run=True).sync()
        assert set(result.synced_secrets) == {"auto1", "auto2"}
        assert "manual1" in result.pending_secrets
        assert "failed1" in result.failed_secrets
        assert result.automation_summary["fully_synced"] == 2
        assert result.automation_summary["requires_intervention"] == 1
        assert result.automation_summary["failed"] == 1

    def test_automation_summary_keys_are_always_present(self) -> None:
        from secretzero.lockfile import Lockfile

        sf = _make_secretfile([])
        lock = Lockfile()
        result = AgentSecretSynchronizer(sf, lock, dry_run=True).sync()
        assert "fully_synced" in result.automation_summary
        assert "requires_intervention" in result.automation_summary
        assert "failed" in result.automation_summary

    def test_secret_already_in_lockfile_is_skipped(self) -> None:
        """Secrets already in lockfile should be skipped without error."""
        from datetime import datetime, timezone

        from secretzero.lockfile import Lockfile, SecretLockEntry

        # Create a static secret without explicit value (would normally fail)
        sf = _make_secretfile([_make_secret("existing_secret", "static")])

        # Create lockfile with existing entry
        lock = Lockfile()
        now = datetime.now(UTC).isoformat()
        lock.secrets["existing_secret"] = SecretLockEntry(
            hash="abc123",
            created_at=now,
            updated_at=now,
            rotation_count=0,
        )

        result = AgentSecretSynchronizer(sf, lock, dry_run=True).sync()

        # Should be in already_synced, not failed or pending
        assert "existing_secret" in result.already_synced
        assert "existing_secret" not in result.synced_secrets
        assert "existing_secret" not in result.pending_secrets
        assert "existing_secret" not in result.failed_secrets
        assert result.automation_summary["already_synced"] == 1
        assert result.automation_summary["fully_synced"] == 0
        assert result.automation_summary["requires_intervention"] == 0
        assert result.automation_summary["failed"] == 0


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestAgentSyncCLI:
    """Integration tests for `secretzero agent sync`."""

    @staticmethod
    def _write_secretfile(path: Path, secrets_yaml: str = "") -> None:
        path.write_text(f"""version: '1.0'
variables: {{}}
providers: {{}}
secrets:
{secrets_yaml}
templates: {{}}
""")

    def test_help_output(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["agent", "sync", "--help"])
        assert result.exit_code == 0
        assert "Agent-aware" in result.output

    def test_agent_group_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["agent", "--help"])
        assert result.exit_code == 0
        assert "agent" in result.output.lower() or "sync" in result.output.lower()

    def test_json_output_auto_secrets(self, runner: CliRunner) -> None:
        with TemporaryDirectory() as tmpdir:
            sf = Path(tmpdir) / "Secretfile.yml"
            self._write_secretfile(
                sf,
                "  - name: pwd\n    kind: random_password\n    config: {length: 24}",
            )
            result = runner.invoke(
                main, ["agent", "sync", "--file", str(sf), "--json", "--dry-run"]
            )
            assert result.exit_code == 0, result.output
            data = json.loads(result.output)
            assert "pwd" in data["synced_secrets"]
            assert data["automation_summary"]["fully_synced"] == 1

    def test_json_output_pending_secrets(self, runner: CliRunner) -> None:
        with TemporaryDirectory() as tmpdir:
            sf = Path(tmpdir) / "Secretfile.yml"
            sf.write_text("""version: '1.0'
variables: {}
providers: {}
secrets:
  - name: stripe_key
    kind: static
    config: {}
    agent_instructions:
      summary: Sign up for Stripe
      steps:
        - action: Visit https://dashboard.stripe.com/register
          description: Create account
templates: {}
""")
            result = runner.invoke(
                main, ["agent", "sync", "--file", str(sf), "--json", "--dry-run"]
            )
            assert result.exit_code == 0, result.output
            data = json.loads(result.output)
            assert "stripe_key" in data["pending_secrets"]
            assert data["pending_secrets"]["stripe_key"]["summary"] == "Sign up for Stripe"
            assert data["automation_summary"]["requires_intervention"] == 1

    def test_human_readable_output(self, runner: CliRunner) -> None:
        with TemporaryDirectory() as tmpdir:
            sf = Path(tmpdir) / "Secretfile.yml"
            sf.write_text("""version: '1.0'
variables: {}
providers: {}
secrets:
  - name: pwd
    kind: random_password
    config: {length: 16}
  - name: api_key
    kind: static
    config: {}
    agent_instructions:
      summary: Get API key from dashboard
      steps:
        - action: Login to dashboard
          description: Visit https://example.com
templates: {}
""")
            result = runner.invoke(main, ["agent", "sync", "--file", str(sf), "--dry-run"])
            assert result.exit_code == 0, result.output
            assert "pwd" in result.output
            assert "api_key" in result.output
            assert "Get API key from dashboard" in result.output
            assert "Summary" in result.output

    def test_nonexistent_file_raises_error(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["agent", "sync", "--file", "nonexistent.yml"])
        assert result.exit_code != 0

    def test_json_output_structure(self, runner: CliRunner) -> None:
        """JSON output always contains all four top-level keys."""
        with TemporaryDirectory() as tmpdir:
            sf = Path(tmpdir) / "Secretfile.yml"
            self._write_secretfile(sf, "  - name: p\n    kind: random_string\n    config: {}")
            result = runner.invoke(
                main, ["agent", "sync", "--file", str(sf), "--json", "--dry-run"]
            )
            assert result.exit_code == 0, result.output
            data = json.loads(result.output)
            for key in (
                "synced_secrets",
                "pending_secrets",
                "failed_secrets",
                "automation_summary",
            ):
                assert key in data

    def test_empty_secretfile(self, runner: CliRunner) -> None:
        """Agent sync succeeds even with no secrets defined."""
        with TemporaryDirectory() as tmpdir:
            sf = Path(tmpdir) / "Secretfile.yml"
            self._write_secretfile(sf, "  []")
            result = runner.invoke(
                main, ["agent", "sync", "--file", str(sf), "--json", "--dry-run"]
            )
            assert result.exit_code == 0, result.output
            data = json.loads(result.output)
            assert data["synced_secrets"] == []
            assert data["pending_secrets"] == {}
            assert data["failed_secrets"] == {}

    def test_manual_only_agent_sync_does_not_create_empty_lockfile(self, runner: CliRunner) -> None:
        """Non-dry-run agent sync should not write an empty skeleton lockfile."""
        with TemporaryDirectory() as tmpdir:
            sf = Path(tmpdir) / "Secretfile.yml"
            lock = Path(tmpdir) / ".gitsecrets.lock"
            sf.write_text("""version: '1.0'
variables: {}
providers: {}
secrets:
  - name: stripe_key
    kind: static
    config: {}
    agent_instructions:
      summary: Sign up for Stripe
      steps:
        - action: Visit https://dashboard.stripe.com/register
          description: Create account
templates: {}
""")

            result = runner.invoke(
                main,
                [
                    "agent",
                    "sync",
                    "--file",
                    str(sf),
                    "--lockfile",
                    str(lock),
                    "--json",
                ],
            )
            assert result.exit_code == 0, result.output
            assert not lock.exists()

    def test_web_host_option_is_ignored_for_safety(self, runner: CliRunner) -> None:
        with TemporaryDirectory() as tmpdir:
            sf = Path(tmpdir) / "Secretfile.yml"
            sf.write_text("""version: '1.0'
variables: {}
providers: {}
secrets:
  - name: stripe_key
    kind: static
    config: {}
    agent_instructions:
      summary: Sign up for Stripe
      steps:
        - action: Visit https://dashboard.stripe.com/register
          description: Create account
templates: {}
""")

            fake_result = AgentSyncResult(
                synced_secrets=[],
                pending_secrets={},
                failed_secrets={},
                already_synced=[],
                automation_summary={},
            )
            with patch("secretzero.agent.AgentSecretSynchronizer") as sync_cls:
                sync_cls.return_value.sync.return_value = fake_result
                result = runner.invoke(
                    main,
                    [
                        "agent",
                        "sync",
                        "--file",
                        str(sf),
                        "--web",
                        "--web-host",
                        "0.0.0.0",
                        "--dry-run",
                    ],
                )
            assert result.exit_code == 0, result.output
            assert "--web-host is deprecated" in result.output
            assert "127.0.0.1" in result.output


def test_secret_supports_automatic_generation_random() -> None:
    s = _make_secret("n", "random_password", {"length": 16})
    assert secret_supports_automatic_generation(s) is True


def test_secret_supports_automatic_generation_static_literal() -> None:
    s = _make_secret("n", "static", {"value": "x"})
    assert secret_supports_automatic_generation(s) is True


def test_secret_supports_automatic_generation_static_needs_prompt() -> None:
    s = _make_secret("n", "static", {"value": None})
    assert secret_supports_automatic_generation(s) is False


def test_secret_supports_automatic_generation_entra_blueprint() -> None:
    s = _make_secret("n", "entra-agent-blueprint", {"provider": "entra_agent_id", "spec": {}})
    assert secret_supports_automatic_generation(s) is True
