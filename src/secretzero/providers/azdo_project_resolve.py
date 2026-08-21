"""Resolve Azure DevOps project names for targets and generators."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_AUTO = frozenset({"auto", ""})


def parse_azdo_remote_project(remote_url: str, organization: str | None = None) -> str | None:
    """Extract project name from an Azure DevOps git remote URL."""
    url = remote_url.strip()
    if not url:
        return None

    if url.startswith("git@"):
        match = re.match(r"^git@(?:ssh\.)?dev\.azure\.com:v\d+/([^/]+)/([^/]+?)(?:\.git)?$", url)
        if match:
            if organization and match.group(1) != organization:
                return None
            return match.group(2)
        return None

    if "://" in url:
        parsed = urlparse(url)
        parts = parsed.path.strip("/").split("/")
        if "dev.azure.com" in parsed.netloc and len(parts) >= 2:
            if organization and parts[0] != organization:
                return None
            project = parts[1]
            if project.endswith(".git"):
                project = project[:-4]
            return project
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


def resolve_azdo_project(
    *,
    project: str | None = None,
    provider_config: dict[str, Any] | None = None,
    variables: dict[str, Any] | None = None,
    organization: str | None = None,
    cwd: Path | None = None,
) -> str:
    """Resolve an Azure DevOps project name."""
    provider_config = provider_config or {}
    variables = variables or {}

    if project and project not in _AUTO:
        return project

    for key in ("project", "project_name"):
        candidate = provider_config.get(key)
        if candidate and str(candidate) not in _AUTO:
            return str(candidate)

    manifest_project = variables.get("azdo_project")
    if manifest_project and str(manifest_project) not in _AUTO:
        return str(manifest_project)

    for env_key in ("SYSTEM_TEAMPROJECT", "BUILD_PROJECTNAME"):
        env_project = os.environ.get(env_key)
        if env_project:
            return env_project

    org = organization or provider_config.get("organization")
    remote = _git_origin_remote(cwd or Path.cwd())
    if remote:
        parsed = parse_azdo_remote_project(remote, organization=org)
        if parsed:
            return parsed

    raise ValueError(
        "Could not resolve Azure DevOps project. Set target config 'project', "
        "provider.project, variables.azdo_project, run inside Azure Pipelines, "
        "or use a git remote pointing at dev.azure.com."
    )
