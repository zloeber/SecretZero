"""Tests for GitNexus / MetaGit sidecar helpers."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from secretzero.cli import _should_emit_gitnexus_sidecar, main
from secretzero.gitnexus_intel import (
    build_secrets_overlay,
    emit_gitnexus_sidecars,
    load_discovery_bindings,
    merge_metagit_registry,
    secret_density_score,
    write_secrets_overlay,
)
from secretzero.models import Secret, Secretfile


def test_build_secrets_overlay_includes_process_tags_and_uri(tmp_path: Path) -> None:
    sf_path = tmp_path / "Secretfile.yml"
    bindings = {
        "api_key": {
            "symbol_id": "sym_123",
            "symbol_fqn": "pkg.module.Handler.auth_header",
            "source_file": "pkg/handler.py",
            "line_number": 42,
            "containing_symbol": "Handler.send",
        }
    }
    (tmp_path / ".gitnexus").mkdir(parents=True)
    (tmp_path / ".gitnexus" / "discovery_bindings.json").write_text(
        json.dumps({"schema_version": "1", "bindings": bindings}),
        encoding="utf-8",
    )

    secretfile = Secretfile(
        secrets=[
            Secret(name="api_key", kind="static", process_tags=["auth_flow"]),
        ]
    )
    overlay = build_secrets_overlay(
        secretfile,
        secretfile_path=sf_path,
        repo_root=tmp_path,
    )
    api = overlay["secrets"]["api_key"]
    assert api["process_tags"] == ["auth_flow"]
    assert "sym_123" in api["symbol_ids"]
    assert "pkg.module.Handler.auth_header" in api["fqns"]
    assert api["mcp_resource_uri"].startswith("secretzero://repo/")
    assert api["source_refs"][0]["file"] == "pkg/handler.py"


def test_write_secrets_overlay_creates_dot_gitnexus(tmp_path: Path) -> None:
    sf_path = tmp_path / "Secretfile.yml"
    sf_path.write_text("secrets: []\n", encoding="utf-8")
    overlay = {"schema_version": "1", "secrets": {}}
    out = write_secrets_overlay(sf_path, overlay)
    assert out.is_file()
    assert out.parent.name == ".gitnexus"


def test_load_discovery_bindings_missing(tmp_path: Path) -> None:
    assert load_discovery_bindings(tmp_path) == {}


def test_merge_metagit_registry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    os.environ["SZ_METAGIT_REGISTRY"] = "1"
    try:
        sf_path = tmp_path / "Secretfile.yml"
        sf_path.parent.mkdir(parents=True, exist_ok=True)
        sf = Secretfile(secrets=[Secret(name="a", kind="static"), Secret(name="b", kind="static")])
        p = merge_metagit_registry(sf_path, sf)
        mg = tmp_path / ".metagit.yml"
        assert p is not None and p.is_file()
        data = yaml.safe_load(mg.read_text(encoding="utf-8"))
        entry = data["secretzero"]["repos"][str(tmp_path.resolve())]
        assert entry["secret_count"] == 2
        assert "secret_density_score" in entry
    finally:
        os.environ.pop("SZ_METAGIT_REGISTRY", None)


def test_secret_density_score_positive(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x", encoding="utf-8")
    score = secret_density_score(2, tmp_path)
    assert score > 0


def test_emit_respects_disable_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    os.environ["SZ_NO_GITNEXUS_OVERLAY"] = "1"
    try:
        sf_path = tmp_path / "Secretfile.yml"
        sf_path.write_text("secrets: []\n", encoding="utf-8")
        res = emit_gitnexus_sidecars(secretfile_path=sf_path, secretfile=Secretfile())
        assert res.get("skipped") is True
        assert not (tmp_path / ".gitnexus").exists()
    finally:
        os.environ.pop("SZ_NO_GITNEXUS_OVERLAY", None)


def test_emit_does_not_create_gitnexus_without_workspace(tmp_path: Path) -> None:
    """Sync-style emission must not invent a .gitnexus directory."""
    sf_path = tmp_path / "Secretfile.yml"
    sf_path.write_text("secrets: []\n", encoding="utf-8")
    res = emit_gitnexus_sidecars(secretfile_path=sf_path, secretfile=Secretfile())
    assert res.get("skipped") is True
    assert res.get("reason") == "no_gitnexus_workspace"
    assert not (tmp_path / ".gitnexus").exists()


def test_emit_writes_into_existing_gitnexus_dir(tmp_path: Path) -> None:
    sf_path = tmp_path / "Secretfile.yml"
    sf_path.write_text("secrets: []\n", encoding="utf-8")
    (tmp_path / ".gitnexus").mkdir()
    (tmp_path / ".gitnexus" / "meta.json").write_text("{}\n", encoding="utf-8")
    res = emit_gitnexus_sidecars(secretfile_path=sf_path, secretfile=Secretfile())
    assert res.get("skipped") is False
    overlay = tmp_path / ".gitnexus" / "secrets_overlay.json"
    assert overlay.is_file()
    assert Path(res["secrets_overlay"]) == overlay


def test_emit_uses_repo_root_index_not_a_nested_dir(tmp_path: Path) -> None:
    """An existing GitNexus index at the git root is the overlay destination."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    index = tmp_path / ".gitnexus"
    index.mkdir()
    (index / "meta.json").write_text("{}\n", encoding="utf-8")
    app = tmp_path / "app"
    app.mkdir()
    sf_path = app / "Secretfile.yml"
    sf_path.write_text("secrets: []\n", encoding="utf-8")

    res = emit_gitnexus_sidecars(secretfile_path=sf_path, secretfile=Secretfile())
    assert res.get("skipped") is False
    assert (index / "secrets_overlay.json").is_file()
    assert not (app / ".gitnexus").exists()


