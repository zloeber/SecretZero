"""API parity endpoint tests for MCP HttpBackend."""

import os

import pytest
from fastapi.testclient import TestClient

from secretzero.api.app import create_app
from secretzero.api.auth import generate_api_key


@pytest.fixture
def test_secretfile(tmp_path):
    secretfile = tmp_path / "Secretfile.yml"
    secretfile.write_text("""
version: '1.0'
variables:
  environment: test
providers:
  local:
    kind: local
    config: {}
secrets:
  - name: test_password
    kind: random_password
    config:
      length: 16
    targets:
      - provider: local
        kind: file
        config:
          path: test.env
          format: dotenv
""")
    return secretfile


@pytest.fixture
def parity_client(test_secretfile, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = create_app(secretfile_path=str(test_secretfile))
    client = TestClient(app)
    api_key = generate_api_key()
    os.environ["SECRETZERO_API_KEY"] = api_key
    client.headers["X-API-Key"] = api_key
    yield client
    os.environ.pop("SECRETZERO_API_KEY", None)


def test_get_version(parity_client):
    response = parity_client.get("/version?detailed=true")
    assert response.status_code == 200
    assert response.json()["name"] == "secretzero"


def test_get_catalog(parity_client):
    response = parity_client.get("/catalog")
    assert response.status_code == 200
    assert "generators" in response.json()


def test_post_detect_metadata_only(parity_client, tmp_path):
    (tmp_path / ".env").write_text("MY_TEST_KEY=hidden-value\n")
    response = parity_client.post("/detect", json={"directory": str(tmp_path)})
    assert response.status_code == 200
    body = response.json()
    assert "hidden-value" not in str(body)


def test_inventory_status(parity_client):
    response = parity_client.get("/inventory/status")
    assert response.status_code == 200
    assert "secrets" in response.json()


def test_agent_list(parity_client):
    response = parity_client.get("/agent/list")
    assert response.status_code == 200
    assert "registered_targets" in response.json()


def test_sync_execute_dry_run(parity_client):
    response = parity_client.post(
        "/sync/execute",
        json={"dry_run": True},
    )
    assert response.status_code == 200
    assert response.json()["dry_run"] is True
