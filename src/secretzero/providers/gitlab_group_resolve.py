"""Resolve GitLab group paths for targets and generators."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from secretzero.providers.gitlab_project_resolve import resolve_gitlab_project

_AUTO = frozenset({"auto", ""})


def derive_group_from_project(project_path: str) -> str:
    """Return parent namespace path for a GitLab project path."""
    parts = project_path.strip("/").split("/")
    if len(parts) <= 1:
        return project_path
    return "/".join(parts[:-1])


def resolve_gitlab_group(
    *,
    group: str | None = None,
    provider_config: dict[str, Any] | None = None,
    variables: dict[str, Any] | None = None,
    cwd: Path | None = None,
) -> str:
    """Resolve a GitLab group ID or path.

    Resolution order:
        1. Explicit ``group`` (not ``auto``)
        2. Provider ``group`` / ``group_id``
        3. Manifest ``variables.gitlab_group``
        4. ``CI_PROJECT_NAMESPACE`` when ``GITLAB_CI=true``
        5. Derive from resolved project path via :func:`resolve_gitlab_project`

    Args:
        group: Target or generator ``group`` config value.
        provider_config: Provider-level configuration dict.
        variables: Interpolated manifest ``variables`` dict.
        cwd: Working directory for git remote lookup when resolving project.

    Returns:
        GitLab group path or numeric ID string.

    Raises:
        ValueError: When no group can be resolved.
    """
    provider_config = provider_config or {}
    variables = variables or {}

    if group and group not in _AUTO:
        return group

    for key in ("group", "group_id"):
        candidate = provider_config.get(key)
        if candidate and str(candidate) not in _AUTO:
            return str(candidate)

    manifest_group = variables.get("gitlab_group")
    if manifest_group and str(manifest_group) not in _AUTO:
        return str(manifest_group)

    if os.environ.get("GITLAB_CI") == "true":
        namespace = os.environ.get("CI_PROJECT_NAMESPACE")
        if namespace:
            return namespace

    try:
        project = resolve_gitlab_project(
            project="auto",
            provider_config=provider_config,
            cwd=cwd or Path.cwd(),
        )
        return derive_group_from_project(project)
    except ValueError:
        pass

    raise ValueError(
        "Could not resolve GitLab group. Set config 'group' (or 'group: auto' with "
        "provider.group / variables.gitlab_group), run inside GitLab CI, or ensure "
        "project auto-resolution succeeds."
    )


def resolve_gitlab_top_level_group(client: Any | None, group_path: str) -> str:
    """Return the top-level group path for group service account APIs.

    Group service account creation requires a top-level group. When ``group_path``
    is nested, walk parent groups via the GitLab API when a client is available,
    otherwise use the first path segment as a heuristic.

    Args:
        client: Authenticated python-gitlab client, or ``None`` for path heuristic.
        group_path: Resolved group path or numeric ID string.

    Returns:
        Top-level group path or ID suitable for service account API calls.
    """
    if not group_path or "/" not in group_path.strip("/"):
        return group_path

    if client is None:
        return group_path.strip("/").split("/")[0]

    try:
        current = client.groups.get(group_path, lazy=False)
    except Exception:
        return group_path.strip("/").split("/")[0]

    visited: set[int | str] = set()
    while True:
        current_id = getattr(current, "id", None)
        if current_id is not None and current_id in visited:
            break
        if current_id is not None:
            visited.add(current_id)

        parent_id = getattr(current, "parent_id", None)
        if not parent_id:
            break

        current = client.groups.get(parent_id, lazy=False)

    full_path = getattr(current, "full_path", None)
    if full_path:
        return str(full_path)

    return group_path.strip("/").split("/")[0]
