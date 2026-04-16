"""Import pre-seeded secret values from targets into the lockfile."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from secretzero.lockfile import Lockfile
from secretzero.models import Secret, Secretfile, Template
from secretzero.sync import SyncEngine


def _import_actor(engine: SyncEngine) -> dict[str, Any]:
    return {"operation": "lockfile_import", "client": engine.sync_client}


def _retrieve_plain(engine: SyncEngine, secret: Secret) -> tuple[str | None, str | None]:
    """Return (value, first_target_id) from the first target that yields a value."""
    for tc in secret.targets:
        val = engine._retrieve_from_target(secret.name, tc)
        if val is not None:
            return val, engine._build_target_id(tc)
    return None, None


def _apply_plain_import(
    engine: SyncEngine,
    secret: Secret,
    *,
    dry_run: bool,
) -> dict[str, Any]:
    name = secret.name
    out: dict[str, Any] = {"secret": name, "kind": "plain", "status": "skipped", "detail": ""}

    if not secret.targets:
        out["detail"] = "no_targets"
        return out

    value, _first_tid = _retrieve_plain(engine, secret)
    if value is None:
        out["detail"] = "not_retrievable"
        return out

    canonical = Lockfile._hash_value(value)
    matched_targets: list[str] = []

    for tc in secret.targets:
        got = engine._retrieve_from_target(name, tc)
        if got is None:
            continue
        if Lockfile._hash_value(got) != canonical:
            out["detail"] = "target_value_mismatch"
            out["status"] = "error"
            return out
        matched_targets.append(engine._build_target_id(tc))

    if not matched_targets:
        out["detail"] = "not_retrievable"
        return out

    entry = engine.lockfile.get_secret_info(name)
    if entry and entry.hash == canonical:
        tracked = set(entry.targets.keys())
        if tracked.issuperset(set(matched_targets)):
            out["status"] = "unchanged"
            out["detail"] = "hash_and_targets_current"
            return out

    if dry_run:
        out["status"] = "would_import" if not entry else "would_update"
        out["detail"] = "dry_run"
        return out

    for tid in matched_targets:
        engine.lockfile.add_secret(name, value, target_id=tid)
        engine.lockfile.record_target_update(name, tid, actor=_import_actor(engine))

    out["status"] = "imported" if not entry else "updated"
    out["detail"] = f"targets={len(matched_targets)}"
    return out


def _import_template_fields(
    engine: SyncEngine,
    secret: Secret,
    template: Template,
    *,
    dry_run: bool,
) -> dict[str, Any]:
    name = secret.name
    out: dict[str, Any] = {
        "secret": name,
        "kind": "template",
        "status": "skipped",
        "fields": [],
        "detail": "",
    }

    any_change = False
    any_error = False

    for field_name, field_def in template.fields.items():
        field_secret_name = f"{name}.{field_name}"
        all_targets = field_def.targets + template.targets
        if not all_targets:
            out["fields"].append({"field": field_name, "status": "skipped", "detail": "no_targets"})
            continue

        value: str | None = None
        for tc in all_targets:
            value = engine._retrieve_from_target(field_name, tc)
            if value is not None:
                break
        if value is None:
            out["fields"].append(
                {"field": field_name, "status": "skipped", "detail": "not_retrievable"}
            )
            continue

        canonical = Lockfile._hash_value(value)
        matched: list[str] = []
        for tc in all_targets:
            got = engine._retrieve_from_target(field_name, tc)
            if got is None:
                continue
            if Lockfile._hash_value(got) != canonical:
                out["fields"].append(
                    {"field": field_name, "status": "error", "detail": "target_value_mismatch"}
                )
                any_error = True
                matched = []
                break
            matched.append(engine._build_target_id(tc))

        if not matched:
            continue

        entry = engine.lockfile.get_secret_info(field_secret_name)
        if entry and entry.hash == canonical:
            tracked = set(entry.targets.keys())
            if tracked.issuperset(set(matched)):
                out["fields"].append(
                    {"field": field_name, "status": "unchanged", "detail": "current"}
                )
                continue

        any_change = True
        if dry_run:
            out["fields"].append(
                {
                    "field": field_name,
                    "status": "would_import" if not entry else "would_update",
                    "detail": "dry_run",
                }
            )
            continue

        for tid in matched:
            engine.lockfile.add_secret(field_secret_name, value, target_id=tid)
            engine.lockfile.record_target_update(
                field_secret_name, tid, actor=_import_actor(engine)
            )
        out["fields"].append({"field": field_name, "status": "imported", "detail": ""})

    if any_error:
        out["status"] = "error"
        out["detail"] = "field_errors"
    elif any_change and dry_run:
        out["status"] = "would_change"
    elif any_change:
        out["status"] = "imported"
    else:
        out["status"] = "unchanged"
        out["detail"] = "no_field_changes"
    return out


def run_lockfile_import(
    engine: SyncEngine,
    *,
    secretfile: Secretfile,
    secretfile_path: Path,
    secretfile_content: str,
    secret_names: list[str] | None = None,
    active_var_files: list[Path] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Refresh stale lockfile target IDs, then import/update hashes from live targets.

    Does not write to targets; only reads and updates the lockfile (unless *dry_run*).

    Returns:
        Summary dict with ``refresh``, ``details`` (per secret), and counters.
    """
    scoped = secretfile.secrets
    if secret_names:
        wanted = set(secret_names)
        scoped = [s for s in secretfile.secrets if s.name in wanted]

    engine._enforce_provider_identity_policies(scoped)

    refresh = engine.refresh_lockfile_targets(
        secret_names=list(secret_names) if secret_names else None,
        dry_run=dry_run,
    )

    details: list[dict[str, Any]] = []
    imported = updated = unchanged = skipped = errors = 0
    would_apply = 0

    for secret in scoped:
        try:
            if secret.kind.startswith("templates."):
                tname = secret.kind.split(".", 1)[1]
                tmpl = secretfile.templates.get(tname)
                if not tmpl:
                    details.append(
                        {
                            "secret": secret.name,
                            "kind": "template",
                            "status": "error",
                            "detail": f"unknown_template:{tname}",
                        }
                    )
                    errors += 1
                    continue
                row = _import_template_fields(engine, secret, tmpl, dry_run=dry_run)
                details.append(row)
                st = row.get("status")
                if dry_run and st == "would_change":
                    would_apply += 1
                elif st == "imported":
                    imported += 1
                elif st == "unchanged":
                    unchanged += 1
                elif st == "error":
                    errors += 1
                else:
                    skipped += 1
            else:
                row = _apply_plain_import(engine, secret, dry_run=dry_run)
                details.append(row)
                st = row.get("status")
                if dry_run and str(st).startswith("would_"):
                    would_apply += 1
                elif st == "imported":
                    imported += 1
                elif st == "updated":
                    updated += 1
                elif st == "unchanged":
                    unchanged += 1
                elif st == "error":
                    errors += 1
                else:
                    skipped += 1
        except Exception as exc:
            details.append(
                {"secret": secret.name, "status": "error", "detail": str(exc), "kind": "plain"}
            )
            errors += 1

    if not dry_run and (
        imported
        or updated
        or refresh.get("mismatch_targets", 0)
        or refresh.get("mismatch_secrets", 0)
    ):
        engine.lockfile.track_secretfile(secretfile_path, secretfile_content)
        engine.lockfile.track_variable_context(
            list(active_var_files or []),
            dict(secretfile.variables or {}),
        )

    return {
        "dry_run": dry_run,
        "refresh": refresh,
        "imported": imported,
        "updated": updated,
        "unchanged": unchanged,
        "skipped": skipped,
        "errors": errors,
        "would_apply": would_apply,
        "details": details,
    }
