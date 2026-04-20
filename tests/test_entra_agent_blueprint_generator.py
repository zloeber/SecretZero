"""Tests for Entra Agent Blueprint generator."""

from __future__ import annotations

import json

import pytest

from secretzero.generators.entra_agent_blueprint import EntraAgentBlueprintGenerator
from secretzero.providers.entra_agent_id import EntraAgentIdProvider


class _FakeEntraProvider(EntraAgentIdProvider):
    def __init__(self) -> None:
        super().__init__("entra", config={"auth": {"access_token": "token"}})

    def store_blueprint(self, secret_name: str, spec: dict):  # type: ignore[override]
        return {
            "secret_name": secret_name,
            "blueprint_id": "bp1",
            "application_id": "app1",
            "spec_echo": spec,
        }


def test_generator_requires_provider_injection() -> None:
    gen = EntraAgentBlueprintGenerator({"provider": "entra_alias", "spec": {}})
    with pytest.raises(ValueError, match="provider injection"):
        gen.generate()


def test_generator_returns_metadata_json() -> None:
    provider = _FakeEntraProvider()
    gen = EntraAgentBlueprintGenerator(
        {
            "provider": "entra_alias",
            "_provider_instance": provider,
            "secret_name": "hr-assistant-blueprint",
            "spec": {
                "tenant_id": "tenant-1",
                "blueprint": {"display_name": "HR Assistant Blueprint"},
            },
        }
    )
    result = gen.generate()
    parsed = json.loads(result)
    assert parsed["blueprint_id"] == "bp1"
    assert parsed["application_id"] == "app1"


def test_generator_manual_instructions_include_permissions() -> None:
    gen = EntraAgentBlueprintGenerator({})
    instructions = gen.get_manual_instructions()
    assert "AgentIdentityBlueprint.Create" in instructions.steps[1].description

