"""Tests for MCP discovery operations."""

from pathlib import Path

import pytest

from secretzero.mcp.config import load_mcp_config
from secretzero.mcp.discovery_ops import resolve_scan_directory, run_detect_scan


@pytest.fixture
def workspace_cfg(tmp_path, monkeypatch):
    (tmp_path / "Secretfile.yml").write_text("secrets: []\nvariables: {}\n")
    (tmp_path / ".env").write_text("MY_API_KEY=should-not-appear-in-output\n")
    monkeypatch.setenv("SECRETZERO_CONFIG", str(tmp_path / "Secretfile.yml"))
    monkeypatch.setenv("SZ_MCP_WORKSPACE_ROOT", str(tmp_path))
    return load_mcp_config(argv=[])


def test_detect_secrets_metadata_only(workspace_cfg):
    scan_dir = resolve_scan_directory(workspace_cfg, None)
    result = run_detect_scan(scan_dir)
    assert result["total"] >= 1
    payload = str(result)
    assert "should-not-appear-in-output" not in payload
    names = {item["env_var"] for item in result["detected"]}
    assert "MY_API_KEY" in names


def test_resolve_scan_directory_rejects_outside_jail(workspace_cfg):
    with pytest.raises(ValueError, match="outside workspace"):
        resolve_scan_directory(workspace_cfg, "/")
