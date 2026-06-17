#!/usr/bin/env python3
"""Sync public repo-root skills into package data for wheel bundling."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "skills"
DEST_ROOT = ROOT / "src" / "secretzero" / "data" / "skills"


def _public_skill_dirs(source_root: Path) -> list[Path]:
    if not source_root.is_dir():
        return []
    return sorted(
        item for item in source_root.iterdir() if item.is_dir() and (item / "SKILL.md").is_file()
    )


def sync_bundled_skills(*, dry_run: bool = False) -> list[str]:
    """Copy repo-root public skills into package data. Returns synced skill names."""
    skill_dirs = _public_skill_dirs(SOURCE_ROOT)
    if not skill_dirs:
        raise SystemExit(f"No public skills found under {SOURCE_ROOT}")

    synced: list[str] = []
    if not dry_run:
        DEST_ROOT.mkdir(parents=True, exist_ok=True)

    expected_names = {item.name for item in skill_dirs}
    if DEST_ROOT.exists() and not dry_run:
        for existing in DEST_ROOT.iterdir():
            if existing.is_dir() and existing.name not in expected_names:
                shutil.rmtree(existing)

    for skill_dir in skill_dirs:
        destination = DEST_ROOT / skill_dir.name
        if dry_run:
            synced.append(skill_dir.name)
            continue
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(skill_dir, destination)
        synced.append(skill_dir.name)

    return synced


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report skills that would be synced without writing files",
    )
    args = parser.parse_args(argv)
    synced = sync_bundled_skills(dry_run=args.dry_run)
    verb = "Would sync" if args.dry_run else "Synced"
    print(f"{verb} {len(synced)} bundled skill(s): {', '.join(synced)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
