"""Dashboard data and helpers for ``secretzero web``."""

from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from secretzero.lockfile import Lockfile, SecretLockEntry
from secretzero.models import AgentInstructions, Secret, Secretfile, TargetConfig
from secretzero.sync import SyncEngine

logger = logging.getLogger(__name__)


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


def _kind_str(kind: Any) -> str:
    if isinstance(kind, Enum):
        return str(kind.value)
    return str(kind)


def _target_dest_label(tc: TargetConfig) -> str:
    """Path or name shown inside the provider/kind bubble."""
    k = _kind_str(tc.kind)
    if k == "file":
        return str(tc.config.get("path", "") or "—")
    return str(tc.config.get("name", "") or "—")


def _lock_hash_for_target(
    entry: SecretLockEntry | None, target_id: str, tc: TargetConfig
) -> str | None:
    """Resolve per-target hash from lockfile, including legacy file target ids."""
    if not entry or not entry.targets:
        return None
    h = entry.targets.get(target_id)
    if h is not None:
        return h
    if _kind_str(tc.kind) == "file":
        legacy = f"{tc.provider}/file/"
        return entry.targets.get(legacy)
    return None


def _sync_state_for_target(entry: SecretLockEntry | None, locked_hash: str | None) -> str:
    """Arrow color state: synced | pending | drift."""
    if not entry or not entry.hash:
        return "pending"
    if locked_hash is None:
        return "pending"
    if locked_hash == entry.hash:
        return "synced"
    return "drift"


_ARROW_TITLE = {
    "synced": "Lockfile shows this target has the current secret value (hash matches).",
    "pending": "This target is not recorded in the lockfile yet — run Sync.",
    "drift": "Recorded hash for this target differs from the current secret hash — re-sync.",
}


def build_agent_instructions_payload(secretfile: Secretfile, sec: Secret) -> dict[str, Any] | None:
    """Structured, human-readable agent instructions for web templates (best-effort render)."""
    if not sec.agent_instructions:
        return None
    ai: AgentInstructions
    try:
        ai = sec.agent_instructions.render_for_secret(
            variables=secretfile.variables,
            secret_name=sec.name,
            secret=sec,
        )
    except Exception:
        logger.exception("Agent instructions render failed for %s; showing raw fields", sec.name)
        ai = sec.agent_instructions
    steps_out: list[dict[str, Any]] = []
    for s in ai.steps:
        steps_out.append(
            {
                "action": s.action,
                "description": s.description,
                "required": s.required,
            }
        )
    return {
        "summary": ai.summary,
        "prerequisites": list(ai.prerequisites) if ai.prerequisites else [],
        "steps": steps_out,
        "automation_hint": ai.automation_hint,
        "estimated_time": ai.estimated_time,
        "fallback": ai.fallback,
        "required_tools": list(ai.required_tools) if ai.required_tools else [],
        "documentation_url": ai.documentation_url,
    }


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
    """One card per secret: grouped targets, per-target sync arrows, agent instructions."""
    rows: list[dict[str, Any]] = []
    for sec in secretfile.secrets:
        entry = lockfile.secrets.get(sec.name)
        has_targets = bool(sec.targets)
        target_groups: list[dict[str, Any]] = []
        if has_targets:
            order: list[tuple[str, str]] = []
            bucket: dict[tuple[str, str], list[dict[str, Any]]] = {}
            for tc in sec.targets:
                key = (tc.provider, _kind_str(tc.kind))
                if key not in bucket:
                    order.append(key)
                    bucket[key] = []
                tid = SyncEngine._build_target_id(tc)
                locked = _lock_hash_for_target(entry, tid, tc)
                sync_state = _sync_state_for_target(entry, locked)
                bucket[key].append(
                    {
                        "dest": _target_dest_label(tc),
                        "sync_state": sync_state,
                        "arrow_title": _ARROW_TITLE[sync_state],
                        "target_id": tid,
                    }
                )
            for key in order:
                target_groups.append(
                    {
                        "provider": key[0],
                        "kind": key[1],
                        "items": bucket[key],
                    }
                )
        agent_payload = build_agent_instructions_payload(secretfile, sec)
        rows.append(
            {
                "name": sec.name,
                "kind": sec.kind,
                "has_targets": has_targets,
                "target_groups": target_groups,
                "hash_preview": (entry.hash[:18] + "…") if entry and entry.hash else "—",
                "updated_at": _fmt_ts(entry.updated_at) if entry else "—",
                "last_rotated": _fmt_ts(entry.last_rotated)
                if entry and entry.last_rotated
                else "—",
                "rotation_count": entry.rotation_count if entry else 0,
                "in_lock": entry is not None,
                "can_set_value": sec.kind == "static",
                "agent_instructions": agent_payload,
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
