"""Tests for provider-specific manual retrieval instructions in generators.

Verifies that:
- BaseGenerator exposes get_manual_instructions() returning None by default
- GitHubPATGenerator returns built-in GitHub PAT instructions
- ScriptGenerator returns built-in script-execution instructions
- StaticGenerator displays instructions before prompting
- SyncEngine passes Secretfile agent_instructions to generators and displays
  them when generation fails
"""

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from secretzero.generators.base import BaseGenerator
from secretzero.generators.github_pat import GitHubPATGenerator
from secretzero.generators.provider_backed import (
    ProviderBackedGenerator,
    _build_provider_manual_steps,
)
from secretzero.generators.script import ScriptGenerator
from secretzero.generators.static import StaticGenerator
from secretzero.models import AgentInstructions, AgentInstructionStep

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_instructions(summary: str = "Test summary") -> AgentInstructions:
    """Create a minimal AgentInstructions object for testing."""
    return AgentInstructions(
        summary=summary,
        steps=[
            AgentInstructionStep(
                action="Do something",
                description="First step description",
            )
        ],
    )


# ---------------------------------------------------------------------------
# BaseGenerator
# ---------------------------------------------------------------------------


class TestBaseGeneratorManualInstructions:
    """Tests for the BaseGenerator manual instructions interface."""

    def test_base_get_manual_instructions_returns_none_by_default(self):
        """get_manual_instructions returns None when no instructions are set."""

        class MinimalGenerator(BaseGenerator):
            def generate(self) -> str:
                return "value"

        gen = MinimalGenerator({})
        assert gen.get_manual_instructions() is None

    def test_manual_instructions_attribute_returned_by_get(self):
        """Setting manual_instructions makes get_manual_instructions return it."""

        class MinimalGenerator(BaseGenerator):
            def generate(self) -> str:
                return "value"

        gen = MinimalGenerator({})
        instructions = _make_instructions()
        gen.manual_instructions = instructions
        assert gen.get_manual_instructions() is instructions

    def test_display_manual_instructions_prints_summary(self, capsys):
        """_display_manual_instructions prints the summary."""
        instructions = _make_instructions("Find this secret in the vault")
        BaseGenerator._display_manual_instructions(instructions)
        out = capsys.readouterr().out
        assert "Find this secret in the vault" in out

    def test_display_manual_instructions_prints_steps(self, capsys):
        """_display_manual_instructions prints each step description and action."""
        instructions = AgentInstructions(
            summary="Summary",
            steps=[
                AgentInstructionStep(
                    action="Run: vault kv get secret/mykey",
                    description="Retrieve from Vault",
                )
            ],
        )
        BaseGenerator._display_manual_instructions(instructions)
        out = capsys.readouterr().out
        assert "Retrieve from Vault" in out
        assert "Run: vault kv get secret/mykey" in out

    def test_display_manual_instructions_prints_prerequisites(self, capsys):
        """_display_manual_instructions prints prerequisites."""
        instructions = AgentInstructions(
            summary="S",
            steps=[],
            prerequisites=["Install the CLI", "Have VPN access"],
        )
        BaseGenerator._display_manual_instructions(instructions)
        out = capsys.readouterr().out
        assert "Install the CLI" in out
        assert "Have VPN access" in out

    def test_display_manual_instructions_prints_optional_fields(self, capsys):
        """_display_manual_instructions prints estimated_time, documentation_url, fallback."""
        instructions = AgentInstructions(
            summary="S",
            steps=[],
            estimated_time="10 minutes",
            documentation_url="https://docs.example.com",
            fallback="Ask your admin",
        )
        BaseGenerator._display_manual_instructions(instructions)
        out = capsys.readouterr().out
        assert "10 minutes" in out
        assert "docs.example" in out  # URL appears without protocol check
        assert "Ask your admin" in out


# ---------------------------------------------------------------------------
# GitHubPATGenerator
# ---------------------------------------------------------------------------


