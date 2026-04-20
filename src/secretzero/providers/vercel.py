"""Vercel provider for project environment variable management."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any

from secretzero.providers.base import BaseProvider, ProviderAuth

if TYPE_CHECKING:
    from secretzero.bundles.registry import BundleManifest


class VercelAuth(ProviderAuth):
    """Vercel token authentication."""

    ENV_TOKEN = "VERCEL_TOKEN"
    ENV_TEAM_ID = "VERCEL_TEAM_ID"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._token: str | None = None

    def authenticate(self) -> bool:
        token = self.config.get("token") or os.environ.get(self.ENV_TOKEN)
        if not token:
            return False
        self._token = str(token)
        return True

    def is_authenticated(self) -> bool:
        return bool(self._token)

    def get_client(self) -> str | None:
        return self._token

    def get_token_info(self) -> dict[str, Any]:
        if not self._token:
            raise RuntimeError("Not authenticated")
        team_id = self.config.get("team_id") or os.environ.get(self.ENV_TEAM_ID)
        return {
            "user": "vercel_token_holder",
            "scopes": [],
            "token_type": "vercel_token",
            "team_id": team_id,
        }


class VercelProvider(BaseProvider):
    """Provider for Vercel project environment variables."""

    display_name = "Vercel"
    description = "Vercel project environment variable management"
    required_package = ("requests", "secretzero[vercel]")
    auth_class = VercelAuth
    auth_methods = {"token": "Use Vercel API token"}
    config_options = {
        "project_id": "Vercel project ID",
        "team_id": "Optional Vercel team ID",
    }
    config_example = """providers:
  vercel:
    kind: vercel
    auth:
      kind: token
      config:
        token: ${VERCEL_TOKEN}
    config:
      project_id: prj_xxxxx"""
    target_details = {
        "vercel_env": {
            "description": "Vercel project environment variable",
            "config": {
                "project_id": "Vercel project ID",
                "secret_name": "Optional key override (defaults to secret name)",
                "environments": "List: development | preview | production",
            },
            "example": """targets:
  - provider: vercel
    kind: vercel_env
    config:
      project_id: prj_xxxxx
      secret_name: DATABASE_URL
      environments: [preview, production]""",
        },
    }

    def __init__(
        self,
        name: str,
        config: dict[str, Any] | None = None,
        auth: VercelAuth | None = None,
    ):
        if auth is None and config:
            auth_config = config.get("auth", {}).get("config", {})
            if "token" in config:
                auth_config = {**auth_config, "token": config["token"]}
            if "team_id" in config:
                auth_config = {**auth_config, "team_id": config["team_id"]}
            auth = VercelAuth(auth_config)
        super().__init__(name, config, auth)
        self._session: Any | None = None

    @property
    def provider_kind(self) -> str:
        return "vercel"

    def get_supported_targets(self) -> list[str]:
        return ["vercel_env"]

    def _get_session(self) -> Any:
        if self._session is not None:
            return self._session

        import requests

        self._session = requests.Session()
        return self._session

    def _api_base(self) -> str:
        return "https://api.vercel.com"

    def _team_id(self) -> str | None:
        if self.auth:
            team_id = self.auth.config.get("team_id") or os.environ.get(VercelAuth.ENV_TEAM_ID)
            if team_id:
                return str(team_id)
        team_id = self.config.get("team_id")
        return str(team_id) if team_id else None

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.auth or not self.auth.is_authenticated():
            if not self.auth or not self.auth.authenticate():
                raise RuntimeError("Vercel authentication failed. Set VERCEL_TOKEN.")

        token = self.auth.get_client()
        if not token:
            raise RuntimeError("Vercel token unavailable after authentication")

        request_params = dict(params or {})
        team_id = self._team_id()
        if team_id:
            request_params["teamId"] = team_id

        session = self._get_session()
        response = session.request(
            method,
            f"{self._api_base()}{path}",
            params=request_params or None,
            json=json_payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=20,
        )
        if response.status_code >= 400:
            detail = response.text[:500]
            raise RuntimeError(f"Vercel API {response.status_code} for {path}: {detail}")
        if not response.text:
            return {}
        return response.json()

    def _resolve_project_id(self, project_id: str | None = None) -> str:
        pid = project_id or self.config.get("project_id")
        if not pid:
            raise ValueError("project_id is required for Vercel operations")
        return str(pid)

    @staticmethod
    def _normalize_targets(environments: list[str] | None) -> list[str]:
        if not environments:
            return ["production"]
        allowed = {"development", "preview", "production"}
        result: list[str] = []
        for value in environments:
            candidate = str(value).strip().lower()
            if candidate not in allowed:
                raise ValueError(
                    f"Invalid Vercel environment target '{value}'. Allowed: development, preview, production"
                )
            if candidate not in result:
                result.append(candidate)
        return result

    def test_connection(self) -> tuple[bool, str | None]:
        try:
            team = self._team_id()
            params = (
                {"slug": self.config.get("project_id")} if self.config.get("project_id") else {}
            )
            if team:
                params["teamId"] = team
            self._request("GET", "/v2/user", params=params)
            return True, "Connected to Vercel API"
        except Exception as exc:
            return False, str(exc)

    def _list_project_env(self, project_id: str) -> list[dict[str, Any]]:
        payload = self._request("GET", f"/v10/projects/{project_id}/env")
        return list(payload.get("envs", []))

    def store_secret(
        self,
        secret_name: str,
        secret_value: str,
        project_id: str | None = None,
        environments: list[str] | None = None,
    ) -> bool:
        """Upsert a Vercel project environment variable."""
        pid = self._resolve_project_id(project_id)
        targets = self._normalize_targets(environments)
        existing = self._list_project_env(pid)

        for env in existing:
            key = env.get("key")
            target = str(env.get("target", "")).lower()
            if key == secret_name and target in targets:
                env_id = env.get("id")
                if env_id:
                    self._request("DELETE", f"/v10/projects/{pid}/env/{env_id}")

        self._request(
            "POST",
            f"/v10/projects/{pid}/env",
            json_payload={
                "key": secret_name,
                "value": secret_value,
                "target": targets,
                "type": "encrypted",
            },
        )
        return True

    def retrieve_secret(
        self,
        secret_name: str,
        project_id: str | None = None,
        environment: str | None = None,
    ) -> str:
        """Return metadata for matching Vercel env vars.

        Vercel does not return decrypted values for existing variables.
        """
        pid = self._resolve_project_id(project_id)
        envs = self._list_project_env(pid)
        target = environment.strip().lower() if environment else None
        matches = []
        for env in envs:
            if env.get("key") != secret_name:
                continue
            env_target = str(env.get("target", "")).lower()
            if target and env_target != target:
                continue
            matches.append(
                {
                    "id": env.get("id"),
                    "key": env.get("key"),
                    "target": env.get("target"),
                    "type": env.get("type"),
                    "created_at": env.get("createdAt"),
                    "updated_at": env.get("updatedAt"),
                }
            )
        if not matches:
            raise ValueError(f"Vercel env var '{secret_name}' not found")
        return json.dumps(matches, sort_keys=True)

    def delete_secret(
        self,
        secret_name: str,
        project_id: str | None = None,
        environments: list[str] | None = None,
    ) -> bool:
        """Delete one or more matching Vercel environment variables."""
        pid = self._resolve_project_id(project_id)
        targets = self._normalize_targets(environments) if environments else None
        envs = self._list_project_env(pid)
        removed_any = False
        for env in envs:
            if env.get("key") != secret_name:
                continue
            env_target = str(env.get("target", "")).lower()
            if targets and env_target not in targets:
                continue
            env_id = env.get("id")
            if not env_id:
                continue
            self._request("DELETE", f"/v10/projects/{pid}/env/{env_id}")
            removed_any = True
        return removed_any


def _get_bundle_manifest() -> BundleManifest:
    from secretzero.bundles.registry import BundleManifest

    return BundleManifest(
        name="vercel",
        version="1.0.0",
        provider_class="secretzero.providers.vercel:VercelProvider",
        targets={"vercel_env": "secretzero.targets.vercel:VercelEnvTarget"},
        target_kinds=["vercel_env"],
    )
