"""Shared service helpers for MCP/API parity endpoints."""

from __future__ import annotations

import platform
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from secretzero import __version__
from secretzero.agent_instructions_report import (
    InstructionScope,
    build_instructions_json_payload,
    collect_instruction_entries,
)
from secretzero.bundle_catalog import build_bundle_catalog
from secretzero.config import ConfigLoader
from secretzero.drift import DriftDetector
from secretzero.environment_resolution import apply_target_profile, resolve_environment_context
from secretzero.ingest_preseed import describe_ingest_source_match, secret_names_for_ingest_source
from secretzero.integrations.adopt import run_agent_adopt, run_agent_list
from secretzero.integrations.registry import list_agent_targets
from secretzero.lockfile import Lockfile
from secretzero.lockfile_import import run_lockfile_import
from secretzero.manifest_plaintext import list_manifest_plaintext_violations
from secretzero.mcp.discovery_ops import run_detect_scan, run_discover_bindings
from secretzero.models import SECRETFILE_MANIFEST_SPEC_VERSION, Secretfile
from secretzero.rotation import should_rotate_secret
from secretzero.sync import SyncEngine


def load_api_workspace(
    secretfile_path: Path,
    *,
    environment: str | None = None,
    var_files: list[str] | None = None,
    lockfile_override: str | None = None,
) -> tuple[Path, Secretfile, Any, Lockfile, str]:
    """Load Secretfile, env context, lockfile, and raw content for API handlers."""
    loader = ConfigLoader()
    base = loader.load_file(secretfile_path)
    env_ctx = resolve_environment_context(
        secretfile=base,
        secretfile_path=secretfile_path,
        environment=environment,
        runtime_var_files=[Path(vf) for vf in (var_files or [])],
        runtime_lockfile=lockfile_override,
    )
    secretfile = loader.load_file(secretfile_path, var_files=env_ctx.resolved_var_files or None)
    secretfile = apply_target_profile(secretfile, env_ctx.resolved_target_profile)
    lockfile_path = env_ctx.resolved_lockfile
    lock = Lockfile.load(lockfile_path)
    content = secretfile_path.read_text(encoding="utf-8")
    return secretfile_path, secretfile, env_ctx, lock, content


def api_catalog(
    *,
    bundle: str | None = None,
    provider_kind: str | None = None,
    kind: str | None = None,
) -> dict[str, Any]:
    return build_bundle_catalog(bundle=bundle, provider_kind=provider_kind, kind=kind)


def api_version(*, detailed: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": "secretzero",
        "version": __version__,
        "website": "https://secret0.com",
        "backend": "api",
    }
    if detailed:
        payload.update(
            {
                "python_version": platform.python_version(),
                "platform": platform.platform(),
                "executable": sys.executable,
                "manifest_spec_version": SECRETFILE_MANIFEST_SPEC_VERSION,
            }
        )
    return payload


def api_detect(
    secretfile_path: Path, *, directory: str | None = None, all_keys: bool = False
) -> dict[str, Any]:
    scan_root = (
        Path(directory).expanduser().resolve() if directory else secretfile_path.parent.resolve()
    )
    return run_detect_scan(scan_root, all_keys=all_keys)


def api_discover(
    secretfile_path: Path,
    *,
    directory: str | None = None,
    local_only: bool = True,
) -> dict[str, Any]:
    scan_root = (
        Path(directory).expanduser().resolve() if directory else secretfile_path.parent.resolve()
    )
    return run_discover_bindings(scan_root, local_only=local_only)


def api_agent_instructions(
    secretfile_path: Path,
    *,
    environment: str | None = None,
    show_all: bool = False,
    detailed: bool = False,
    secret_names: list[str] | None = None,
) -> dict[str, Any]:
    _, secretfile, env_ctx, lock, _ = load_api_workspace(secretfile_path, environment=environment)
    scope = InstructionScope.ALL if show_all else InstructionScope.PENDING
    name_filter = frozenset(secret_names) if secret_names else None
    entries = collect_instruction_entries(
        secretfile,
        lock,
        scope=scope,
        secret_names=name_filter,
    )
    payload = build_instructions_json_payload(entries, scope=scope, detailed=detailed)
    payload["resolved_lockfile"] = str(env_ctx.resolved_lockfile)
    return payload


