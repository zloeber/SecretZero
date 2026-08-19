"""Tests for GitLab group service account REST helpers."""

from unittest.mock import MagicMock

import gitlab
import pytest

from secretzero.providers.gitlab_service_accounts import (
    add_group_member,
    apply_memberships,
    create_group_service_account,
    create_service_account_pat,
)


def test_create_group_service_account():
    client = MagicMock()
    client.http_post.return_value = {"id": 123, "username": "service_account_myorg_bot"}

    result = create_group_service_account(client, "myorg", "secretzero-bot")

    assert result["user_id"] == 123
    assert result["username"] == "service_account_myorg_bot"
    client.http_post.assert_called_once()


def test_create_service_account_pat():
    client = MagicMock()
    client.http_post.return_value = {
        "token": "glpat-sa-token",
        "id": 456,
        "expires_at": "2027-01-01",
    }

    result = create_service_account_pat(
        client,
        "myorg",
        123,
        name="secretzero-token",
        scopes=["api"],
        expires_at="2027-01-01",
    )

    assert result["token"] == "glpat-sa-token"
    assert result["token_id"] == 456


def test_add_group_member_idempotent():
    client = MagicMock()
    group = MagicMock()
    client.groups.get.return_value = group
    group.members.create.side_effect = gitlab.exceptions.GitlabCreateError(
        "Member already exists", response_code=409
    )

    add_group_member(client, "myorg", 123, 30)

    group.members.create.assert_called_once()


def test_apply_memberships_project_and_group():
    client = MagicMock()
    group = MagicMock()
    project = MagicMock()
    client.groups.get.return_value = group
    client.projects.get.return_value = project

    apply_memberships(
        client,
        123,
        [
            {"resource_type": "group", "resource": "myorg/platform", "access_level": 40},
            {"resource_type": "project", "resource": "myorg/app", "access_level": 30},
        ],
    )

    group.members.create.assert_called_once()
    project.members.create.assert_called_once()
