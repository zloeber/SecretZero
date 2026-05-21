"""Tests for tfvars file format on the local file target."""

from pathlib import Path

import pytest

from secretzero.hcl_tfvars import format_tfvars, parse_tfvars
from secretzero.targets.file import FileTarget


class TestTfvarsParseFormat:
    def test_roundtrip_simple(self) -> None:
        data = {"api_token": "abc123", "db_password": "p@ss w0rd!"}
        text = format_tfvars(data)
        assert parse_tfvars(text) == data

    def test_ignores_comments_and_blank_lines(self) -> None:
        content = """
# Cloudflare
cloudflare_api_token = "token-here"

# Database
database_password = "secret"
"""
        assert parse_tfvars(content) == {
            "cloudflare_api_token": "token-here",
            "database_password": "secret",
        }

    def test_quotes_and_escapes(self) -> None:
        raw = 'special = "say \\"hi\\" and \\n newline"'
        parsed = parse_tfvars(raw)
        assert parsed["special"] == 'say "hi" and \n newline'

    def test_boolean_and_number_literals_as_strings(self) -> None:
        content = "flag = true\nport = 443\n"
        assert parse_tfvars(content) == {"flag": "true", "port": "443"}

    def test_rejects_nested_map(self) -> None:
        with pytest.raises(ValueError, match="Unsupported"):
            parse_tfvars('config = { key = "value" }')

    def test_rejects_heredoc(self) -> None:
        with pytest.raises(ValueError, match="Unsupported"):
            parse_tfvars("x = <<EOF\nsecret\nEOF")


class TestFileTargetTfvars:
    def test_store_retrieve_merge(self, tmp_path: Path) -> None:
        path = tmp_path / "terraform.tfvars"
        path.write_text('# existing\nexisting_key = "keep"\n', encoding="utf-8")

        target = FileTarget({"path": str(path), "format": "tfvars", "merge": True})
        assert target.store("secret_a", "value-a") is True
        assert target.store("secret_b", "value-b") is True

        content = path.read_text(encoding="utf-8")
        assert 'existing_key = "keep"' in content
        assert 'secret_a = "value-a"' in content
        assert 'secret_b = "value-b"' in content

        assert target.retrieve("secret_a") == "value-a"
        assert target.retrieve("existing_key") == "keep"

    def test_config_key_override(self, tmp_path: Path) -> None:
        path = tmp_path / "vars.tfvars"
        target = FileTarget(
            {
                "path": str(path),
                "format": "tfvars",
                "key": "TF_VAR_NAME",
            }
        )
        target.store("manifest_name", "hidden-value")
        content = path.read_text(encoding="utf-8")
        assert 'TF_VAR_NAME = "hidden-value"' in content
        assert target.retrieve("manifest_name") == "hidden-value"

    def test_path_infers_tfvars_format(self, tmp_path: Path) -> None:
        path = tmp_path / "auto.tfvars"
        target = FileTarget({"path": str(path)})
        assert target.format == "tfvars"

    def test_tfvars_json_stays_dotenv_default(self, tmp_path: Path) -> None:
        path = tmp_path / "auto.tfvars.json"
        target = FileTarget({"path": str(path)})
        assert target.format == "dotenv"
