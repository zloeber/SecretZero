"""Tests for the SOPS provider + target integration."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from secretzero.bundles.registry import get_bundle_registry, reset_bundle_registry
from secretzero.providers.sops import SopsProvider


def _proc(returncode: int = 0, stdout: str = "", stderr: str = "") -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def test_sops_store_and_retrieve_json(tmp_path: Path) -> None:
    sops_path = tmp_path / "secrets.enc.json"
    provider = SopsProvider(
        name="repo_sops",
        config={"sops_file": str(sops_path), "format": "json"},
    )

    encrypted_payload = 'ENC({\n  "API_TOKEN": "abc123"\n})'
    with (
        patch("secretzero.providers.sops.shutil.which", return_value="/usr/bin/sops"),
        patch(
            "secretzero.providers.sops.subprocess.run",
            side_effect=[
                _proc(stdout=encrypted_payload),  # store -> encrypt
                _proc(stdout='{"API_TOKEN":"abc123"}'),  # retrieve -> decrypt
            ],
        ),
    ):
        assert provider.store_secret("API_TOKEN", "abc123") is True
        assert sops_path.read_text() == encrypted_payload
        assert provider.retrieve_secret("API_TOKEN") == "abc123"


def test_sops_provider_reports_cli_missing(tmp_path: Path) -> None:
    provider = SopsProvider(name="repo_sops", config={"sops_file": str(tmp_path / "x.enc.yaml")})
    with patch("secretzero.providers.sops.shutil.which", return_value=None):
        ok, msg = provider.test_connection()
    assert ok is False
    assert msg is not None and "sops" in msg.lower()


def test_sops_bundle_registration_exposes_target_kind() -> None:
    reset_bundle_registry()
    reg = get_bundle_registry()
    assert "sops" in reg.list_provider_kinds()
    assert "sops_file" in reg.list_target_kinds()
