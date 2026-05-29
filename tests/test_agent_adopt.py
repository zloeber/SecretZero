"""Tests for agent adopt/list integrations."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from secretzero.cli import main
from secretzero.integrations.adopt import run_agent_adopt, run_agent_list
from secretzero.integrations.scan_utils import dotenv_key_is_set
from secretzero.integrations.registry import resolve_agent_install


def test_dotenv_key_is_set_without_leaking_value(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    secret = "super-secret-value-12345"
    env_path.write_text(f"OPENROUTER_API_KEY={secret}\nEMPTY=\n", encoding="utf-8")
    assert dotenv_key_is_set(env_path, "OPENROUTER_API_KEY") is True
    assert dotenv_key_is_set(env_path, "EMPTY") is False
    assert dotenv_key_is_set(env_path, "MISSING") is False


def test_resolve_hermes_install(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    home.mkdir()
    (home / ".env").write_text("OPENROUTER_API_KEY=abc\n", encoding="utf-8")
    (home / "cli-config.yaml").write_text("model:\n  default: test\n", encoding="utf-8")
    resolved = resolve_agent_install(target="hermes", source_dir=home)
    assert resolved is not None
    adapter, root = resolved
    assert adapter.target_id == "hermes"
    assert root == home.resolve()


def test_run_agent_adopt_writes_secretfile(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    home.mkdir()
    (home / ".env").write_text("GITHUB_TOKEN=gh_test_token_value\n", encoding="utf-8")
    (home / "config.yaml").write_text("agent:\n  max_turns: 1\n", encoding="utf-8")

    result = run_agent_adopt(target="hermes", source_dir=home, template=True)
    assert result.generated is True
    assert result.target == "hermes"
    secretfile = home / "Secretfile.yml"
    assert secretfile.is_file()
    payload = secretfile.read_text(encoding="utf-8")
    assert "gh_test_token_value" not in payload
    assert "github_token" in payload
    assert (home / "agent.env.template").is_file()


def test_run_agent_adopt_dry_run_json_no_write(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    home.mkdir()
    (home / ".env").write_text("OPENROUTER_API_KEY=abc\n", encoding="utf-8")
    (home / "cli-config.yaml").write_text("model: {}\n", encoding="utf-8")

    result = run_agent_adopt(target="hermes", source_dir=home, dry_run=True)
    assert result.generated is False
    assert not (home / "Secretfile.yml").exists()
    assert any(item["env_key"] == "OPENROUTER_API_KEY" for item in result.discovered)


def test_run_agent_adopt_merge_existing(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    home.mkdir()
    (home / "cli-config.yaml").write_text("model: {}\n", encoding="utf-8")
    (home / ".env").write_text("OPENROUTER_API_KEY=abc\n", encoding="utf-8")
    (home / "Secretfile.yml").write_text(
        yaml.dump(
            {
                "secrets": [
                    {
                        "name": "existing_secret",
                        "kind": "static",
                        "config": {"default": None},
                        "targets": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = run_agent_adopt(target="hermes", source_dir=home)
    assert result.generated is True
    doc = yaml.safe_load((home / "Secretfile.yml").read_text(encoding="utf-8"))
    names = {item["name"] for item in doc["secrets"]}
    assert "existing_secret" in names
    assert "openrouter_api_key" in names


def test_run_agent_adopt_no_present_secrets(tmp_path: Path) -> None:
    home = tmp_path / "hermes"
    home.mkdir()
    (home / "cli-config.yaml").write_text("model: {}\n", encoding="utf-8")
    (home / ".env").write_text("# empty\n", encoding="utf-8")
    result = run_agent_adopt(target="hermes", source_dir=home)
    assert result.generated is False
    assert result.reason is not None


def test_agent_list_cli_json() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["agent", "list", "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "detections" in payload
    assert "registered_targets" in payload


def test_agent_adopt_cli_json_no_secret_leak(tmp_path: Path, monkeypatch: object) -> None:
    home = tmp_path / "hermes"
    home.mkdir()
    (home / ".env").write_text("NOUS_API_KEY=nous-secret-value\n", encoding="utf-8")
    (home / "cli-config.yaml").write_text("model: {}\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "agent",
            "adopt",
            "--target",
            "hermes",
            "--source-dir",
            str(home),
            "--dry-run",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    assert "nous-secret-value" not in result.output
    payload = json.loads(result.output)
    assert payload["target"] == "hermes"
    assert payload["discovered"]


def test_agent_backup_alias_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["agent", "backup", "--help"])
    assert result.exit_code == 0
    assert "Alias" in result.output or "adopt" in result.output


def test_run_agent_list_returns_detections_shape() -> None:
    result = run_agent_list()
    assert result.generated is False
    assert isinstance(result.detections, list)
