"""Tests for Entra Agent ID provider and Graph client flows."""

from __future__ import annotations

from typing import Any

import pytest

from secretzero.providers.entra_agent_id import EntraAgentIdProvider


class _FakeResponse:
    def __init__(self, payload: dict[str, Any], text: str = "x"):
        self._payload = payload
        self.text = text

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeSession:
    def __init__(self, responses: list[dict[str, Any]]):
        self._responses = responses
        self.calls: list[dict[str, Any]] = []

    def request(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        payload = self._responses.pop(0) if self._responses else {}
        return _FakeResponse(payload)


def _provider_with_session(responses: list[dict[str, Any]]) -> EntraAgentIdProvider:
    provider = EntraAgentIdProvider(
        "entra",
        config={"auth": {"access_token": "token-value"}},
    )
    assert provider.authenticate() is True
    provider._session = _FakeSession(responses)  # type: ignore[attr-defined]
    return provider


def test_store_blueprint_creates_blueprint_and_agent_identity() -> None:
    provider = _provider_with_session(
        [
            {"value": []},  # lookup existing blueprints
            {"id": "bp1", "applicationId": "app1", "appObjectId": "obj1"},  # create blueprint
            {"keyId": "k1", "secretText": "never-log-me"},  # addPassword
            {"value": []},  # list child identities
            {"id": "agent-1"},  # create child identity
        ]
    )

    result = provider.store_blueprint(
        "hr-assistant-blueprint",
        {
            "tenant_id": "tenant-1",
            "blueprint": {"display_name": "HR Assistant Blueprint"},
            "credentials": [
                {"type": "client_secret", "display_name": "blueprint-secret-v1"},
            ],
            "agent_identities": [{"display_name": "HR Assistant - Onboarding v1"}],
        },
    )

    assert result["blueprint_id"] == "bp1"
    assert result["application_id"] == "app1"
    assert result["credential_results"][0]["type"] == "client_secret"
    assert "secretText" not in str(result)
    assert result["agent_identities"][0]["status"] == "created"


def test_rotate_blueprint_credentials_skips_without_policy() -> None:
    provider = _provider_with_session([])
    result = provider.rotate_blueprint_credentials(
        "hr-assistant-blueprint",
        {
            "tenant_id": "tenant-1",
            "blueprint": {"display_name": "HR Assistant Blueprint"},
            "credentials": [],
        },
        force=False,
    )
    assert result["status"] == "skipped"


def test_retrieve_blueprint_state_not_found_raises() -> None:
    provider = _provider_with_session([{"value": []}])
    with pytest.raises(ValueError, match="not found"):
        provider.retrieve_blueprint_state("missing-blueprint")
