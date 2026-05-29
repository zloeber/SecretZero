"""Load integration catalog YAML files."""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from secretzero.integrations.base import SecretCatalogEntry


def _parse_catalog_payload(data: dict[str, Any]) -> list[SecretCatalogEntry]:
    rows: list[SecretCatalogEntry] = []
    for item in data.get("entries") or []:
        if not isinstance(item, dict):
            continue
        secret_name = str(item.get("secret_name") or "").strip()
        env_key = str(item.get("env_key") or "").strip()
        if not secret_name or not env_key:
            continue
        rows.append(
            SecretCatalogEntry(
                secret_name=secret_name,
                env_key=env_key,
                description=str(item.get("description") or secret_name),
                group=str(item.get("group") or "general"),
                dotenv_file=str(item.get("dotenv_file") or ".env"),
            )
        )
    return rows


def load_catalog(package: str, resource_name: str = "catalog.yaml") -> list[SecretCatalogEntry]:
    """Load a packaged catalog resource."""
    ref = resources.files(package).joinpath(resource_name)
    with resources.as_file(ref) as path:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return []
    return _parse_catalog_payload(data)


def load_catalog_path(path: Path) -> list[SecretCatalogEntry]:
    """Load catalog YAML from an explicit path (tests)."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return []
    return _parse_catalog_payload(data)