class TestGitHubPATGeneratorManualInstructions:
    """Tests for GitHubPATGenerator built-in manual instructions."""

    def test_returns_agent_instructions_instance(self):
        """get_manual_instructions returns an AgentInstructions object."""
        gen = GitHubPATGenerator({"provider": "github"})
        instructions = gen.get_manual_instructions()
        assert isinstance(instructions, AgentInstructions)

    def test_instructions_mention_github(self):
        """The summary or steps mention GitHub."""
        gen = GitHubPATGenerator({"provider": "github"})
        instructions = gen.get_manual_instructions()
        text = instructions.summary + " ".join(s.description for s in instructions.steps)
        assert "GitHub" in text or "github" in text.lower()

    def test_instructions_include_github_url(self):
        """At least one step action contains a github.com URL."""
        gen = GitHubPATGenerator({"provider": "github"})
        instructions = gen.get_manual_instructions()
        actions = " ".join(s.action for s in instructions.steps if s.action)
        assert "github" in actions.lower()

    def test_permissions_included_in_instructions(self):
        """Configured permissions are reflected in the instructions."""
        gen = GitHubPATGenerator(
            {"provider": "github", "permissions": {"contents": "read", "actions": "write"}}
        )
        instructions = gen.get_manual_instructions()
        text = " ".join(s.action or "" for s in instructions.steps)
        assert "contents" in text
        assert "actions" in text

    def test_repositories_included_in_instructions(self):
        """Configured repositories are reflected in the instructions."""
        gen = GitHubPATGenerator({"provider": "github", "repositories": ["my-org/my-repo"]})
        instructions = gen.get_manual_instructions()
        text = " ".join(s.action or "" for s in instructions.steps)
        assert "my-org/my-repo" in text

    def test_manual_instructions_attribute_takes_precedence(self):
        """Explicitly set manual_instructions take precedence over built-in ones."""
        gen = GitHubPATGenerator({"provider": "github"})
        custom = _make_instructions("Custom instructions")
        gen.manual_instructions = custom
        result = gen.get_manual_instructions()
        assert result is custom
        assert result.summary == "Custom instructions"

    def test_has_documentation_url(self):
        """Built-in instructions include a documentation URL."""
        gen = GitHubPATGenerator({"provider": "github"})
        instructions = gen.get_manual_instructions()
        assert instructions.documentation_url
        assert "github" in instructions.documentation_url.lower()

    def test_has_prerequisites(self):
        """Built-in instructions include prerequisites."""
        gen = GitHubPATGenerator({"provider": "github"})
        instructions = gen.get_manual_instructions()
        assert instructions.prerequisites
        assert len(instructions.prerequisites) > 0


# ---------------------------------------------------------------------------
# ProviderBackedGenerator helpers
# ---------------------------------------------------------------------------


class TestBuildProviderManualSteps:
    """Tests for the _build_provider_manual_steps helper."""

    @pytest.mark.parametrize(
        "provider_kind",
        ["aws", "azure", "vault", "github", "gitlab", "jenkins", "kubernetes"],
    )
    def test_known_providers_return_steps(self, provider_kind):
        """Known provider kinds return a non-empty list of steps."""
        steps = _build_provider_manual_steps(provider_kind, "generate_password", provider_kind)
        assert len(steps) > 0
        assert all(isinstance(s, AgentInstructionStep) for s in steps)

    def test_unknown_provider_returns_generic_steps(self):
        """Unknown provider kinds return generic fallback steps."""
        steps = _build_provider_manual_steps(
            "my_custom_provider", "generate_key", "my_custom_provider"
        )
        assert len(steps) > 0

    def test_aws_steps_mention_console(self):
        """AWS steps mention the AWS console."""
        steps = _build_provider_manual_steps("aws", "generate_password", "aws")
        text = " ".join(s.action or "" for s in steps)
        assert "aws" in text.lower() or "console" in text.lower()

    def test_vault_steps_mention_vault_cli(self):
        """Vault steps mention the vault CLI command."""
        steps = _build_provider_manual_steps("vault", "generate_password", "vault")
        text = " ".join(s.action or "" for s in steps)
        assert "vault" in text.lower()


# ---------------------------------------------------------------------------
# ScriptGenerator
# ---------------------------------------------------------------------------


class TestScriptGeneratorManualInstructions:
    """Tests for ScriptGenerator built-in manual instructions."""

    def test_returns_agent_instructions_instance(self):
        """get_manual_instructions returns an AgentInstructions object."""
        gen = ScriptGenerator({"command": "my-script.sh"})
        instructions = gen.get_manual_instructions()
        assert isinstance(instructions, AgentInstructions)

    def test_command_included_in_instructions(self):
        """The configured command appears in the instructions."""
        gen = ScriptGenerator({"command": "get-api-key.sh", "args": ["--env", "prod"]})
        instructions = gen.get_manual_instructions()
        text = " ".join(s.action or "" for s in instructions.steps)
        assert "get-api-key.sh" in text

    def test_args_included_in_instructions(self):
        """Args are included in the command shown in instructions."""
        gen = ScriptGenerator({"command": "myscript", "args": ["--env", "prod"]})
        instructions = gen.get_manual_instructions()
        text = " ".join(s.action or "" for s in instructions.steps)
        assert "--env" in text
        assert "prod" in text

    def test_manual_instructions_attribute_takes_precedence(self):
        """Explicitly set manual_instructions take precedence over built-in ones."""
        gen = ScriptGenerator({"command": "ignored"})
        custom = _make_instructions("Custom script instructions")
        gen.manual_instructions = custom
        result = gen.get_manual_instructions()
        assert result is custom


# ---------------------------------------------------------------------------
# StaticGenerator – display instructions before prompting
# ---------------------------------------------------------------------------


