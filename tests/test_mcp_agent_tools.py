"""Tests for MCP agent Tier 2 tools."""

import json

import pytest

from secretzero.agent_instructions_report import InstructionScope
from secretzero.mcp.agent_ops import (
    run_agent_instructions,
    run_agent_sync,
    run_agent_sync_web_poll,
)
from secretzero.mcp.backend.local import LocalBackend
from secretzero.mcp.config import load_mcp_config
from secretzero.models import (
    AgentInstructions,
    AgentInstructionStep,
    Secret,
    Secretfile,
    TargetConfig,
)


def _write_secretfile(path, secrets):
    import yaml

    data = {
        "secrets": [
            {
                "name": s.name,
                "kind": s.kind,
                "config": s.config,
                **(
                    {"agent_instructions": s.agent_instructions.model_dump(exclude_none=True)}
                    if s.agent_instructions
                    else {}
                ),
                "targets": [
                    {"provider": t.provider, "kind": t.kind, "config": t.config} for t in s.targets
                ],
            }
            for s in secrets
        ]
    }
    path.write_text(yaml.safe_dump(data, sort_keys=False))


@pytest.fixture
def pending_manual_cfg(tmp_path, monkeypatch):
    secretfile_path = tmp_path / "Secretfile.yml"
    secret = Secret(
        name="manual_key",
        kind="static",
        config={"default": None},
        agent_instructions=AgentInstructions(
            summary="Create a key in the console",
            steps=[AgentInstructionStep(action="Open console", description="Create API key")],
        ),
        targets=[
            TargetConfig(provider="local", kind="file", config={"path": ".env", "format": "dotenv"})
        ],
    )
    _write_secretfile(secretfile_path, [secret])
    monkeypatch.setenv("SECRETZERO_CONFIG", str(secretfile_path))
    monkeypatch.setenv("SZ_AGENT_MODE", "true")
    return load_mcp_config(argv=[])


def test_agent_sync_dry_run_metadata_only(pending_manual_cfg):
    payload = run_agent_sync(pending_manual_cfg, dry_run=True)
    assert payload["dry_run"] is True
    assert "manual_key" in payload["pending_secrets"]
    dumped = json.dumps(payload)
    assert "password" not in dumped.lower() or "pending_secrets" in dumped


def test_agent_instructions_pending_scope(pending_manual_cfg):
    payload = run_agent_instructions(pending_manual_cfg)
    assert payload["scope"] == InstructionScope.PENDING.value
    assert "manual_key" in payload["secrets"]
    assert payload["secrets"]["manual_key"]["summary"]


def test_agent_sync_web_poll_unknown_session_raises():
    with pytest.raises(ValueError, match="Unknown web session"):
        run_agent_sync_web_poll("does-not-exist")


def test_mcp_app_registers_agent_tools(pending_manual_cfg):
    from secretzero.mcp.app import create_mcp_app

    backend = LocalBackend(pending_manual_cfg)
    app = create_mcp_app(pending_manual_cfg, backend)
    tool_names = {tool.name for tool in app._tool_manager.list_tools()}  # noqa: SLF001
    assert "agent_sync" in tool_names
    assert "agent_sync_web_start" in tool_names
    assert "agent_sync_web_poll" in tool_names
    assert "agent_instructions" in tool_names


def test_agent_sync_tool_via_app(pending_manual_cfg):
    from secretzero.mcp.app import create_mcp_app

    backend = LocalBackend(pending_manual_cfg)
    app = create_mcp_app(pending_manual_cfg, backend)
    tool = app._tool_manager._tools["agent_sync"]  # noqa: SLF001
    result = tool.fn(dry_run=True)
    assert result["status"] in {"pending_manual", "complete", "partial", "failed"}
    assert "pending_secrets" in result
