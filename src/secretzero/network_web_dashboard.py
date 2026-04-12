"""Dashboard data and helpers for ``secretzero web``."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from secretzero.lockfile import Lockfile
from secretzero.models import Secretfile, TargetConfig
from secretzero.sync import SyncEngine


def format_target_line(target: TargetConfig) -> str:
    """Human-readable single target (aligned with :meth:`SyncEngine._build_target_id` semantics)."""
    provider = target.provider
    kind = str(target.kind)
    if kind == "file":
        ident = str(target.config.get("path", "") or "")
    else:
        ident = str(target.config.get("name", "") or "")
    tail = ident if ident else "—"
    return f"{provider} · {kind} · {tail}"


def _fmt_ts(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        s = iso.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            return dt.strftime("%Y-%m-%d %H:%M")
        return dt.strftime("%Y-%m-%d %H:%M %Z").strip()
    except Exception:
        return iso[:22] if len(iso) > 22 else iso


def build_manifest_rows(lockfile: Lockfile, secretfile_path: Path | None) -> dict[str, Any]:
    """Secretfile / lockfile metadata for the dashboard header."""
    sf = lockfile.secretfile
    name = str(secretfile_path) if secretfile_path else "—"
    if not sf:
        return {
            "secretfile_display": name,
            "synced_at": "—",
            "secretfile_hash": "—",
            "var_files": "—",
        }
    vf = ", ".join(sf.var_files) if sf.var_files else "—"
    h = sf.hash
    hp = (h[:20] + "…") if h and len(h) > 20 else (h or "—")
    return {
        "secretfile_display": name,
        "synced_at": _fmt_ts(sf.synced_at),
        "secretfile_hash": hp,
        "var_files": vf,
    }


def build_secret_rows(secretfile: Secretfile, lockfile: Lockfile) -> list[dict[str, Any]]:
    """One table row per secret: targets, lock metadata, UI affordances."""
    rows: list[dict[str, Any]] = []
    for sec in secretfile.secrets:
        entry = lockfile.secrets.get(sec.name)
        targets = [format_target_line(t) for t in sec.targets]
        if not targets:
            targets = ["(no targets)"]
        rows.append(
            {
                "name": sec.name,
                "kind": sec.kind,
                "targets": targets,
                "hash_preview": (entry.hash[:18] + "…") if entry and entry.hash else "—",
                "updated_at": _fmt_ts(entry.updated_at) if entry else "—",
                "last_rotated": _fmt_ts(entry.last_rotated) if entry and entry.last_rotated else "—",
                "rotation_count": entry.rotation_count if entry else 0,
                "in_lock": entry is not None,
                "can_set_value": sec.kind == "static",
            }
        )
    return rows


def make_sync_engine(
    secretfile: Secretfile,
    lockfile: Lockfile,
    *,
    secretfile_path: Path | None,
    secretfile_content: str | None,
) -> SyncEngine:
    """SyncEngine with non-interactive web defaults (no prompts)."""
    return SyncEngine(
        secretfile,
        lockfile,
        secretfile_path=secretfile_path,
        secretfile_content=secretfile_content,
        hide_input=True,
        prompt_on_empty=False,
    )