class TestStaticGeneratorDisplaysInstructions:
    """Tests that StaticGenerator shows instructions before prompting."""

    def test_instructions_displayed_before_prompt(self, capsys):
        """Manual instructions are printed before the value prompt."""
        gen = StaticGenerator({"value": None, "prompt_on_empty": True})
        gen.manual_instructions = _make_instructions("Please retrieve the token from vault")

        with patch("builtins.input", side_effect=["my-secret-value"]):
            value = gen.generate()

        out = capsys.readouterr().out
        assert "Please retrieve the token from vault" in out
        assert value == "my-secret-value"

    def test_no_output_when_no_instructions(self, capsys):
        """No instructions banner is printed when no instructions are set."""
        gen = StaticGenerator({"value": None, "prompt_on_empty": True})
        # no manual_instructions set

        with patch("builtins.input", side_effect=["my-secret"]):
            gen.generate()

        out = capsys.readouterr().out
        assert "MANUAL RETRIEVAL INSTRUCTIONS" not in out

    def test_steps_displayed_before_prompt(self, capsys):
        """Step details appear in the output before the input prompt."""
        gen = StaticGenerator({"value": None, "prompt_on_empty": True})
        gen.manual_instructions = AgentInstructions(
            summary="Retrieve your API key",
            steps=[
                AgentInstructionStep(
                    action="https://example.com/api-keys",
                    description="Open the API keys page",
                )
            ],
        )

        with patch("builtins.input", side_effect=["key-value"]):
            gen.generate()

        out = capsys.readouterr().out
        assert "Open the API keys page" in out
        assert "https://example.com/api-keys" in out


# ---------------------------------------------------------------------------
# SyncEngine – instructions displayed on generation failure
# ---------------------------------------------------------------------------


class TestSyncEngineManualInstructionsOnFailure:
    """Tests that SyncEngine displays instructions when generation fails."""

    def _make_sync_engine(self, kind: str, config: dict):
        """Create a minimal SyncEngine with a single secret."""
        from secretzero.lockfile import Lockfile
        from secretzero.models import Secret, Secretfile
        from secretzero.sync import SyncEngine

        secret = Secret(name="test_secret", kind=kind, config=config)
        secretfile = Secretfile(version="1", secrets=[secret])
        lockfile = Lockfile()
        return SyncEngine(
            secretfile=secretfile,
            lockfile=lockfile,
            hide_input=False,
            prompt_on_empty=False,
        )

    def test_instructions_displayed_on_github_pat_failure(self, capsys):
        """GitHub PAT instructions are shown when the github_pat generator fails."""
        engine = self._make_sync_engine(
            "github_pat",
            {"provider": "github", "permissions": {"contents": "read"}},
        )

        with pytest.raises(Exception):
            engine._generate_secret_value(
                "github_pat",
                {"provider": "github", "permissions": {"contents": "read"}},
                "TEST_SECRET",
            )

        out = capsys.readouterr().out
        assert "MANUAL RETRIEVAL INSTRUCTIONS" in out
        # GitHub-specific content
        assert "github" in out.lower()

    def test_agent_instructions_override_built_in(self, capsys):
        """Secretfile agent_instructions override the built-in generator instructions."""
        from secretzero.lockfile import Lockfile
        from secretzero.models import Secret, Secretfile
        from secretzero.sync import SyncEngine

        custom_instructions = AgentInstructions(
            summary="Custom: retrieve from our internal vault",
            steps=[
                AgentInstructionStep(
                    action="https://vault.internal/path",
                    description="Get token from internal vault",
                )
            ],
        )
        secret = Secret(
            name="test_secret",
            kind="github_pat",
            config={"provider": "github"},
            agent_instructions=custom_instructions,
        )
        secretfile = Secretfile(version="1", secrets=[secret])
        lockfile = Lockfile()
        engine = SyncEngine(
            secretfile=secretfile,
            lockfile=lockfile,
            hide_input=False,
            prompt_on_empty=False,
        )

        with pytest.raises(Exception):
            engine._generate_secret_value(
                "github_pat",
                {"provider": "github"},
                "TEST_SECRET",
                agent_instructions=custom_instructions,
            )

        out = capsys.readouterr().out
        assert "Custom: retrieve from our internal vault" in out

    def test_no_instructions_output_for_random_password(self, capsys):
        """random_password generator (no built-in instructions) produces no banner on success."""
        engine = self._make_sync_engine("random_password", {"length": 16})
        value = engine._generate_secret_value("random_password", {"length": 16}, "TEST_SECRET")
        out = capsys.readouterr().out
        assert "MANUAL RETRIEVAL INSTRUCTIONS" not in out
        assert value  # value was generated

    def test_script_instructions_displayed_on_failure(self, capsys):
        """Script instructions are shown when the script generator fails."""
        engine = self._make_sync_engine(
            "script", {"command": "nonexistent-command-xyz", "shell": False}
        )

        with pytest.raises(Exception):
            engine._generate_secret_value(
                "script",
                {"command": "nonexistent-command-xyz", "shell": False},
                "TEST_SECRET",
            )

        out = capsys.readouterr().out
        assert "MANUAL RETRIEVAL INSTRUCTIONS" in out
        assert "nonexistent-command-xyz" in out
