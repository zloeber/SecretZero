"""CLI tests for secretzero skills commands."""

from pathlib import Path

from click.testing import CliRunner

from secretzero.cli import main


def test_skills_list_displays_bundled_skills() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["skills", "list"])
    assert result.exit_code == 0
    assert "secretzero-agent" in result.output


def test_skills_show_prints_skill_markdown() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["skills", "show", "secretzero-agent"])
    assert result.exit_code == 0
    assert "name: secretzero-agent" in result.output or "SecretZero" in result.output


def test_skills_install_project_target_creates_skill_directory() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            main,
            ["skills", "install", "--scope", "project", "--target", "opencode"],
        )
        assert result.exit_code == 0
        destination = Path(".opencode/skills")
        assert destination.exists()
        assert any(item.is_dir() for item in destination.iterdir())


def test_skills_install_single_skill_only() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            main,
            [
                "skills",
                "install",
                "--scope",
                "project",
                "--target",
                "opencode",
                "--skill",
                "secretzero-author",
            ],
        )
        assert result.exit_code == 0
        assert "Installed skill 'secretzero-author'" in result.output
        installed = [p.name for p in Path(".opencode/skills").iterdir() if p.is_dir()]
        assert installed == ["secretzero-author"]


def test_skills_install_dry_run_does_not_write_files() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            main,
            [
                "skills",
                "install",
                "--scope",
                "project",
                "--target",
                "opencode",
                "--skill",
                "secretzero-author",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "dry run" in result.output
        assert "Would install skill 'secretzero-author'" in result.output
        assert not Path(".opencode/skills").exists()


def test_skills_install_unknown_skill_fails() -> None:
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "skills",
            "install",
            "--target",
            "opencode",
            "--skill",
            "not-a-skill",
        ],
    )
    assert result.exit_code != 0
    assert "Unknown skill" in result.output
