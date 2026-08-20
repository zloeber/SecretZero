"""Azure DevOps Library variable group helpers."""

from __future__ import annotations

from typing import Any

from secretzero.providers.azdo_client import AzdoClient

API_VERSION = "7.1"


def _variable_groups_url(client: AzdoClient, project: str) -> str:
    return client.project_url(project, "_apis/distributedtask/variablegroups")


def get_variable_group_by_name(
    client: AzdoClient, project: str, name: str
) -> dict[str, Any] | None:
    url = _variable_groups_url(client, project)
    payload = client.get(url, params={"groupName": name, "api-version": API_VERSION})
    if not payload:
        return None
    groups = payload.get("value") or []
    for group in groups:
        if group.get("name") == name:
            return group
    return groups[0] if groups else None


def upsert_variable_group_secret(
    client: AzdoClient,
    project: str,
    group_name: str,
    variable_name: str,
    value: str,
    *,
    create_if_missing: bool = True,
    is_secret: bool = True,
    allow_override: bool = False,
    description: str | None = None,
) -> dict[str, Any]:
    """Create or update a secret variable in a Library variable group."""
    existing = get_variable_group_by_name(client, project, group_name)
    variable_payload = {
        "value": value,
        "isSecret": is_secret,
        "isReadOnly": not allow_override,
    }

    if existing is None:
        if not create_if_missing:
            raise ValueError(f"Azure DevOps variable group not found: {group_name}")
        body = {
            "name": group_name,
            "description": description or "",
            "variables": {variable_name: variable_payload},
            "variableGroupProjectReferences": [
                {
                    "name": group_name,
                    "projectReference": {"name": project},
                }
            ],
        }
        url = _variable_groups_url(client, project)
        return client.post(url, json=body, params={"api-version": API_VERSION}) or {}

    variables = dict(existing.get("variables") or {})
    variables[variable_name] = variable_payload
    existing["variables"] = variables
    if description:
        existing["description"] = description
    group_id = existing.get("id")
    url = f"{_variable_groups_url(client, project)}/{group_id}"
    return client.put(url, json=existing, params={"api-version": API_VERSION}) or existing


def variable_group_has_secret(
    client: AzdoClient,
    project: str,
    group_name: str,
    variable_name: str,
) -> bool:
    group = get_variable_group_by_name(client, project, group_name)
    if not group:
        return False
    variables = group.get("variables") or {}
    entry = variables.get(variable_name)
    return isinstance(entry, dict) and entry.get("isSecret") is True
