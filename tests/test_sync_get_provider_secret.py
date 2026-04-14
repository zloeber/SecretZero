"""Tests for SyncEngine provider retrieval helper."""

from typing import Any

import pytest

from secretzero.lockfile import Lockfile
from secretzero.models import Secretfile
from secretzero.providers.capabilities import (
    Capability,
    CapabilityType,
    MethodSignature,
    ProviderCapabilities,
)
from secretzero.sync import SyncEngine


class _DummyProvider:
    def __init__(self, should_authenticate: bool = True) -> None:
        self._authenticated = False
        self._should_authenticate = should_authenticate

    def is_authenticated(self) -> bool:
        return self._authenticated

    def authenticate(self) -> bool:
        self._authenticated = self._should_authenticate
        return self._authenticated

    @classmethod
    def get_capabilities(cls) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_kind="dummy",
            capabilities=[
                Capability(
                    capability_type=CapabilityType.RETRIEVE,
                    method=MethodSignature(
                        name="retrieve_secret",
                        description="Retrieve secret",
                        return_type="str",
                    ),
                )
            ],
        )

    def retrieve_secret(self, secret_name: str, version: str | None = None) -> str:
        if version:
            return f"{secret_name}@{version}"
        return f"value:{secret_name}"


def _engine_with_provider(provider: Any) -> SyncEngine:
    engine = SyncEngine(Secretfile(secrets=[]), Lockfile())
    engine._providers["dummy"] = provider
    return engine


def test_get_provider_secret_success_with_args() -> None:
    """Uses provider method args and passes secret id as primary parameter."""
    engine = _engine_with_provider(_DummyProvider())
    result = engine.get_provider_secret(
        provider_name="dummy",
        secret_id="my/secret",
        method_args={"version": "v2"},
    )
    assert result["retrieved"] is True
    assert result["method"] == "retrieve_secret"
    assert result["value"] == "my/secret@v2"
    assert result["revealable"] is True


def test_get_provider_secret_marks_placeholder_as_non_revealable() -> None:
    """Placeholder-only provider responses should not be revealable."""

    class _PlaceholderProvider(_DummyProvider):
        def retrieve_secret(
            self, secret_name: str, version: str | None = None
        ) -> str:  # noqa: ARG002
            return "[SECRET EXISTS]"

    engine = _engine_with_provider(_PlaceholderProvider())
    result = engine.get_provider_secret(provider_name="dummy", secret_id="my/secret")
    assert result["revealable"] is False
    assert result["notes"] is not None


def test_get_provider_secret_missing_method_raises() -> None:
    """Errors clearly when requested method is unavailable."""
    engine = _engine_with_provider(_DummyProvider())
    with pytest.raises(ValueError, match="does not expose retrieval method"):
        engine.get_provider_secret(
            provider_name="dummy",
            secret_id="my/secret",
            method_name="retrieve_nonexistent",
        )
