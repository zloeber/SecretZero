"""Azure DevOps environment variable helpers."""

from __future__ import annotations

from typing import Any

from secretzero.providers.azdo_client import AzdoClient

API_VERSION = "7.1-preview.1"


def _environments_url(client: AzdoClient, project: str) -> str:
    return client.project_url(project, "_apis/pipelines/environments")


def get_environment_by_name(client: AzdoClient, project: str, name: str) -> dict[str, Any] | None:
    payload = client.get(_environments_url(client, project), params={"api-version": API_VERSION})
    for environment in (payload or {}).get("value") or []:
        if environment.get("name") == name:
            return environment
    return None


def ensure_environment(client: AzdoClient, project: str, name: str, *, create_if_missing: bool) -> dict[str, Any]:
    existing = get_environment_by_name(client, project, name)
    if existing:
        return existing
    if not create_if_missing:
        raise ValueError(f"Azure DevOps environment not found: {name}")
    return client.post(
        _environments_url(client, project),
        json={"name": name, "description": f"SecretZero-managed environment {name}"},
        params={"api-version": API_VERSION},
    ) or {"name": name}


def upsert_environment_variable(
    client: AzdoClient,
    project: str,
    environment: str,
    variable_name: str,
    value: str,
    *,
    is_secret: bool = True,
    create_if_missing: bool = True,
) -> dict[str, Any]:
    env = ensure_environment(client, project, environment, create_if_missing=create_if_missing)
    env_id = env.get("id")
    if env_id is None:
        raise ValueError(f"Azure DevOps environment id missing for {environment}")

    url = client.project_url(
        project,
        f"_apis/pipelines/pipelinePermissions/environment/{env_id}",
    )
    payload = client.get(url, params={"api-version": API_VERSION}) or {}
    resource = dict(payload.get("resource") or {})
    variables = dict(resource.get("variables") or {})
    variables[variable_name] = {"value": value, "isSecret": is_secret}
    resource["variables"] = variables
    payload["resource"] = resource
    payload["typeName"] = "environment"
    payload["resourceId"] = str(env_id)
    return client.patch(url, json=payload, params={"api-version": API_VERSION}) or payload
