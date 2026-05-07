"""Tests for GitNexus / MetaGit sidecar helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import yaml

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
    finally:
        os.environ.pop("SZ_NO_GITNEXUS_OVERLAY", None)
