"""Tests for drift detection extensions."""

from __future__ import annotations

from unittest.mock import patch

from secretzero.drift import DriftDetector
from secretzero.models import Provider, Secret, Secretfile


class _FakeEntraProvider:
    def __init__(self, name: str, config: dict):  # noqa: ARG002
        self.name = name

    def retrieve_blueprint_state(self, display_name: str) -> dict:
        return {"id": "bp1", "displayName": display_name, "applicationId": "app1"}


def test_entra_blueprint_drift_provider_state_success() -> None:
    detector = DriftDetector.__new__(DriftDetector)
    detector.config = Secretfile(
        providers={"entra_agent_id": Provider(kind="entra-agent-id")},
        secrets=[],
    )
    secret = Secret(
        name="hr_assistant_blueprint",
        kind="entra-agent-blueprint",
        config={
            "provider": "entra_agent_id",
            "spec": {"blueprint": {"display_name": "HR Assistant Blueprint"}},
        },
    )

    with patch(
        "secretzero.drift.GLOBAL_PROVIDER_REGISTRY.get_provider_class",
        return_value=_FakeEntraProvider,
    ):
        result = detector._check_entra_blueprint_drift(secret)

    assert result is not None
    assert result.has_drift is False
    assert result.details["provider_state"]["id"] == "bp1"


def test_entra_blueprint_drift_missing_provider_alias() -> None:
    detector = DriftDetector.__new__(DriftDetector)
    detector.config = Secretfile(providers={}, secrets=[])
    secret = Secret(name="bp", kind="entra-agent-blueprint", config={})

    result = detector._check_entra_blueprint_drift(secret)
    assert result is not None
    assert result.has_drift is True
    assert result.details["reason"] == "missing_provider"

