"""Mock-provider sync, drift, and rotation tests (no live cloud credentials).

These tests gate CI: they verify the sync engine and drift detector work end-to-end
using the in-memory mock provider plugin harness in ``tests.support``.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from secretzero.bundles import get_bundle_registry, reset_bundle_registry
from secretzero.drift import DriftDetector
from secretzero.lockfile import Lockfile
from secretzero.models import Provider, ProviderAuth, Secret, Secretfile, TargetConfig
from secretzero.sync import SyncEngine
from tests.support.mock_provider_bundle import (
    get_mock_bundle_manifest,
    get_mock_store,
    reset_mock_store,
)


@pytest.fixture(autouse=True)
def _isolated_mock_bundle():
    """Register mock plugin bundle and reset store for each test."""
    reset_bundle_registry()
    reset_mock_store()
    reg = get_bundle_registry()
    reg.register_bundle(get_mock_bundle_manifest())
    yield
    reset_mock_store()
    reset_bundle_registry()


def _mock_secretfile(*, include_file_target: Path | None = None) -> Secretfile:
    targets: list[TargetConfig] = [
        TargetConfig(
            provider="mock",
            kind="mock_memory_secret",
            config={"key": "app_token"},
        ),
    ]
    if include_file_target is not None:
        targets.append(
            TargetConfig(
                provider="local",
                kind="file",
                config={
                    "path": str(include_file_target),
                    "format": "dotenv",
                    "merge": True,
                },
            )
        )
    return Secretfile(
        providers={
            "local": Provider(kind="local"),
            "mock": Provider(
                kind="mock_memory",
                auth=ProviderAuth(kind="token", config={"token": "test-token"}),
            ),
        },
        secrets=[
            Secret(
                name="app_token",
                kind="static",
                config={"default": "initial-value"},
                targets=targets,
            ),
        ],
    )


class TestMockProviderSync:
    def test_sync_stores_via_plugin_target(self) -> None:
        engine = SyncEngine(_mock_secretfile(), Lockfile())
        result = engine.sync(dry_run=False)

        assert result["secrets_generated"] == 1
        assert get_mock_store()["app_token"] == "initial-value"
        assert engine.lockfile.has_secret("app_token")

    def test_resync_skips_when_targets_synced(self) -> None:
        engine = SyncEngine(_mock_secretfile(), Lockfile())
        engine.sync(dry_run=False)
        second = engine.sync(dry_run=False)

        detail = second["details"][0]
        assert detail.get("skipped") is True
        assert get_mock_store()["app_token"] == "initial-value"

    def test_force_rotation_regenerates_and_updates_mock_target(self) -> None:
        sf = _mock_secretfile()
        sf.secrets[0].config["default"] = "rotated-value"
        engine = SyncEngine(sf, Lockfile())
        engine.sync(dry_run=False)

        result = engine.sync(dry_run=False, force_rotation=True)
        detail = result["details"][0]
        assert detail.get("generated") is True
        assert get_mock_store()["app_token"] == "rotated-value"


class TestMockProviderDrift:
    def test_file_target_drift_when_env_file_missing(self, tmp_path: Path) -> None:
        """Drift detection works without cloud credentials (local file target)."""
        env_path = tmp_path / ".env.app"
        secretfile_path = tmp_path / "Secretfile.yml"
        lockfile_path = tmp_path / ".gitsecrets.lock"

        secretfile_path.write_text(
            f"""
providers:
  local:
    kind: local
secrets:
  - name: app_token
    kind: static
    config:
      default: initial-value
    targets:
      - provider: local
        kind: file
        config:
          path: {env_path}
          format: dotenv
          merge: true
templates: {{}}
""",
            encoding="utf-8",
        )

        from secretzero.config import ConfigLoader

        sf = ConfigLoader().load_file(secretfile_path)
        engine = SyncEngine(sf, Lockfile())
        engine.sync(dry_run=False)
        engine.lockfile.save(lockfile_path)

        assert env_path.exists()
        env_path.unlink()

        detector = DriftDetector(secretfile_path, lockfile_path)
        results = detector.check_drift("app_token")
        assert any(r.has_drift for r in results)
        assert any("file_missing" in str(r.details) for r in results if r.has_drift)


class TestEntryPointFactoryPattern:
    def test_callable_entry_point_loads_manifest(self) -> None:
        """Entry points may expose a zero-arg factory (built-in provider pattern)."""
        from unittest.mock import MagicMock

        from secretzero.bundles.registry import BundleRegistry

        manifest = get_mock_bundle_manifest()
        ep = MagicMock()
        ep.load.return_value = lambda: manifest

        reg = BundleRegistry()
        with patch("importlib.metadata.entry_points", return_value=[ep]):
            reg.discover_and_register()

        assert "mock_memory" in reg.list_bundles()
        assert reg.get_provider_class("mock_memory") is not None
        assert reg.get_target_class("mock_memory_secret") is not None
