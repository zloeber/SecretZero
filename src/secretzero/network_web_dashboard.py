"""Dashboard data and helpers for ``secretzero web``."""

from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from secretzero.generators.traits import secret_prompts_like_static
from secretzero.lockfile import Lockfile, SecretLockEntry
from secretzero.models import AgentInstructions, Secret, Secretfile, TargetConfig
from secretzero.sync import SyncEngine

logger = logging.getLogger(__name__)


def _secret_can_set_value_web(secret: Secret) -> bool:
    """True when the dashboard may offer manual value entry (static-like generators)."""
    return secret_prompts_like_static(secret)


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


def build_target_lane_ui(secret_name: str, tc: TargetConfig) -> dict[str, Any]:
    """Primary destination line plus labeled rows for the dashboard (no secret values).

    Mirrors how built-in targets resolve storage keys/names so operators see e.g. dotenv key,
    GitHub Actions secret name, K8s data key, etc.
    """
    cfg = tc.config
    kind = _kind_str(tc.kind).lower()
    details: list[dict[str, str]] = []

    def add(label: str, value: str | None) -> None:
        if value is None:
            return
        v = str(value).strip()
        if v:
            details.append({"label": label, "value": v})

    # --- file (local) ---
    if kind == "file":
        path = str(cfg.get("path", "") or "")
        dest = path if path else "—"
        add("Format", str(cfg.get("format", "dotenv")))
        # Optional override; default is manifest secret name (FileTarget dict key).
        add("Entry key", str(cfg.get("key", secret_name)))
        return {"dest": dest, "details": details}

    # --- GitHub Actions ---
    if kind == "github_secret":
        owner, repo = cfg.get("owner"), cfg.get("repo")
        dest = f"{owner}/{repo}" if (owner and repo) else str(cfg.get("name", "") or "—")
        remote = str(cfg.get("secret_name") or secret_name)
        add("Actions secret", remote)
        env = cfg.get("environment")
        if env:
            add("Environment", str(env))
        return {"dest": dest, "details": details}

    # --- GitLab CI variable ---
    if kind in ("gitlab_variable", "gitlab_ci_variable"):
        proj = str(cfg.get("project", "") or "")
        dest = proj if proj else "—"
        add("Variable key", secret_name)
        add("Environment scope", str(cfg.get("environment_scope", "*")))
        vt = cfg.get("variable_type")
        if vt:
            add("Variable type", str(vt))
        return {"dest": dest, "details": details}

    # --- Kubernetes ---
    if kind == "kubernetes_secret":
        ns = str(cfg.get("namespace", "default"))
        obj = str(cfg.get("secret_name", "") or "")
        dkey = str(cfg.get("data_key") or secret_name)
        dest = f"{ns}/{obj}" if obj else ns
        add("Secret object", obj)
        add("Data key", dkey)
        return {"dest": dest, "details": details}

    # --- Jenkins ---
    if kind == "jenkins_credential":
        cid = str(cfg.get("credential_id", "") or "")
        dest = cid if cid else "—"
        add("Domain", str(cfg.get("domain", "_")))
        add("Credential type", str(cfg.get("credential_type", "string")))
        return {"dest": dest, "details": details}

    # --- Vault KV ---
    if kind == "vault_kv":
        path = str(cfg.get("path", "") or cfg.get("name", "") or "")
        dest = path if path else "—"
        add("Mount", str(cfg.get("mount_point", "secret")))
        ver = cfg.get("version")
        if ver is not None:
            add("KV version", str(ver))
        return {"dest": dest, "details": details}

    # --- Azure Key Vault ---
    if kind == "azure_keyvault":
        vault_url = str(cfg.get("vault_url", "") or "")
        kv_sn = str(cfg.get("secret_name") or secret_name)
        dest = kv_sn
        add("Vault", vault_url)
        return {"dest": dest, "details": details}

    # --- AWS SSM & Secrets Manager ---
    if kind in ("ssm_parameter", "secrets_manager"):
        nm = str(cfg.get("name", "") or "")
        dest = nm if nm else "—"
        if kind == "ssm_parameter":
            add("Parameter type", str(cfg.get("type", "SecureString")))
        return {"dest": dest, "details": details}

    # --- Jinja template output ---
    if kind == "template":
        out = str(cfg.get("output_path", "") or "")
        tpl = str(cfg.get("template_path", "") or "")
        dest = out if out else (tpl or "—")
        add("Template", tpl)
        add("Context key", secret_name)
        return {"dest": dest, "details": details}

    # --- Generic fallback (bundles / future targets) ---
    ident = str(cfg.get("path", "") or cfg.get("name", "") or "")
    dest = ident if ident else "—"
    if kind:
        add("Target kind", kind)
    return {"dest": dest, "details": details}


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


