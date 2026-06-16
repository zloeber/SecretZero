"""Tests for SecretZero MCP server configuration."""

from secretzero.mcp.config import load_mcp_config


def test_load_mcp_config_defaults_local_backend(monkeypatch):
    monkeypatch.delenv("SZ_MCP_BACKEND", raising=False)
    monkeypatch.setenv("SECRETZERO_CONFIG", "Secretfile.yml")
    cfg = load_mcp_config(argv=[])
    assert cfg.backend == "local"
    assert cfg.secretfile_path.name == "Secretfile.yml"
    assert cfg.force_agent_mode is True


def test_load_mcp_config_http_requires_api_key(monkeypatch):
    monkeypatch.setenv("SZ_MCP_BACKEND", "http")
    monkeypatch.setenv("SECRETZERO_API_URL", "http://127.0.0.1:8000")
    monkeypatch.delenv("SECRETZERO_API_KEY", raising=False)
    try:
        load_mcp_config(argv=[])
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "SECRETZERO_API_KEY" in str(exc)


def test_load_mcp_config_cli_overrides_backend(monkeypatch):
    monkeypatch.setenv("SZ_MCP_BACKEND", "local")
    monkeypatch.setenv("SECRETZERO_CONFIG", "Secretfile.yml")
    cfg = load_mcp_config(
        argv=[
            "--backend",
            "http",
            "--api-url",
            "https://sz.example:8000",
            "--api-key",
            "test-key",
        ]
    )
    assert cfg.backend == "http"
    assert cfg.api_url == "https://sz.example:8000"
    assert cfg.api_key == "test-key"
