"""OpenClaw integration adapter (v1 dotenv catalog)."""

from __future__ import annotations

import os
from pathlib import Path

from secretzero.integrations.base import (
    AgentInstallDetection,
    DetectedSecretRef,
    SecretCatalogEntry,
)
from secretzero.integrations.catalog_loader import load_catalog_path
from secretzero.integrations.scan_utils import dotenv_key_is_set, expand_user_path


class OpenClawAgentAdapter:
    target_id = "openclaw"
    display_name = "OpenClaw"
    autodetect_order = 20

    _SIGNAL_FILES = (
        ".env",
        "openclaw.json",
        "config.json",
    )
    _SIGNAL_DIRS = (
        "agents",
        "workspace",
    )

    def default_install_paths(self) -> list[Path]:
        paths: list[Path] = []
        env_home = os.environ.get("OPENCLAW_HOME")
        if env_home:
            paths.append(expand_user_path(env_home))
        paths.append(expand_user_path("~/.openclaw"))
        return paths

    def catalog_entries(self) -> list[SecretCatalogEntry]:
        return load_catalog_path(Path(__file__).with_name("catalog.yaml"))

    def detect_install(self, path: Path) -> AgentInstallDetection | None:
        root = path.expanduser().resolve()
        if not root.is_dir():
            return None
        signals = [name for name in self._SIGNAL_FILES if (root / name).exists()]
        signals.extend(name for name in self._SIGNAL_DIRS if (root / name).is_dir())
        if not signals:
            return None
        secretfile = root / "Secretfile.yml"
        lockfile = root / ".gitsecrets.lock"
        return AgentInstallDetection(
            target=self.target_id,
            source_dir=root,
            detected=True,
            signals=signals,
            secretfile_path=secretfile if secretfile.is_file() else None,
            lockfile_path=lockfile if lockfile.is_file() else None,
            has_secretzero_env=secretfile.is_file(),
        )

    def scan_present_secrets(self, install_root: Path) -> tuple[list[DetectedSecretRef], list[str]]:
        present: list[DetectedSecretRef] = []
        skipped: list[str] = []
        for entry in self.catalog_entries():
            dotenv_path = install_root / entry.dotenv_file
            if dotenv_key_is_set(dotenv_path, entry.env_key):
                present.append(
                    DetectedSecretRef(
                        secret_name=entry.secret_name,
                        env_key=entry.env_key,
                        source_file=str(dotenv_path.relative_to(install_root)),
                        group=entry.group,
                    )
                )
            else:
                skipped.append(entry.env_key)
        return present, skipped
