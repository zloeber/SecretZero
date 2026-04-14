"""Capability flags resolved from registered generator classes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from secretzero.bundles.registry import get_bundle_registry

if TYPE_CHECKING:
    from secretzero.bundles.registry import BundleRegistry
    from secretzero.models import Secret


def secret_prompts_like_static(
    secret: Secret,
    registry: BundleRegistry | None = None,
) -> bool:
    """True when the secret's generator is registered and uses static-style prompting.

    Used by agent sync, web forms, and dashboard instead of hard-coding
    ``kind == "static"``.
    """
    reg = registry or get_bundle_registry()
    cls = reg.get_generator_class(secret.kind)
    if cls is None:
        return False
    return bool(getattr(cls, "PROMPTS_LIKE_STATIC", False))
