"""In-process SecretZero backend for MCP tools."""

from __future__ import annotations

import platform
import sys
from typing import Any

from secretzero import __version__
from secretzero.agent_context import spill_guard_active
from secretzero.bundle_catalog import build_bundle_catalog
from secretzero.manifest_plaintext import list_manifest_plaintext_violations
from secretzero.mcp.agent_ops import (
    run_agent_instructions,
    run_agent_sync,
    run_agent_sync_web_poll,
    run_agent_sync_web_start,
)
from secretzero.mcp.config import McpConfig
from secretzero.mcp.discovery_ops import (
    resolve_scan_directory,
    run_detect_scan,
    run_discover_bindings,
)
from secretzero.mcp.mutation_ops import (
    run_agent_adopt,
    run_clean_lockfile,
    run_drift_check,
    run_ingest_preseed,
    run_rotate_check,
    run_rotate_execute,
    run_sync_dry_run,
    run_sync_execute,
)
from secretzero.mcp.workspace import WorkspaceContext, load_workspace
from secretzero.models import SECRETFILE_MANIFEST_SPEC_VERSION, Secretfile
from secretzero.provider_identity import collect_provider_identity_rows
from secretzero.sync import SyncEngine


def _redact_target_config_for_spill_guard(cfg: dict[str, Any]) -> dict[str, Any]:
    if not cfg:
        return {}
    allow = {"path", "format", "merge", "key", "environment", "output_path", "namespace"}
    out: dict[str, Any] = {k: cfg[k] for k in allow if k in cfg}
    extra = sorted(set(cfg) - set(out))
    if extra:
        out["_redacted_config_keys"] = extra
    return out


