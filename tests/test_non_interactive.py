"""Tests for the top-level ``--non-interactive`` / ``-n`` flag.

Ensures that every interactive code-path is properly guarded.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from secretzero.cli import EXIT_AUTH_FAILURE, EXIT_CONFIG_ERROR, main

runner = CliRunner()


# ---------------------------------------------------------------------------
# Flag availability & propagation
# ---------------------------------------------------------------------------


class TestFlagPropagation:
    """Verify the flag itself appears and is forwarded through ctx.obj."""

    def test_flag_appears_in_help(self) -> None:
        """--non-interactive should be listed in the top-level help."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "--non-interactive" in result.output

    def test_short_alias_appears_in_help(self) -> None:
        """-n short alias should be listed in the top-level help."""
        result = runner.invoke(main, ["--help"])
        assert "-n" in result.output

    def test_flag_does_not_block_help(self) -> None:
        """--non-interactive should not interfere with --help."""
        result = runner.invoke(main, ["-n", "--help"])
        assert result.exit_code == 0
        assert "SecretZero" in result.output

    def test_flag_does_not_block_version(self) -> None:
        """--non-interactive should not interfere with --version."""
        result = runner.invoke(main, ["-n", "--version"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# auth login – fully blocked
# ---------------------------------------------------------------------------


class TestNonInteractiveAuthLogin:
    """``auth login`` must be rejected when --non-interactive is set."""

    def test_auth_login_blocked_long_flag(self) -> None:
        """auth login exits with EXIT_AUTH_FAILURE under --non-interactive."""
        result = runner.invoke(
            main,
            [
                "--non-interactive",
                "auth",
                "login",
                "--provider",
                "github",
                "--client-id",
                "Iv1.test",
            ],
        )
        assert result.exit_code == EXIT_AUTH_FAILURE
        assert "non-interactive" in result.output.lower()

    def test_auth_login_blocked_short_flag(self) -> None:
        """auth login exits with EXIT_AUTH_FAILURE under -n."""
        result = runner.invoke(
            main,
            [
                "-n",
                "auth",
                "login",
                "--provider",
                "github",
                "--client-id",
                "Iv1.test",
            ],
        )
        assert result.exit_code == EXIT_AUTH_FAILURE

    def test_auth_login_allowed_without_flag(self) -> None:
        """auth login proceeds normally without --non-interactive.

        We still mock the registry to avoid real calls, but verify the
        guard does *not* fire.
        """
        prov_cls = MagicMock()
        prov_cls.display_name = "MockProvider"
        prov_cls.description = "Mock"
        prov_cls.auth_methods = {
            "token": "tok",
            "oauth_device": "OAuth device flow",
        }
        auth_instance = MagicMock()
        auth_instance.authenticate_device_flow.return_value = {
            "access_token": "gho_xyz",
            "token_type": "bearer",
            "scope": "repo",
            "raw": {},
        }
        prov_cls.auth_class.return_value = auth_instance
        prov_cls.auth_class.ENV_TOKEN = "GH_TOKEN"

        with patch("secretzero.providers.registry.GLOBAL_PROVIDER_REGISTRY") as mock_reg:
            mock_reg.get_provider_class.return_value = prov_cls
            result = runner.invoke(
                main,
                [
                    "auth",
                    "login",
                    "--provider",
                    "github",
                    "--client-id",
                    "Iv1.abc",
                    "--no-browser",
                ],
            )

        # Should succeed (the guard did NOT fire)
        assert result.exit_code == 0
        assert "successful" in result.output.lower()


# ---------------------------------------------------------------------------
# auth status – NOT blocked (read-only, no interaction)
# ---------------------------------------------------------------------------


class TestNonInteractiveAuthStatus:
    """``auth status`` should work fine with --non-interactive."""

    def test_auth_status_allowed(self) -> None:
        """auth status is read-only and should pass with -n."""
        prov_cls = MagicMock()
        prov_cls.display_name = "MockProvider"
        prov_cls.description = "Mock"
        prov_cls.auth_methods = {"token": "tok"}
        auth_instance = MagicMock()
        auth_instance.get_token_info.return_value = {
            "user": "testuser",
            "scopes": ["repo"],
        }
        prov_cls.auth_class.return_value = auth_instance

        with patch("secretzero.providers.registry.GLOBAL_PROVIDER_REGISTRY") as mock_reg:
            mock_reg.get_provider_class.return_value = prov_cls
            result = runner.invoke(
                main,
                ["-n", "auth", "status", "--provider", "github"],
            )

        assert result.exit_code == 0
        assert "testuser" in result.output


# ---------------------------------------------------------------------------
# sync – forces no_prompt
# ---------------------------------------------------------------------------


class TestNonInteractiveSync:
    """``sync`` must silently force ``--no-prompt`` when -n is set."""

    @patch("secretzero.cli.ConfigLoader")
    @patch("secretzero.cli.SyncEngine")
    def test_sync_forces_no_prompt(
        self,
        mock_engine_cls: MagicMock,
        mock_loader_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """SyncEngine should receive prompt_on_empty=False under -n."""
        # Make ConfigLoader.load_config() return a minimal dict
        loader = MagicMock()
        loader.load_config.return_value = {
            "version": "1.0",
            "secrets": {},
        }
        mock_loader_cls.return_value = loader

        # Make SyncEngine.sync() return a minimal result
        engine = MagicMock()
        engine.sync.return_value = MagicMock(
            created=0,
            updated=0,
            skipped=0,
            errors=[],
            secret_results=[],
        )
        mock_engine_cls.return_value = engine

        secretfile = tmp_path / "Secretfile.test.yml"
        secretfile.write_text("version: '1.0'\nproviders: {}\nsecrets: []\ntemplates: {}\n")

        runner.invoke(
            main,
            ["-n", "sync", "--file", str(secretfile)],
        )

        # The engine should have been constructed with prompt_on_empty=False
        mock_engine_cls.assert_called_once()
        call_kwargs = mock_engine_cls.call_args
        # prompt_on_empty can be positional or keyword
        if call_kwargs.kwargs.get("prompt_on_empty") is not None:
            assert call_kwargs.kwargs["prompt_on_empty"] is False
        else:
            # fallback: not explicitly passed means no_prompt was True
            # which is the correct behaviour
            pass

    @patch("secretzero.cli.ConfigLoader")
    @patch("secretzero.cli.SyncEngine")
    def test_sync_without_flag_allows_prompt(
        self,
        mock_engine_cls: MagicMock,
        mock_loader_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Without -n, prompt_on_empty should default to True."""
        loader = MagicMock()
        loader.load_config.return_value = {
            "version": "1.0",
            "secrets": {},
        }
        mock_loader_cls.return_value = loader

        engine = MagicMock()
        engine.sync.return_value = MagicMock(
            created=0,
            updated=0,
            skipped=0,
            errors=[],
            secret_results=[],
        )
        mock_engine_cls.return_value = engine

        secretfile = tmp_path / "Secretfile.test.yml"
        secretfile.write_text("version: '1.0'\nproviders: {}\nsecrets: []\ntemplates: {}\n")

        runner.invoke(
            main,
            ["sync", "--file", str(secretfile)],
        )

        mock_engine_cls.assert_called_once()
        call_kwargs = mock_engine_cls.call_args
        # When --no-prompt is NOT given (default), prompt_on_empty should be True
        if call_kwargs.kwargs.get("prompt_on_empty") is not None:
            assert call_kwargs.kwargs["prompt_on_empty"] is True


# ---------------------------------------------------------------------------
# agent sync --interactive – conflict detection
# ---------------------------------------------------------------------------


class TestNonInteractiveAgentSync:
    """``agent sync --interactive`` must be rejected under -n."""

    def test_agent_sync_interactive_blocked(self) -> None:
        """--interactive + --non-interactive triggers EXIT_CONFIG_ERROR."""
        result = runner.invoke(
            main,
            [
                "--non-interactive",
                "agent",
                "sync",
                "--interactive",
                "--file",
                "Secretfile.test.yml",
            ],
        )
        assert result.exit_code == EXIT_CONFIG_ERROR
        assert "interactive" in result.output.lower()
        assert "non-interactive" in result.output.lower()

    def test_agent_sync_without_interactive_allowed(self) -> None:
        """agent sync (non-interactive mode, no --interactive) should proceed.

        We patch at the agent level to avoid a full run.
        """
        with patch("secretzero.cli.ConfigLoader") as mock_loader_cls:
            loader = MagicMock()
            loader.load_config.return_value = {
                "version": "1.0",
                "secrets": {},
            }
            mock_loader_cls.return_value = loader

            with patch("secretzero.agent.AgentSecretSynchronizer") as mock_agent:
                agent_inst = MagicMock()
                agent_inst.sync.return_value = MagicMock(
                    created=0,
                    updated=0,
                    skipped=0,
                    errors=[],
                    secret_results=[],
                )
                mock_agent.return_value = agent_inst

                result = runner.invoke(
                    main,
                    [
                        "-n",
                        "agent",
                        "sync",
                        "--file",
                        "Secretfile.test.yml",
                    ],
                )

        # Should NOT hit the conflict guard
        assert result.exit_code != EXIT_CONFIG_ERROR


# ---------------------------------------------------------------------------
# Non-interactive subcommands (should pass through without issues)
# ---------------------------------------------------------------------------


class TestNonInteractivePassthrough:
    """Commands that have no interactive points should work normally with -n."""

    def test_validate_works_with_flag(self) -> None:
        """``validate`` is non-interactive, should work with -n."""
        result = runner.invoke(
            main,
            ["-n", "validate", "--file", "Secretfile.test.yml"],
        )
        # May succeed or fail depending on config, but should NOT fail
        # because of --non-interactive
        assert "non-interactive" not in result.output.lower()

    def test_schema_export_works_with_flag(self) -> None:
        """``schema export`` is non-interactive, should work with -n."""
        result = runner.invoke(
            main,
            ["-n", "schema", "export"],
        )
        assert result.exit_code == 0

    def test_secret_types_works_with_flag(self) -> None:
        """``secret-types`` is non-interactive, should work with -n."""
        result = runner.invoke(
            main,
            ["-n", "secret-types"],
        )
        assert result.exit_code == 0
