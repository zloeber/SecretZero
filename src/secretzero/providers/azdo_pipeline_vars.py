"""Azure DevOps pipeline definition variable helpers."""

from __future__ import annotations

from typing import Any

from secretzero.providers.azdo_client import AzdoClient

API_VERSION = "7.1"


def _definitions_url(client: AzdoClient, project: str) -> str:
    return client.project_url(project, "_apis/build/definitions")


def _resolve_definition_id(client: AzdoClient, project: str, pipeline: str | int) -> int:
    if isinstance(pipeline, int) or str(pipeline).isdigit():
        return int(pipeline)
    url = _definitions_url(client, project)
    payload = client.get(url, params={"name": pipeline, "api-version": API_VERSION})
    definitions = (payload or {}).get("value") or []
    for definition in definitions:
        if definition.get("name") == pipeline:
            return int(definition["id"])
    raise ValueError(f"Azure DevOps pipeline definition not found: {pipeline}")


def upsert_pipeline_variable(
    client: AzdoClient,
    project: str,
    pipeline: str | int,
    variable_name: str,
    value: str,
    *,
    is_secret: bool = True,
    allow_override: bool = False,
) -> dict[str, Any]:
    definition_id = _resolve_definition_id(client, project, pipeline)
    url = f"{_definitions_url(client, project)}/{definition_id}"
    definition = client.get(url, params={"api-version": API_VERSION})
    if not definition:
        raise ValueError(f"Azure DevOps pipeline definition not found: {pipeline}")

    variables = dict(definition.get("variables") or {})
    variables[variable_name] = {
        "value": value,
        "isSecret": is_secret,
        "allowOverride": allow_override,
    }
    definition["variables"] = variables
    return client.put(url, json=definition, params={"api-version": API_VERSION}) or definition
