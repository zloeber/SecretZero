"""Tests for the SecretZero API."""

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from secretzero.api.app import create_app
from secretzero.api.auth import generate_api_key


@pytest.fixture
def test_secretfile(tmp_path):
    """Create a test Secretfile."""
    secretfile = tmp_path / "Secretfile.yml"
    secretfile.write_text("""
version: '1.0'

variables:
  environment: test

metadata:
  project: test-project
  compliance:
    - soc2

providers:
  local:
    kind: local
    config: {}

secrets:
  - name: test_password
    kind: random_password
    config:
      length: 16
    rotation_period: 90d
    targets:
      - provider: local
        kind: file
        config:
          path: test.env
          format: dotenv

  - name: api_key
    kind: random_string
    config:
      length: 32
    targets:
      - provider: local
        kind: file
        config:
          path: test.env
          format: dotenv

policies:
  rotation_required:
    kind: rotation
    require_rotation_period: true
    max_age: 90d
    severity: warning
""")
    return secretfile


@pytest.fixture
def client(test_secretfile, tmp_path, monkeypatch):
    """Create a test client."""
    # Change to temp directory
    monkeypatch.chdir(tmp_path)

    # Create app with test config
    app = create_app(secretfile_path=str(test_secretfile))

    # Create test client
    return TestClient(app)


@pytest.fixture
def authenticated_client(client):
    """Create an authenticated test client."""
    # Generate and set API key
    api_key = generate_api_key()
    os.environ["SECRETZERO_API_KEY"] = api_key

    # Add API key to headers
    client.headers["X-API-Key"] = api_key

    yield client

    # Clean up
    if "SECRETZERO_API_KEY" in os.environ:
        del os.environ["SECRETZERO_API_KEY"]


class TestHealthEndpoint:
    """Tests for health endpoint."""

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data

    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "docs" in data


class TestAuthentication:
    """Tests for authentication."""

    def test_unauthenticated_request_no_api_key_set(self, client):
        """Test that requests work when no API key is configured (insecure mode)."""
        # Ensure no API key is set
        if "SECRETZERO_API_KEY" in os.environ:
            del os.environ["SECRETZERO_API_KEY"]

        response = client.get("/secrets")
        assert response.status_code in [200, 404]  # Should not be 401

    def test_authenticated_request_with_valid_key(self, authenticated_client):
        """Test that requests work with valid API key."""
        response = authenticated_client.get("/secrets")
        assert response.status_code in [200, 404]  # Not 401

    def test_authenticated_request_with_invalid_key(self, client):
        """Test that requests fail with invalid API key."""
        # Set an API key in environment
        os.environ["SECRETZERO_API_KEY"] = generate_api_key()

        # Use wrong API key in request
        client.headers["X-API-Key"] = "wrong-key"

        response = client.get("/secrets")
        assert response.status_code == 401

        # Clean up
        del os.environ["SECRETZERO_API_KEY"]

    def test_authenticated_request_with_missing_key(self, client):
        """Test that requests fail when API key is required but missing."""
        # Set an API key in environment
        os.environ["SECRETZERO_API_KEY"] = generate_api_key()

        # Don't include API key in request
        response = client.get("/secrets")
        assert response.status_code == 401

        # Clean up
        del os.environ["SECRETZERO_API_KEY"]


class TestConfigValidation:
    """Tests for config validation endpoint."""

    def test_validate_valid_config(self, authenticated_client):
        """Test validating a valid configuration."""
        config = {
            "version": "1.0",
            "secrets": [
                {
                    "name": "test",
                    "kind": "random_password",
                }
            ],
        }

        response = authenticated_client.post("/config/validate", json={"config": config})
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert len(data["errors"]) == 0

    def test_validate_invalid_config_missing_version(self, authenticated_client):
        """Test validating config without version."""
        config = {
            "secrets": [{"name": "test"}],
        }

        response = authenticated_client.post("/config/validate", json={"config": config})
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "version" in str(data["errors"])

    def test_validate_invalid_config_missing_secrets(self, authenticated_client):
        """Test validating config without secrets."""
        config = {
            "version": "1.0",
        }

        response = authenticated_client.post("/config/validate", json={"config": config})
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "secrets" in str(data["errors"])


class TestAppConfigEndpoint:
    """Tests for GET /config (effective app config)."""

    def test_get_config_returns_effective_config(self, authenticated_client):
        """GET /config returns merged config and sources."""
        response = authenticated_client.get("/config")
        assert response.status_code == 200
        data = response.json()
        assert "config" in data
        assert "sources" in data
        assert isinstance(data["sources"], list)
        assert "defaults" in data["sources"]
        assert "llm" in data["config"]
        assert data["config"]["llm"]["default_provider"] in (
            "ollama",
            "openai",
            "anthropic",
            "azure_openai",
        )


