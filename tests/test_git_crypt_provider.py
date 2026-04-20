"""Tests for git-crypt provider + target registration."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from secretzero.bundles.registry import get_bundle_registry, reset_bundle_registry
from secretzero.providers.git_crypt import GitCryptProvider


def _proc(returncode: int = 0, stdout: str = "", stderr: str = "") -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def test_git_crypt_store_and_retrieve_yaml(tmp_path: Path) -> None:
    secret_file = tmp_path / "secrets.yaml"
    provider = GitCryptProvider(
        name="repo_gitcrypt",
        config={"secret_file": str(secret_file), "format": "yaml"},
    )

    with (
        patch("secretzero.providers.git_crypt.shutil.which", return_value="/usr/bin/git-crypt"),
        patch(
            "secretzero.providers.git_crypt.subprocess.run",
            return_value=_proc(stdout="not encrypted: .gitattributes"),
        ),
    ):
        ok, _msg = provider.test_connection()
        assert ok is True

    assert provider.store_secret("APP_DB_PASSWORD", "pw123") is True
    assert provider.retrieve_secret("APP_DB_PASSWORD") == "pw123"


def test_git_crypt_locked_repo_fails_connection(tmp_path: Path) -> None:
    provider = GitCryptProvider(
        name="repo_gitcrypt", config={"secret_file": str(tmp_path / "s.yaml")}
    )
    with (
        patch("secretzero.providers.git_crypt.shutil.which", return_value="/usr/bin/git-crypt"),
        patch(
            "secretzero.providers.git_crypt.subprocess.run",
            return_value=_proc(returncode=1, stderr="repository locked"),
        ),
    ):
        ok, msg = provider.test_connection()
    assert ok is False
    assert msg is not None and "locked" in msg.lower()


def test_git_crypt_bundle_registration_exposes_target_kind() -> None:
    reset_bundle_registry()
    reg = get_bundle_registry()
    assert "git_crypt" in reg.list_provider_kinds()
    assert "git_crypt_file" in reg.list_target_kinds()
