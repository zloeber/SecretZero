"""Validate repo-root skills/ conform to the Agent Skills specification."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

SKILLS_ROOT = Path(__file__).resolve().parent.parent / "skills"
NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
REQUIRED_KEYS = {"name", "description"}


def _discover_skill_dirs() -> list[Path]:
    if not SKILLS_ROOT.is_dir():
        return []
    return sorted(p for p in SKILLS_ROOT.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())


def _parse_frontmatter(skill_md: Path) -> dict:
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError("SKILL.md must begin with YAML frontmatter")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("SKILL.md frontmatter not closed")
    data = yaml.safe_load(parts[1])
    if not isinstance(data, dict):
        raise ValueError("Frontmatter must be a YAML mapping")
    return data


@pytest.mark.parametrize("skill_dir", _discover_skill_dirs(), ids=lambda p: p.name)
def test_skill_frontmatter_matches_spec(skill_dir: Path) -> None:
    meta = _parse_frontmatter(skill_dir / "SKILL.md")

    missing = REQUIRED_KEYS - set(meta.keys())
    assert not missing, f"Missing required frontmatter keys: {missing}"

    name = meta["name"]
    assert isinstance(name, str)
    assert name == skill_dir.name, f"name {name!r} must match directory {skill_dir.name!r}"
    assert len(name) <= 64
    assert NAME_PATTERN.match(name), f"name {name!r} must be lowercase hyphens only"

    description = meta["description"]
    assert isinstance(description, str)
    assert description.strip()
    assert len(description) <= 1024

    if "metadata" in meta:
        assert isinstance(meta["metadata"], dict)
        for key, value in meta["metadata"].items():
            assert isinstance(key, str)
            assert isinstance(value, str)

    if "allowed-tools" in meta:
        assert isinstance(meta["allowed-tools"], str)
        assert meta["allowed-tools"].strip()

    if "compatibility" in meta:
        assert isinstance(meta["compatibility"], str)
        assert len(meta["compatibility"]) <= 500


def test_public_skills_include_discovery_metadata() -> None:
    """Bundled public skills should expose metadata for npx skills / agent runtimes."""
    for skill_dir in _discover_skill_dirs():
        meta = _parse_frontmatter(skill_dir / "SKILL.md")
        assert "metadata" in meta, f"{skill_dir.name} missing metadata.version"
        assert meta["metadata"].get("version"), f"{skill_dir.name} missing metadata.version"
        assert "allowed-tools" in meta, f"{skill_dir.name} missing allowed-tools"