class TestSecretsEndpoints:
    """Tests for secrets endpoints."""

    def test_list_secrets(self, authenticated_client):
        """Test listing secrets."""
        response = authenticated_client.get("/secrets")
        assert response.status_code == 200
        data = response.json()
        assert "secrets" in data
        assert "count" in data
        assert data["count"] >= 0

    def test_get_secret_status_not_exists(self, authenticated_client):
        """Test getting status of non-existent secret."""
        response = authenticated_client.get("/secrets/nonexistent/status")
        assert response.status_code == 200
        data = response.json()
        assert data["exists"] is False
        assert data["name"] == "nonexistent"

    def test_get_secret_status_exists(self, authenticated_client, tmp_path):
        """Test getting status of existing secret."""
        # First sync to create the secret
        sync_response = authenticated_client.post(
            "/sync",
            json={"secret_name": "test_password", "dry_run": False, "force": False},
        )
        assert sync_response.status_code == 200

        # Then get status
        response = authenticated_client.get("/secrets/test_password/status")
        assert response.status_code == 200
        data = response.json()
        assert data["exists"] is True
        assert data["name"] == "test_password"


class TestSyncEndpoint:
    """Tests for sync endpoint."""

    def test_sync_dry_run(self, authenticated_client):
        """Test sync with dry run."""
        response = authenticated_client.post(
            "/sync",
            json={"dry_run": True, "force": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert len(data["secrets_generated"]) == 0

    def test_sync_specific_secret(self, authenticated_client):
        """Test syncing a specific secret."""
        response = authenticated_client.post(
            "/sync",
            json={"secret_name": "test_password", "dry_run": False, "force": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert (
            "test_password" in data["secrets_generated"]
            or "test_password" in data["secrets_skipped"]
        )

    def test_sync_nonexistent_secret(self, authenticated_client):
        """Test syncing a non-existent secret."""
        response = authenticated_client.post(
            "/sync",
            json={"secret_name": "nonexistent", "dry_run": False, "force": False},
        )
        assert response.status_code == 404


class TestRotationEndpoints:
    """Tests for rotation endpoints."""

    def test_check_rotation(self, authenticated_client):
        """Test checking rotation status."""
        response = authenticated_client.post(
            "/rotation/check",
            json={"dry_run": True},
        )
        assert response.status_code == 200
        data = response.json()
        assert "secrets_checked" in data
        assert "secrets_due" in data
        assert "secrets_overdue" in data

    def test_execute_rotation_dry_run(self, authenticated_client, tmp_path):
        """Test executing rotation (should work even without secrets)."""
        response = authenticated_client.post(
            "/rotation/execute",
            json={"force": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert "rotated" in data
        assert "failed" in data
        assert "message" in data


class TestPolicyEndpoint:
    """Tests for policy endpoint."""

    def test_check_policy(self, authenticated_client):
        """Test checking policy compliance."""
        response = authenticated_client.post(
            "/policy/check",
            json={"fail_on_warning": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert "compliant" in data
        assert "errors" in data
        assert "warnings" in data


class TestDriftEndpoint:
    """Tests for drift endpoint."""

    def test_check_drift(self, authenticated_client):
        """Test checking for drift."""
        response = authenticated_client.post(
            "/drift/check",
            json={},
        )
        assert response.status_code == 200
        data = response.json()
        assert "has_drift" in data
        assert "secrets_with_drift" in data


class TestAuditEndpoint:
    """Tests for audit endpoint."""

    def test_get_audit_logs(self, authenticated_client):
        """Test getting audit logs."""
        # First perform some action to generate logs
        authenticated_client.get("/secrets")

        # Then get audit logs
        response = authenticated_client.get("/audit/logs")
        assert response.status_code == 200
        data = response.json()
        assert "entries" in data
        assert "count" in data

    def test_get_audit_logs_with_filters(self, authenticated_client):
        """Test getting audit logs with filters."""
        response = authenticated_client.get("/audit/logs?limit=10&action=list_secrets")
        assert response.status_code == 200
        data = response.json()
        assert "entries" in data


class TestListEndpoints:
    """Tests for list endpoints (providers, targets, variables)."""

    def test_list_providers(self, authenticated_client):
        """Test listing providers from Secretfile."""
        response = authenticated_client.get("/list/providers")
        assert response.status_code == 200
        data = response.json()
        assert "providers" in data
        assert "total" in data
        assert data["total"] >= 0

    def test_list_providers_has_local(self, authenticated_client):
        """Test that the local provider is listed."""
        response = authenticated_client.get("/list/providers")
        assert response.status_code == 200
        data = response.json()
        provider_names = [p["name"] for p in data["providers"]]
        assert "local" in provider_names

    def test_list_targets(self, authenticated_client):
        """Test listing targets from Secretfile."""
        response = authenticated_client.get("/list/targets")
        assert response.status_code == 200
        data = response.json()
        assert "targets" in data
        assert "total" in data
        assert data["total"] >= 0

    def test_list_targets_has_entries(self, authenticated_client):
        """Test that targets are returned for the test Secretfile."""
        response = authenticated_client.get("/list/targets")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] > 0
        target = data["targets"][0]
        assert "secret" in target
        assert "provider" in target
        assert "kind" in target

    def test_list_variables(self, authenticated_client):
        """Test listing variables from Secretfile."""
        response = authenticated_client.get("/list/variables")
        assert response.status_code == 200
        data = response.json()
        assert "variables" in data
        assert "total" in data

    def test_list_variables_has_environment(self, authenticated_client):
        """Test that the environment variable is listed."""
        response = authenticated_client.get("/list/variables")
        assert response.status_code == 200
        data = response.json()
        assert "environment" in data["variables"]
        assert data["variables"]["environment"] == "test"


class TestConfigRenderEndpoint:
    """Tests for config render endpoint."""

    def test_render_config(self, authenticated_client):
        """Test rendering Secretfile configuration."""
        response = authenticated_client.get("/config/render")
        assert response.status_code == 200
        data = response.json()
        assert "config" in data
        config = data["config"]
        assert "secrets" in config
        assert "version" in config

    def test_render_config_includes_variables(self, authenticated_client):
        """Test that rendered config includes variables."""
        response = authenticated_client.get("/config/render")
        assert response.status_code == 200
        data = response.json()
        config = data["config"]
        assert "variables" in config


class TestSchemaEndpoint:
    """Tests for schema endpoint."""

    def test_get_schema(self, client):
        """Test getting JSON schema (no auth required)."""
        response = client.get("/schema")
        assert response.status_code == 200
        schema = response.json()
        assert "properties" in schema or "title" in schema

    def test_schema_has_secrets_property(self, client):
        """Test that the schema describes the Secretfile structure."""
        response = client.get("/schema")
        assert response.status_code == 200
        schema = response.json()
        # JSON schema should have some structure
        assert isinstance(schema, dict)
        assert len(schema) > 0


class TestSecretTypesEndpoint:
    """Tests for secret-types endpoint."""

    def test_get_secret_types(self, client):
        """Test getting available secret types (no auth required)."""
        response = client.get("/secret-types")
        assert response.status_code == 200
        data = response.json()
        assert "generators" in data
        assert "targets" in data

    def test_secret_types_has_generators(self, client):
        """Test that generators are listed."""
        response = client.get("/secret-types")
        assert response.status_code == 200
        data = response.json()
        assert len(data["generators"]) > 0
        generator = data["generators"][0]
        assert "type" in generator
        assert "description" in generator

    def test_secret_types_has_targets(self, client):
        """Test that targets are listed."""
        response = client.get("/secret-types")
        assert response.status_code == 200
        data = response.json()
        assert len(data["targets"]) > 0


class TestGraphEndpoint:
    """Tests for graph endpoint."""

    def test_get_graph(self, authenticated_client):
        """Test generating a graph of Secretfile relationships."""
        response = authenticated_client.get("/graph")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data

    def test_graph_has_secret_nodes(self, authenticated_client):
        """Test that the graph contains secret nodes."""
        response = authenticated_client.get("/graph")
        assert response.status_code == 200
        data = response.json()
        secret_nodes = [n for n in data["nodes"] if n.get("type") == "secret"]
        assert len(secret_nodes) > 0

    def test_graph_has_edges(self, authenticated_client):
        """Test that the graph contains edges."""
        response = authenticated_client.get("/graph")
        assert response.status_code == 200
        data = response.json()
        assert len(data["edges"]) > 0


class TestSecretDetailEndpoint:
    """Tests for secret detail endpoint."""

    def test_get_secret_detail(self, authenticated_client):
        """Test getting detailed info about a secret."""
        response = authenticated_client.get("/secrets/test_password")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test_password"
        assert data["kind"] == "random_password"
        assert "targets" in data
        assert "exists" in data

    def test_get_secret_detail_includes_targets(self, authenticated_client):
        """Test that secret detail includes target information."""
        response = authenticated_client.get("/secrets/test_password")
        assert response.status_code == 200
        data = response.json()
        assert len(data["targets"]) > 0
        target = data["targets"][0]
        assert "provider" in target
        assert "kind" in target

    def test_get_secret_detail_not_found(self, authenticated_client):
        """Test getting detail for non-existent secret returns 404."""
        response = authenticated_client.get("/secrets/nonexistent_secret")
        assert response.status_code == 404

    def test_secret_detail_has_rotation_period(self, authenticated_client):
        """Test that secret with rotation period shows it."""
        response = authenticated_client.get("/secrets/test_password")
        assert response.status_code == 200
        data = response.json()
        assert data["rotation_period"] == "90d"


class TestErrorHandling:
    """Tests for error handling."""

    def test_invalid_endpoint(self, client):
        """Test accessing invalid endpoint."""
        response = client.get("/invalid")
        assert response.status_code == 404

    def test_invalid_method(self, authenticated_client):
        """Test using invalid HTTP method."""
        response = authenticated_client.delete("/secrets")
        assert response.status_code == 405
