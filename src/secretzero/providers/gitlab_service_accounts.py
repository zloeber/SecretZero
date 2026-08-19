"""GitLab group service account REST helpers."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import gitlab


def _group_path(group: str) -> str:
    return quote(str(group), safe="")


def create_group_service_account(client: Any, top_level_group: str, name: str) -> dict[str, Any]:
    """Create a group service account user.

    Returns:
        Dict with ``user_id`` and ``username``.
    """
    path = f"/groups/{_group_path(top_level_group)}/service_accounts"
    try:
        response = client.http_post(path, post_data={"name": name})
    except gitlab.exceptions.GitlabCreateError as exc:
        raise RuntimeError(f"GitLab service account creation failed: {exc}") from exc

    user_id = response.get("id")
    username = response.get("username")
    if user_id is None:
        raise RuntimeError("GitLab API response missing service account user id")
    return {"user_id": int(user_id), "username": username}


def create_service_account_pat(
    client: Any,
    top_level_group: str,
    user_id: int,
    *,
    name: str,
    scopes: list[str],
    expires_at: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Create a personal access token for a group service account."""
    path = (
        f"/groups/{_group_path(top_level_group)}/service_accounts/{user_id}/personal_access_tokens"
    )
    payload: dict[str, Any] = {"name": name, "scopes": scopes}
    if expires_at:
        payload["expires_at"] = expires_at
    if description:
        payload["description"] = description

    try:
        response = client.http_post(path, post_data=payload)
    except gitlab.exceptions.GitlabCreateError as exc:
        raise RuntimeError(f"GitLab service account PAT creation failed: {exc}") from exc

    token_value = response.get("token")
    token_id = response.get("id")
    if not token_value:
        raise RuntimeError("GitLab API response missing service account PAT value")
    return {
        "token": token_value,
        "token_id": token_id,
        "expires_at": response.get("expires_at"),
    }


def rotate_service_account_pat(
    client: Any,
    top_level_group: str,
    user_id: int,
    token_id: int,
    *,
    expires_at: str | None = None,
) -> dict[str, Any]:
    """Rotate a service account personal access token."""
    path = (
        f"/groups/{_group_path(top_level_group)}/service_accounts/{user_id}/"
        f"personal_access_tokens/{token_id}/rotate"
    )
    post_data = {"expires_at": expires_at} if expires_at else None
    try:
        response = client.http_post(path, post_data=post_data)
    except gitlab.exceptions.GitlabCreateError as exc:
        raise RuntimeError(f"GitLab service account PAT rotation failed: {exc}") from exc

    token_value = response.get("token")
    new_id = response.get("id", token_id)
    if not token_value:
        raise RuntimeError("GitLab API response missing rotated service account PAT value")
    return {
        "token": token_value,
        "token_id": new_id,
        "expires_at": response.get("expires_at"),
    }


def revoke_service_account_pat(
    client: Any,
    top_level_group: str,
    user_id: int,
    token_id: int,
) -> None:
    """Revoke a service account personal access token."""
    path = (
        f"/groups/{_group_path(top_level_group)}/service_accounts/{user_id}/"
        f"personal_access_tokens/{token_id}"
    )
    try:
        client.http_delete(path)
    except gitlab.exceptions.GitlabDeleteError as exc:
        raise RuntimeError(f"GitLab service account PAT revoke failed: {exc}") from exc


def add_group_member(
    client: Any,
    group: str,
    user_id: int,
    access_level: int,
) -> None:
    """Add a service account user to a group (idempotent)."""
    gl_group = client.groups.get(group, lazy=True)
    try:
        gl_group.members.create({"user_id": user_id, "access_level": access_level})
    except gitlab.exceptions.GitlabCreateError as exc:
        if "Member already exists" in str(exc):
            return
        raise RuntimeError(f"GitLab group membership failed: {exc}") from exc


def add_project_member(
    client: Any,
    project: str,
    user_id: int,
    access_level: int,
) -> None:
    """Add a service account user to a project (idempotent)."""
    gl_project = client.projects.get(project, lazy=True)
    try:
        gl_project.members.create({"user_id": user_id, "access_level": access_level})
    except gitlab.exceptions.GitlabCreateError as exc:
        if "Member already exists" in str(exc):
            return
        raise RuntimeError(f"GitLab project membership failed: {exc}") from exc


def apply_memberships(
    client: Any,
    user_id: int,
    memberships: list[dict[str, Any]],
    *,
    default_project: str | None = None,
) -> None:
    """Apply configured group/project memberships for a service account."""
    for entry in memberships:
        resource_type = entry.get("resource_type")
        resource = entry.get("resource")
        access_level = int(entry.get("access_level", 30))
        if resource in (None, "", "auto") and resource_type == "project" and default_project:
            resource = default_project
        if not resource:
            continue
        if resource_type == "group":
            add_group_member(client, str(resource), user_id, access_level)
        elif resource_type == "project":
            add_project_member(client, str(resource), user_id, access_level)
        else:
            raise ValueError(f"Unsupported membership resource_type: {resource_type}")
