"""Strict manifest checks: forbid static-like payloads that embed literal secret material."""

from __future__ import annotations

import re
from typing import Any

from secretzero.generators.traits import secret_prompts_like_static
from secretzero.models import Secret, Secretfile

# Whole-string env placeholder only (no surrounding text).
_RE_ENV_PLACEHOLDER = re.compile(r"^\$\{[^}]+\}$")
# Whole-string Jinja-style variable reference from Secretfile interpolation.
_RE_JINJA_PLACEHOLDER = re.compile(r"^\{\{[^{}]+\}\}$")


def _scalar_allows_placeholder_only(value: str) -> bool:
    s = value.strip()
    if s == "":
        return True
    return bool(_RE_ENV_PLACEHOLDER.match(s) or _RE_JINJA_PLACEHOLDER.match(s))


def static_like_payload_has_plaintext_literal(payload: Any) -> bool:
    """Return True if ``payload`` embeds a non-placeholder scalar (manifest leak risk)."""
    if payload is None:
        return False
    if isinstance(payload, dict):
        return any(static_like_payload_has_plaintext_literal(v) for v in payload.values())
    if isinstance(payload, list):
        return any(static_like_payload_has_plaintext_literal(v) for v in payload)
    if isinstance(payload, str):
        return not _scalar_allows_placeholder_only(payload)
    if isinstance(payload, bool):
        return False
    if isinstance(payload, int | float):
        return True
    return True


def _effective_static_payload(secret: Secret) -> Any:
    cfg = secret.config
    if "default" in cfg:
        return cfg.get("default")
    return cfg.get("value")


def list_manifest_plaintext_violations(secretfile: Secretfile) -> list[str]:
    """Human-readable violations for static-like secrets with literal material in manifest."""
    violations: list[str] = []
    for secret in secretfile.secrets:
        if not secret_prompts_like_static(secret):
            continue
        payload = _effective_static_payload(secret)
        if static_like_payload_has_plaintext_literal(payload):
            violations.append(
                f"secret {secret.name!r} ({secret.kind}): remove literal static "
                f"value/default from the manifest; use placeholders, null leaves, "
                f"`secretzero ingest preseed`, or `secretzero agent sync --web`."
            )
    return violations
