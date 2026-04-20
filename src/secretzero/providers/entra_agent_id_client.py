"""Microsoft Graph client for Entra Agent ID blueprint workflows."""

from __future__ import annotations

import json
from typing import Any

from secretzero.providers.entra_agent_id_types import (
    EntraAgentIdentitySpec,
    EntraBlueprintOperationSpec,
    EntraCredentialSpec,
)


class MicrosoftGraphClient:
    """Small typed Graph wrapper for Entra Agent ID preview endpoints."""

    GRAPH_BASE = "https://graph.microsoft.com"

    def __init__(self, *, access_token: str, session: Any):
        self._access_token = access_token
        self._session = session

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        response = self._session.request(
            method=method,
            url=f"{self.GRAPH_BASE}{path}",
            headers=headers,
            params=params or {},
            data=json.dumps(json_payload) if json_payload is not None else None,
            timeout=30,
        )
        response.raise_for_status()
        if not getattr(response, "text", ""):
            return {}
        return response.json()

    def upsert_blueprint(self, spec: EntraBlueprintOperationSpec) -> dict[str, Any]:
        """Create/update an agent identity blueprint."""
        existing = self._request(
            "GET",
            "/beta/identity/agentIdentityManagement/agentIdentityBlueprints",
            params={"$filter": f"displayName eq '{spec.blueprint.display_name}'"},
        ).get("value", [])

        payload = {
            "@odata.type": "microsoft.graph.agentIdentityBlueprint",
            "displayName": spec.blueprint.display_name,
            "sponsors": spec.blueprint.sponsors,
            "owners": spec.blueprint.owners,
            "identifierUris": spec.blueprint.identifier_uris,
            "oauthScopes": spec.blueprint.oauth_scopes,
        }
        if existing:
            blueprint_id = existing[0]["id"]
            return self._request(
                "PATCH",
                f"/beta/identity/agentIdentityManagement/agentIdentityBlueprints/{blueprint_id}",
                json_payload=payload,
            ) | {"id": blueprint_id}
        created = self._request(
            "POST",
            "/beta/identity/agentIdentityManagement/agentIdentityBlueprints",
            json_payload=payload,
        )
        return created

    def _add_client_secret(self, app_object_id: str, credential: EntraCredentialSpec) -> dict[str, Any]:
        payload = {
            "passwordCredential": {
                "displayName": credential.display_name,
                "endDateTime": credential.end_date_time,
            }
        }
        return self._request(
            "POST",
            f"/v1.0/applications/{app_object_id}/addPassword",
            json_payload=payload,
        )

    def _add_federated_credential(
        self, app_object_id: str, credential: EntraCredentialSpec
    ) -> dict[str, Any]:
        payload = {
            "name": credential.name,
            "issuer": credential.issuer,
            "subject": credential.subject,
            "audiences": credential.audiences,
        }
        payload.update(credential.custom_claims or {})
        return self._request(
            "POST",
            f"/v1.0/applications/{app_object_id}/federatedIdentityCredentials",
            json_payload=payload,
        )

    def _add_certificate(self, app_object_id: str, credential: EntraCredentialSpec) -> dict[str, Any]:
        payload = {
            "keyCredential": {
                "displayName": credential.display_name,
                "type": "AsymmetricX509Cert",
                "usage": "Verify",
                "key": credential.certificate_pem or "",
            }
        }
        return self._request(
            "POST",
            f"/v1.0/applications/{app_object_id}/addKey",
            json_payload=payload,
        )

    def reconcile_credentials(
        self,
        app_object_id: str,
        credentials: list[EntraCredentialSpec],
    ) -> list[dict[str, Any]]:
        """Ensure all declared blueprint credentials exist."""
        results: list[dict[str, Any]] = []
        for cred in credentials:
            if cred.type == "client_secret":
                result = self._add_client_secret(app_object_id, cred)
                result.pop("secretText", None)
                results.append({"type": cred.type, "result": result})
            elif cred.type == "federated_identity_credential":
                result = self._add_federated_credential(app_object_id, cred)
                results.append({"type": cred.type, "result": result})
            elif cred.type == "certificate":
                result = self._add_certificate(app_object_id, cred)
                results.append({"type": cred.type, "result": result})
            else:
                raise ValueError(f"Unsupported Entra credential type: {cred.type}")
        return results

    def ensure_agent_identity(
        self,
        blueprint_id: str,
        identity_spec: EntraAgentIdentitySpec,
    ) -> dict[str, Any]:
        payload = {
            "displayName": identity_spec.display_name,
            "sponsor": identity_spec.sponsor,
            "tags": identity_spec.tags,
        }
        return self._request(
            "POST",
            f"/beta/identity/agentIdentityManagement/agentIdentityBlueprints/{blueprint_id}/agentIdentities",
            json_payload=payload,
        )

    def list_agent_identities(self, blueprint_id: str) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            f"/beta/identity/agentIdentityManagement/agentIdentityBlueprints/{blueprint_id}/agentIdentities",
        ).get("value", [])

