"""Canonical hashing for Secretfile secret definitions (no secret values)."""

from __future__ import annotations

from typing import Any

from secretzero.lockfile import Lockfile
from secretzero.models import Secret, Secretfile, Template

_DEFINITION_FIELDS = frozenset(
    {
        "kind",
        "config",
        "vars",
        "source",
        "one_time",
        "rotation_period",
        "targets",
        "local",
        "local_allow_cloud",
    }
)


def _target_payload(target: Any) -> dict[str, Any]:
    if hasattr(target, "model_dump"):
        return target.model_dump(mode="json")
    if isinstance(target, dict):
        return target
    raise TypeError(f"Unsupported target type for definition hash: {type(target)!r}")


def _template_payload(template: Template) -> dict[str, Any]:
    return template.model_dump(mode="json")


def hash_secret_definition(secret: Secret, *, secretfile: Secretfile | None = None) -> str:
    """Hash the structural secret definition used for lockfile drift tracking.

    Includes generator/target configuration and optional template body when
    ``kind`` is ``templates.*``. Excludes operational metadata such as
    ``agent_instructions`` and ``process_tags`` (they do not change synced values).
    """
    payload: dict[str, Any] = secret.model_dump(mode="json", include=_DEFINITION_FIELDS)

    if secret.kind.startswith("templates.") and secretfile is not None:
        template_name = secret.kind.split(".", 1)[1]
        template = secretfile.templates.get(template_name)
        if template is not None:
            payload["template"] = _template_payload(template)

    # Normalize target ordering for stable hashes.
    targets = payload.get("targets")
    if isinstance(targets, list):
        normalized = [_target_payload(t) for t in secret.targets]
        payload["targets"] = sorted(normalized, key=lambda item: Lockfile._hash_value(item))

    return Lockfile._hash_value(payload)


def stored_definition_hash(lockfile: Any, secret: Secret) -> str | None:
    """Return the last recorded definition hash for *secret*, if any."""
    entry = lockfile.get_secret_info(secret.name)
    if entry is not None and entry.definition_hash:
        return entry.definition_hash

    if secret.kind.startswith("templates."):
        prefix = f"{secret.name}."
        for name, field_entry in lockfile.secrets.items():
            if name.startswith(prefix) and field_entry.definition_hash:
                return field_entry.definition_hash
    return None
