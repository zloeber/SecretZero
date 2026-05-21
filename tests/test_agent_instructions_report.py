"""Tests for agent instructions report collection and rendering."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from click.testing import CliRunner

from secretzero.agent_instructions_report import (
    InstructionScope,
    build_instructions_json_payload,
    collect_instruction_entries,
    instruction_entries_from_mapping,
    render_instruction_entries,
    render_instructions_console,
)
from secretzero.cli import console, main
from secretzero.lockfile import Lockfile
from secretzero.models import (
    AgentInstructions,
    AgentInstructionStep,
    Secret,
    Secretfile,
)


def _make_instructions(summary: str = "Do the thing") -> AgentInstructions:
    return AgentInstructions(
        summary=summary,
        steps=[
            AgentInstructionStep(
                action="Run setup",
                description="Prepare environment",
            ),
            AgentInstructionStep(
                action="Copy value",
                description="Save securely",
            ),
        ],
        prerequisites=["Admin access"],
        estimated_time="5 minutes",
    )


def _make_secret(
    name: str,
    *,
    kind: str = "static",
    config: dict | None = None,
    instructions: AgentInstructions | None = None,
) -> Secret:
    return Secret(
        name=name,
        kind=kind,
        config=config or {},
        agent_instructions=instructions,
    )


class TestCollectInstructionEntries:
    def test_pending_includes_manual_secret_not_in_lockfile(self) -> None:
        secretfile = Secretfile(
            secrets=[_make_secret("manual", instructions=_make_instructions())],
        )
        lock = Lockfile()
        entries = collect_instruction_entries(
            secretfile,
            lock,
            scope=InstructionScope.PENDING,
        )
        assert [entry.secret_name for entry in entries] == ["manual"]

    def test_pending_excludes_secret_already_in_lockfile(self) -> None:
        secretfile = Secretfile(
            secrets=[_make_secret("manual", instructions=_make_instructions())],
        )
        lock = Lockfile()
        lock.add_secret("manual", "already-set")
        entries = collect_instruction_entries(
            secretfile,
            lock,
            scope=InstructionScope.PENDING,
        )
        assert entries == []

    def test_pending_excludes_auto_syncable_secret(self) -> None:
        secretfile = Secretfile(
            secrets=[
                _make_secret(
                    "pwd",
                    kind="random_password",
                    config={"length": 16},
                    instructions=_make_instructions("Should not appear"),
                )
            ],
        )
        entries = collect_instruction_entries(
            secretfile,
            Lockfile(),
            scope=InstructionScope.PENDING,
        )
        assert entries == []

    def test_all_includes_locked_and_auto_capable_when_instructions_exist(self) -> None:
        instructions = _make_instructions("Always show")
        secretfile = Secretfile(
            secrets=[
                _make_secret("manual", instructions=instructions),
                _make_secret(
                    "pwd",
                    kind="random_password",
                    config={"length": 16},
                    instructions=instructions,
                ),
            ],
        )
        lock = Lockfile()
        lock.add_secret("manual", "value")
        entries = collect_instruction_entries(
            secretfile,
            lock,
            scope=InstructionScope.ALL,
        )
        assert [entry.secret_name for entry in entries] == ["manual", "pwd"]

    def test_secret_filter_limits_results(self) -> None:
        secretfile = Secretfile(
            secrets=[
                _make_secret("one", instructions=_make_instructions("One")),
                _make_secret("two", instructions=_make_instructions("Two")),
            ],
        )
        entries = collect_instruction_entries(
            secretfile,
            Lockfile(),
            scope=InstructionScope.ALL,
            secret_names=frozenset({"two"}),
        )
        assert [entry.secret_name for entry in entries] == ["two"]
        assert entries[0].instructions.summary == "Two"


class TestRenderInstructionsConsole:
    def test_renders_numbered_steps(self, capsys: pytest.CaptureFixture[str]) -> None:
        entries = [
            collect_instruction_entries(
                Secretfile(secrets=[_make_secret("api_key", instructions=_make_instructions())]),
                Lockfile(),
                scope=InstructionScope.ALL,
            )[0]
        ]
        render_instructions_console(entries, console, scope=InstructionScope.ALL)
        out = capsys.readouterr().out
        assert "api_key" in out
        assert "Do the thing" in out
        assert "1." in out
        assert "Run setup" in out
        assert "Prepare environment" in out

    def test_detailed_includes_optional_fields(self, capsys: pytest.CaptureFixture[str]) -> None:
        entries = [
            collect_instruction_entries(
                Secretfile(secrets=[_make_secret("api_key", instructions=_make_instructions())]),
                Lockfile(),
                scope=InstructionScope.ALL,
            )[0]
        ]
        render_instructions_console(
            entries,
            console,
            detailed=True,
            scope=InstructionScope.ALL,
        )
        out = capsys.readouterr().out
        assert "Prerequisites" in out
        assert "Admin access" in out
        assert "Estimated time" in out

    def test_empty_pending_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        render_instructions_console([], console, scope=InstructionScope.PENDING)
        out = capsys.readouterr().out
        assert "No pending secrets with agent instructions" in out


class TestInstructionEntriesFromMapping:
    def test_builds_entries_from_pending_mapping(self) -> None:
        instructions = _make_instructions("Mapped")
        entries = instruction_entries_from_mapping({"api_key": instructions})
        assert len(entries) == 1
        assert entries[0].secret_name == "api_key"
        assert entries[0].instructions is instructions


class TestSharedRendererParity:
    def test_agent_sync_pending_matches_instructions_command(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        instructions = _make_instructions("Shared layout")
        pending = instruction_entries_from_mapping({"stripe_key": instructions})

        render_instruction_entries(
            pending,
            console,
            detailed=False,
            header="\n[bold yellow]pending header[/bold yellow]",
        )
        sync_out = capsys.readouterr().out

        render_instructions_console(
            [
                collect_instruction_entries(
                    Secretfile(secrets=[_make_secret("stripe_key", instructions=instructions)]),
                    Lockfile(),
                    scope=InstructionScope.ALL,
                )[0]
            ],
            console,
            scope=InstructionScope.ALL,
        )
        instructions_out = capsys.readouterr().out

        for snippet in ("Shared layout", "1.", "Run setup", "Prepare environment"):
            assert snippet in sync_out
            assert snippet in instructions_out


class TestBuildInstructionsJsonPayload:
    def test_concise_payload_omits_optional_fields(self) -> None:
        entries = [
            collect_instruction_entries(
                Secretfile(secrets=[_make_secret("api_key", instructions=_make_instructions())]),
                Lockfile(),
                scope=InstructionScope.ALL,
            )[0]
        ]
        payload = build_instructions_json_payload(
            entries,
            scope=InstructionScope.ALL,
            detailed=False,
        )
        secret_payload = payload["secrets"]["api_key"]
        assert "summary" in secret_payload
        assert "steps" in secret_payload
        assert "prerequisites" not in secret_payload
        assert payload["total"] == 1
        assert payload["scope"] == "all"

    def test_detailed_payload_includes_optional_fields(self) -> None:
        entries = [
            collect_instruction_entries(
                Secretfile(secrets=[_make_secret("api_key", instructions=_make_instructions())]),
                Lockfile(),
                scope=InstructionScope.ALL,
            )[0]
        ]
        payload = build_instructions_json_payload(
            entries,
            scope=InstructionScope.PENDING,
            detailed=True,
        )
        secret_payload = payload["secrets"]["api_key"]
        assert secret_payload["prerequisites"] == ["Admin access"]
        assert secret_payload["estimated_time"] == "5 minutes"


class TestAgentInstructionsCli:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_help_output(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["agent", "instructions", "--help"])
        assert result.exit_code == 0
        assert "agent instructions" in result.output.lower() or "instructions" in result.output

    def test_pending_default(self, runner: CliRunner) -> None:
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
            result = runner.invoke(main, ["agent", "instructions", "--file", str(sf)])
            assert result.exit_code == 0, result.output
            assert "stripe_key" in result.output
            assert "Sign up for Stripe" in result.output
            assert "1." in result.output

    def test_all_flag_includes_locked_secret(self, runner: CliRunner) -> None:
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
        - action: Visit dashboard
          description: Create account
templates: {}
""")
            lockfile = Lockfile()
            lockfile.add_secret("stripe_key", "existing-value")
            lockfile.save(lock)
            pending = runner.invoke(
                main,
                ["agent", "instructions", "--file", str(sf), "--lockfile", str(lock)],
            )
            assert pending.exit_code == 0, pending.output
            assert "No pending secrets with agent instructions" in pending.output

            all_result = runner.invoke(
                main,
                [
                    "agent",
                    "instructions",
                    "--file",
                    str(sf),
                    "--lockfile",
                    str(lock),
                    "--all",
                ],
            )
            assert all_result.exit_code == 0, all_result.output
            assert "stripe_key" in all_result.output
            assert "Sign up for Stripe" in all_result.output

    def test_json_output(self, runner: CliRunner) -> None:
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
        - action: Visit dashboard
          description: Create account
templates: {}
""")
            result = runner.invoke(
                main,
                ["agent", "instructions", "--file", str(sf), "--format", "json"],
            )
            assert result.exit_code == 0, result.output
            data = json.loads(result.output)
            assert data["scope"] == "pending"
            assert data["secrets"]["stripe_key"]["summary"] == "Sign up for Stripe"
