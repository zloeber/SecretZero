"""Tests for Azure DevOps variable group helpers."""

from unittest.mock import MagicMock

from secretzero.providers.azdo_variable_groups import upsert_variable_group_secret

ORG_WRITE_URL = "https://dev.azure.com/org/_apis/distributedtask/variablegroups"


def test_upsert_variable_group_secret_creates_group():
    client = MagicMock()
    client.project_url.return_value = (
        "https://dev.azure.com/org/my-project/_apis/distributedtask/variablegroups"
    )
    client.organization_url.return_value = ORG_WRITE_URL
    client.get.return_value = None
    client.post.return_value = {"id": 1, "name": "prod-secrets"}

    result = upsert_variable_group_secret(
        client,
        "my-project",
        "prod-secrets",
        "API_KEY",
        "secret-value",
    )

    assert result["name"] == "prod-secrets"
    client.post.assert_called_once()
    assert client.post.call_args.args[0] == ORG_WRITE_URL
    body = client.post.call_args.kwargs["json"]
    assert body["variableGroupProjectReferences"][0]["projectReference"]["name"] == "my-project"


def test_upsert_variable_group_secret_updates_at_org_scope():
    client = MagicMock()
    client.project_url.return_value = (
        "https://dev.azure.com/org/my-project/_apis/distributedtask/variablegroups"
    )
    client.organization_url.side_effect = lambda path: f"https://dev.azure.com/org/{path}"
    client.get.return_value = {
        "value": [
            {
                "id": 42,
                "name": "prod-secrets",
                "variables": {"OLD": {"value": "kept", "isSecret": True}},
            }
        ]
    }
    client.put.return_value = {"id": 42, "name": "prod-secrets"}

    upsert_variable_group_secret(
        client,
        "my-project",
        "prod-secrets",
        "API_KEY",
        "secret-value",
        create_if_missing=False,
    )

    client.put.assert_called_once()
    assert (
        client.put.call_args.args[0]
        == "https://dev.azure.com/org/_apis/distributedtask/variablegroups/42"
    )
    assert "/my-project/" not in client.put.call_args.args[0]
    body = client.put.call_args.kwargs["json"]
    assert body["variables"]["API_KEY"]["value"] == "secret-value"
    assert "OLD" in body["variables"]
    assert body["variableGroupProjectReferences"] == [
        {
            "name": "prod-secrets",
            "description": "",
            "projectReference": {"name": "my-project"},
        }
    ]


def test_upsert_variable_group_secret_keeps_existing_project_references():
    client = MagicMock()
    client.project_url.return_value = (
        "https://dev.azure.com/org/my-project/_apis/distributedtask/variablegroups"
    )
    client.organization_url.side_effect = lambda path: f"https://dev.azure.com/org/{path}"
    shared_refs = [
        {
            "name": "prod-secrets",
            "projectReference": {"id": "proj-a", "name": "project-a"},
        },
        {
            "name": "prod-secrets",
            "projectReference": {"id": "proj-b", "name": "project-b"},
        },
    ]
    client.get.return_value = {
        "value": [
            {
                "id": 42,
                "name": "prod-secrets",
                "variables": {},
                "variableGroupProjectReferences": shared_refs,
            }
        ]
    }
    client.put.return_value = {"id": 42}

    upsert_variable_group_secret(
        client,
        "my-project",
        "prod-secrets",
        "API_KEY",
        "secret-value",
    )

    body = client.put.call_args.kwargs["json"]
    assert body["variableGroupProjectReferences"] == shared_refs


def test_keyvault_variable_group_create_is_org_scoped():
    from secretzero.targets.azure_devops import AzdoKeyVaultVariableGroupTarget

    provider = MagicMock()
    provider.config = {"project": "my-project"}
    provider.auth.organization = "org"
    client = MagicMock()
    client.organization_url.return_value = ORG_WRITE_URL
    provider.auth.get_client.return_value = client

    target = AzdoKeyVaultVariableGroupTarget(
        provider,
        {
            "project": "my-project",
            "variable_group": "kv-group",
            "service_connection": "endpoint-id",
            "vault_name": "prod-vault",
        },
    )

    assert target.store("DB_PASSWORD", "unused-by-keyvault-map") is True
    client.project_url.assert_not_called()
    assert client.post.call_args.args[0] == ORG_WRITE_URL
    body = client.post.call_args.kwargs["json"]
    assert body["variableGroupProjectReferences"][0]["projectReference"]["name"] == "my-project"
