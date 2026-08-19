"""Shared GitLab project and group access token REST helpers."""

from __future__ import annotations

from typing import Any


def create_group_access_token(
    client: Any,
    group: str,
    *,
    token_name: str,
    scopes: list[str],
    access_level: int,
    expires_at: str,
    description: str | None = None,
) -> dict[str, Any]:
    """Create a GitLab group access token.

    Args:
        client: Authenticated python-gitlab client.
        group: Group path or numeric ID.
        token_name: Token display name in GitLab.
        scopes: GitLab token scopes.
        access_level: GitLab role integer.
        expires_at: Expiration date ``YYYY-MM-DD``.
        description: Optional token description.

    Returns:
        Dict with ``token`` (one-time plaintext) and ``token_id``.

    Raises:
        RuntimeError: When the GitLab API call fails or omits the token value.
    """
    payload: dict[str, Any] = {
        "name": token_name,
        "scopes": scopes,
        "expires_at": expires_at,
        "access_level": access_level,
    }
    if description:
        payload["description"] = description

    gl_group = client.groups.get(group, lazy=True)
    try:
        created = gl_group.access_tokens.create(payload)
    except Exception as exc:
        raise RuntimeError(f"GitLab group access token creation failed: {exc}") from exc

    token_value = getattr(created, "token", None)
    token_id = getattr(created, "id", None)
    if not token_value:
        raise RuntimeError("GitLab API response missing group access token value")
    return {"token": token_value, "token_id": token_id}


def revoke_group_access_tokens_by_name(client: Any, group: str, token_name: str) -> int:
    """Revoke all group access tokens matching ``token_name``.

    Returns:
        Number of tokens revoked.
    """
    gl_group = client.groups.get(group, lazy=True)
    revoked = 0
    for token in gl_group.access_tokens.list():
        if getattr(token, "name", None) == token_name:
            token.delete()
            revoked += 1
    return revoked


def rotate_group_access_token(
    client: Any,
    group: str,
    *,
    token_id: int,
    expires_at: str | None = None,
) -> dict[str, Any]:
    """Rotate a GitLab group access token.

    Returns:
        Dict with rotated ``token`` and ``token_id``.
    """
    gl_group = client.groups.get(group, lazy=True)
    body: dict[str, str] = {}
    if expires_at:
        body["expires_at"] = expires_at
    try:
        rotated = gl_group.access_tokens.rotate(token_id, body or None)
    except Exception as exc:
        raise RuntimeError(f"GitLab group access token rotation failed: {exc}") from exc

    token_value = getattr(rotated, "token", None)
    new_id = getattr(rotated, "id", token_id)
    if not token_value:
        raise RuntimeError("GitLab API response missing rotated group access token value")
    return {"token": token_value, "token_id": new_id}
