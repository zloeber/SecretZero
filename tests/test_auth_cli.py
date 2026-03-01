"""Tests for the ``secretzero auth`` CLI group (login + status)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from secretzero.cli import main

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

runner = CliRunner()


def _mock_provider_class(
    *,
    has_oauth: bool = True,
    display_name: str = "MockProvider",
    env_token: str = "MOCK_TOKEN",
) -> MagicMock:
    """Build a fake provider class with the expected class attributes."""
    cls = MagicMock()
    cls.display_name = display_name
    cls.description = "Mock provider"
    cls.auth_methods = {"token": "Use token"}
    if has_oauth:
        cls.auth_methods["oauth_device"] = "Interactive OAuth device flow"

    auth_cls = MagicMock()
    auth_cls.ENV_TOKEN = env_token
    cls.auth_class = auth_cls

    return cls


# ---------------------------------------------------------------------------
# auth login
# ---------------------------------------------------------------------------


class TestAuthLogin:
    """Tests for ``secretzero auth login``."""

    def test_unknown_provider(self) -> None:
        """Unknown provider name aborts."""
        with patch(
            "secretzero.cli.GLOBAL_PROVIDER_REGISTRY",
            create=True,
        ):
            result = runner.invoke(
                main,
                ["auth", "login", "--provider", "nonexistent", "--client-id", "x"],
            )
        assert result.exit_code != 0

    def test_provider_without_oauth(self) -> None:
        """Provider that does not list oauth_device aborts."""
        prov_cls = _mock_provider_class(has_oauth=False)

        with patch("secretzero.providers.registry.GLOBAL_PROVIDER_REGISTRY") as mock_reg:
            mock_reg.get_provider_class.return_value = prov_cls
            result = runner.invoke(
                main,
                ["auth", "login", "--provider", "nooauth", "--client-id", "x"],
            )

        assert result.exit_code != 0
        assert "does not support" in result.output

    def test_successful_login_prints_token(self) -> None:
        """Successful device flow prints a masked token."""
        prov_cls = _mock_provider_class()
        auth_instance = MagicMock()
        auth_instance.authenticate_device_flow.return_value = {
            "access_token": "gho_test_token_value",
            "token_type": "bearer",
            "scope": "repo,workflow",
            "raw": {},
        }
        prov_cls.auth_class.return_value = auth_instance

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

        assert result.exit_code == 0
        assert "successful" in result.output.lower()
        assert "repo,workflow" in result.output

    def test_save_to_creates_file(self, tmp_path: Path) -> None:
        """--save-to writes the token to the specified file."""
        prov_cls = _mock_provider_class()
        auth_instance = MagicMock()
        auth_instance.authenticate_device_flow.return_value = {
            "access_token": "gho_saved",
            "token_type": "bearer",
            "scope": "repo",
            "raw": {},
        }
        prov_cls.auth_class.return_value = auth_instance

        env_file = tmp_path / ".env"

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
                    "--save-to",
                    str(env_file),
                ],
            )

        assert result.exit_code == 0
        contents = env_file.read_text()
        assert "MOCK_TOKEN=gho_saved" in contents

    def test_save_to_replaces_existing_entry(self, tmp_path: Path) -> None:
        """--save-to replaces an existing KEY=old line."""
        prov_cls = _mock_provider_class()
        auth_instance = MagicMock()
        auth_instance.authenticate_device_flow.return_value = {
            "access_token": "gho_new",
            "token_type": "bearer",
            "scope": "",
            "raw": {},
        }
        prov_cls.auth_class.return_value = auth_instance

        env_file = tmp_path / ".env"
        env_file.write_text("OTHER=keep\nMOCK_TOKEN=old_value\nANOTHER=also_keep\n")

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
                    "--save-to",
                    str(env_file),
                ],
            )

        assert result.exit_code == 0
        contents = env_file.read_text()
        assert "MOCK_TOKEN=gho_new" in contents
        assert "MOCK_TOKEN=old_value" not in contents
        assert "OTHER=keep" in contents
        assert "ANOTHER=also_keep" in contents

    def test_custom_env_var(self, tmp_path: Path) -> None:
        """--env-var overrides the default variable name."""
        prov_cls = _mock_provider_class()
        auth_instance = MagicMock()
        auth_instance.authenticate_device_flow.return_value = {
            "access_token": "gho_custom",
            "token_type": "bearer",
            "scope": "",
            "raw": {},
        }
        prov_cls.auth_class.return_value = auth_instance

        env_file = tmp_path / ".env"

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
                    "--save-to",
                    str(env_file),
                    "--env-var",
                    "MY_GH_TOKEN",
                ],
            )

        assert result.exit_code == 0
        contents = env_file.read_text()
        assert "MY_GH_TOKEN=gho_custom" in contents

    def test_scopes_passed_through(self) -> None:
        """--scopes CSV is split and forwarded to authenticate_device_flow."""
        prov_cls = _mock_provider_class()
        auth_instance = MagicMock()
        auth_instance.authenticate_device_flow.return_value = {
            "access_token": "gho_scoped",
            "token_type": "bearer",
            "scope": "read:org",
            "raw": {},
        }
        prov_cls.auth_class.return_value = auth_instance

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
                    "--scopes",
                    "read:org,admin:repo_hook",
                    "--no-browser",
                ],
            )

        assert result.exit_code == 0
        auth_instance.authenticate_device_flow.assert_called_once()
        call_kwargs = auth_instance.authenticate_device_flow.call_args
        assert call_kwargs.kwargs["scopes"] == ["read:org", "admin:repo_hook"]

    def test_auth_failure_exits(self) -> None:
        """RuntimeError from device flow causes non-zero exit."""
        prov_cls = _mock_provider_class()
        auth_instance = MagicMock()
        auth_instance.authenticate_device_flow.side_effect = RuntimeError("auth boom")
        prov_cls.auth_class.return_value = auth_instance

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

        assert result.exit_code != 0
        assert "auth boom" in result.output


# ---------------------------------------------------------------------------
# auth status
# ---------------------------------------------------------------------------


class TestAuthStatus:
    """Tests for ``secretzero auth status``."""

    def test_text_output(self) -> None:
        """Default text format prints key-value pairs."""
        prov_cls = _mock_provider_class()
        auth_instance = MagicMock()
        auth_instance.get_token_info.return_value = {
            "user": "octocat",
            "scopes": ["repo", "workflow"],
            "token_type": "PAT",
        }
        prov_cls.auth_class.return_value = auth_instance

        with patch("secretzero.providers.registry.GLOBAL_PROVIDER_REGISTRY") as mock_reg:
            mock_reg.get_provider_class.return_value = prov_cls
            result = runner.invoke(
                main,
                ["auth", "status", "--provider", "github"],
            )

        assert result.exit_code == 0
        assert "octocat" in result.output
        assert "repo" in result.output

    def test_json_output(self) -> None:
        """JSON format outputs valid JSON."""
        prov_cls = _mock_provider_class()
        auth_instance = MagicMock()
        auth_instance.get_token_info.return_value = {
            "user": "octocat",
            "scopes": ["repo"],
        }
        prov_cls.auth_class.return_value = auth_instance

        with patch("secretzero.providers.registry.GLOBAL_PROVIDER_REGISTRY") as mock_reg:
            mock_reg.get_provider_class.return_value = prov_cls
            result = runner.invoke(
                main,
                ["auth", "status", "--provider", "github", "--format", "json"],
            )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["user"] == "octocat"

    def test_unknown_provider(self) -> None:
        """Unknown provider aborts."""
        with patch("secretzero.providers.registry.GLOBAL_PROVIDER_REGISTRY") as mock_reg:
            mock_reg.get_provider_class.return_value = None
            result = runner.invoke(
                main,
                ["auth", "status", "--provider", "nope"],
            )

        assert result.exit_code != 0

    def test_no_token_exits(self) -> None:
        """RuntimeError from get_token_info causes non-zero exit."""
        prov_cls = _mock_provider_class()
        auth_instance = MagicMock()
        auth_instance.get_token_info.side_effect = RuntimeError("no token")
        prov_cls.auth_class.return_value = auth_instance

        with patch("secretzero.providers.registry.GLOBAL_PROVIDER_REGISTRY") as mock_reg:
            mock_reg.get_provider_class.return_value = prov_cls
            result = runner.invoke(
                main,
                ["auth", "status", "--provider", "github"],
            )

        assert result.exit_code != 0
        assert "no token" in result.output
