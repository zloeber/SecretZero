"""Tests for the Terraform Cloud provider upsert and read behavior."""

import ast
import inspect

import pytest

from secretzero.providers.terraform_cloud import TerraformCloudProvider


def _provider() -> TerraformCloudProvider:
    return TerraformCloudProvider(
        "tfc",
        config={
            "organization": "acme",
            "auth": {
                "kind": "token",
                "config": {"token": "test-token", "organization": "acme"},
            },
        },
    )


class _Client:
    def __init__(self) -> None:
        self.workspace = {"id": "ws-1", "name": "network-prod"}
        self.workspace_vars: list[dict] = []
        self.varsets: list[dict] = []
        self.varset_vars: list[dict] = []
        self.created_workspace_vars: list[dict] = []
        self.updated_workspace_vars: list[dict] = []
        self.created_varsets: list[dict] = []
        self.created_varset_vars: list[dict] = []
        self.updated_varset_vars: list[dict] = []

    def get_workspace(self, organization: str, name: str) -> dict:
        assert organization == "acme"
        assert name == "network-prod"
        return self.workspace

    def list_workspace_variables(self, workspace_id: str) -> list[dict]:
        assert workspace_id == "ws-1"
        return list(self.workspace_vars)

    def create_workspace_variable(self, workspace_id: str, **kwargs) -> dict:
        self.created_workspace_vars.append({"workspace_id": workspace_id, **kwargs})
        return {"id": "var-new", **kwargs}

    def update_workspace_variable(self, workspace_id: str, variable_id: str, attributes: dict):
        self.updated_workspace_vars.append(
            {"workspace_id": workspace_id, "variable_id": variable_id, "attributes": attributes}
        )
        return {"id": variable_id}

    def list_varsets(self, organization: str) -> list[dict]:
        assert organization == "acme"
        return list(self.varsets)

    def create_varset(self, organization: str, **kwargs) -> dict:
        self.created_varsets.append({"organization": organization, **kwargs})
        return {"id": "varset-new", "name": kwargs.get("name")}

    def list_varset_variables(self, varset_id: str) -> list[dict]:
        assert varset_id in {"varset-1", "varset-new"}
        return list(self.varset_vars)

    def create_varset_variable(self, varset_id: str, **kwargs) -> dict:
        self.created_varset_vars.append({"varset_id": varset_id, **kwargs})
        return {"id": "var-set", **kwargs}

    def update_varset_variable(self, varset_id: str, variable_id: str, attributes: dict):
        self.updated_varset_vars.append(
            {"varset_id": varset_id, "variable_id": variable_id, "attributes": attributes}
        )
        return {"id": variable_id}

    def account_details(self) -> dict:
        return {"id": "user-1", "username": "octo", "email": "octo@example.com"}


def test_provider_module_does_not_import_requests():
    import secretzero.providers.terraform_cloud as module

    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name != "requests" for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module != "requests"


def test_provider_kind_is_a_string():
    provider = _provider()
    assert provider.provider_kind == "terraform_cloud"


def test_upsert_workspace_variable_creates():
    provider = _provider()
    client = _Client()
    provider._tfc = client

    provider.upsert_workspace_variable(
        organization="acme",
        workspace="network-prod",
        workspace_id=None,
        key="API_TOKEN",
        value="example-value",
        category="env",
        sensitive=True,
        description="api",
    )

    created = client.created_workspace_vars[0]
    assert created["key"] == "API_TOKEN"
    assert created["sensitive"] is True
    assert created["description"] == "api"
    assert client.updated_workspace_vars == []


def test_sensitive_update_sends_only_value():
    provider = _provider()
    client = _Client()
    client.workspace_vars = [
        {
            "id": "var-1",
            "key": "API_TOKEN",
            "category": "env",
            "sensitive": True,
            "hcl": False,
            "value": None,
        }
    ]
    provider._tfc = client

    provider.upsert_workspace_variable(
        organization="acme",
        workspace="network-prod",
        workspace_id=None,
        key="API_TOKEN",
        value="rotated-value",
        description="should-not-be-sent",
    )

    assert client.created_workspace_vars == []
    assert client.updated_workspace_vars[0]["attributes"] == {"value": "rotated-value"}


