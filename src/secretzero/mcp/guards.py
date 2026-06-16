"""Spill guards and tool allowlists for the SecretZero MCP server."""

from __future__ import annotations

import copy
import os
from typing import Any

from secretzero.agent_context import spill_guard_active
from secretzero.mcp.config import McpConfig

SENSITIVE_KEYS = frozenset(
    {
        "value",
        "secret",
        "password",
        "token",
        "plaintext",
        "client_secret",
        "access_token",
        "refresh_token",
        "api_key",
        "private_key",
        "public_key",
        "default_value",
    }
)

MUTATION_TOOLS = frozenset(
    {
        "sync_execute",
        "rotate_execute",
        "agent_adopt",
        "clean_lockfile",
        "ingest_preseed",
    }
)

REVEAL_TOOLS = frozenset(
    {
        "get_secret_reveal",
        "config_render",
        "backup_restore_print",
    }
)


def apply_startup_env(cfg: McpConfig) -> None:
    """Apply process environment defaults for agent-safe MCP operation."""
    if cfg.force_agent_mode:
        os.environ.setdefault("SZ_AGENT_MODE", "true")
    if cfg.sz_agent:
        os.environ.setdefault("SZ_AGENT", "true")


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def assert_tool_allowed(tool_name: str) -> None:
    """Raise PermissionError when a gated tool is invoked without opt-in."""
    if tool_name in REVEAL_TOOLS and not _truthy_env("SZ_MCP_ALLOW_REVEAL"):
        raise PermissionError(
            f"Tool {tool_name!r} is blocked; set SZ_MCP_ALLOW_REVEAL=true (not recommended for agents)"
        )
    if tool_name in MUTATION_TOOLS and not _truthy_env("SZ_MCP_ALLOW_MUTATIONS"):
        raise PermissionError(f"Tool {tool_name!r} is blocked; set SZ_MCP_ALLOW_MUTATIONS=true")


def _redact_object(obj: Any) -> Any:
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for key, val in obj.items():
            if key.lower() in SENSITIVE_KEYS:
                continue
            out[key] = _redact_object(val)
        return out
    if isinstance(obj, list):
        return [_redact_object(item) for item in obj]
    return obj


def sanitize_tool_result(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Remove sensitive fields from tool JSON when spill guards are active."""
    if tool_name in REVEAL_TOOLS and _truthy_env("SZ_MCP_ALLOW_REVEAL"):
        return payload
    if not spill_guard_active():
        return payload
    redacted = _redact_object(copy.deepcopy(payload))
    assert isinstance(redacted, dict)
    return redacted


def sanitize_error_message(message: str) -> str:
    """Best-effort scrub of exception text before returning to MCP clients."""
    if not spill_guard_active():
        return message
    lowered = message.lower()
    for key in SENSITIVE_KEYS:
        if key in lowered:
            return "Operation failed (details redacted under agent spill guard)"
    return message