class LocalBackend:
    """Call SecretZero core libraries directly on the local filesystem."""

    def __init__(self, cfg: McpConfig) -> None:
        self._cfg = cfg
        self._workspace: WorkspaceContext | None = None

    def _ws(self) -> WorkspaceContext:
        if self._workspace is None:
            self._workspace = load_workspace(self._cfg)
        return self._workspace

    def catalog_list(
        self,
        *,
        provider: str | None = None,
        bundle: str | None = None,
        kind: str | None = None,
    ) -> dict[str, Any]:
        catalog = build_bundle_catalog(
            bundle=bundle,
            provider_kind=provider,
            kind=kind,
        )
        return catalog

    def schema_get(self) -> dict[str, Any]:
        return Secretfile.model_json_schema()

    def secretfile_validate(self) -> dict[str, Any]:
        ws = self._ws()
        plaintext_violations: list[str] = []
        try:
            is_valid = True
            message = "Secretfile is valid"
            if spill_guard_active():
                plaintext_violations = list_manifest_plaintext_violations(ws.secretfile)
                if plaintext_violations:
                    is_valid = False
                    message = "Manifest contains plaintext static-like payloads"
        except Exception as exc:
            is_valid = False
            message = str(exc)

        result: dict[str, Any] = {
            "valid": is_valid,
            "message": message,
            "file": str(ws.secretfile_path),
        }
        if plaintext_violations:
            result["plaintext_violations"] = plaintext_violations
        if is_valid:
            result["config"] = {
                "manifest_spec_version": SECRETFILE_MANIFEST_SPEC_VERSION,
                "variables_count": len(ws.secretfile.variables),
                "providers_count": len(ws.secretfile.providers),
                "secrets_count": len(ws.secretfile.secrets),
                "templates_count": len(ws.secretfile.templates),
            }
        return result

    def secrets_list(self, *, name_filter: str | None = None) -> dict[str, Any]:
        ws = self._ws()
        secrets = ws.secretfile.secrets
        if name_filter:
            secrets = [s for s in secrets if name_filter.lower() in s.name.lower()]
        return {
            "secrets": [
                {
                    "name": s.name,
                    "kind": s.kind,
                    "one_time": s.one_time,
                    "rotation_period": s.rotation_period,
                    "targets_count": len(s.targets),
                    "targets": [{"provider": t.provider, "kind": t.kind} for t in s.targets],
                }
                for s in secrets
            ],
            "total": len(secrets),
        }

    def secrets_status(self) -> dict[str, Any]:
        ws = self._ws()
        lock = ws.lockfile
        config = ws.secretfile
        tracked_secretfile = lock.get_secretfile_info()
        current_secretfile_hash = lock._hash_value(ws.secretfile_content)
        secretfile_changed = None
        if tracked_secretfile:
            tracked_hash = tracked_secretfile.get("hash")
            tracked_filename = tracked_secretfile.get("filename")
            secretfile_changed = (
                tracked_filename != ws.secretfile_path.name
                or tracked_hash != current_secretfile_hash
            )

        sync_engine = SyncEngine(config, lock)
        sync_readiness = sync_engine.preflight_sync_readiness()

        secrets_data = []
        for secret in config.secrets:
            entry = lock.get_secret_info(secret.name)
            secret_info: dict[str, Any] = {
                "name": secret.name,
                "kind": secret.kind,
                "one_time": secret.one_time,
                "rotation_period": secret.rotation_period,
                "status": "synced" if entry else "not_synced",
                "targets": [{"provider": t.provider, "kind": t.kind} for t in secret.targets],
            }
            if entry:
                secret_info["created_at"] = str(entry.created_at)
                secret_info["updated_at"] = str(entry.updated_at)
                if entry.last_rotated:
                    secret_info["last_rotated"] = str(entry.last_rotated)
                    secret_info["rotation_count"] = entry.rotation_count
            secrets_data.append(secret_info)

        return {
            "secrets": secrets_data,
            "total": len(config.secrets),
            "synced": sum(1 for s in secrets_data if s["status"] == "synced"),
            "lockfile": str(ws.lockfile_path),
            "lockfile_exists": ws.lockfile_path.exists(),
            "provider_identity": collect_provider_identity_rows(config),
            "secretfile": {
                "path": str(ws.secretfile_path),
                "current_hash": current_secretfile_hash,
                "tracked_hash": tracked_secretfile.get("hash") if tracked_secretfile else None,
                "tracked_filename": (
                    tracked_secretfile.get("filename") if tracked_secretfile else None
                ),
                "tracked_synced_at": (
                    tracked_secretfile.get("synced_at") if tracked_secretfile else None
                ),
                "changed": secretfile_changed,
            },
            "sync_readiness": sync_readiness,
        }

    def providers_list(self) -> dict[str, Any]:
        ws = self._ws()
        return {
            "providers": [
                {
                    "name": name,
                    "kind": p.kind,
                    "auth_kind": p.auth.kind if p.auth else None,
                    "fallback_generator": p.fallback_generator,
                }
                for name, p in ws.secretfile.providers.items()
            ],
            "provider_identity": collect_provider_identity_rows(ws.secretfile),
            "total": len(ws.secretfile.providers),
        }

    def targets_list(self) -> dict[str, Any]:
        ws = self._ws()
        all_targets = []
        for secret in ws.secretfile.secrets:
            for target in secret.targets:
                cfg = dict(target.config)
                if spill_guard_active():
                    cfg = _redact_target_config_for_spill_guard(cfg)
                all_targets.append(
                    {
                        "secret": secret.name,
                        "provider": target.provider,
                        "kind": target.kind,
                        "config": cfg,
                    }
                )
        return {"targets": all_targets, "total": len(all_targets)}

    def variables_list(self, *, name_filter: str | None = None) -> dict[str, Any]:
        ws = self._ws()
        variables = dict(ws.secretfile.variables)
        if name_filter:
            variables = {k: v for k, v in variables.items() if name_filter.lower() in k.lower()}
        if spill_guard_active():
            return {
                "variable_names": sorted(variables.keys()),
                "total": len(variables),
                "values_redacted": True,
                "note": "Values omitted under SZ_AGENT or SZ_AGENT_MODE",
            }
        return {"variables": variables, "total": len(variables)}

    def version_info(self, *, detailed: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": "secretzero",
            "version": __version__,
            "website": "https://secret0.com",
            "backend": "local",
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

    def detect_secrets(
        self,
        *,
        directory: str | None = None,
        all_keys: bool = False,
    ) -> dict[str, Any]:
        scan_dir = resolve_scan_directory(self._cfg, directory)
        return run_detect_scan(scan_dir, all_keys=all_keys)

    def discover_bindings(
        self,
        *,
        directory: str | None = None,
        local_only: bool = True,
    ) -> dict[str, Any]:
        scan_dir = resolve_scan_directory(self._cfg, directory)
        return run_discover_bindings(scan_dir, local_only=local_only)

    def agent_sync(
        self,
        *,
        dry_run: bool = False,
        refresh: bool = True,
        web: bool = False,
        sz_agent: bool | None = None,
    ) -> dict[str, Any]:
        return run_agent_sync(
            self._cfg,
            dry_run=dry_run,
            refresh=refresh,
            web=web,
            sz_agent=sz_agent,
        )

    def agent_sync_web_start(
        self,
        *,
        dry_run: bool = False,
        refresh: bool = True,
    ) -> dict[str, Any]:
        return run_agent_sync_web_start(self._cfg, dry_run=dry_run, refresh=refresh)

    def agent_sync_web_poll(self, session_id: str) -> dict[str, Any]:
        return run_agent_sync_web_poll(session_id)

    def agent_instructions(
        self,
        *,
        show_all: bool = False,
        detailed: bool = False,
        secret_names: list[str] | None = None,
    ) -> dict[str, Any]:
        return run_agent_instructions(
            self._cfg,
            show_all=show_all,
            detailed=detailed,
            secret_names=secret_names,
        )

    def drift_check(self, *, secret_name: str | None = None) -> dict[str, Any]:
        return run_drift_check(self._cfg, secret_name=secret_name)

    def sync_dry_run(
        self,
        *,
        secret_name: str | None = None,
        refresh: bool = True,
        force: bool = False,
    ) -> dict[str, Any]:
        return run_sync_dry_run(self._cfg, secret_name=secret_name, refresh=refresh, force=force)

    def sync_execute(
        self,
        *,
        secret_name: str | None = None,
        refresh: bool = True,
        force: bool = False,
    ) -> dict[str, Any]:
        return run_sync_execute(self._cfg, secret_name=secret_name, refresh=refresh, force=force)

    def rotate_check(self, *, secret_name: str | None = None) -> dict[str, Any]:
        return run_rotate_check(self._cfg, secret_name=secret_name)

    def rotate_execute(
        self, *, secret_name: str | None = None, force: bool = False
    ) -> dict[str, Any]:
        return run_rotate_execute(self._cfg, secret_name=secret_name, force=force)

    def agent_adopt(
        self,
        *,
        target: str | None = None,
        source_dir: str | None = None,
        output_dir: str | None = None,
        template: bool = False,
        preseed_lockfile: bool = False,
        dry_run: bool = True,
        force: bool = False,
    ) -> dict[str, Any]:
        return run_agent_adopt(
            self._cfg,
            target=target,
            source_dir=source_dir,
            output_dir=output_dir,
            template=template,
            preseed_lockfile=preseed_lockfile,
            dry_run=dry_run,
            force=force,
        )

    def clean_lockfile(self, *, dry_run: bool = True) -> dict[str, Any]:
        return run_clean_lockfile(self._cfg, dry_run=dry_run)

    def ingest_preseed(self, *, source: str, dry_run: bool = True) -> dict[str, Any]:
        return run_ingest_preseed(self._cfg, source=source, dry_run=dry_run)
