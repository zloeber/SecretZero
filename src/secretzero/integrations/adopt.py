"""Orchestrate agent adopt/list workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from secretzero.config import ConfigLoader
from secretzero.integrations.base import AgentAdoptPlan, AgentAdoptResult, DetectedSecretRef
from secretzero.integrations.registry import (
    detect_all_installs,
    list_adapters,
    resolve_agent_install,
)
from secretzero.lockfile import Lockfile
from secretzero.lockfile_import import run_lockfile_import
from secretzero.sync import SyncEngine

_SCHEMA_HEADER = (
    "# yaml-language-server: $schema="
    "https://github.com/zloeber/SecretZero/raw/refs/heads/main/Secretfile.schema.json\n"
)
_DEFAULT_LOCKFILE = ".gitsecrets.lock"
_TEMPLATE_NAME = "agent.env.template"


def _default_next_steps(output_dir: Path) -> list[str]:
    sf = output_dir / "Secretfile.yml"
    return [
        f"secretzero validate -f {sf}",
        f"secretzero agent adopt --preseed-lockfile --output-dir {output_dir}",
        f"secretzero agent sync --json -f {sf}",
        f"secretzero sync -f {sf}",
    ]


def _ref_to_dict(ref: DetectedSecretRef) -> dict[str, Any]:
    return {
        "secret_name": ref.secret_name,
        "env_key": ref.env_key,
        "source_file": ref.source_file,
        "group": ref.group,
        "present": ref.present,
    }


def _detection_to_dict(det: Any) -> dict[str, Any]:
    return {
        "target": det.target,
        "source_dir": str(det.source_dir),
        "detected": det.detected,
        "signals": list(det.signals),
        "has_secretzero_env": det.has_secretzero_env,
        "secretfile_path": str(det.secretfile_path) if det.secretfile_path else None,
        "lockfile_path": str(det.lockfile_path) if det.lockfile_path else None,
    }


def run_agent_list() -> AgentAdoptResult:
    """Read-only discovery of agent installs."""
    detections = detect_all_installs()
    return AgentAdoptResult(
        generated=False,
        detections=[_detection_to_dict(d) for d in detections],
        next_steps=[
            "secretzero agent adopt --dry-run --format json",
            "secretzero agent adopt --target hermes --output-dir ./agents/hermes",
        ],
    )


def _secret_definition(
    ref: DetectedSecretRef,
    *,
    install_root: Path,
    output_dir: Path,
    target_id: str,
) -> dict[str, Any]:
    use_absolute = output_dir.resolve() != install_root.resolve()
    if use_absolute:
        dotenv_path = str((install_root / ref.source_file).resolve())
    else:
        dotenv_path = ref.source_file
    return {
        "name": ref.secret_name,
        "kind": "static",
        "description": f"{target_id} credential for {ref.env_key}",
        "config": {"default": None},
        "targets": [
            {
                "provider": "local",
                "kind": "file",
                "config": {
                    "path": dotenv_path,
                    "format": "dotenv",
                    "key": ref.env_key,
                    "merge": True,
                },
            }
        ],
    }


def _load_existing_secret_names(secretfile_path: Path) -> set[str]:
    if not secretfile_path.is_file():
        return set()
    try:
        data = yaml.safe_load(secretfile_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return set()
    names: set[str] = set()
    for item in data.get("secrets") or []:
        if isinstance(item, dict) and item.get("name"):
            names.add(str(item["name"]))
    return names


def _build_manifest_document(
    *,
    adapter: Any,
    install_root: Path,
    output_dir: Path,
    discovered: list[DetectedSecretRef],
    existing_path: Path,
    merged_existing: bool,
) -> dict[str, Any]:
    existing_names = _load_existing_secret_names(existing_path) if merged_existing else set()
    new_defs = [
        _secret_definition(
            ref,
            install_root=install_root,
            output_dir=output_dir,
            target_id=adapter.target_id,
        )
        for ref in discovered
        if ref.secret_name not in existing_names
    ]

    if merged_existing and existing_path.is_file():
        doc = yaml.safe_load(existing_path.read_text(encoding="utf-8")) or {}
        if not isinstance(doc, dict):
            doc = {}
        secrets = list(doc.get("secrets") or [])
        secrets.extend(new_defs)
        doc["secrets"] = secrets
        metadata = dict(doc.get("metadata") or {})
        annotations = dict(metadata.get("annotations") or {})
        annotations["secretzero.integration.target"] = adapter.target_id
        annotations["secretzero.integration.source"] = str(install_root)
        metadata["annotations"] = annotations
        metadata.setdefault("project", f"{adapter.target_id}-agent")
        doc["metadata"] = metadata
        doc.setdefault("providers", {"local": {"kind": "local", "config": {}}})
        variables = dict(doc.get("variables") or {})
        variables["agent_home"] = str(install_root)
        doc["variables"] = variables
        return doc

    return {
        "metadata": {
            "project": f"{adapter.target_id}-agent",
            "owner": "agent-operator",
            "annotations": {
                "secretzero.integration.target": adapter.target_id,
                "secretzero.integration.source": str(install_root),
            },
        },
        "variables": {"agent_home": str(install_root)},
        "providers": {"local": {"kind": "local", "config": {}}},
        "secrets": new_defs,
    }


def _write_env_template(output_dir: Path, discovered: list[DetectedSecretRef]) -> Path:
    lines = [
        "# SecretZero agent.env.template — safe to commit (no values)",
        "# Generated from present credentials at adopt time.",
        "",
    ]
    for ref in sorted(discovered, key=lambda r: r.env_key):
        lines.append(f"# {ref.group}: {ref.secret_name}")
        lines.append(f"# {ref.env_key}=")
        lines.append("")
    path = output_dir / _TEMPLATE_NAME
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _run_preseed(
    *,
    output_dir: Path,
    secretfile_path: Path,
    install_root: Path,
) -> dict[str, Any]:
    loader = ConfigLoader()
    config = loader.load_file(secretfile_path)
    lockfile_path = output_dir / _DEFAULT_LOCKFILE
    lock = Lockfile.load(lockfile_path)
    secretfile_content = secretfile_path.read_text(encoding="utf-8")
    engine = SyncEngine(
        config,
        lock,
        secretfile_path=secretfile_path,
        secretfile_content=secretfile_content,
        hide_input=True,
        prompt_on_empty=False,
        sync_client="cli",
    )
    env_source = install_root / ".env"
    from secretzero.ingest_preseed import secret_names_for_ingest_source

    matched = secret_names_for_ingest_source(
        config, source=env_source.resolve(), secretfile_dir=secretfile_path.parent
    )
    if not matched:
        return {
            "skipped": True,
            "reason": "no secrets matched .env target path",
            "matched_count": 0,
        }
    summary = run_lockfile_import(
        engine,
        secretfile=config,
        secretfile_path=secretfile_path,
        secretfile_content=secretfile_content,
        secret_names=matched,
        active_var_files=[],
        dry_run=False,
    )
    lock.save(lockfile_path)
    return dict(summary)


def run_agent_adopt(
    *,
    target: str | None = None,
    source_dir: Path | None = None,
    output_dir: Path | None = None,
    template: bool = False,
    preseed_lockfile: bool = False,
    dry_run: bool = False,
    force: bool = False,
) -> AgentAdoptResult:
    """Resolve, scan, and optionally write a SecretZero environment for an agent install."""
    resolved = resolve_agent_install(target=target, source_dir=source_dir)
    if resolved is None:
        detections = detect_all_installs()
        return AgentAdoptResult(
            generated=False,
            reason="Could not resolve agent target and install path",
            detections=[_detection_to_dict(d) for d in detections],
            next_steps=[
                "secretzero agent list --format json",
                "secretzero agent adopt --target hermes --source-dir ~/.hermes",
            ],
        )

    adapter, install_root = resolved
    out_root = (output_dir or install_root).expanduser().resolve()
    discovered, skipped = adapter.scan_present_secrets(install_root)

    plan = AgentAdoptPlan(
        target=adapter.target_id,
        source_dir=install_root,
        output_dir=out_root,
        discovered=discovered,
        skipped_empty=skipped,
    )

    secretfile_path = out_root / "Secretfile.yml"
    merged_existing = secretfile_path.is_file() and not force

    if not discovered:
        return AgentAdoptResult(
            generated=False,
            target=adapter.target_id,
            source_dir=str(install_root),
            output_dir=str(out_root),
            discovered=[],
            skipped_empty=skipped,
            reason="No present credentials found in agent install catalog surfaces",
            dry_run=dry_run,
            next_steps=_default_next_steps(out_root),
        )

    artifacts: list[str] = [str(secretfile_path)]
    if template:
        artifacts.append(str(out_root / _TEMPLATE_NAME))
    if preseed_lockfile:
        artifacts.append(str(out_root / _DEFAULT_LOCKFILE))

    preseed_summary: dict[str, Any] | None = None
    if not dry_run:
        out_root.mkdir(parents=True, exist_ok=True)
        doc = _build_manifest_document(
            adapter=adapter,
            install_root=install_root,
            output_dir=out_root,
            discovered=discovered,
            existing_path=secretfile_path,
            merged_existing=merged_existing,
        )
        secretfile_path.write_text(
            _SCHEMA_HEADER + yaml.safe_dump(doc, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )
        plan.merged_existing = merged_existing

        if template:
            _write_env_template(out_root, discovered)

        if preseed_lockfile:
            preseed_summary = _run_preseed(
                output_dir=out_root,
                secretfile_path=secretfile_path,
                install_root=install_root,
            )

    plan.artifacts = artifacts
    return AgentAdoptResult(
        generated=not dry_run,
        target=adapter.target_id,
        source_dir=str(install_root),
        output_dir=str(out_root),
        discovered=[_ref_to_dict(r) for r in discovered],
        skipped_empty=skipped,
        artifacts=artifacts,
        preseed=preseed_summary,
        dry_run=dry_run,
        next_steps=_default_next_steps(out_root),
    )


def adapters_summary() -> list[dict[str, str]]:
    return [{"target": a.target_id, "display_name": a.display_name} for a in list_adapters()]