def test_emit_force_env_creates_overlay(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SZ_GITNEXUS_OVERLAY", "1")
    sf_path = tmp_path / "Secretfile.yml"
    sf_path.write_text("secrets: []\n", encoding="utf-8")
    res = emit_gitnexus_sidecars(secretfile_path=sf_path, secretfile=Secretfile())
    assert res.get("skipped") is False
    assert (tmp_path / ".gitnexus" / "secrets_overlay.json").is_file()


def test_disable_env_wins_over_existing_workspace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SZ_NO_GITNEXUS_OVERLAY", "1")
    monkeypatch.setenv("SZ_GITNEXUS_OVERLAY", "1")
    (tmp_path / ".gitnexus").mkdir()
    sf_path = tmp_path / "Secretfile.yml"
    sf_path.write_text("secrets: []\n", encoding="utf-8")
    res = emit_gitnexus_sidecars(secretfile_path=sf_path, secretfile=Secretfile())
    assert res.get("skipped") is True
    assert res.get("reason") == "SZ_NO_GITNEXUS_OVERLAY"
    assert not (tmp_path / ".gitnexus" / "secrets_overlay.json").exists()


def test_should_emit_sidecar_ignores_unchanged_secretfile() -> None:
    """secretfile_changed is always a bool; False must not force an overlay write."""
    assert (
        _should_emit_gitnexus_sidecar(
            False,
            {"secrets_stored": 0, "secretfile_changed": False},
            [],
        )
        is False
    )
    assert (
        _should_emit_gitnexus_sidecar(
            False,
            {"secrets_stored": 0, "secretfile_changed": True},
            [],
        )
        is True
    )
    assert (
        _should_emit_gitnexus_sidecar(
            False,
            {"secrets_stored": 1, "secretfile_changed": False},
            [],
        )
        is True
    )
    assert (
        _should_emit_gitnexus_sidecar(
            True,
            {"secrets_stored": 1, "secretfile_changed": True},
            [],
        )
        is False
    )


def _local_sync_secretfile(tmp_path: Path) -> Path:
    env_file = tmp_path / ".env.test"
    secretfile = tmp_path / "Secretfile.yml"
    secretfile.write_text(
        f"""
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
""",
        encoding="utf-8",
    )
    return secretfile


def test_sync_does_not_create_gitnexus_overlay(tmp_path: Path) -> None:
    secretfile = _local_sync_secretfile(tmp_path)
    result = CliRunner().invoke(
        main,
        ["sync", "--file", str(secretfile), "--lockfile", str(tmp_path / ".lock")],
    )
    assert result.exit_code == 0, result.output
    assert not (tmp_path / ".gitnexus").exists()
    assert "GitNexus overlay" not in result.output


def test_import_does_not_create_gitnexus_overlay(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("APP_TOKEN=seeded-token-value\n", encoding="utf-8")
    secretfile = tmp_path / "Secretfile.yml"
    secretfile.write_text(
        f"""
providers:
  local:
    kind: local
secrets:
  - name: app_token
    kind: static
    config: {{}}
    targets:
      - provider: local
        kind: file
        config:
          path: {env_path}
          format: dotenv
          key: APP_TOKEN
""",
        encoding="utf-8",
    )
    result = CliRunner().invoke(
        main,
        ["import", "-f", str(secretfile), "-l", str(tmp_path / ".gitsecrets.lock")],
    )
    assert result.exit_code == 0, result.output
    assert not (tmp_path / ".gitnexus").exists()


def test_get_does_not_create_gitnexus_overlay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secretfile = tmp_path / "Secretfile.yml"
    secretfile.write_text(
        """
providers:
  local:
    kind: local
secrets: []
""",
        encoding="utf-8",
    )

    def _fake_get(self, provider_name, secret_id, method_name=None, method_args=None):
        return {
            "provider": provider_name,
            "method": method_name or "retrieve_secret",
            "retrieved": True,
            "revealable": False,
            "value": None,
            "notes": None,
        }

    monkeypatch.setattr("secretzero.cli.SyncEngine.get_provider_secret", _fake_get)
    result = CliRunner().invoke(
        main,
        [
            "get",
            "--file",
            str(secretfile),
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
    assert "gitnexus" not in payload
    assert not (tmp_path / ".gitnexus").exists()
