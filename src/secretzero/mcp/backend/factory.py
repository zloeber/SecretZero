"""Construct MCP backends from configuration."""

from __future__ import annotations

from secretzero.mcp.backend.local import LocalBackend
from secretzero.mcp.backend.protocol import SecretZeroBackend
from secretzero.mcp.config import McpConfig


def build_backend(cfg: McpConfig) -> SecretZeroBackend:
    """Return the configured SecretZero backend implementation."""
    if cfg.backend == "local":
        return LocalBackend(cfg)
    if cfg.backend == "http":
        from secretzero.mcp.backend.http import HttpBackend

        return HttpBackend(cfg)
    raise ValueError(f"Unsupported backend: {cfg.backend!r}")
