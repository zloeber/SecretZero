"""Resolve human-readable authenticated identity for configured providers."""

from __future__ import annotations

import logging
from typing import Any

from secretzero.bundles import get_bundle_registry
from secretzero.models import Secretfile

logger = logging.getLogger(__name__)

# Order matters: first non-empty wins for one-line "who" display.
_PRIMARY_IDENTITY_KEYS: tuple[str, ...] = (
    "user",
    "arn",
    "name",
    "fullName",
    "workspace_name",
    "workspace_id",
    "principal_id",
    "object_id",
    "cluster_host",
    "account",
)


def _truncate(s: str, max_len: int = 72) -> str:
    s = s.strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def primary_identity_label(info: dict[str, Any]) -> str:
    """Pick the best single string to represent *who* is authenticated."""
    for key in _PRIMARY_IDENTITY_KEYS:
        val = info.get(key)
        if val is None or val == "":
            continue
        return _truncate(str(val))
    return "—"


def secondary_identity_hint(info: dict[str, Any]) -> str:
    """Short subtitle: token or platform type plus a few stable context keys."""
    parts: list[str] = []
    tt = info.get("token_type")
    if tt:
        parts.append(str(tt))
    for key in (
        "tenant_id",
        "account",
        "region",
        "environment",
        "namespace",
        "api_url",
        "ci_actor",
    ):
        v = info.get(key)
        if v is None or v == "":
            continue
        parts.append(f"{key}={_truncate(str(v), 48)}")
        if len(parts) >= 4:
            break
    return " · ".join(parts)


def collect_provider_identity_rows(secretfile: Secretfile) -> list[dict[str, Any]]:
    """One row per ``providers:`` entry: alias, kind, auth status, identity summary.

    Safe for UI: no secret values; failed lookups yield error hints only.
    """
    rows: list[dict[str, Any]] = []
    if not secretfile.providers:
        return rows

    reg = get_bundle_registry()

    for alias, pconf in secretfile.providers.items():
        config_dict = pconf.model_dump()
        kind = config_dict.get("kind") or alias
        row: dict[str, Any] = {
            "alias": alias,
            "kind": kind,
            "status": "unknown",
            "primary": "—",
            "secondary": "",
            "error": None,
        }

        if kind == "local":
            row["status"] = "local"
            row["primary"] = "Local filesystem (no remote credentials)"
            rows.append(row)
            continue

        pclass = reg.get_provider_class(kind)
        if pclass is None:
            row["status"] = "unregistered"
            row["primary"] = f"No provider class registered for kind '{kind}'"
            rows.append(row)
            continue

        try:
            instance = pclass(name=alias, config=config_dict)
        except Exception as exc:
            logger.debug("Provider %s instantiate failed: %s", alias, exc)
            row["status"] = "error"
            row["error"] = str(exc)
            row["primary"] = "Could not load provider"
            rows.append(row)
            continue

        if getattr(instance, "auth", None) is not None:
            try:
                ok = instance.authenticate()
            except Exception as exc:
                logger.debug("Provider %s authenticate raised: %s", alias, exc)
                ok = False
            if not ok:
                row["status"] = "unauthenticated"
                row["primary"] = "Not authenticated (check credentials / environment)"
                rows.append(row)
                continue

        try:
            info = instance.get_actor_info()
        except Exception as exc:
            logger.debug("Provider %s get_actor_info failed: %s", alias, exc)
            row["status"] = "error"
            row["error"] = str(exc)
            row["primary"] = "Identity unavailable"
            rows.append(row)
            continue

        if not isinstance(info, dict):
            row["status"] = "error"
            row["primary"] = "Unexpected identity payload"
            rows.append(row)
            continue

        row["status"] = "ok"
        row["primary"] = primary_identity_label(info)
        row["secondary"] = secondary_identity_hint(info)
        rows.append(row)

    return sorted(rows, key=lambda r: str(r.get("alias", "")))
