"""HTTP client backend for secretzero-api (remote MCP bridge)."""

from __future__ import annotations

from typing import Any

import httpx

from secretzero.mcp.config import McpConfig


class HttpBackend:
    """REST client for secretzero-api with MCP tool parity."""

    def __init__(self, cfg: McpConfig) -> None:
        if not cfg.api_url or not cfg.api_key:
            raise ValueError("HttpBackend requires SECRETZERO_API_URL and SECRETZERO_API_KEY")
        self._cfg = cfg
        self._base = cfg.api_url.rstrip("/")
        self._headers = {"X-API-Key": cfg.api_key}

    def _params(self) -> dict[str, str]:
        if self._cfg.environment:
            return {"environment": self._cfg.environment}
        return {}

    def _get(self, path: str, **params: Any) -> dict[str, Any]:
        merged = {**self._params(), **params}
        with httpx.Client(base_url=self._base, headers=self._headers, timeout=60.0) as client:
            response = client.get(path, params=merged or None)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else {"data": data}

    def _post(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = dict(body or {})
        if self._cfg.environment and "environment" not in payload:
            payload.setdefault("environment", self._cfg.environment)
        with httpx.Client(base_url=self._base, headers=self._headers, timeout=120.0) as client:
            response = client.post(path, json=payload)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else {"data": data}

    def catalog_list(
        self,
        *,
        provider: str | None = None,
        bundle: str | None = None,
        kind: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if provider:
            params["provider_kind"] = provider
        if bundle:
            params["bundle"] = bundle
        if kind:
            params["kind"] = kind
        return self._get("/catalog", **params)

    def schema_get(self) -> dict[str, Any]:
        with httpx.Client(base_url=self._base, headers=self._headers, timeout=60.0) as client:
            response = client.get("/schema/full")
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else {"schema": data}

    def secretfile_validate(self) -> dict[str, Any]:
        return self._get("/manifest/validate")

    def secrets_list(self, *, name_filter: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if name_filter:
            params["name_filter"] = name_filter
        return self._get("/inventory/secrets", **params)

    def secrets_status(self) -> dict[str, Any]:
        return self._get("/inventory/status")

    def providers_list(self) -> dict[str, Any]:
        return self._get("/inventory/providers")

    def targets_list(self) -> dict[str, Any]:
        return self._get("/inventory/targets")

    def variables_list(self, *, name_filter: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if name_filter:
            params["name_filter"] = name_filter
        return self._get("/inventory/variables", **params)

    def version_info(self, *, detailed: bool = False) -> dict[str, Any]:
        return self._get("/version", detailed=detailed)

    def detect_secrets(
        self,
        *,
        directory: str | None = None,
        all_keys: bool = False,
    ) -> dict[str, Any]:
        return self._post("/detect", {"directory": directory, "all_keys": all_keys})

    def discover_bindings(
        self,
        *,
        directory: str | None = None,
        local_only: bool = True,
    ) -> dict[str, Any]:
        return self._post("/discover", {"directory": directory, "local_only": local_only})

    def agent_sync(
        self,
        *,
        dry_run: bool = False,
        refresh: bool = True,
        web: bool = False,
        sz_agent: bool | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "dry_run": dry_run,
            "refresh": refresh,
            "web": web,
        }
        if sz_agent is not None:
            body["sz_agent"] = sz_agent
        return self._post("/agent/sync", body)

    def agent_sync_web_start(
        self,
        *,
        dry_run: bool = False,
        refresh: bool = True,
    ) -> dict[str, Any]:
        return self.agent_sync(dry_run=dry_run, refresh=refresh, web=True)

    def agent_sync_web_poll(self, session_id: str) -> dict[str, Any]:
        with httpx.Client(base_url=self._base, headers=self._headers, timeout=30.0) as client:
            response = client.get(f"/agent/sync/web/{session_id}")
            response.raise_for_status()
            return response.json()

    def agent_instructions(
        self,
        *,
        show_all: bool = False,
        detailed: bool = False,
        secret_names: list[str] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"show_all": show_all, "detailed": detailed}
        return self._get("/agent/instructions", **params)

    def sync_dry_run(
        self,
        *,
        secret_name: str | None = None,
        refresh: bool = True,
        force: bool = False,
    ) -> dict[str, Any]:
        return self._post(
            "/sync/execute",
            {
                "dry_run": True,
                "refresh": refresh,
                "force": force,
                "secret_name": secret_name,
            },
        )

    def sync_execute(
        self,
        *,
        secret_name: str | None = None,
        refresh: bool = True,
        force: bool = False,
    ) -> dict[str, Any]:
        return self._post(
            "/sync/execute",
            {
                "dry_run": False,
                "refresh": refresh,
                "force": force,
                "secret_name": secret_name,
            },
        )

    def rotate_check(self, *, secret_name: str | None = None) -> dict[str, Any]:
        return self._post("/rotation/check", {"secret_name": secret_name, "dry_run": True})

    def rotate_execute(
        self, *, secret_name: str | None = None, force: bool = False
    ) -> dict[str, Any]:
        return self._post("/rotation/execute", {"secret_name": secret_name, "force": force})

    def agent_adopt(self, **kwargs: Any) -> dict[str, Any]:
        body = {k: v for k, v in kwargs.items() if v is not None}
        body.setdefault("dry_run", True)
        return self._post("/agent/adopt", body)

    def clean_lockfile(self, *, dry_run: bool = True) -> dict[str, Any]:
        return self._post("/clean", {"dry_run": dry_run})

    def ingest_preseed(self, *, source: str, dry_run: bool = True) -> dict[str, Any]:
        return self._post("/ingest/preseed", {"source": source, "dry_run": dry_run})

    def drift_check(self, *, secret_name: str | None = None) -> dict[str, Any]:
        return self._post("/import/check", {"secret_name": secret_name})
