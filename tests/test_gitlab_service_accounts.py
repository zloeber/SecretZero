"""Tests for GitLab group service account REST helpers."""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock

import gitlab
import pytest

from secretzero.providers.gitlab_service_accounts import (
    add_group_member,
    apply_memberships,
    create_group_service_account,
    create_service_account_pat,
)


def test_module_has_no_toplevel_gitlab_import() -> None:
    """python-gitlab is extras-only; module import must not require it."""
    src = (
        Path(__file__).resolve().parents[1] / "src/secretzero/providers/gitlab_service_accounts.py"
    )
    tree = ast.parse(src.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Import):
            assert all(alias.name != "gitlab" for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert module != "gitlab" and not module.startswith("gitlab.")


def test_gitlab_service_accounts_importable_without_python_gitlab(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Simulate a bare install without the gitlab extra."""
    monkeypatch.setitem(sys.modules, "gitlab", None)
    monkeypatch.delitem(sys.modules, "secretzero.providers.gitlab_service_accounts", raising=False)
    mod = importlib.import_module("secretzero.providers.gitlab_service_accounts")
    assert callable(mod.create_group_service_account)


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
