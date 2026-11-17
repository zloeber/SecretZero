"""Thin REST client for Azure DevOps Services."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import requests

_ADO_ERROR_MESSAGE_LIMIT = 300


def ado_error_message(response: requests.Response) -> str | None:
    """Return Azure DevOps' JSON ``message`` field.

    The raw body is ignored so a failed write cannot echo a secret payload
    into CLI output.
    """
    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    message = payload.get("message")
    if not isinstance(message, str):
        return None
    cleaned = " ".join(message.split())
    if not cleaned:
        return None
    if len(cleaned) > _ADO_ERROR_MESSAGE_LIMIT:
        return cleaned[: _ADO_ERROR_MESSAGE_LIMIT - 3] + "..."
    return cleaned


def raise_for_azdo_status(response: requests.Response) -> None:
    """Raise ``HTTPError``, appending Azure DevOps' ``message`` when present."""
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        detail = ado_error_message(response)
        if not detail:
            raise
        raise requests.HTTPError(f"{exc} - {detail}", response=response) from exc


class AzdoClient:
    """Minimal Azure DevOps Services REST client using PAT basic auth."""

    def __init__(self, organization: str, pat: str, *, timeout: int = 30) -> None:
        if not organization:
            raise ValueError("organization is required for Azure DevOps Services")
        if not pat:
            raise ValueError("PAT is required for Azure DevOps Services")
        self.organization = organization
        self.base_url = f"https://dev.azure.com/{organization}"
        self._session = requests.Session()
        self._session.auth = ("", pat)
        self._session.headers.update({"Content-Type": "application/json"})
        self._timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def project_url(self, project: str, path: str) -> str:
        encoded = quote(project, safe="")
        return self._url(f"{encoded}/{path.lstrip('/')}")

    def organization_url(self, path: str) -> str:
        """Build an organization-scoped REST URL.

        Variable group create and update are organization-scoped. The project
        is carried in ``variableGroupProjectReferences``, not the path.
        """
        return self._url(path)

    def get(self, url: str, *, params: dict[str, Any] | None = None) -> Any:
        response = self._session.get(url, params=params, timeout=self._timeout)
        if response.status_code == 404:
            return None
        raise_for_azdo_status(response)
        if not response.content:
            return None
        return response.json()

    def post(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        response = self._session.post(
            url,
            json=json,
            data=data,
            headers=headers,
            params=params,
            timeout=self._timeout,
        )
        raise_for_azdo_status(response)
        if not response.content:
            return None
        return response.json()

    def put(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        response = self._session.put(url, json=json, params=params, timeout=self._timeout)
        raise_for_azdo_status(response)
        if not response.content:
            return None
        return response.json()

    def patch(
        self,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        response = self._session.patch(url, json=json, params=params, timeout=self._timeout)
        raise_for_azdo_status(response)
        if not response.content:
            return None
        return response.json()

    def delete(self, url: str) -> None:
        response = self._session.delete(url, timeout=self._timeout)
        raise_for_azdo_status(response)

    def connection_data(self) -> dict[str, Any]:
        # connectionData is preview-only; api-version 7.1 returns HTTP 400.
        return (
            self.get(self._url("_apis/connectionData"), params={"api-version": "7.1-preview.1"})
            or {}
        )
