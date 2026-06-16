"""Load Secretfile workspace context for MCP backends."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from secretzero.config import ConfigLoader
from secretzero.environment_resolution import (
    ResolvedEnvironmentContext,
    apply_target_profile,
    resolve_environment_context,
)
from secretzero.lockfile import Lockfile
from secretzero.mcp.config import McpConfig
from secretzero.models import Secretfile


def _runtime_lockfile_override(secretfile_path: Path, lockfile: str | None) -> str | None:
    if lockfile is None or lockfile == ".gitsecrets.lock":
        return None
    return lockfile


@dataclass
class WorkspaceContext:
    """Resolved on-disk workspace for one MCP operation."""

    secretfile_path: Path
    secretfile: Secretfile
    env_ctx: ResolvedEnvironmentContext
    lockfile_path: Path
    lockfile: Lockfile
    secretfile_content: str


def load_workspace(cfg: McpConfig) -> WorkspaceContext:
    """Load Secretfile, environment lane, and lockfile for backend calls."""
    file_path = cfg.secretfile_path
    loader = ConfigLoader()
    base_secretfile = loader.load_file(file_path)
    env_ctx = resolve_environment_context(
        secretfile=base_secretfile,
        secretfile_path=file_path,
        environment=cfg.environment,
        runtime_var_files=None,
        runtime_lockfile=_runtime_lockfile_override(file_path, cfg.lockfile_path),
    )
    secretfile = loader.load_file(file_path, var_files=env_ctx.resolved_var_files or None)
    secretfile = apply_target_profile(secretfile, env_ctx.resolved_target_profile)
    lockfile_path = env_ctx.resolved_lockfile
    lockfile = Lockfile.load(lockfile_path)
    secretfile_content = file_path.read_text(encoding="utf-8")
    return WorkspaceContext(
        secretfile_path=file_path,
        secretfile=secretfile,
        env_ctx=env_ctx,
        lockfile_path=lockfile_path,
        lockfile=lockfile,
        secretfile_content=secretfile_content,
    )
