"""Tavern response verifiers for agent E2E tests."""

from __future__ import annotations

from typing import Any


def assert_vector1_pending_manual(response: Any, **kwargs: Any) -> None:
    """Vector 1: templated instructions, no secret values in JSON."""
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "pending_manual"
    assert data.get("resolved_mode") == "human"
    summary = data.get("pending_secrets", {}).get("manual_token", {}).get("summary")
    assert summary == "Set token for manual_token (project e2eproj)"


def assert_vector3_sz_agent(response: Any, **kwargs: Any) -> None:
    """Vector 3: automation-only semantics via sz_agent flag."""
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "failed"
    assert data.get("sz_agent") is True
    assert data.get("resolved_mode") == "auto"
    assert data.get("pending_secrets") == {}
    msg = data.get("failed_secrets", {}).get("manual_token", "")
    assert "SZ_AGENT" in msg


def assert_vector2_web_response(response: Any, **kwargs: Any) -> None:
    """Assert Vector 2 contract: awaiting_web_input, localhost URL, session id (no secrets)."""
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "awaiting_web_input"
    url = data.get("web_url") or ""
    assert url.startswith("http://127.0.0.1:"), url
    assert url.endswith("/")
    sid = data.get("web_session_id")
    assert isinstance(sid, str) and len(sid) >= 16
