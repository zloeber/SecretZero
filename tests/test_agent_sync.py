"""Tests for agent-guided secret synchronisation."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from click.testing import CliRunner

from secretzero.agent import AgentSecretSynchronizer, AgentSyncResult, detect_automation_level
from secretzero.cli import main
from secretzero.models import (
    AgentInstructions,
    AgentInstructionStep,
    AutomationLevel,
    Secret,
    Secretfile,
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
        sf = _make_secretfile([_make_secret("pwd", "random_password")])
        sync = AgentSecretSynchronizer(sf, dry_run=True)
        result = sync.sync()
        assert "pwd" in result.synced_secrets
        assert len(result.pending_secrets) == 0
        assert len(result.failed_secrets) == 0

    def test_random_string_is_auto_synced(self) -> None:
        sf = _make_secretfile([_make_secret("tok", "random_string")])
        result = AgentSecretSynchronizer(sf, dry_run=True).sync()
        assert "tok" in result.synced_secrets

    def test_static_with_value_is_auto_synced(self) -> None:
        sf = _make_secretfile([_make_secret("k", "static", config={"value": "secret123"})])
        result = AgentSecretSynchronizer(sf, dry_run=True).sync()
        assert "k" in result.synced_secrets

    def test_static_without_value_with_instructions_goes_to_pending(self) -> None:
        """Static secret with no value but with instructions ends up in pending."""
        instructions = AgentInstructions(
            summary="Manual setup required",
            steps=[AgentInstructionStep(action="Visit site", description="Sign up")],
        )
        sf = _make_secretfile([_make_secret("api_key", "static", agent_instructions=instructions)])
        result = AgentSecretSynchronizer(sf, dry_run=True).sync()
        assert "api_key" in result.pending_secrets
        assert result.pending_secrets["api_key"].summary == "Manual setup required"

    def test_static_without_value_or_instructions_goes_to_failed(self) -> None:
        """Static secret with no value and no instructions ends up in failed."""
        sf = _make_secretfile([_make_secret("bare", "static")])
        result = AgentSecretSynchronizer(sf, dry_run=True).sync()
        assert "bare" in result.failed_secrets

    def test_mixed_secrets(self) -> None:
        """Mixed auto, pending, and failed secrets are correctly classified."""
        instructions = AgentInstructions(summary="Manual", steps=[])
        secrets = [
            _make_secret("auto1", "random_password"),
            _make_secret("auto2", "random_string"),
            _make_secret("manual1", "static", agent_instructions=instructions),
            _make_secret("failed1", "static"),  # no value, no instructions
        ]
        sf = _make_secretfile(secrets)
        result = AgentSecretSynchronizer(sf, dry_run=True).sync()
        assert set(result.synced_secrets) == {"auto1", "auto2"}
        assert "manual1" in result.pending_secrets
        assert "failed1" in result.failed_secrets
        assert result.automation_summary["fully_synced"] == 2
        assert result.automation_summary["requires_intervention"] == 1
        assert result.automation_summary["failed"] == 1

    def test_automation_summary_keys_are_always_present(self) -> None:
        sf = _make_secretfile([])
        result = AgentSecretSynchronizer(sf, dry_run=True).sync()
        assert "fully_synced" in result.automation_summary
        assert "requires_intervention" in result.automation_summary
        assert "failed" in result.automation_summary


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
