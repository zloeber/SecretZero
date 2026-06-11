"""Unit tests for bundled skills installer helpers."""

import pytest

from secretzero.skills.installer import (
    autodetect_targets,
    install_skills_for_targets,
    list_bundled_skills,
    resolve_skill_names,
    resolve_targets,
)


def test_list_bundled_skills_includes_public_skills() -> None:
    bundled = list_bundled_skills()
    assert "secretzero-agent" in bundled
    assert "secretzero-author" in bundled


def test_resolve_targets_respects_disable() -> None:
    targets = resolve_targets(
        mode="skills",
        scope="project",
        enable_targets=["opencode", "hermes"],
        disable_targets=["hermes"],
    )
    assert targets == ["opencode"]


def test_autodetect_targets_project_scope(monkeypatch, tmp_path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / ".opencode").mkdir()
    monkeypatch.chdir(project_root)
    detected = autodetect_targets(scope="project")
    assert "opencode" in detected


def test_resolve_skill_names_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Unknown skill"):
        resolve_skill_names(["not-a-real-skill"])


def test_install_skills_for_targets_single_skill(monkeypatch, tmp_path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / ".opencode").mkdir()
    monkeypatch.chdir(project_root)
    results = install_skills_for_targets(
        targets=["opencode"],
        scope="project",
        skill_names=["secretzero-agent"],
    )
    destination = project_root / ".opencode" / "skills"
    assert results[0].applied is True
    assert "secretzero-agent" in results[0].details
    installed = [p.name for p in destination.iterdir() if p.is_dir()]
    assert installed == ["secretzero-agent"]
    assert (destination / "secretzero-agent" / "SKILL.md").exists()


def test_install_skills_dry_run_writes_nothing(monkeypatch, tmp_path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / ".opencode").mkdir()
    monkeypatch.chdir(project_root)
    results = install_skills_for_targets(
        targets=["opencode"],
        scope="project",
        skill_names=["secretzero-agent"],
        dry_run=True,
    )
    destination = project_root / ".opencode" / "skills"
    assert results[0].dry_run is True
    assert results[0].details.startswith("Would install")
    assert not destination.exists()
