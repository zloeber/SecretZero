"""Entra Agent ID provider implementation for SecretZero."""

from __future__ import annotations

import base64
import json
import os
from typing import TYPE_CHECKING, Any

from secretzero.providers.base import BaseProvider, ProviderAuth
from secretzero.providers.entra_agent_id_client import MicrosoftGraphClient
from secretzero.providers.entra_agent_id_types import EntraBlueprintOperationSpec

if TYPE_CHECKING:
    from secretzero.bundles.registry import BundleManifest


def _decode_jwt_payload_unverified(token: str) -> dict[str, Any]:
    """Parse JWT payload without verifying signature (metadata only)."""
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        raw = base64.urlsafe_b64decode(payload.encode("ascii"))
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else {}
    except (ValueError, json.JSONDecodeError, OSError):
        return {}


class EntraAgentIdAuth(ProviderAuth):
    """Authentication for Microsoft Graph Entra Agent ID operations."""

    ENV_TOKEN = "ENTRA_AGENT_ID_ACCESS_TOKEN"
    ENV_TENANT_ID = "AZURE_TENANT_ID"
    ENV_CLIENT_ID = "AZURE_CLIENT_ID"
    ENV_CLIENT_SECRET = "AZURE_CLIENT_SECRET"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._token: str | None = None

    def authenticate(self) -> bool:
        """Authenticate using provided token or Azure identity credentials."""
        token = self.config.get("access_token") or os.environ.get(self.ENV_TOKEN)
        if token:
            self._token = str(token)
            return True

        try:
            from azure.identity import ClientSecretCredential, DefaultAzureCredential
        except ImportError:
            return False

        auth_kind = self.config.get("kind", "default")
        try:
            if auth_kind == "service_principal":
                tenant_id = self.config.get("tenant_id") or os.environ.get(self.ENV_TENANT_ID)
                client_id = self.config.get("client_id") or os.environ.get(self.ENV_CLIENT_ID)
                client_secret = self.config.get("client_secret") or os.environ.get(
                    self.ENV_CLIENT_SECRET
                )
                if not tenant_id or not client_id or not client_secret:
                    return False
                cred = ClientSecretCredential(
                    tenant_id=tenant_id,
                    client_id=client_id,
                    client_secret=client_secret,
                )
            else:
                cred = DefaultAzureCredential()
            self._token = cred.get_token("https://graph.microsoft.com/.default").token
            return True
        except Exception:
            return False

    def is_authenticated(self) -> bool:
        return bool(self._token)

    def get_client(self) -> str | None:
        return self._token

    def get_token_info(self) -> dict[str, Any]:
        if not self._token:
            raise RuntimeError("Not authenticated with Entra Agent ID provider")
        claims = _decode_jwt_payload_unverified(self._token)
        scopes_raw = claims.get("scp") or claims.get("roles") or ""
        if isinstance(scopes_raw, str):
            scopes = [s for s in scopes_raw.split() if s]
        elif isinstance(scopes_raw, list):
            scopes = [str(s) for s in scopes_raw]
        else:
            scopes = []
        return {
            "user": claims.get("upn")
            or claims.get("preferred_username")
            or claims.get("oid")
            or claims.get("appid"),
            "tenant_id": claims.get("tid"),
            "object_id": claims.get("oid"),
            "app_id": claims.get("appid") or claims.get("azp"),
            "scopes": scopes,
            "token_type": "entra_graph",
        }


