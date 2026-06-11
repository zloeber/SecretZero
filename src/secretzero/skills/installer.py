"""Installer utilities for bundled SecretZero skills."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from secretzero import DATA_PATH

InstallScope = Literal["project", "user"]
InstallMode = Literal["skills"]

SUPPORTED_TARGETS = [
    "opencode",
    "hermes",
    "openclaw",
    "claude_code",
    "cursor",
    "github_copilot",
    "windsurf",
    "codex",
]


class TargetPaths(BaseModel):
    """Paths for target deployment in each scope."""

    project_skills_path: str = Field(..., description="Project-local skills destination")
    user_skills_path: str = Field(..., description="User-global skills destination")


class InstallResult(BaseModel):
    """Summary for a single target installation."""

    target: str
    mode: InstallMode
    scope: InstallScope
    applied: bool
    path: str
    details: str
    dry_run: bool = Field(default=False, description="True when no changes were written")


TARGET_PATHS: dict[str, TargetPaths] = {
    "opencode": TargetPaths(
        project_skills_path=".opencode/skills",
        user_skills_path="~/.config/opencode/skills",
    ),
    "hermes": TargetPaths(
        project_skills_path=".hermes/skills",
        user_skills_path="~/.config/hermes/skills",
    ),
    "openclaw": TargetPaths(
        project_skills_path=".openclaw/skills",
        user_skills_path="~/.config/openclaw/skills",
    ),
    "claude_code": TargetPaths(
        project_skills_path=".claude/skills",
        user_skills_path="~/.claude/skills",
    ),
    "cursor": TargetPaths(
        project_skills_path=".cursor/skills",
        user_skills_path="~/.cursor/skills",
    ),
    "github_copilot": TargetPaths(
        project_skills_path=".github/skills",
        user_skills_path="~/.copilot/skills",
    ),
    "windsurf": TargetPaths(
        project_skills_path=".windsurf/skills",
        user_skills_path="~/.codeium/windsurf/skills",
    ),
    "codex": TargetPaths(
        project_skills_path=".agents/skills",
        user_skills_path="~/.agents/skills",
    ),
}


def bundled_skills_root() -> Path:
    """Resolve bundled skill source path."""
    override = os.getenv("SECRETZERO_SKILLS_SOURCE_ROOT")
    if override:
        return Path(override)
    data_root = Path(DATA_PATH) / "skills"
    if data_root.exists():
        return data_root
    repo_root = Path(__file__).resolve().parents[3]
    repo_skills = repo_root / "skills"
    if repo_skills.is_dir():
        return repo_skills
    return data_root


def list_bundled_skills() -> list[str]:
    """Return bundled skill names."""
    skills_root = bundled_skills_root()
    if not skills_root.exists():
        return []
    return sorted(
        [
            item.name
            for item in skills_root.iterdir()
            if item.is_dir() and (item / "SKILL.md").exists()
        ]
    )


def skill_markdown(skill_name: str) -> str | None:
    """Load SKILL.md content for a bundled skill."""
    skill_file = bundled_skills_root() / skill_name / "SKILL.md"
    if not skill_file.exists():
        return None
    return skill_file.read_text(encoding="utf-8")


def resolve_skill_names(skill_names: list[str] | None) -> list[str]:
    """Validate and resolve bundled skill names for install."""
    bundled = list_bundled_skills()
    if not skill_names:
        return bundled
    unknown = sorted({name for name in skill_names if name not in bundled})
    if unknown:
        available = ", ".join(bundled) if bundled else "(none)"
        raise ValueError(f"Unknown skill(s): {', '.join(unknown)}. Available: {available}")
    return list(dict.fromkeys(skill_names))


def resolve_targets(
    mode: InstallMode,
    scope: InstallScope,
    enable_targets: list[str],
    disable_targets: list[str],
) -> list[str]:
    """Resolve install targets by explicit include/exclude or auto-detection."""
    del mode  # skills-only installer; kept for parity with metagit-cli API
    disabled = set(disable_targets)
    if enable_targets:
        return [target for target in enable_targets if target not in disabled]
    detected = autodetect_targets(scope=scope)
    return [target for target in detected if target not in disabled]


def autodetect_targets(scope: InstallScope) -> list[str]:
    """Detect target applications by existing config/directories."""
    resolved: list[str] = []
    for target in SUPPORTED_TARGETS:
        target_paths = TARGET_PATHS[target]
        candidate = _expand_target_path(
            target_paths.project_skills_path
            if scope == "project"
            else target_paths.user_skills_path
        )
        if candidate.exists() or candidate.parent.exists():
            resolved.append(target)
    return resolved


def _install_details_label(
    installed_names: list[str],
    *,
    dry_run: bool,
) -> str:
    """Build a human-readable install summary line."""
    verb = "Would install" if dry_run else "Installed"
    if len(installed_names) == 1:
        return f"{verb} skill '{installed_names[0]}'"
    names = ", ".join(installed_names)
    return f"{verb} {len(installed_names)} skills: {names}"


def install_skills_for_targets(
    targets: list[str],
    scope: InstallScope,
    skill_names: list[str] | None = None,
    *,
    dry_run: bool = False,
) -> list[InstallResult]:
    """Install bundled skills for selected targets."""
    source_root = bundled_skills_root()
    results: list[InstallResult] = []
    if not source_root.exists():
        return [
            InstallResult(
                target="all",
                mode="skills",
                scope=scope,
                applied=False,
                path=str(source_root),
                details="Bundled skills directory not found",
            )
        ]
    selected_skills = resolve_skill_names(skill_names)
    if not selected_skills:
        return [
            InstallResult(
                target="all",
                mode="skills",
                scope=scope,
                applied=False,
                path=str(source_root),
                details="No bundled skills available to install",
            )
        ]
    for target in targets:
        target_paths = TARGET_PATHS[target]
        destination = _expand_target_path(
            target_paths.project_skills_path
            if scope == "project"
            else target_paths.user_skills_path
        )
        if not dry_run:
            destination.mkdir(parents=True, exist_ok=True)
        installed_names: list[str] = []
        for skill_name in selected_skills:
            source_skill = source_root / skill_name
            if not source_skill.is_dir():
                continue
            dest_skill = destination / skill_name
            if dry_run:
                installed_names.append(skill_name)
                continue
            if dest_skill.exists():
                shutil.rmtree(dest_skill)
            shutil.copytree(source_skill, dest_skill)
            installed_names.append(skill_name)
        results.append(
            InstallResult(
                target=target,
                mode="skills",
                scope=scope,
                applied=bool(installed_names),
                path=str(destination),
                details=_install_details_label(installed_names, dry_run=dry_run),
                dry_run=dry_run,
            )
        )
    return results


def _expand_target_path(path_value: str) -> Path:
    expanded = Path(os.path.expanduser(path_value))
    return expanded if expanded.is_absolute() else Path.cwd() / expanded
