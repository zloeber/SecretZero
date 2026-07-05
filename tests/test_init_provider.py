"""Tests for ``secretzero init provider`` scaffolding."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from secretzero.cli import main


def test_init_provider_scaffolds_package(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "init",
            "provider",
            "mycloud",
            "-o",
            str(tmp_path),
            "--with-target",
            "mycloud_secret",
        ],
    )
    assert result.exit_code == 0, result.output
    pkg = tmp_path / "secretzero_mycloud"
    assert pkg.is_dir()
    assert (pkg / "pyproject.toml").is_file()
    assert (pkg / "src" / "secretzero_mycloud" / "provider.py").is_file()
    assert "secretzero.providers" in (pkg / "pyproject.toml").read_text()


def test_scaffold_bundle_alias_still_works(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["scaffold-bundle", "legacycloud", "-o", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "secretzero_legacycloud").is_dir()
