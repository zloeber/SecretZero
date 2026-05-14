"""Lockfile pre-seed from an on-disk secrets file (dotenv / json / yaml) without emitting values."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from secretzero.models import Secret, Secretfile, TargetConfig


def _resolve_file_target_path(target: TargetConfig, secretfile_dir: Path) -> Path | None:
    if target.provider != "local" or target.kind != "file":
        return None
    raw = target.config.get("path")
    if not raw:
        return None
    p = Path(str(raw))
    if not p.is_absolute():
        p = secretfile_dir / p
    try:
        return p.resolve()
    except OSError:
        return None


def secret_names_for_ingest_source(
    secretfile: Secretfile,
    *,
    source: Path,
    secretfile_dir: Path,
) -> list[str]:
    """Return manifest secret names whose **local file** target points at ``source``."""
    want = source.resolve()
    names: list[str] = []
    for secret in secretfile.secrets:
        for t in secret.targets:
            rp = _resolve_file_target_path(t, secretfile_dir)
            if rp == want:
                names.append(secret.name)
                break
    return names


def describe_ingest_source_match(
    secretfile: Secretfile, *, source: Path, secretfile_dir: Path
) -> dict[str, Any]:
    """Structured summary for JSON (no secret values)."""
    names = secret_names_for_ingest_source(secretfile, source=source, secretfile_dir=secretfile_dir)
    return {
        "source": str(source.resolve()),
        "matched_secrets": names,
        "matched_count": len(names),
    }
