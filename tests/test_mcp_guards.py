"""Tests for MCP spill guards."""

import pytest

from secretzero.mcp.config import McpConfig, load_mcp_config
from secretzero.mcp.guards import (
    MUTATION_TOOLS,
    assert_tool_allowed,
    apply_startup_env,
    sanitize_tool_result,
)


def test_sanitize_redacts_nested_value_key(monkeypatch):
    monkeypatch.setenv("SZ_AGENT_MODE", "true")
    payload = {"secrets": [{"name": "x", "value": "plaintext"}]}
    out = sanitize_tool_result("secrets_list", payload)
    assert "value" not in out["secrets"][0]
    assert out["secrets"][0]["name"] == "x"


def test_sanitize_passes_through_when_spill_guard_off(monkeypatch):
    monkeypatch.delenv("SZ_AGENT_MODE", raising=False)
    monkeypatch.delenv("SZ_AGENT", raising=False)
    payload = {"value": "keep-me"}
    out = sanitize_tool_result("secrets_list", payload)
    assert out["value"] == "keep-me"


def test_assert_tool_blocked_sync_execute_by_default(monkeypatch):
    monkeypatch.delenv("SZ_MCP_ALLOW_MUTATIONS", raising=False)
    with pytest.raises(PermissionError, match="sync_execute"):
        assert_tool_allowed("sync_execute")


def test_assert_tool_allows_sync_execute_when_enabled(monkeypatch):
    monkeypatch.setenv("SZ_MCP_ALLOW_MUTATIONS", "true")
    assert_tool_allowed("sync_execute")


def test_apply_startup_env_sets_agent_mode(monkeypatch):
    monkeypatch.delenv("SZ_AGENT_MODE", raising=False)
    cfg = load_mcp_config(argv=[])
    apply_startup_env(cfg)
    assert __import__("os").environ.get("SZ_AGENT_MODE") == "true"


def test_mutation_tools_registry_includes_sync_execute():
    assert "sync_execute" in MUTATION_TOOLS
