"""Runtime flags for agent / automation contexts (CLI, API, CI)."""

from __future__ import annotations

import os


def env_sz_agent_mode() -> bool:
    """True when ``SZ_AGENT_MODE`` requests spill-safe CLI semantics.

    Unlike ``SZ_AGENT`` (non-interactive automation that may hard-fail manual
    work), ``SZ_AGENT_MODE`` keeps full product features available while
    blocking or redacting commands that would dump secret material or full
    interpolated manifests to stdout.
    """
    return os.environ.get("SZ_AGENT_MODE", "").strip().lower() in ("1", "true", "yes", "on")


def spill_guard_active() -> bool:
    """True when either automation or spill-safe agent mode is enabled."""
    return _truthy(os.environ.get("SZ_AGENT", "")) or env_sz_agent_mode()


def _truthy(raw: str) -> bool:
    return raw.strip().lower() in ("1", "true", "yes", "on")
