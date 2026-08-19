"""Tests for GitLab access token REST helpers."""

from unittest.mock import MagicMock

import pytest

from secretzero.providers.gitlab_tokens import (
    create_group_access_token,
    revoke_group_access_tokens_by_name,
    rotate_group_access_token,
)


@pytest.fixture
def mock_group_client():
    group = MagicMock()
    group.id = 42
    token_obj = MagicMock()
    token_obj.token = "glpat-group-token"
    token_obj.id = 99
    group.access_tokens.create.return_value = token_obj
    existing = MagicMock()
    existing.name = "secretzero-deploy"
    existing.delete = MagicMock()
    group.access_tokens.list.return_value = [existing]
    client = MagicMock()
    client.groups.get.return_value = group
    return client, group


def test_create_group_access_token_returns_token_and_id(mock_group_client):
    client, group = mock_group_client

    result = create_group_access_token(
        client,
        "myorg",
        token_name="secretzero-deploy",
        scopes=["read_repository"],
        access_level=30,
        expires_at="2027-01-01",
        description="test",
    )

    assert result["token"] == "glpat-group-token"
    assert result["token_id"] == 99
    group.access_tokens.create.assert_called_once()
    payload = group.access_tokens.create.call_args[0][0]
    assert payload["name"] == "secretzero-deploy"
    assert payload["scopes"] == ["read_repository"]


def test_revoke_group_access_tokens_by_name(mock_group_client):
    client, group = mock_group_client

    revoked = revoke_group_access_tokens_by_name(client, "myorg", "secretzero-deploy")

    assert revoked == 1
    group.access_tokens.list.return_value[0].delete.assert_called_once()


def test_rotate_group_access_token(mock_group_client):
    client, group = mock_group_client
    rotated = MagicMock()
    rotated.token = "glpat-rotated"
    rotated.id = 100
    group.access_tokens.rotate.return_value = rotated

    result = rotate_group_access_token(client, "myorg", token_id=99, expires_at="2027-06-01")

    assert result["token"] == "glpat-rotated"
    assert result["token_id"] == 100
    group.access_tokens.rotate.assert_called_once_with(99, {"expires_at": "2027-06-01"})
