"""Tests for secretzero add / new."""

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner
from fastapi.testclient import TestClient

from secretzero.api.app import create_app
from secretzero.api.auth import generate_api_key
from secretzero.cli import main
from secretzero.secret_author import SecretAuthorError, parse_target_spec, reject_plaintext_static

BASE = """\
# yaml-language-server: $schema=https://example.invalid/Secretfile.schema.json
# keep this comment
providers:
  local:
    kind: local
    config: {}
secrets:
  - name: existing_password
    kind: random_password
    config:
      length: 16
    rotation_period: 30d
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
"""


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _invoke(runner: CliRunner, args: list[str]):
    return runner.invoke(main, args)


def test_add_creates_secret_and_preserves_comment(runner: CliRunner, tmp_path: Path) -> None:
    secretfile = tmp_path / "Secretfile.yml"
    secretfile.write_text(BASE, encoding="utf-8")
    result = _invoke(
        runner,
        [
            "add",
            "api_token",
            "-f",
            str(secretfile),
            "--kind",
            "random_string",
            "--create",
            "--target",
            "provider=local,kind=file,path=.env.local,format=dotenv",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["action"] == "created"
    assert payload["generator_kind"] == "random_string"
    assert "config" not in payload
    text = secretfile.read_text(encoding="utf-8")
    assert "keep this comment" in text
    doc = yaml.safe_load(text)
    created = next(item for item in doc["secrets"] if item["name"] == "api_token")
    assert created["kind"] == "random_string"
    assert created["config"]["length"] == 32
    existing = next(item for item in doc["secrets"] if item["name"] == "existing_password")
    assert existing["rotation_period"] == "30d"


def test_new_alias_edits_and_appends_target(runner: CliRunner, tmp_path: Path) -> None:
    secretfile = tmp_path / "Secretfile.yml"
    secretfile.write_text(BASE, encoding="utf-8")
    result = _invoke(
        runner,
        [
            "new",
            "existing_password",
            "-f",
            str(secretfile),
            "--edit",
            "--kind",
            "random_password",
            "-G",
            "length=24",
            "--target",
            "provider=aws,kind=ssm_parameter,name=/app/db",
        ],
    )
    assert result.exit_code == 0, result.output
    doc = yaml.safe_load(secretfile.read_text(encoding="utf-8"))
    secret = doc["secrets"][0]
    assert secret["config"]["length"] == 24
    assert len(secret["targets"]) == 2
    assert doc["providers"]["aws"]["kind"] == "aws"
    assert doc["providers"]["aws"]["auth"]["kind"] == "ambient"


def test_replace_targets(runner: CliRunner, tmp_path: Path) -> None:
    secretfile = tmp_path / "Secretfile.yml"
    secretfile.write_text(BASE, encoding="utf-8")
    result = _invoke(
        runner,
        [
            "add",
            "existing_password",
            "-f",
            str(secretfile),
            "--edit",
            "--replace-targets",
            "--kind",
            "random_password",
            "--target",
            "provider=local,kind=file,path=.env.new,format=dotenv",
        ],
    )
    assert result.exit_code == 0, result.output
    doc = yaml.safe_load(secretfile.read_text(encoding="utf-8"))
    targets = doc["secrets"][0]["targets"]
    assert len(targets) == 1
    assert targets[0]["config"]["path"] == ".env.new"


def test_rejects_static_plaintext(runner: CliRunner, tmp_path: Path) -> None:
    secretfile = tmp_path / "Secretfile.yml"
    secretfile.write_text(BASE, encoding="utf-8")
    result = _invoke(
        runner,
        [
            "add",
            "api_key",
            "-f",
            str(secretfile),
            "--kind",
            "static",
            "-G",
            "value=super-secret",
            "--target",
            "provider=local,kind=file,path=.env,format=dotenv",
        ],
    )
    assert result.exit_code != 0
    assert "placeholder" in result.output
    assert "api_key" not in secretfile.read_text(encoding="utf-8")


def test_static_placeholder_allowed(runner: CliRunner, tmp_path: Path) -> None:
    secretfile = tmp_path / "Secretfile.yml"
    secretfile.write_text(BASE, encoding="utf-8")
    result = _invoke(
        runner,
        [
            "add",
            "api_key",
            "-f",
            str(secretfile),
            "--kind",
            "static",
            "-G",
            "value=${API_KEY}",
            "--source-kind",
            "env",
            "--source-config",
            "name=API_KEY",
            "--target",
            "provider=local,kind=file,path=.env,format=dotenv",
        ],
    )
    assert result.exit_code == 0, result.output
    doc = yaml.safe_load(secretfile.read_text(encoding="utf-8"))
    created = next(item for item in doc["secrets"] if item["name"] == "api_key")
    assert created["config"]["value"] == "${API_KEY}"
    assert created["source"]["kind"] == "env"
    assert created["source"]["config"]["name"] == "API_KEY"


def test_dry_run_does_not_write(runner: CliRunner, tmp_path: Path) -> None:
    secretfile = tmp_path / "Secretfile.yml"
    before = BASE
    secretfile.write_text(before, encoding="utf-8")
    result = _invoke(
        runner,
        [
            "add",
            "other",
            "-f",
            str(secretfile),
            "--kind",
            "random_password",
            "--target",
            "provider=local,kind=file,path=.env,format=dotenv",
            "--dry-run",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["dry_run"] is True
    assert secretfile.read_text(encoding="utf-8") == before


def test_create_fails_when_name_exists(runner: CliRunner, tmp_path: Path) -> None:
    secretfile = tmp_path / "Secretfile.yml"
    secretfile.write_text(BASE, encoding="utf-8")
    result = _invoke(
        runner,
        [
            "add",
            "existing_password",
            "-f",
            str(secretfile),
            "--create",
            "--kind",
            "random_password",
            "--target",
            "provider=local,kind=file,path=.env,format=dotenv",
        ],
    )
    assert result.exit_code != 0
    assert "already exists" in result.output


def test_missing_flags_without_tty(runner: CliRunner) -> None:
    result = _invoke(runner, ["add"])
    assert result.exit_code != 0
    assert "--interactive" in result.output


def test_interactive_create(runner: CliRunner, tmp_path: Path) -> None:
    secretfile = tmp_path / "Secretfile.yml"
    secretfile.write_text(BASE, encoding="utf-8")
    # add, name, generator 1 (random_password), length, special yes,
    # source skip, replace? no (existing inventory is shown but action is add),
    # add target yes, category local, kind file (1), path, format, alias, another no, confirm
    user_input = "\n".join(
        [
            "add",
            "session_key",
            "1",
            "32",
            "y",
            "skip",
            "y",
            "local",
            "1",
            ".env.session",
            "dotenv",
            "local",
            "n",
            "y",
        ]
    )
    result = runner.invoke(
        main,
        ["add", "-f", str(secretfile), "--interactive"],
        input=user_input + "\n",
    )
    assert result.exit_code == 0, result.output
    doc = yaml.safe_load(secretfile.read_text(encoding="utf-8"))
    created = next(item for item in doc["secrets"] if item["name"] == "session_key")
    assert created["kind"] == "random_password"
    assert created["targets"][0]["config"]["path"] == ".env.session"


def test_creates_missing_secretfile(runner: CliRunner, tmp_path: Path) -> None:
    secretfile = tmp_path / "nested" / "Secretfile.yml"
    result = _invoke(
        runner,
        [
            "add",
            "db_password",
            "-f",
            str(secretfile),
            "--kind",
            "random_password",
            "--target",
            "provider=local,kind=file,path=.env.local,format=dotenv,merge=true",
        ],
    )
    assert result.exit_code == 0, result.output
    assert secretfile.exists()
    doc = yaml.safe_load(secretfile.read_text(encoding="utf-8"))
    assert doc["secrets"][0]["name"] == "db_password"
    assert doc["providers"]["local"]["kind"] == "local"


def test_parse_target_spec_and_plaintext_guard() -> None:
    target = parse_target_spec("provider=local,kind=file,path=.env,merge=true")
    assert target.provider == "local"
    assert target.config["merge"] is True
    with pytest.raises(SecretAuthorError):
        reject_plaintext_static("static", {"value": "nope"})


def test_api_post_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    secretfile = tmp_path / "Secretfile.yml"
    secretfile.write_text(BASE, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    app = create_app(secretfile_path=str(secretfile))
    client = TestClient(app)
    api_key = generate_api_key()
    monkeypatch.setenv("SECRETZERO_API_KEY", api_key)
    response = client.post(
        "/secrets",
        headers={"X-API-Key": api_key},
        json={
            "name": "from_api",
            "kind": "random_string",
            "mode": "create",
            "targets": [
                {
                    "provider": "local",
                    "kind": "file",
                    "config": {"path": ".env", "format": "dotenv"},
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["action"] == "created"
    assert body["name"] == "from_api"
    assert "value" not in body
    doc = yaml.safe_load(secretfile.read_text(encoding="utf-8"))
    assert any(item["name"] == "from_api" for item in doc["secrets"])

    rejected = client.post(
        "/secrets",
        headers={"X-API-Key": api_key},
        json={
            "name": "leaked",
            "kind": "static",
            "config": {"value": "plaintext"},
            "targets": [{"provider": "local", "kind": "file", "config": {"path": ".env"}}],
        },
    )
    assert rejected.status_code == 400