def test_attribute_mismatch_does_not_patch():
    provider = _provider()
    client = _Client()
    client.workspace_vars = [
        {
            "id": "var-1",
            "key": "API_TOKEN",
            "category": "env",
            "sensitive": False,
            "hcl": True,
            "value": "old",
        }
    ]
    provider._tfc = client

    with pytest.raises(ValueError, match="hcl"):
        provider.upsert_workspace_variable(
            organization="acme",
            workspace="network-prod",
            workspace_id=None,
            key="API_TOKEN",
            value="new-value",
            sensitive=False,
            hcl=False,
        )

    assert client.updated_workspace_vars == []


def test_missing_variable_without_create_raises():
    provider = _provider()
    client = _Client()
    provider._tfc = client

    with pytest.raises(ValueError, match="API_TOKEN"):
        provider.upsert_workspace_variable(
            organization="acme",
            workspace="network-prod",
            workspace_id=None,
            key="API_TOKEN",
            value="example-value",
            create_if_missing=False,
        )


def test_missing_varset_without_create_set_raises():
    provider = _provider()
    client = _Client()
    provider._tfc = client

    with pytest.raises(ValueError, match="shared-prod"):
        provider.upsert_varset_variable(
            organization="acme",
            varset="shared-prod",
            varset_id=None,
            key="API_TOKEN",
            value="example-value",
            create_set=False,
        )

    assert client.created_varsets == []


def test_create_set_then_variable_without_assignments():
    provider = _provider()
    client = _Client()
    provider._tfc = client

    provider.upsert_varset_variable(
        organization="acme",
        varset="shared-prod",
        varset_id=None,
        key="API_TOKEN",
        value="example-value",
        create_set=True,
    )

    created = client.created_varsets[0]
    assert created["name"] == "shared-prod"
    assert created["global_set"] is False
    assert created["workspace_ids"] in (None, [])
    assert client.created_varset_vars[0]["varset_id"] == "varset-new"


def test_existing_varset_is_not_updated():
    provider = _provider()
    client = _Client()
    client.varsets = [{"id": "varset-1", "name": "shared-prod"}]
    provider._tfc = client

    provider.upsert_varset_variable(
        organization="acme",
        varset="shared-prod",
        varset_id=None,
        key="API_TOKEN",
        value="example-value",
        create_set=True,
        global_set=True,
    )

    assert client.created_varsets == []
    assert client.created_varset_vars[0]["varset_id"] == "varset-1"


def test_retrieve_secret_returns_nonsensitive_value():
    provider = _provider()
    client = _Client()
    client.workspace_vars = [
        {
            "id": "var-1",
            "key": "LOG_LEVEL",
            "category": "env",
            "sensitive": False,
            "hcl": False,
            "value": "debug",
        }
    ]
    provider._tfc = client

    assert (
        provider.retrieve_secret(
            "LOG_LEVEL",
            organization="acme",
            workspace="network-prod",
            category="env",
            kind="tfc_workspace_variable",
        )
        == "debug"
    )


def test_retrieve_secret_rejects_sensitive_variable():
    provider = _provider()
    client = _Client()
    client.workspace_vars = [
        {
            "id": "var-1",
            "key": "API_TOKEN",
            "category": "env",
            "sensitive": True,
            "hcl": False,
            "value": None,
        }
    ]
    provider._tfc = client

    with pytest.raises(ValueError, match="sensitive and write-only"):
        provider.retrieve_secret(
            "API_TOKEN",
            organization="acme",
            workspace="network-prod",
            kind="tfc_workspace_variable",
        )


def test_token_info_omits_token():
    provider = _provider()
    provider._tfc = _Client()
    info = provider.get_token_info()
    assert info["user"] == "octo"
    assert info["organization"] == "acme"
    assert "test-token" not in str(info)