class EntraAgentIdProvider(BaseProvider):
    """Microsoft Entra Agent ID provider."""

    display_name = "Microsoft Entra Agent ID"
    description = "Entra Agent Identity Blueprint lifecycle and credential management"
    required_package = ("azure.identity", "secretzero[entra_agent_id]")
    auth_class = EntraAgentIdAuth
    auth_methods = {
        "token": "Use static Microsoft Graph bearer token",
        "service_principal": "Use tenant/client credentials for app-only Graph auth",
        "default": "Use Azure SDK default credential chain",
    }
    config_options = {
        "tenant_id": "Entra tenant ID",
        "graph_base_url": "Microsoft Graph base URL (default: https://graph.microsoft.com)",
    }
    config_example = """providers:
  entra_agent_id:
    kind: entra-agent-id
    auth:
      kind: service_principal
      config:
        tenant_id: ${AZURE_TENANT_ID}
        client_id: ${AZURE_CLIENT_ID}
        client_secret: ${AZURE_CLIENT_SECRET}"""
    target_details: dict[str, dict[str, Any]] = {}

    def __init__(
        self,
        name: str = "entra_agent_id",
        config: dict[str, Any] | None = None,
        auth: EntraAgentIdAuth | None = None,
    ):
        if auth is None and config:
            auth = EntraAgentIdAuth(config.get("auth", {}))
        super().__init__(name, config, auth)
        self._session = None

    @property
    def provider_kind(self) -> str:
        return "entra-agent-id"

    @classmethod
    def get_scope_descriptions(cls) -> dict[str, str]:
        return {
            "AgentIdentityBlueprint.Create": "Create Entra agent identity blueprints",
            "AgentIdentityBlueprint.AddRemoveCreds.All": "Manage blueprint credentials",
            "AgentIdentityBlueprint.UpdateAuthProperties.All": "Update blueprint auth properties",
            "Application.ReadWrite.All": "Manage Entra applications and credentials",
            "Directory.ReadWrite.All": "Manage service principals and directory objects",
        }

    def _get_session(self) -> Any:
        if self._session is not None:
            return self._session
        try:
            import requests
        except ImportError as e:
            raise RuntimeError(
                "requests dependency missing. Install with: pip install secretzero[entra_agent_id]"
            ) from e
        self._session = requests.Session()
        return self._session

    def _client(self) -> MicrosoftGraphClient:
        if not self.is_authenticated():
            if not self.authenticate():
                raise RuntimeError("Entra Agent ID authentication failed")
        token = self.auth.get_client() if isinstance(self.auth, EntraAgentIdAuth) else None
        if not token:
            raise RuntimeError("Graph access token unavailable after authentication")
        return MicrosoftGraphClient(access_token=token, session=self._get_session())

    def test_connection(self) -> tuple[bool, str | None]:
        """Verify Graph connectivity and token usability."""
        try:
            client = self._client()
            client._request("GET", "/v1.0/organization")
            return True, "Connected to Microsoft Graph"
        except Exception as e:
            return False, f"Entra Agent ID connection test failed: {e}"

    def get_supported_targets(self) -> list[str]:
        return []

    def store_blueprint(self, secret_name: str, spec: dict[str, Any]) -> dict[str, Any]:
        """Create/update blueprint, credentials, and optional child agent identities."""
        parsed = EntraBlueprintOperationSpec(**spec)
        client = self._client()
        blueprint = client.upsert_blueprint(parsed)
        blueprint_id = blueprint.get("id")
        app_object_id = blueprint.get("applicationId") or blueprint.get("appObjectId")
        if not blueprint_id:
            raise RuntimeError("Graph did not return blueprint id")
        if not app_object_id:
            raise RuntimeError("Graph did not return blueprint application id")

        credentials = client.reconcile_credentials(app_object_id, parsed.credentials)

        child_results: list[dict[str, Any]] = []
        if parsed.agent_identities:
            existing = {
                i.get("displayName"): i
                for i in client.list_agent_identities(blueprint_id)
                if isinstance(i, dict)
            }
            for identity in parsed.agent_identities:
                if identity.display_name in existing:
                    child_results.append(
                        {
                            "display_name": identity.display_name,
                            "status": "exists",
                            "id": existing[identity.display_name].get("id"),
                        }
                    )
                else:
                    created = client.ensure_agent_identity(blueprint_id, identity)
                    child_results.append(
                        {
                            "display_name": identity.display_name,
                            "status": "created",
                            "id": created.get("id"),
                        }
                    )

        return {
            "secret_name": secret_name,
            "blueprint_id": blueprint_id,
            "application_id": blueprint.get("applicationId"),
            "credential_results": credentials,
            "agent_identities": child_results,
        }

    def rotate_blueprint_credentials(
        self, secret_name: str, spec: dict[str, Any], force: bool = False
    ) -> dict[str, Any]:
        """Rotate blueprint credentials according to rotation policy."""
        parsed = EntraBlueprintOperationSpec(**spec)
        if not force and not parsed.rotation_policy:
            return {
                "secret_name": secret_name,
                "status": "skipped",
                "message": "No rotation_policy configured",
            }
        result = self.store_blueprint(secret_name, spec)
        result["status"] = "rotated"
        return result

    def retrieve_blueprint_state(self, display_name: str) -> dict[str, Any]:
        """Fetch blueprint state by display name."""
        client = self._client()
        items = client._request(
            "GET",
            "/beta/identity/agentIdentityManagement/agentIdentityBlueprints",
            params={"$filter": f"displayName eq '{display_name}'"},
        ).get("value", [])
        if not items:
            raise ValueError(f"Blueprint '{display_name}' not found")
        item = items[0]
        return {
            "id": item.get("id"),
            "displayName": item.get("displayName"),
            "applicationId": item.get("applicationId"),
            "owners": item.get("owners", []),
            "sponsors": item.get("sponsors", []),
        }

    def delete_blueprint(self, blueprint_id: str) -> bool:
        """Delete blueprint by id."""
        client = self._client()
        client._request(
            "DELETE",
            f"/beta/identity/agentIdentityManagement/agentIdentityBlueprints/{blueprint_id}",
        )
        return True


def _get_bundle_manifest() -> BundleManifest:
    """Lazily construct the Entra Agent ID bundle manifest."""
    from secretzero.bundles.registry import BundleManifest

    return BundleManifest(
        name="entra-agent-id",
        version="1.0.0",
        provider_class="secretzero.providers.entra_agent_id:EntraAgentIdProvider",
        generators={
            "entra-agent-blueprint": "secretzero.generators.entra_agent_blueprint:EntraAgentBlueprintGenerator",
        },
        targets={},
        generator_kinds=["entra-agent-blueprint"],
        target_kinds=[],
    )

