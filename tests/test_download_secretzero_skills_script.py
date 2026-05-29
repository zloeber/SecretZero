import os
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "download-secretzero-skills.zsh"


def _script_runner() -> str:
    """Use bash (CI-friendly); zsh is optional for local runs."""
    for exe in ("bash", "zsh"):
        path = shutil.which(exe)
        if path:
            return path
    raise RuntimeError("Neither bash nor zsh found on PATH; cannot run downloader script tests.")


def _write_skill(source_root: Path, skill_name: str, *, include_nested_file: bool = False) -> None:
    skill_dir = source_root / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {skill_name}\ndescription: test fixture\n---\n",
        encoding="utf-8",
    )
    if include_nested_file:
        nested_dir = skill_dir / "references"
        nested_dir.mkdir(parents=True, exist_ok=True)
        (nested_dir / "guide.md").write_text(
            f"# {skill_name}\nfixture\n",
            encoding="utf-8",
        )


def _write_all_skills(source_root: Path, *, include_nested_file: bool = False) -> None:
    for name in (
        "secretzero-agent-adopt",
        "secretzero-agent",
        "secretzero-author",
        "secretzero-handle",
    ):
        _write_skill(source_root, name, include_nested_file=include_nested_file)


def test_download_script_copies_skill_directories_recursively(tmp_path: Path) -> None:
    source_root = tmp_path / "source-skills"
    target_root = tmp_path / "target-skills"
    _write_all_skills(source_root, include_nested_file=True)

    env = os.environ.copy()
    env["SECRETZERO_SKILLS_SOURCE_ROOT"] = str(source_root)

    result = subprocess.run(
        [_script_runner(), str(SCRIPT_PATH), str(target_root)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    for skill in (
        "secretzero-agent-adopt",
        "secretzero-agent",
        "secretzero-author",
        "secretzero-handle",
    ):
        assert (target_root / skill / "SKILL.md").exists()
        assert (target_root / skill / "references" / "guide.md").exists()


def test_download_script_replaces_existing_skill_directories(tmp_path: Path) -> None:
    source_root = tmp_path / "source-skills"
    target_root = tmp_path / "target-skills"
    _write_all_skills(source_root)

    stale_file = target_root / "secretzero-agent" / "stale.txt"
    stale_file.parent.mkdir(parents=True, exist_ok=True)
    stale_file.write_text("old\n", encoding="utf-8")

    env = os.environ.copy()
    env["SECRETZERO_SKILLS_SOURCE_ROOT"] = str(source_root)

    result = subprocess.run(
        [_script_runner(), str(SCRIPT_PATH), str(target_root)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert not stale_file.exists()
    for skill in (
        "secretzero-agent-adopt",
        "secretzero-agent",
        "secretzero-author",
        "secretzero-handle",
    ):
        assert (target_root / skill / "SKILL.md").exists()


def test_download_script_fails_before_replacing_anything_when_a_skill_is_missing(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source-skills"
    target_root = tmp_path / "target-skills"
    _write_skill(source_root, "secretzero-agent")

    preserved_agent = target_root / "secretzero-agent" / "preserved.txt"
    preserved_author = target_root / "secretzero-author" / "preserved.txt"
    preserved_handle = target_root / "secretzero-handle" / "preserved.txt"
    preserved_agent.parent.mkdir(parents=True, exist_ok=True)
    preserved_author.parent.mkdir(parents=True, exist_ok=True)
    preserved_handle.parent.mkdir(parents=True, exist_ok=True)
    preserved_agent.write_text("keep\n", encoding="utf-8")
    preserved_author.write_text("keep\n", encoding="utf-8")
    preserved_handle.write_text("keep\n", encoding="utf-8")

    env = os.environ.copy()
    env["SECRETZERO_SKILLS_SOURCE_ROOT"] = str(source_root)

    result = subprocess.run(
        [_script_runner(), str(SCRIPT_PATH), str(target_root)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode != 0
    assert "missing skill directory" in result.stderr or "missing skill directory" in result.stdout
    assert preserved_agent.exists()
    assert preserved_author.exists()
    assert preserved_handle.exists()
