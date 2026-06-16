"""Tests for MCP app tool registration."""

from secretzero.mcp.app import create_mcp_app
from secretzero.mcp.backend.local import LocalBackend
from secretzero.mcp.config import load_mcp_config


def test_create_mcp_app_registers_tier1_tools(monkeypatch):
    monkeypatch.setenv("SECRETZERO_CONFIG", "examples/script-ssh-keypair/Secretfile.yml")
    cfg = load_mcp_config(argv=[])
    backend = LocalBackend(cfg)
    app = create_mcp_app(cfg, backend)
    tool_names = {tool.name for tool in app._tool_manager.list_tools()}  # noqa: SLF001
    assert "catalog_list" in tool_names
    assert "detect_secrets" in tool_names
    assert "discover_bindings" in tool_names
    assert "secrets_status" in tool_names
    assert "agent_sync" in tool_names


def test_catalog_list_tool_returns_generators(monkeypatch):
    monkeypatch.setenv("SECRETZERO_CONFIG", "examples/script-ssh-keypair/Secretfile.yml")
    monkeypatch.setenv("SZ_AGENT_MODE", "true")
    cfg = load_mcp_config(argv=[])
    backend = LocalBackend(cfg)
    app = create_mcp_app(cfg, backend)
    tool = app._tool_manager._tools["catalog_list"]  # noqa: SLF001
    result = tool.fn()
    assert "generators" in result
