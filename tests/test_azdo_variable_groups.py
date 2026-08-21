"""Tests for Azure DevOps variable group helpers."""

from unittest.mock import MagicMock

from secretzero.providers.azdo_variable_groups import upsert_variable_group_secret


def test_upsert_variable_group_secret_creates_group():
    client = MagicMock()
    client.project_url.return_value = "https://dev.azure.com/org/project/_apis/groups"
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
