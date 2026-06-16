"""Tests for LocalBackend MCP operations."""

from pathlib import Path

import pytest

from secretzero.mcp.backend.local import LocalBackend
from secretzero.mcp.config import load_mcp_config


@pytest.fixture
def ssh_keypair_config(monkeypatch):
    secretfile = Path("examples/script-ssh-keypair/Secretfile.yml").resolve()
    monkeypatch.setenv("SECRETZERO_CONFIG", str(secretfile))
    monkeypatch.delenv("SZ_MCP_BACKEND", raising=False)
    return load_mcp_config(argv=[])


def test_local_backend_catalog_list_includes_generators(ssh_keypair_config):
    backend = LocalBackend(ssh_keypair_config)
    result = backend.catalog_list()
    kinds = {entry["kind"] for entry in result.get("generators", [])}
    assert "script" in kinds


def test_local_backend_schema_get_has_properties(ssh_keypair_config):
    backend = LocalBackend(ssh_keypair_config)
    schema = backend.schema_get()
    assert "properties" in schema


def test_local_backend_secrets_list_for_example_manifest(ssh_keypair_config):
    backend = LocalBackend(ssh_keypair_config)
    result = backend.secrets_list()
    assert result["total"] >= 1
    assert result["secrets"][0]["name"]


def test_local_backend_variables_list_redacts_under_agent_mode(ssh_keypair_config, monkeypatch):
    monkeypatch.setenv("SZ_AGENT_MODE", "true")
    backend = LocalBackend(ssh_keypair_config)
    result = backend.variables_list()
    assert result.get("values_redacted") is True
    assert "variables" not in result


def test_local_backend_version_info(ssh_keypair_config):
    backend = LocalBackend(ssh_keypair_config)
    result = backend.version_info(detailed=True)
    assert result["backend"] == "local"
    assert "version" in result
