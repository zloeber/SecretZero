"""In-memory mock provider plugin for sync/drift/rotation tests without cloud credentials."""

from __future__ import annotations

from typing import Any

from secretzero.bundles.registry import BundleManifest
from secretzero.providers.base import BaseProvider, ProviderAuth
from secretzero.targets.base import BaseTarget

_MOCK_STORE: dict[str, str] = {}


class MockMemoryAuth(ProviderAuth):
    """Token auth that always succeeds when a token is present."""

    ENV_TOKEN = "MOCK_PROVIDER_TOKEN"

    def authenticate(self) -> bool:
        token = self.config.get("token") or __import__("os").environ.get(self.ENV_TOKEN, "mock")
        self._token = token
        return bool(token)

    def is_authenticated(self) -> bool:
        return hasattr(self, "_token") and bool(self._token)


class MockMemoryProvider(BaseProvider):
    """Provider that stores secrets in a process-local dict (test harness only)."""

    display_name = "Mock Memory Provider"
    description = "In-memory mock provider for CI sync tests"
    auth_class = MockMemoryAuth
    auth_methods: dict[str, str] = {"token": "Mock token for tests"}
    config_options: dict[str, str] = {}
    config_example: str = ""
    target_details: dict[str, dict[str, Any]] = {}

    def __init__(
        self,
        name: str = "mock_memory",
        config: dict[str, Any] | None = None,
        auth: ProviderAuth | None = None,
    ) -> None:
        if auth is None and config:
            auth_cfg = (config.get("auth") or {}).get("config", {})
            auth = MockMemoryAuth(auth_cfg)
        super().__init__(name=name, config=config or {}, auth=auth)

    @property
    def provider_kind(self) -> str:
        return "mock_memory"

    def test_connection(self) -> tuple[bool, str | None]:
        if not self.is_authenticated() and not self.authenticate():
            return False, "Not authenticated"
        return True, None

    def get_supported_targets(self) -> list[str]:
        return ["mock_memory_secret"]

    def store_secret(self, secret_name: str, secret_value: str) -> bool:
        _MOCK_STORE[secret_name] = secret_value
        return True

    def retrieve_secret(self, secret_name: str, **_kwargs: Any) -> str | None:
        return _MOCK_STORE.get(secret_name)


class MockMemorySecretTarget(BaseTarget):
    """Target that delegates store/retrieve to MockMemoryProvider."""

    def store(self, secret_name: str, secret_value: str) -> bool:
        if self.provider is None:
            return False
        key = self.config.get("key", secret_name)
        return bool(self.provider.store_secret(key, secret_value))

    def retrieve(self, secret_name: str) -> str | None:
        if self.provider is None:
            return None
        key = self.config.get("key", secret_name)
        return self.provider.retrieve_secret(key)


def get_mock_bundle_manifest() -> BundleManifest:
    """Return a BundleManifest matching the plugin entry-point factory pattern."""
    return BundleManifest(
        name="mock_memory",
        version="0.0.test",
        provider_class="tests.support.mock_provider_bundle:MockMemoryProvider",
        targets={
            "mock_memory_secret": "tests.support.mock_provider_bundle:MockMemorySecretTarget",
        },
        target_kinds=["mock_memory_secret"],
    )


def reset_mock_store() -> None:
    """Clear the in-memory secret store between tests."""
    _MOCK_STORE.clear()


def get_mock_store() -> dict[str, str]:
    """Return the live mock store (for assertions)."""
    return _MOCK_STORE
