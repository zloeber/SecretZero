"""Shared types for agent target integrations."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class SecretCatalogEntry:
    """Catalog row mapping a SecretZero secret to an on-disk credential surface."""

    secret_name: str
    env_key: str
    description: str
    group: str = "general"
    dotenv_file: str = ".env"


@dataclass
class DetectedSecretRef:
    """Metadata-only scan result for one present credential."""

    secret_name: str
    env_key: str
    source_file: str
    group: str
    present: bool = True


@dataclass
class AgentInstallDetection:
    """One agent install candidate (read-only discovery)."""

    target: str
    source_dir: Path
    detected: bool
    signals: list[str] = field(default_factory=list)
    secretfile_path: Path | None = None
    lockfile_path: Path | None = None
    has_secretzero_env: bool = False


@dataclass
class AgentAdoptPlan:
    """Planned artifacts for an adopt run (no secret values)."""

    target: str
    source_dir: Path
    output_dir: Path
    discovered: list[DetectedSecretRef]
    skipped_empty: list[str]
    artifacts: list[str] = field(default_factory=list)
    merged_existing: bool = False


@dataclass
class AgentAdoptResult:
    """Outcome of adopt/list operations (safe for agent JSON)."""

    generated: bool
    target: str | None = None
    source_dir: str | None = None
    output_dir: str | None = None
    discovered: list[dict[str, Any]] = field(default_factory=list)
    skipped_empty: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    detections: list[dict[str, Any]] = field(default_factory=list)
    preseed: dict[str, Any] | None = None
    reason: str | None = None
    dry_run: bool = False
    next_steps: list[str] = field(default_factory=list)


class AgentTargetAdapter(Protocol):
    """Pluggable adapter for a claw-like agent runtime."""

    target_id: str
    display_name: str
    autodetect_order: int

    def default_install_paths(self) -> list[Path]:
        """Candidate install roots (expanded)."""

    def detect_install(self, path: Path) -> AgentInstallDetection | None:
        """Return detection metadata when ``path`` looks like this agent."""

    def catalog_entries(self) -> list[SecretCatalogEntry]:
        """Known secret catalog for this agent."""

    def scan_present_secrets(self, install_root: Path) -> tuple[list[DetectedSecretRef], list[str]]:
        """Return present secret refs and env keys skipped as empty/unset."""
