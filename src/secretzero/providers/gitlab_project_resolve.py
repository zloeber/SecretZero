"""Resolve GitLab project paths for targets and generators."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_AUTO = frozenset({"auto", ""})


def parse_gitlab_remote_project(remote_url: str) -> str | None:
    """Extract ``group/project`` from a GitLab git remote URL.

    Supports SSH and HTTPS remotes for GitLab.com and self-hosted instances.

    Args:
        remote_url: Value from ``git remote get-url origin``.

    Returns:
        URL-encoded path ``group/project`` or nested ``group/subgroup/project``,
        or ``None`` when the URL does not look like GitLab.
    """
    url = remote_url.strip()
    if not url:
        return None

    if url.startswith("git@"):
        # git@gitlab.com:group/project.git
        match = re.match(r"^git@[^:]+:(.+?)(?:\.git)?$", url)
        if match:
            return match.group(1).strip("/")
        return None

    if "://" in url:
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        if path.endswith(".git"):
            path = path[:-4]
        return path or None

    return None


def _git_origin_remote(cwd: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def resolve_gitlab_project(
    *,
    project: str | None = None,
    provider_config: dict[str, Any] | None = None,
    cwd: Path | None = None,
) -> str:
    """Resolve a GitLab project ID or path.

    Resolution order:
        1. Explicit ``project`` (not ``auto``)
        2. Provider ``project`` / ``project_id``
        3. ``CI_PROJECT_PATH`` when ``GITLAB_CI=true``
        4. ``git remote get-url origin`` parsed as GitLab project path

    Args:
        project: Target or generator ``project`` config value.
        provider_config: Provider-level configuration dict.
        cwd: Working directory for git remote lookup.

    Returns:
        GitLab project path or numeric ID string.

    Raises:
        ValueError: When no project can be resolved.
    """
    provider_config = provider_config or {}

    if project and project not in _AUTO:
        return project

    for key in ("project", "project_id"):
        candidate = provider_config.get(key)
        if candidate and str(candidate) not in _AUTO:
            return str(candidate)

    if os.environ.get("GITLAB_CI") == "true":
        ci_project = os.environ.get("CI_PROJECT_PATH")
        if ci_project:
            return ci_project

    workdir = cwd or Path.cwd()
    remote = _git_origin_remote(workdir)
    if remote:
        parsed = parse_gitlab_remote_project(remote)
        if parsed:
            return parsed

    raise ValueError(
        "Could not resolve GitLab project. Set target config 'project' (or 'project: auto' "
        "with provider.project / variables.gitlab_project), run inside GitLab CI, or use a "
        "git repository with a GitLab origin remote."
    )
