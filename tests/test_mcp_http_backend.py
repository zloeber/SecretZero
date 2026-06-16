"""Tests for HttpBackend MCP client."""

from unittest.mock import MagicMock, patch

import pytest

from secretzero.mcp.backend.http import HttpBackend
from secretzero.mcp.config import load_mcp_config


@pytest.fixture
def http_cfg(monkeypatch):
    monkeypatch.setenv("SZ_MCP_BACKEND", "http")
    monkeypatch.setenv("SECRETZERO_API_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("SECRETZERO_API_KEY", "test-key")
    return load_mcp_config(argv=[])


def test_http_backend_catalog_list(http_cfg):
    backend = HttpBackend(http_cfg)
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"generators": [{"kind": "static"}]}
    with patch("httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.get.return_value = mock_response
        result = backend.catalog_list()
    assert result["generators"][0]["kind"] == "static"
    client.get.assert_called_once()
