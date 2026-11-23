"""Thin JSON:API client for HCP Terraform and Terraform Enterprise."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

DEFAULT_HOSTNAME = "app.terraform.io"
_ERROR_LIMIT = 300
_MAX_PAGES = 10


def normalize_hostname(value: str | None) -> str:
    """Return a bare hostname, defaulting to HCP Terraform."""
    raw = (value or DEFAULT_HOSTNAME).strip()
    if "://" in raw:
        raw = raw.split("://", 1)[1]
    return raw.strip("/") or DEFAULT_HOSTNAME


def api_error_detail(payload: Any) -> str | None:
    """Return the first JSON:API error detail, truncated to one line.

    The raw response body is ignored so a failed write cannot echo a secret.
    """
    if not isinstance(payload, dict):
        return None
    errors = payload.get("errors")
    if not isinstance(errors, list) or not errors:
        return None
    first = errors[0]
    if not isinstance(first, dict):
        return None
    detail = first.get("detail") or first.get("title")
    if not isinstance(detail, str):
        return None
    cleaned = " ".join(detail.split())
    if not cleaned:
        return None
    if len(cleaned) > _ERROR_LIMIT:
        return cleaned[: _ERROR_LIMIT - 3] + "..."
    return cleaned


class TfcApiError(RuntimeError):
    """Terraform Cloud API failure that does not include the request body."""

    def __init__(self, status: int, detail: str, method: str, path: str) -> None:
        self.status = status
        self.detail = detail
        self.method = method
        self.path = path
        message = f"Terraform Cloud API {status} {method} {path}"
        if detail:
            message = f"{message}: {detail}"
        super().__init__(message)


def _normalize_resource(item: dict[str, Any]) -> dict[str, Any]:
    attributes = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
    normalized = {"id": item.get("id"), "type": item.get("type")}
    normalized.update(attributes)
    return normalized


class TfcClient:
    """Minimal HCP Terraform / Terraform Enterprise API client."""

    def __init__(self, *, hostname: str | None, token: str, timeout: int = 30) -> None:
        if not token:
            raise ValueError("token is required for Terraform Cloud")
        self.hostname = normalize_hostname(hostname)
        self._token = token
        self._timeout = timeout
        self._session: Any | None = None

    def _base(self) -> str:
        return f"https://{self.hostname}/api/v2"

    def _url(self, path: str) -> str:
        if path.startswith("https://") or path.startswith("http://"):
            return path
        return f"{self._base()}/{path.lstrip('/')}"

    def _session_obj(self) -> Any:
        if self._session is not None:
            return self._session
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError(
                "Terraform Cloud provider requires requests. "
                "Install with: pip install 'secretzero[terraform-cloud]'"
            ) from exc
        session = requests.Session()
        session.headers.update(
            {
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/vnd.api+json",
                "Accept": "application/vnd.api+json",
            }
        )
        self._session = session
        return session

    def _safe_json(self, response: Any) -> Any:
        try:
            return response.json()
        except ValueError:
            return None

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session = self._session_obj()
        caller = getattr(session, method.lower())
        kwargs: dict[str, Any] = {"timeout": self._timeout}
        if json_body is not None:
            kwargs["json"] = json_body
        response = caller(self._url(path), **kwargs)
        status = int(response.status_code)
        if status >= 400:
            detail = api_error_detail(self._safe_json(response)) or "request failed"
            if status == 401:
                detail = "authentication failed"
            raise TfcApiError(status, detail, method, path)
        if not response.content:
            return {}
        payload = self._safe_json(response)
        return payload if isinstance(payload, dict) else {}

    def _collect(self, path: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        url = path
        for _page in range(_MAX_PAGES):
            payload = self._request("GET", url)
            data = payload.get("data") or []
            if isinstance(data, dict):
                data = [data]
            items.extend(item for item in data if isinstance(item, dict))
            next_link = (payload.get("links") or {}).get("next")
            if not next_link:
                return items
            url = str(next_link)
        raise TfcApiError(0, "variable list truncated", "GET", path)

    def account_details(self) -> dict[str, Any]:
        payload = self._request("GET", "account/details")
        data = payload.get("data")
        if not isinstance(data, dict):
            return {}
        return _normalize_resource(data)

    def get_workspace(self, organization: str, name: str) -> dict[str, Any]:
        path = f"organizations/{quote(organization, safe='')}/workspaces/{quote(name, safe='')}"
        payload = self._request("GET", path)
        data = payload.get("data")
        if not isinstance(data, dict):
            raise TfcApiError(404, "not found", "GET", path)
        return _normalize_resource(data)

    def list_workspace_variables(self, workspace_id: str) -> list[dict[str, Any]]:
        path = f"workspaces/{quote(workspace_id, safe='')}/vars"
        return [_normalize_resource(item) for item in self._collect(path)]

    def create_workspace_variable(
        self,
        workspace_id: str,
        *,
        key: str,
        value: str,
        category: str,
        sensitive: bool,
        hcl: bool = False,
        description: str | None = None,
    ) -> dict[str, Any]:
        path = f"workspaces/{quote(workspace_id, safe='')}/vars"
        payload = self._request(
            "POST",
            path,
            json_body=_var_body(
                key=key,
                value=value,
                category=category,
                sensitive=sensitive,
                hcl=hcl,
                description=description,
            ),
        )
        data = payload.get("data")
        return _normalize_resource(data) if isinstance(data, dict) else {}

    def update_workspace_variable(
        self,
        workspace_id: str,
        variable_id: str,
        attributes: dict[str, Any],
    ) -> dict[str, Any]:
        path = f"workspaces/{quote(workspace_id, safe='')}/vars/{quote(variable_id, safe='')}"
        payload = self._request(
            "PATCH",
            path,
            json_body={"data": {"type": "vars", "id": variable_id, "attributes": attributes}},
        )
        data = payload.get("data")
        return _normalize_resource(data) if isinstance(data, dict) else {}

    def list_varsets(self, organization: str) -> list[dict[str, Any]]:
        path = f"organizations/{quote(organization, safe='')}/varsets"
        return [_normalize_resource(item) for item in self._collect(path)]

    def create_varset(
        self,
        organization: str,
        *,
        name: str,
        description: str | None = None,
        global_set: bool = False,
        priority: bool = False,
        workspace_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        path = f"organizations/{quote(organization, safe='')}/varsets"
        relationships: dict[str, Any] = {}
        if workspace_ids and not global_set:
            relationships["workspaces"] = {
                "data": [
                    {"type": "workspaces", "id": workspace_id} for workspace_id in workspace_ids
                ]
            }
        body: dict[str, Any] = {
            "data": {
                "type": "varsets",
                "attributes": {
                    "name": name,
                    "description": description or "",
                    "global": global_set,
                    "priority": priority,
                },
            }
        }
        if relationships:
            body["data"]["relationships"] = relationships
        payload = self._request("POST", path, json_body=body)
        data = payload.get("data")
        return _normalize_resource(data) if isinstance(data, dict) else {}

    def list_varset_variables(self, varset_id: str) -> list[dict[str, Any]]:
        path = f"varsets/{quote(varset_id, safe='')}/relationships/vars"
        return [_normalize_resource(item) for item in self._collect(path)]

    def create_varset_variable(
        self,
        varset_id: str,
        *,
        key: str,
        value: str,
        category: str,
        sensitive: bool,
        hcl: bool = False,
        description: str | None = None,
    ) -> dict[str, Any]:
        path = f"varsets/{quote(varset_id, safe='')}/relationships/vars"
        payload = self._request(
            "POST",
            path,
            json_body=_var_body(
                key=key,
                value=value,
                category=category,
                sensitive=sensitive,
                hcl=hcl,
                description=description,
            ),
        )
        data = payload.get("data")
        return _normalize_resource(data) if isinstance(data, dict) else {}

    def update_varset_variable(
        self,
        varset_id: str,
        variable_id: str,
        attributes: dict[str, Any],
    ) -> dict[str, Any]:
        path = (
            f"varsets/{quote(varset_id, safe='')}/relationships/vars/{quote(variable_id, safe='')}"
        )
        payload = self._request(
            "PATCH",
            path,
            json_body={"data": {"type": "vars", "id": variable_id, "attributes": attributes}},
        )
        data = payload.get("data")
        return _normalize_resource(data) if isinstance(data, dict) else {}


def _var_body(
    *,
    key: str,
    value: str,
    category: str,
    sensitive: bool,
    hcl: bool,
    description: str | None,
) -> dict[str, Any]:
    attributes: dict[str, Any] = {
        "key": key,
        "value": value,
        "category": category,
        "hcl": hcl,
        "sensitive": sensitive,
    }
    if description:
        attributes["description"] = description
    return {"data": {"type": "vars", "attributes": attributes}}
