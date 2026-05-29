"""Presence-only parsers for agent install surfaces (never return secret values)."""

from __future__ import annotations

import os
import re
from pathlib import Path

_DOTENV_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=")


def expand_user_path(raw: str | Path) -> Path:
    """Expand ``~`` and environment variables in a path string."""
    text = os.path.expandvars(os.path.expanduser(str(raw)))
    return Path(text)


def dotenv_key_is_set(path: Path, key: str) -> bool:
    """Return True when ``key`` is assigned a non-empty value in a dotenv file."""
    if not path.is_file():
        return False
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _DOTENV_KEY.match(stripped)
        if not match or match.group(1) != key:
            continue
        _, _, value = stripped.partition("=")
        cleaned = value.strip().strip('"').strip("'")
        return bool(cleaned)
    return False


def list_dotenv_keys(path: Path) -> set[str]:
    """Return dotenv key names present in a file (values ignored)."""
    keys: set[str] = set()
    if not path.is_file():
        return keys
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return keys
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _DOTENV_KEY.match(stripped)
        if match:
            keys.add(match.group(1))
    return keys
