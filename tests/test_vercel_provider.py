"""Tests for Vercel provider and target behavior."""

from __future__ import annotations

from typing import Any

import pytest

from secretzero.providers.vercel import VercelProvider


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = "" if payload is None else "ok"

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeSession:
    def __init__(self, responses: list[_FakeResponse]):
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        if not self.responses:
            return _FakeResponse(200, {})
        return self.responses.pop(0)


def _provider_with_session(responses: list[_FakeResponse]) -> VercelProvider:
    provider = VercelProvider(
        "vercel",
        config={
            "project_id": "prj_test",
            "auth": {"config": {"token": "token-value"}},
        },
    )
    assert provider.authenticate() is True
    provider._session = _FakeSession(responses)  # type: ignore[attr-defined]
    return provider


def test_store_secret_upserts_in_requested_targets() -> None:
    provider = _provider_with_session(
        [
            _FakeResponse(
                200,
                {
                    "envs": [
                        {"id": "env1", "key": "DATABASE_URL", "target": "preview"},
                        {"id": "env2", "key": "OTHER", "target": "production"},
                    ]
                },
            ),
            _FakeResponse(200, {}),
            _FakeResponse(200, {"id": "created"}),
        ]
    )
    result = provider.store_secret(
        "DATABASE_URL",
        "postgres://new",
        project_id="prj_test",
        environments=["preview", "production"],
    )
    assert result is True


def test_retrieve_secret_returns_json_metadata() -> None:
    provider = _provider_with_session(
        [
            _FakeResponse(
                200,
                {
                    "envs": [
                        {"id": "env1", "key": "DATABASE_URL", "target": "preview"},
                    ]
                },
            )
        ]
    )
    value = provider.retrieve_secret("DATABASE_URL", project_id="prj_test", environment="preview")
    assert '"key": "DATABASE_URL"' in value


def test_delete_secret_returns_false_when_missing() -> None:
    provider = _provider_with_session([_FakeResponse(200, {"envs": []})])
    removed = provider.delete_secret("MISSING", project_id="prj_test")
    assert removed is False


def test_store_secret_rejects_invalid_target() -> None:
    provider = _provider_with_session([])
    with pytest.raises(ValueError, match="Invalid Vercel environment target"):
        provider.store_secret(
            "KEY",
            "value",
            project_id="prj_test",
            environments=["invalid-env"],
        )
