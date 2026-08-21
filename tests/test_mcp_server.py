"""Tests for the SecretZero MCP server."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import yaml

from secretzero.lockfile import Lockfile
from secretzero.mcp_server import (
    _build_status_payload,
    _discover_candidates_payload,
    _reject_reveal_params,
    _sanitize_payload,
    create_mcp_server,
    ensure_agent_mode,
    generate_mcp_config,
    resolve_mcp_paths,
    resolve_mcp_server_cls,
)


def _write_minimal_manifest(tmp_path: Path) -> Path:
    sf = tmp_path / "Secretfile.yml"
    sf.write_text(
        yaml.safe_dump(
            {
                "providers": {"local": {"kind": "local"}},
                "secrets": [
                    {
                        "name": "demo_secret",
                        "kind": "static",
                        "config": {"value": "placeholder"},
                        "targets": [
                            {
                                "provider": "local",
                                "kind": "file",
                                "config": {"path": ".env", "format": "dotenv"},
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    lock = Lockfile()
    lock.add_secret("demo_secret", "hashed-value-not-real", target_id="local/file/.env")
    lock.save(tmp_path / ".gitsecrets.lock")
    return sf


class TestSpillGuards:
    def test_ensure_agent_mode_sets_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SZ_AGENT_MODE", raising=False)
        ensure_agent_mode()
        assert os.environ.get("SZ_AGENT_MODE") == "true"

    def test_ensure_agent_mode_respects_existing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SZ_AGENT_MODE", "false")
        ensure_agent_mode()
        assert os.environ["SZ_AGENT_MODE"] == "false"

    def test_reject_reveal_params(self) -> None:
        with pytest.raises(ValueError, match="reveal"):
            _reject_reveal_params(reveal=True)

    def test_sanitize_payload_strips_values(self) -> None:
        payload = {"name": "x", "value": "secret", "nested": {"raw_value": "y", "ok": 1}}
        cleaned = _sanitize_payload(payload)
        assert "value" not in cleaned
        assert "raw_value" not in cleaned["nested"]
        assert cleaned["nested"]["ok"] == 1


class TestDiscoverPayload:
    def test_discover_candidates_strip_raw_value(self) -> None:
        from secretzero.discovery import DiscoveryResult, SecretCandidate

        result = DiscoveryResult(
            candidates=[
                SecretCandidate(
                    name="api_key",
                    raw_value="super-secret",
                    confidence=0.9,
                    source_file=".env",
                    line_number=3,
                )
            ]
        )
        rows = _discover_candidates_payload(result)
        assert rows[0]["name"] == "api_key"
        assert "raw_value" not in rows[0]


class TestMcpServerClassResolver:
    def test_resolve_prefers_mcp_server_when_available(self) -> None:
        cls = resolve_mcp_server_cls()
        assert cls is not None
        assert callable(cls)

    def test_resolve_falls_back_to_fastmcp(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import builtins
        import types

        sentinel = type("FakeFastMCP", (), {})
        fake_fastmcp = types.ModuleType("mcp.server.fastmcp")
        fake_fastmcp.FastMCP = sentinel  # type: ignore[attr-defined]
        real_import = builtins.__import__

        def _import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "mcp.server" and fromlist and "MCPServer" in fromlist:
                raise ImportError("simulated missing MCPServer")
            if name == "mcp.server.fastmcp":
                return fake_fastmcp
            return real_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", _import)
        assert resolve_mcp_server_cls() is sentinel

    def test_resolve_error_reports_found_version(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import builtins

        real_import = builtins.__import__

        def _import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in {"mcp.server", "mcp.server.fastmcp"} or name.startswith("mcp.server"):
                raise ImportError("simulated missing")
            return real_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", _import)
        monkeypatch.setattr(
            "secretzero.mcp_server._mcp_package_version",
            lambda: "1.27.0",
        )
        with pytest.raises(ImportError, match=r"Found mcp 1\.27\.0"):
            resolve_mcp_server_cls()


class TestMcpPaths:
    def test_resolve_paths_with_workspace(self, tmp_path: Path) -> None:
        _write_minimal_manifest(tmp_path)
        paths = resolve_mcp_paths(workspace=str(tmp_path))
        assert paths.workspace == tmp_path.resolve()
        assert paths.secretfile == (tmp_path / "Secretfile.yml").resolve()
        assert paths.lockfile == (tmp_path / ".gitsecrets.lock").resolve()


class TestStatusPayload:
    def test_status_returns_hashes_not_values(self, tmp_path: Path) -> None:
        sf_path = _write_minimal_manifest(tmp_path)
        from secretzero.config import ConfigLoader

        loader = ConfigLoader()
        config = loader.load_file(sf_path)
        lock = Lockfile.load(tmp_path / ".gitsecrets.lock")
        content = sf_path.read_text(encoding="utf-8")
        paths = resolve_mcp_paths(workspace=str(tmp_path))
        payload = _build_status_payload(paths, config, lock, content)
        assert payload["lockfile_exists"] is True
        assert payload["secrets"][0]["hash"]
        assert "value" not in json.dumps(payload)


class TestGenerateConfig:
    def test_generate_cursor_format(self, tmp_path: Path) -> None:
        out = tmp_path / "mcp.json"
        payload = generate_mcp_config(workspace=tmp_path, output_path=out, format_name="cursor")
        assert "servers" in payload
        entry = payload["servers"]["secretzero"]
        assert entry["command"]
        assert entry["args"] == ["mcp", "serve"]
        assert entry["env"]["SZ_AGENT_MODE"] == "true"
        assert out.exists()

    def test_generate_uses_secretfile_app_config(self, tmp_path: Path) -> None:
        sf = tmp_path / "Secretfile.yml"
        sf.write_text(
            "config:\n  mcp:\n    server_name: project-mcp\nsecrets: []\n",
            encoding="utf-8",
        )
        payload = generate_mcp_config(secretfile_path=sf, format_name="claude")
        assert "project-mcp" in payload["mcpServers"]


class TestMcpTools:
    @pytest.fixture
    def mcp_server(self):
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setenv("SZ_AGENT_MODE", "true")
        server = create_mcp_server()
        yield server
        monkeypatch.undo()

    def test_sz_status_tool(self, tmp_path: Path, mcp_server) -> None:
        _write_minimal_manifest(tmp_path)
        tools = {t.name: t for t in _run_list_tools(mcp_server)}
        assert "sz_status" in tools

        result = _call_tool(mcp_server, "sz_status", {"workspace": str(tmp_path)})
        assert result["lockfile_exists"] is True
        assert result["secrets"][0]["name"] == "demo_secret"

    def test_sz_sync_dry_run(self, tmp_path: Path, mcp_server) -> None:
        _write_minimal_manifest(tmp_path)
        result = _call_tool(
            mcp_server,
            "sz_sync",
            {"workspace": str(tmp_path), "dry_run": True},
        )
        assert result["dry_run"] is True
        assert "details" in result

    def test_sz_drift_check_no_lockfile(self, tmp_path: Path, mcp_server) -> None:
        sf = tmp_path / "Secretfile.yml"
        sf.write_text("secrets: []\n", encoding="utf-8")
        with pytest.raises(Exception):
            _call_tool(mcp_server, "sz_drift_check", {"workspace": str(tmp_path)})

    def test_sz_discover_no_llm(self, tmp_path: Path, mcp_server) -> None:
        (tmp_path / "Secretfile.yml").write_text("secrets: []\n", encoding="utf-8")
        (tmp_path / "README.md").write_text("# demo\n", encoding="utf-8")
        result = _call_tool(
            mcp_server,
            "sz_discover",
            {"workspace": str(tmp_path), "no_llm": True, "dry_run": True},
        )
        assert "files_scanned" in result
        assert "secrets" in result

    def test_reveal_blocked_on_sync(self, tmp_path: Path, mcp_server) -> None:
        _write_minimal_manifest(tmp_path)
        with pytest.raises(Exception, match="reveal"):
            _call_tool(
                mcp_server,
                "sz_sync",
                {"workspace": str(tmp_path), "reveal": True},
            )


def _run_list_tools(server):
    import asyncio

    return asyncio.run(server.list_tools())


def _call_tool(server, name: str, arguments: dict):
    import asyncio

    async def _invoke():
        result = await server.call_tool(name, arguments)
        # mcp SDK 2.x returns CallToolResult; 1.x returned (content, structured).
        structured = getattr(result, "structured_content", None)
        if isinstance(structured, dict):
            return structured
        content = getattr(result, "content", None)
        if content is None and isinstance(result, tuple) and len(result) == 2:
            content, structured = result
            if isinstance(structured, dict):
                return structured
        if content and hasattr(content[0], "text"):
            return json.loads(content[0].text)
        if isinstance(result, dict):
            return result
        return structured

    return asyncio.run(_invoke())


class TestRotateDryRun:
    def test_sz_rotate_dry_run(self, tmp_path: Path) -> None:
        sf_path = _write_minimal_manifest(tmp_path)
        # Add rotation period to manifest
        data = yaml.safe_load(sf_path.read_text(encoding="utf-8"))
        data["secrets"][0]["rotation_period"] = "30d"
        sf_path.write_text(yaml.safe_dump(data), encoding="utf-8")

        server = create_mcp_server()
        result = _call_tool(
            server,
            "sz_rotate",
            {"workspace": str(tmp_path), "force": True, "dry_run": True},
        )
        assert result["dry_run"] is True
        assert "would_rotate" in result
