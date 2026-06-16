#!/usr/bin/env python3
"""Align pyproject.toml >= dependency floors with resolved versions in uv.lock.

Updates direct dependency strings (``name>=version`` and ``name[extra]>=version``)
in:

- ``[project.dependencies]``
- ``[project.optional-dependencies]`` (all extras groups)
- ``[tool.uv.override-dependencies]``

Does not modify build-system requires, upper-bound constraints (for example ``pytest>=9.0.3,<9.1``),
or non-``>=`` specifiers.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

DEP_LINE_RE = re.compile(r'^(\s*)"(.+)"(,?\s*)$')
SPEC_FLOOR_RE = re.compile(r"^([^>\[]+)(?:\[[^\]]*\])?>=(.+)$")


def _parse_floor_spec(spec: str) -> tuple[str, str, str] | None:
    """Return (package_name, floor_version, trailing_constraints) for a >= spec."""
    match = SPEC_FLOOR_RE.match(spec)
    if match is None:
        return None
    name = match.group(1).strip()
    rest = match.group(2)
    if "," in rest:
        floor, trailing = rest.split(",", 1)
        return name, floor.strip(), f",{trailing}"
    return name, rest.strip(), ""


def _lock_versions(lock_path: Path) -> dict[str, str]:
    data = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    versions: dict[str, str] = {}
    for entry in data.get("package", []):
        name = entry.get("name")
        version = entry.get("version")
        if name and version:
            versions[name] = version
    return versions


def _package_name(spec: str) -> str | None:
    parsed = _parse_floor_spec(spec)
    return parsed[0] if parsed else None


def _bump_spec(spec: str, versions: dict[str, str]) -> str | None:
    parsed = _parse_floor_spec(spec)
    if parsed is None:
        return None
    name, current_ver, trailing = parsed
    if name not in versions:
        return None
    locked = versions[name]
    if current_ver == locked:
        return None
    prefix, _, _ = spec.rpartition(">=")
    return f"{prefix}>={locked}{trailing}"


def _upgrade_pyproject_text(text: str, versions: dict[str, str]) -> tuple[str, list[str]]:
    changes: list[str] = []
    out_lines: list[str] = []
    for line in text.splitlines():
        match = DEP_LINE_RE.match(line)
        if match is None:
            out_lines.append(line)
            continue
        spec = match.group(2)
        new_spec = _bump_spec(spec, versions)
        if new_spec is None:
            out_lines.append(line)
            continue
        changes.append(f"{spec} -> {new_spec}")
        out_lines.append(f'{match.group(1)}"{new_spec}"{match.group(3)}')
    return "\n".join(out_lines) + ("\n" if text.endswith("\n") else ""), changes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pyproject",
        type=Path,
        default=Path("pyproject.toml"),
        help="Path to pyproject.toml (default: pyproject.toml)",
    )
    parser.add_argument(
        "--lockfile",
        type=Path,
        default=Path("uv.lock"),
        help="Path to uv.lock (default: uv.lock)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned changes without writing pyproject.toml",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 when pyproject.toml floors are behind uv.lock",
    )
    args = parser.parse_args(argv)

    repo_root = Path.cwd()
    pyproject_path = args.pyproject if args.pyproject.is_absolute() else repo_root / args.pyproject
    lock_path = args.lockfile if args.lockfile.is_absolute() else repo_root / args.lockfile

    if not pyproject_path.is_file():
        print(f"error: {pyproject_path} not found", file=sys.stderr)
        return 1
    if not lock_path.is_file():
        print(f"error: {lock_path} not found", file=sys.stderr)
        return 1

    versions = _lock_versions(lock_path)
    original = pyproject_path.read_text(encoding="utf-8")
    updated, changes = _upgrade_pyproject_text(original, versions)

    if not changes:
        print("pyproject.toml dependency floors already match uv.lock")
        return 0

    for change in changes:
        print(change)

    if args.check or args.dry_run:
        if args.check:
            print(f"{len(changes)} dependency floor(s) behind uv.lock", file=sys.stderr)
            return 1
        return 0

    pyproject_path.write_text(updated, encoding="utf-8")
    print(f"Updated {len(changes)} dependency floor(s) in {pyproject_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
