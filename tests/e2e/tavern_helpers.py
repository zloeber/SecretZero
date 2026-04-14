"""Tavern response verifiers for agent E2E tests."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def assert_vector1_pending_manual(response: Any, **kwargs: Any) -> None:
    """Vector 1: templated instructions, no secret values in JSON."""
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "pending_manual"
    assert data.get("resolved_mode") == "human"
    summary = data.get("pending_secrets", {}).get("manual_token", {}).get("summary")
    assert summary == "Set token for manual_token (project e2eproj)"
    assert "azure_app_registration_seed" in data.get("pending_secrets", {})


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


def _read_file(path: str) -> str:
    workdir = Path(os.environ["SECRETZERO_E2E_WORKDIR"])
    return (workdir / path).read_text(encoding="utf-8")


def assert_rotation_execute_for_single_secret(response: Any, **kwargs: Any) -> None:
    assert response.status_code == 200
    data = response.json()
    assert data.get("rotated") == ["rotatable_password"]
    assert data.get("failed") == []


def assert_single_secret_rotation_count_incremented(response: Any, **kwargs: Any) -> None:
    assert response.status_code == 200
    data = response.json()
    assert data.get("name") == "rotatable_password"
    assert data.get("exists") is True
    assert data.get("rotation_count", 0) >= 2


def assert_sync_writes_dev_environment_target(response: Any, **kwargs: Any) -> None:
    assert response.status_code == 200
    data = response.json()
    assert "rotatable_password" in data.get("secrets_generated", [])
    dev_file = _read_file("e2e-dev.env")
    assert "ROTATABLE_PASSWORD=" in dev_file


def assert_sync_writes_prod_environment_target(response: Any, **kwargs: Any) -> None:
    assert response.status_code == 200
    data = response.json()
    assert "rotatable_password" in data.get("secrets_generated", [])
    prod_file = _read_file("e2e-prod.env")
    assert "ROTATABLE_PASSWORD=" in prod_file


def assert_cross_target_sync_updates_all_targets(response: Any, **kwargs: Any) -> None:
    assert response.status_code == 200
    data = response.json()
    assert "cross_target_shared" in data.get("secrets_generated", [])
    a_file = _read_file("e2e-shared-a.env")
    b_file = _read_file("e2e-shared-b.env")
    assert "CROSS_TARGET_SHARED=" in a_file
    assert "CROSS_TARGET_SHARED=" in b_file
