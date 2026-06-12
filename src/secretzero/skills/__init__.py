"""Bundled skill installation helpers."""

from secretzero.skills.installer import (
    SUPPORTED_TARGETS,
    autodetect_targets,
    install_skills_for_targets,
    list_bundled_skills,
    resolve_skill_names,
    resolve_targets,
    skill_markdown,
)

__all__ = [
    "SUPPORTED_TARGETS",
    "autodetect_targets",
    "install_skills_for_targets",
    "list_bundled_skills",
    "resolve_skill_names",
    "resolve_targets",
    "skill_markdown",
]
