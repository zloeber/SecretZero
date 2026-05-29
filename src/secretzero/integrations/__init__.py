"""Agent runtime integrations (Hermes, OpenClaw, …)."""

from secretzero.integrations.adopt import run_agent_adopt, run_agent_list
from secretzero.integrations.registry import list_agent_targets, resolve_agent_install

__all__ = [
    "list_agent_targets",
    "resolve_agent_install",
    "run_agent_adopt",
    "run_agent_list",
]
