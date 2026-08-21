"""Azure DevOps secure file helpers."""

from __future__ import annotations

from typing import Any

from secretzero.providers.azdo_client import AzdoClient

API_VERSION = "7.1-preview.1"


def upload_secure_file(
    client: AzdoClient,
    project: str,
    file_name: str,
    content: bytes,
) -> dict[str, Any]:
    url = client.project_url(project, "_apis/distributedtask/securefiles")
    return client.post(
        url,
        data=content,
        headers={"Content-Type": "application/octet-stream"},
        params={"api-version": API_VERSION, "name": file_name},
    ) or {"name": file_name}


def get_secure_file_by_name(
    client: AzdoClient, project: str, file_name: str
) -> dict[str, Any] | None:
    url = client.project_url(project, "_apis/distributedtask/securefiles")
    payload = client.get(url, params={"api-version": API_VERSION})
    for entry in (payload or {}).get("value") or []:
        if entry.get("name") == file_name:
            return entry
    return None
