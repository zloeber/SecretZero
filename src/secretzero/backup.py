"""Encrypted backup/restore helpers for synced target values."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from secretzero.models import Secret, Secretfile, TargetConfig
from secretzero.sync import SyncEngine

BACKUP_FORMAT_VERSION = "1"


def _parse_env_age_recipients() -> list[str]:
    values: list[str] = []
    raw_multi = os.environ.get("SOPS_AGE_RECIPIENTS", "")
    if raw_multi.strip():
        values.extend([item.strip() for item in raw_multi.split(",") if item.strip()])
    raw_single = os.environ.get("SOPS_AGE_RECIPIENT", "")
    if raw_single.strip():
        values.append(raw_single.strip())
    # Preserve order while dropping duplicates.
    deduped: list[str] = []
    seen: set[str] = set()
    for item in values:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _public_age_key_from_private_key_file(key_file: Path) -> str:
    for line in key_file.read_text().splitlines():
        low = line.lower().strip()
        if low.startswith("# public key:"):
            return line.split(":", 1)[1].strip()
    raise ValueError(f"Could not find public key in age key file: {key_file}")


def resolve_backup_age_recipients(
    *,
    output_file: Path,
    explicit_recipients: tuple[str, ...],
    age_key_file: Path | None,
) -> tuple[list[str], Path | None]:
    """Resolve encryption recipients; optionally auto-generate an age key."""
    recipients = [r.strip() for r in explicit_recipients if r.strip()]
    generated_key_file: Path | None = None

    if recipients:
        return recipients, None

    if age_key_file is not None:
        if not age_key_file.exists():
            raise ValueError(f"Age key file not found: {age_key_file}")
        return [_public_age_key_from_private_key_file(age_key_file)], None

    env_recipients = _parse_env_age_recipients()
    if env_recipients:
        return env_recipients, None

    if shutil.which("age-keygen") is None:
        raise ValueError(
            "No AGE recipient configured. Set SOPS_AGE_RECIPIENT(S), pass --age-recipient, "
            "or install age-keygen for automatic key generation."
        )

    generated_key_file = output_file.with_suffix(output_file.suffix + ".agekey")
    generated_key_file.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(  # noqa: S603
        ["age-keygen", "-o", str(generated_key_file)],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        msg = (proc.stderr or "").strip() or "age-keygen failed"
        raise ValueError(msg)
    return [_public_age_key_from_private_key_file(generated_key_file)], generated_key_file


def _run_sops(
    args: list[str], input_text: str | None = None, env: dict[str, str] | None = None
) -> str:
    if shutil.which("sops") is None:
        raise ValueError("sops CLI not found in PATH")
    proc = subprocess.run(  # noqa: S603
        ["sops", *args],
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    if proc.returncode != 0:
        msg = (proc.stderr or "").strip() or "sops command failed"
        raise ValueError(msg)
    return proc.stdout


def encrypt_backup_document(
    *,
    backup_doc: dict[str, Any],
    output_file: Path,
    recipients: list[str],
    age_key_file: Path | None,
) -> None:
    args = ["--encrypt", "--input-type", "json", "--output-type", "json"]
    for recipient in recipients:
        args.extend(["--age", recipient])
    args.append("/dev/stdin")
    env = os.environ.copy()
    if age_key_file is not None:
        env["SOPS_AGE_KEY_FILE"] = str(age_key_file)
    encrypted = _run_sops(args, input_text=json.dumps(backup_doc, indent=2), env=env)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(encrypted)


def decrypt_backup_document(*, backup_file: Path, age_key_file: Path | None) -> dict[str, Any]:
    env = os.environ.copy()
    if age_key_file is not None:
        env["SOPS_AGE_KEY_FILE"] = str(age_key_file)
    plain = _run_sops(["--decrypt", str(backup_file)], env=env)
    payload = json.loads(plain)
    if not isinstance(payload, dict):
        raise ValueError("Backup payload is not a JSON object")
    return payload


def _plain_secret_entries(
    engine: SyncEngine, secret: Secret
) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    lock_entry = engine.lockfile.get_secret_info(secret.name)
    tracked_targets = set(lock_entry.targets.keys()) if lock_entry else set()
    for target in secret.targets:
        tid = engine._build_target_id(target)
        if tid not in tracked_targets:
            continue
        value = engine._retrieve_from_target(secret.name, target)
        if value is None:
            warnings.append(f"{secret.name} -> {tid}: not retrievable")
            continue
        rows.append(
            {
                "secret_ref": secret.name,
                "target_secret_key": secret.name,
                "target_id": tid,
                "provider": target.provider,
                "kind": str(target.kind),
                "target_config": dict(target.config),
                "value": value,
            }
        )
    return rows, warnings


def _template_secret_entries(
    engine: SyncEngine,
    secret: Secret,
    secretfile: Secretfile,
) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    template_name = secret.kind.split(".", 1)[1]
    template = secretfile.templates.get(template_name)
    if template is None:
        warnings.append(f"{secret.name}: template '{template_name}' missing")
        return rows, warnings
    for field_name, field_def in template.fields.items():
        secret_ref = f"{secret.name}.{field_name}"
        lock_entry = engine.lockfile.get_secret_info(secret_ref)
        tracked_targets = set(lock_entry.targets.keys()) if lock_entry else set()
        combined: list[TargetConfig] = []
        seen: set[str] = set()
        for target in [*field_def.targets, *template.targets]:
            tid = engine._build_target_id(target)
            if tid in seen:
                continue
            seen.add(tid)
            combined.append(target)
        for target in combined:
            tid = engine._build_target_id(target)
            if tid not in tracked_targets:
                continue
            value = engine._retrieve_from_target(field_name, target)
            if value is None:
                warnings.append(f"{secret_ref} -> {tid}: not retrievable")
                continue
            rows.append(
                {
                    "secret_ref": secret_ref,
                    "target_secret_key": field_name,
                    "target_id": tid,
                    "provider": target.provider,
                    "kind": str(target.kind),
                    "target_config": dict(target.config),
                    "value": value,
                }
            )
    return rows, warnings


def collect_backup_entries(
    *,
    engine: SyncEngine,
    secretfile: Secretfile,
    secret_names: list[str] | None = None,
) -> dict[str, Any]:
    scoped = secretfile.secrets
    if secret_names:
        wanted = set(secret_names)
        scoped = [s for s in secretfile.secrets if s.name in wanted]
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    for secret in scoped:
        if secret.kind.startswith("templates."):
            out_rows, out_warnings = _template_secret_entries(engine, secret, secretfile)
        else:
            out_rows, out_warnings = _plain_secret_entries(engine, secret)
        rows.extend(out_rows)
        warnings.extend(out_warnings)

    return {
        "version": BACKUP_FORMAT_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "entries": rows,
        "warnings": warnings,
        "secret_count": len(scoped),
    }


def restore_backup_entries(
    *,
    engine: SyncEngine,
    entries: list[dict[str, Any]],
    import_only_selectors: set[str] | None = None,
    selected_ids: set[str] | None = None,
) -> dict[str, Any]:
    import_only_selectors = import_only_selectors or set()
    selected_ids = selected_ids or set()

    restored = 0
    imported_only = 0
    skipped = 0
    errors: list[str] = []

    for item in entries:
        entry_id = str(item.get("entry_id") or "")
        if selected_ids and entry_id not in selected_ids:
            skipped += 1
            continue

        secret_ref = str(item.get("secret_ref") or "")
        target_id = str(item.get("target_id") or "")
        target_secret_key = str(item.get("target_secret_key") or secret_ref)
        value = item.get("value")
        if not secret_ref or not target_id or not target_secret_key or value is None:
            errors.append(f"Invalid backup entry: {entry_id or '<unknown>'}")
            continue

        selector = f"{secret_ref}@{target_id}"
        import_only = selector in import_only_selectors or secret_ref in import_only_selectors

        if import_only:
            engine.lockfile.add_secret(secret_ref, value, target_id=target_id, is_rotation=True)
            engine.lockfile.record_target_update(
                secret_ref, target_id, actor=engine._sync_actor_dict()
            )
            imported_only += 1
            continue

        try:
            target = TargetConfig(
                provider=str(item.get("provider") or ""),
                kind=str(item.get("kind") or ""),
                config=dict(item.get("target_config") or {}),
            )
            result = engine._store_in_target(target_secret_key, str(value), target)
            if result.get("status") in {"failed", "error", "unsupported"}:
                msg = str(result.get("message") or "store failed")
                errors.append(f"{selector}: {msg}")
                continue
            engine.lockfile.add_secret(secret_ref, value, target_id=target_id, is_rotation=True)
            engine.lockfile.record_target_update(
                secret_ref,
                target_id,
                actor=engine._target_provenance_actor(result.get("actor")),
            )
            restored += 1
        except Exception as exc:
            errors.append(f"{selector}: {exc}")

    return {
        "restored": restored,
        "imported_only": imported_only,
        "skipped": skipped,
        "errors": errors,
    }