def _target_actor_summary(entry: SecretLockEntry | None, target_id: str) -> str | None:
    """Compact summary of last actor metadata for a target provenance lane."""
    if entry is None:
        return None
    updates = entry.target_provenance.get(target_id) if entry.target_provenance else None
    if not updates:
        return None
    actor = updates[-1].actor or {}
    if not isinstance(actor, dict):
        return None

    preferred = [
        actor.get("provider"),
        actor.get("username"),
        actor.get("account_id"),
        actor.get("arn"),
        actor.get("git_user_name"),
        actor.get("os_user"),
        actor.get("ci_actor"),
    ]
    parts = [str(v).strip() for v in preferred if v not in (None, "")]
    if parts:
        return " | ".join(parts[:3])
    return None


_ARROW_TITLE = {
    "synced": "Lockfile shows this target has the current secret value (hash matches).",
    "pending": "This target is not recorded in the lockfile yet — run Sync.",
    "drift": "Recorded hash for this target differs from the current secret hash — re-sync.",
}


def apply_force_resync_flags(target_groups: list[dict[str, Any]]) -> None:
    """Set ``can_force_resync`` on each lane when multi-target and another lane is synced."""
    flat: list[dict[str, Any]] = []
    for g in target_groups:
        for ln in g["lanes"]:
            flat.append(ln)
    n = len(flat)
    for i, lane in enumerate(flat):
        other_synced = n >= 2 and any(
            flat[j].get("sync_state") == "synced" for j in range(n) if j != i
        )
        lane["can_force_resync"] = other_synced


def compute_is_unsynced(
    *,
    has_targets: bool,
    in_lock: bool,
    target_groups: list[dict[str, Any]],
) -> bool:
    """True if the secret needs attention (lock-only secrets without targets, or any lane not synced)."""
    if not has_targets:
        return not in_lock
    for g in target_groups:
        for lane in g["lanes"]:
            if lane["sync_state"] != "synced":
                return True
    return False


def target_groups_show_only_unsynced_lanes(
    target_groups: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Drop lanes where sync_state is ``synced`` (for the unsynced-only dashboard filter)."""
    out: list[dict[str, Any]] = []
    for g in target_groups:
        lanes = [ln for ln in g["lanes"] if ln.get("sync_state") != "synced"]
        if lanes:
            out.append({**g, "lanes": lanes})
    return out


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


def build_manifest_rows(
    lockfile: Lockfile,
    secretfile_path: Path | None,
    secretfile: Secretfile | None = None,
) -> dict[str, Any]:
    """Secretfile / lockfile metadata for the dashboard header."""
    from secretzero.provider_identity import collect_provider_identity_rows

    sf = lockfile.secretfile
    name = str(secretfile_path) if secretfile_path else "—"
    base: dict[str, Any]
    if not sf:
        base = {
            "secretfile_display": name,
            "synced_at": "—",
            "secretfile_hash": "—",
            "var_files": "—",
        }
    else:
        vf = ", ".join(sf.var_files) if sf.var_files else "—"
        h = sf.hash
        hp = (h[:20] + "…") if h and len(h) > 20 else (h or "—")
        base = {
            "secretfile_display": name,
            "synced_at": _fmt_ts(sf.synced_at),
            "secretfile_hash": hp,
            "var_files": vf,
        }
    base["provider_rows"] = collect_provider_identity_rows(secretfile) if secretfile else []
    return base


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
                lane_ui = build_target_lane_ui(sec.name, tc)
                bucket[key].append(
                    {
                        "dest": lane_ui["dest"],
                        "details": lane_ui["details"],
                        "sync_state": sync_state,
                        "arrow_title": _ARROW_TITLE[sync_state],
                        "target_id": tid,
                        "actor_summary": _target_actor_summary(entry, tid),
                    }
                )
            for key in order:
                target_groups.append(
                    {
                        "provider": key[0],
                        "kind": key[1],
                        # "lanes" not "items": Jinja dicts expose .items as a method
                        "lanes": bucket[key],
                    }
                )
            apply_force_resync_flags(target_groups)
        agent_payload = build_agent_instructions_payload(secretfile, sec)
        in_lock = entry is not None
        is_unsynced = compute_is_unsynced(
            has_targets=has_targets,
            in_lock=in_lock,
            target_groups=target_groups,
        )
        rows.append(
            {
                "name": sec.name,
                "kind": sec.kind,
                "has_targets": has_targets,
                "target_groups": target_groups,
                "hash_preview": (entry.hash[:18] + "…") if entry and entry.hash else "—",
                "updated_at": _fmt_ts(entry.updated_at) if entry else "—",
                "last_rotated": (
                    _fmt_ts(entry.last_rotated) if entry and entry.last_rotated else "—"
                ),
                "rotation_count": entry.rotation_count if entry else 0,
                "in_lock": in_lock,
                "is_unsynced": is_unsynced,
                "can_set_value": _secret_can_set_value_web(sec),
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
        sync_client="network_web",
    )