def api_agent_list() -> dict[str, Any]:
    result = run_agent_list()
    payload = asdict(result)
    payload["registered_targets"] = list_agent_targets()
    return payload


def api_agent_adopt(
    *,
    target: str | None = None,
    source_dir: str | None = None,
    output_dir: str | None = None,
    template: bool = False,
    preseed_lockfile: bool = False,
    dry_run: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    result = run_agent_adopt(
        target=target,
        source_dir=Path(source_dir) if source_dir else None,
        output_dir=Path(output_dir) if output_dir else None,
        template=template,
        preseed_lockfile=preseed_lockfile,
        dry_run=dry_run,
        force=force,
    )
    return asdict(result)


def api_import_check(
    secretfile_path: Path,
    *,
    environment: str | None = None,
    secret_name: str | None = None,
) -> dict[str, Any]:
    _, _, env_ctx, _, _ = load_api_workspace(secretfile_path, environment=environment)
    lockfile_path = env_ctx.resolved_lockfile
    if not lockfile_path.exists():
        raise FileNotFoundError(f"Lockfile not found: {lockfile_path}")
    detector = DriftDetector(secretfile_path, lockfile_path, environment=environment)
    results = detector.check_drift(secret_name)
    drift_found = any(r.has_drift for r in results)
    return {
        "drift_detected": drift_found,
        "results": [
            {
                "secret_name": r.secret_name,
                "has_drift": r.has_drift,
                "message": r.message,
                "details": r.details,
            }
            for r in results
        ],
        "lockfile": str(lockfile_path),
    }


def api_clean_lockfile(
    secretfile_path: Path,
    *,
    environment: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    from secretzero.cli import _clean_lockfile_orphans

    _, secretfile, env_ctx, lock, _ = load_api_workspace(secretfile_path, environment=environment)
    orphaned = _clean_lockfile_orphans(secretfile, lock, dry_run=dry_run)
    if not dry_run and orphaned:
        lock.save(env_ctx.resolved_lockfile)
    return {
        "cleaned": len(orphaned),
        "orphaned_entries": orphaned,
        "dry_run": dry_run,
        "lockfile": str(env_ctx.resolved_lockfile),
    }


def api_ingest_preseed(
    secretfile_path: Path,
    *,
    source: str,
    environment: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    source_path = Path(source).resolve()
    file_path, config, env_ctx, lock, secretfile_content = load_api_workspace(
        secretfile_path, environment=environment
    )
    matched = secret_names_for_ingest_source(
        config, source=source_path, secretfile_dir=file_path.parent
    )
    match_meta = describe_ingest_source_match(
        config, source=source_path, secretfile_dir=file_path.parent
    )
    if not matched:
        raise ValueError(
            f"No secrets reference local file target path {source_path} (resolved from {source!r})"
        )
    engine = SyncEngine(
        config,
        lock,
        secretfile_path=file_path,
        secretfile_content=secretfile_content,
        hide_input=True,
        prompt_on_empty=False,
        sync_client="api",
    )
    summary = run_lockfile_import(
        engine,
        secretfile=config,
        secretfile_path=file_path,
        secretfile_content=secretfile_content,
        secret_names=matched,
        active_var_files=env_ctx.resolved_var_files or [],
        dry_run=dry_run,
    )
    payload = dict(summary)
    payload["ingest"] = match_meta
    payload["lockfile"] = str(env_ctx.resolved_lockfile)
    return payload


def api_sync_execute(
    secretfile_path: Path,
    *,
    dry_run: bool = True,
    force: bool = False,
    refresh: bool = True,
    secret_name: str | None = None,
    environment: str | None = None,
    var_files: list[str] | None = None,
) -> dict[str, Any]:
    file_path, config, env_ctx, lockfile, secretfile_content = load_api_workspace(
        secretfile_path,
        environment=environment,
        var_files=var_files,
    )
    sync_engine = SyncEngine(
        config,
        lockfile,
        secretfile_path=file_path,
        secretfile_content=secretfile_content,
        sync_client="api",
    )
    secret_names = [secret_name] if secret_name else None
    results = sync_engine.sync(
        dry_run=dry_run,
        force_rotation=force,
        secret_names=secret_names,
        refresh=refresh,
    )
    if not dry_run:
        lockfile.save(env_ctx.resolved_lockfile)
    generated = [
        d["name"]
        for d in results.get("details", [])
        if not dry_run and d.get("generated") and d.get("stored")
    ]
    skipped = [d["name"] for d in results.get("details", []) if dry_run or d.get("skipped")]
    return {
        "dry_run": dry_run,
        "generated": generated,
        "skipped": skipped,
        "results": results,
        "resolved_lockfile": str(env_ctx.resolved_lockfile),
    }


def api_rotate_check(
    secretfile_path: Path,
    *,
    secret_name: str | None = None,
) -> dict[str, Any]:
    _, config, _, lockfile, _ = load_api_workspace(secretfile_path)
    due: list[str] = []
    overdue: list[str] = []
    checked = 0
    secrets = config.secrets
    if secret_name:
        secrets = [s for s in secrets if s.name == secret_name]
    for secret in secrets:
        checked += 1
        entry = lockfile.get_secret_info(secret.name)
        if not entry or not secret.rotation_period:
            continue
        should_rotate, is_overdue = should_rotate_secret(
            secret.rotation_period,
            entry.last_rotated,
            entry.created_at,
        )
        if should_rotate:
            (overdue if is_overdue else due).append(secret.name)
    return {
        "secrets_checked": checked,
        "secrets_due": due,
        "secrets_overdue": overdue,
    }


def api_rotate_execute(
    secretfile_path: Path,
    *,
    secret_name: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    file_path, config, env_ctx, lockfile, secretfile_content = load_api_workspace(secretfile_path)
    sync_engine = SyncEngine(
        config,
        lockfile,
        secretfile_path=file_path,
        secretfile_content=secretfile_content,
        sync_client="api",
    )
    rotated: list[str] = []
    failed: list[str] = []
    secrets_to_rotate = []
    if secret_name:
        secret = next((s for s in config.secrets if s.name == secret_name), None)
        if secret is None:
            raise ValueError(f"Secret not found: {secret_name}")
        secrets_to_rotate = [secret]
    else:
        for secret in config.secrets:
            entry = lockfile.get_secret_info(secret.name)
            if entry and secret.rotation_period:
                should_rotate, _ = should_rotate_secret(
                    secret.rotation_period,
                    entry.last_rotated,
                    entry.created_at,
                )
                if should_rotate or force:
                    secrets_to_rotate.append(secret)
    for secret in secrets_to_rotate:
        try:
            result = sync_engine._sync_secret(secret, dry_run=False, force_rotation=True)
            if result.get("generated"):
                rotated.append(secret.name)
            else:
                failed.append(secret.name)
        except Exception:
            failed.append(secret.name)
    lockfile.save(env_ctx.resolved_lockfile)
    return {
        "rotated": rotated,
        "failed": failed,
        "message": f"Rotated {len(rotated)} secret(s)",
    }


def api_validate_loaded(secretfile: Secretfile, secretfile_path: Path) -> dict[str, Any]:
    violations = list_manifest_plaintext_violations(secretfile)
    is_valid = not violations
    result: dict[str, Any] = {
        "valid": is_valid,
        "message": (
            "Secretfile is valid"
            if is_valid
            else "Manifest contains plaintext static-like payloads"
        ),
        "file": str(secretfile_path),
    }
    if violations:
        result["plaintext_violations"] = violations
    else:
        result["config"] = {
            "manifest_spec_version": SECRETFILE_MANIFEST_SPEC_VERSION,
            "variables_count": len(secretfile.variables),
            "providers_count": len(secretfile.providers),
            "secrets_count": len(secretfile.secrets),
            "templates_count": len(secretfile.templates),
        }
    return result
