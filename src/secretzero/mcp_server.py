"""SecretZero MCP server — agent-safe orchestration tools over stdio.

Exposes sync, discover, status, rotate, and drift_check with strict parity to
the CLI/API surfaces. Operates with ``SZ_AGENT_MODE`` spill guards by default
and never returns plaintext secret values.
"""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from secretzero.agent_context import env_sz_agent_mode, spill_guard_active
from secretzero.config import ConfigLoader
from secretzero.drift import DriftDetector
from secretzero.environment_resolution import apply_target_profile, resolve_environment_context
from secretzero.lockfile import Lockfile
from secretzero.lockfile_state import sync_state_for_secret_target, target_id
from secretzero.models import Secretfile
from secretzero.provider_identity import collect_provider_identity_rows
from secretzero.rotation import should_rotate_secret
from secretzero.sync import SyncEngine

# ---------------------------------------------------------------------------
# Spill-safe response keys — never emit these from MCP tools
# ---------------------------------------------------------------------------

_FORBIDDEN_RESPONSE_KEYS = frozenset(
    {
        "value",
        "values",
        "raw_value",
        "secret_value",
        "plaintext",
        "reveal",
    }
)

_REVEAL_PARAM_NAMES = frozenset({"reveal", "show_secrets", "include_values", "print_values"})

# ---------------------------------------------------------------------------
# Tool descriptions (aligned with AGENTS.md / skills)
# ---------------------------------------------------------------------------

_SZ_SYNC_DESC = (
    "Reconcile Secretfile.yml with configured targets via SyncEngine. "
    "Returns metadata-only results (counts, target statuses, errors). "
    "Never returns plaintext secret values. Supports multi-environment profiles "
    "via environment and var_files. Non-interactive: prompts are disabled."
)

_SZ_DISCOVER_DESC = (
    "AI-powered secret discovery for a workspace directory. "
    "Uses local Ollama by default (privacy-first). Returns candidate names, "
    "paths, confidence scores, and suggested generators — never secret values. "
    "Do not use host-LLM filesystem reads instead of this tool."
)

_SZ_STATUS_DESC = (
    "Return lockfile metadata for the workspace: SHA-256 hashes, rotation "
    "history, per-target sync state, Secretfile tracking, and provider identity. "
    "Metadata only — no plaintext values."
)

_SZ_ROTATE_DESC = (
    "Force-trigger rotation policy for secrets with rotation_period configured. "
    "Regenerates and re-syncs eligible secrets. Returns rotation counts and "
    "errors only — never secret values."
)

_SZ_DRIFT_CHECK_DESC = (
    "Detect drift between .gitsecrets.lock and live external targets. "
    "Reports which secrets diverged and why. Metadata only."
)


@dataclass(frozen=True)
class McpPaths:
    """Resolved filesystem paths for one MCP invocation."""

    workspace: Path
    secretfile: Path
    lockfile: Path
    var_files: list[Path]
    environment: str | None
    target_profile: str | None


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def ensure_agent_mode() -> None:
    """Enable spill-safe semantics for MCP unless explicitly disabled."""
    if os.environ.get("SZ_AGENT_MODE") is None:
        os.environ["SZ_AGENT_MODE"] = "true"


def _resolve_workspace(explicit: str | None = None) -> Path:
    raw = explicit or os.environ.get("SZ_WORKSPACE") or os.environ.get("SECRETZERO_WORKSPACE")
    if raw:
        path = Path(raw).expanduser().resolve()
        if not path.is_dir():
            raise ValueError(f"Workspace directory does not exist: {path}")
        return path
    return Path.cwd().resolve()


def _default_secretfile_path(workspace: Path) -> Path:
    cfg = os.environ.get("SECRETZERO_CONFIG", "Secretfile.yml")
    path = Path(cfg)
    if not path.is_absolute():
        path = workspace / path
    return path.resolve()


@contextmanager
def workspace_context(workspace: Path) -> Iterator[None]:
    """Temporarily chdir to the resolved workspace."""
    previous = Path.cwd()
    os.chdir(workspace)
    try:
        yield
    finally:
        os.chdir(previous)


def _reject_reveal_params(**params: Any) -> None:
    for key, value in params.items():
        if key.lower() in _REVEAL_PARAM_NAMES and _truthy_env_value(value):
            raise ValueError(
                f"Parameter '{key}' is blocked: MCP tools must not reveal plaintext secrets."
            )


def _truthy_env_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _enforce_sandbox_sync() -> None:
    """Optional guard when SZ_SANDBOX is set — sync may write to targets."""
    if _truthy_env("SZ_SANDBOX") and not _truthy_env("SZ_ALLOW_SYNC_IN_SANDBOX"):
        raise ValueError(
            "sz_sync is blocked in sandbox mode (SZ_SANDBOX=true). "
            "Set SZ_ALLOW_SYNC_IN_SANDBOX=true to override intentionally."
        )


def resolve_mcp_paths(
    *,
    workspace: str | None = None,
    secretfile: str | None = None,
    lockfile: str | None = None,
    environment: str | None = None,
    var_files: list[str] | None = None,
) -> McpPaths:
    """Resolve workspace-aware paths with environment profile support."""
    ws = _resolve_workspace(workspace)
    sf_path = Path(secretfile) if secretfile else _default_secretfile_path(ws)
    if not sf_path.is_absolute():
        sf_path = (ws / sf_path).resolve()

    runtime_var_files = [Path(vf) for vf in (var_files or [])]
    runtime_lockfile = lockfile if lockfile and lockfile != ".gitsecrets.lock" else None

    loader = ConfigLoader()
    base = loader.load_file(sf_path)
    env_ctx = resolve_environment_context(
        secretfile=base,
        secretfile_path=sf_path,
        environment=environment,
        runtime_var_files=runtime_var_files or None,
        runtime_lockfile=runtime_lockfile,
    )
    return McpPaths(
        workspace=ws,
        secretfile=sf_path,
        lockfile=env_ctx.resolved_lockfile,
        var_files=list(env_ctx.resolved_var_files),
        environment=env_ctx.selected_environment,
        target_profile=env_ctx.resolved_target_profile,
    )


def _load_secretfile(paths: McpPaths) -> tuple[Secretfile, str]:
    loader = ConfigLoader()
    config = loader.load_file(paths.secretfile, var_files=paths.var_files or None)
    config = apply_target_profile(config, paths.target_profile)
    content = paths.secretfile.read_text(encoding="utf-8")
    return config, content


def _build_sync_engine(
    paths: McpPaths,
    config: Secretfile,
    lock: Lockfile,
    secretfile_content: str,
) -> SyncEngine:
    return SyncEngine(
        config,
        lock,
        secretfile_path=paths.secretfile,
        secretfile_content=secretfile_content,
        hide_input=True,
        prompt_on_empty=False,
        sync_client="mcp",
    )


def _sanitize_payload(obj: Any) -> Any:
    """Recursively strip forbidden keys from tool responses."""
    if isinstance(obj, dict):
        cleaned: dict[str, Any] = {}
        for key, value in obj.items():
            if key in _FORBIDDEN_RESPONSE_KEYS:
                continue
            cleaned[key] = _sanitize_payload(value)
        return cleaned
    if isinstance(obj, list):
        return [_sanitize_payload(item) for item in obj]
    return obj


def _build_status_payload(
    paths: McpPaths,
    config: Secretfile,
    lock: Lockfile,
    secretfile_content: str,
) -> dict[str, Any]:
    tracked_secretfile = lock.get_secretfile_info()
    current_hash = Lockfile._hash_value(secretfile_content)
    secretfile_changed = None
    if tracked_secretfile:
        tracked_hash = tracked_secretfile.get("hash")
        tracked_filename = tracked_secretfile.get("filename")
        secretfile_changed = (
            tracked_filename != paths.secretfile.name or tracked_hash != current_hash
        )

    engine = _build_sync_engine(paths, config, lock, secretfile_content)
    sync_readiness = engine.preflight_sync_readiness()

    secrets_data: list[dict[str, Any]] = []
    for secret in config.secrets:
        entry = lock.get_secret_info(secret.name)
        targets_meta: list[dict[str, Any]] = []
        for target in secret.targets:
            tid = target_id(target)
            locked_hash = None
            if entry and entry.targets:
                locked_hash = entry.targets.get(tid)
            state = sync_state_for_secret_target(
                lock,
                secret.name,
                target,
                secret=secret,
                secretfile=config,
                secretfile_path=paths.secretfile,
                secretfile_content=secretfile_content,
            )
            targets_meta.append(
                {
                    "target_id": tid,
                    "provider": target.provider,
                    "kind": str(target.kind),
                    "sync_state": state,
                    "hash": locked_hash,
                }
            )

        secret_info: dict[str, Any] = {
            "name": secret.name,
            "kind": str(secret.kind),
            "one_time": secret.one_time,
            "rotation_period": secret.rotation_period,
            "status": "synced" if entry else "not_synced",
            "targets": targets_meta,
        }
        if entry:
            secret_info["hash"] = entry.hash
            secret_info["definition_hash"] = entry.definition_hash
            secret_info["created_at"] = entry.created_at
            secret_info["updated_at"] = entry.updated_at
            if entry.last_rotated:
                secret_info["last_rotated"] = entry.last_rotated
                secret_info["rotation_count"] = entry.rotation_count
            secret_info["target_hashes"] = dict(entry.targets)
        secrets_data.append(secret_info)

    return _sanitize_payload(
        {
            "agent_mode": env_sz_agent_mode(),
            "spill_guard_active": spill_guard_active(),
            "workspace": str(paths.workspace),
            "environment": paths.environment,
            "target_profile": paths.target_profile,
            "resolved_var_files": [str(p) for p in paths.var_files],
            "secrets": secrets_data,
            "total": len(config.secrets),
            "synced": sum(1 for s in secrets_data if s["status"] == "synced"),
            "lockfile": str(paths.lockfile),
            "lockfile_exists": paths.lockfile.exists(),
            "provider_identity": collect_provider_identity_rows(config),
            "secretfile": {
                "path": str(paths.secretfile),
                "current_hash": current_hash,
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
            "lockfile_metadata": lock.metadata,
        }
    )


def _discover_candidates_payload(result: Any) -> list[dict[str, Any]]:
    """Build metadata-only discovery candidates (strip raw values)."""
    candidates: list[dict[str, Any]] = []
    for candidate in result.candidates:
        candidates.append(
            {
                "name": candidate.name,
                "description": candidate.description,
                "confidence": candidate.confidence,
                "generator": candidate.suggested_generator,
                "source_file": candidate.source_file,
                "line": candidate.line_number,
                "tags": candidate.tags,
                "containing_symbol": candidate.containing_symbol,
                "symbol_fqn": candidate.symbol_fqn,
                "symbol_id": candidate.symbol_id,
            }
        )
    return candidates


def generate_mcp_config(
    *,
    workspace: Path | None = None,
    output_path: Path | None = None,
    command: str | None = None,
    format_name: str | None = None,
    secretfile_path: Path | None = None,
) -> dict[str, Any]:
    """Generate MCP client configuration for the current environment."""
    from secretzero.cli_config import McpConfig, get_effective_config

    effective = get_effective_config(secretfile_path=secretfile_path)
    mcp_cfg: McpConfig = effective.config.mcp

    ws_raw = workspace
    if ws_raw is None and mcp_cfg.workspace:
        ws_raw = Path(mcp_cfg.workspace)
    ws = (ws_raw or _resolve_workspace()).resolve()

    fmt = format_name or mcp_cfg.client_format
    exe = command or mcp_cfg.command or shutil.which("secretzero") or "secretzero"
    serve_args = list(mcp_cfg.serve_args or ["mcp", "serve"])

    env_block: dict[str, str] = {"SZ_WORKSPACE": str(ws)}
    if mcp_cfg.sz_agent_mode:
        env_block["SZ_AGENT_MODE"] = "true"
    if os.environ.get("SECRETZERO_CONFIG"):
        env_block["SECRETZERO_CONFIG"] = os.environ["SECRETZERO_CONFIG"]

    server_entry = {
        "command": exe,
        "args": serve_args,
        "env": env_block,
    }

    server_key = mcp_cfg.server_name or "secretzero"
    if fmt == "cursor":
        payload: dict[str, Any] = {
            "servers": {server_key: {**server_entry, "type": "stdio"}},
        }
    elif fmt == "claude":
        payload = {"mcpServers": {server_key: server_entry}}
    else:
        payload = {
            "secretzero_mcp": server_entry,
            "notes": {
                "cursor": "Use key 'servers' at .cursor/mcp.json",
                "claude_desktop": "Merge 'mcpServers' into claude_desktop_config.json",
                "cli": "Prefer `secretzero mcp config generate --format cursor|claude`",
                "sz_agent_mode": "true when config.mcp.sz_agent_mode is enabled",
            },
        }

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    return payload


def create_mcp_server() -> Any:
    """Build and return the FastMCP server instance."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise ImportError(
            "MCP SDK is not installed. Install with: pip install 'secretzero[mcp]'"
        ) from exc

    ensure_agent_mode()
    mcp = FastMCP(
        "SecretZero",
        instructions=(
            "SecretZero secrets-as-code orchestration. All tools return metadata only — "
            "never plaintext secret values. Use sz_sync to reconcile targets, sz_status "
            "for lockfile state, sz_discover for AI discovery, sz_rotate for rotation, "
            "and sz_drift_check for external drift. Set environment/var_files for "
            "multi-environment profiles."
        ),
        json_response=True,
    )

    @mcp.tool(name="sz_sync", description=_SZ_SYNC_DESC)
    def sz_sync(
        dry_run: bool = False,
        secrets: list[str] | None = None,
        environment: str | None = None,
        secretfile: str | None = None,
        lockfile: str | None = None,
        var_files: list[str] | None = None,
        workspace: str | None = None,
        refresh: bool = True,
        reveal: bool = False,
    ) -> dict[str, Any]:
        _reject_reveal_params(reveal=reveal)
        _enforce_sandbox_sync()
        paths = resolve_mcp_paths(
            workspace=workspace,
            secretfile=secretfile,
            lockfile=lockfile,
            environment=environment,
            var_files=var_files,
        )
        with workspace_context(paths.workspace):
            config, secretfile_content = _load_secretfile(paths)
            lock = Lockfile.load(paths.lockfile)
            engine = _build_sync_engine(paths, config, lock, secretfile_content)

            active_var_files = paths.var_files
            active_variables = dict(config.variables or {})
            variable_context_changed = False
            if active_var_files or active_variables:
                variable_context_changed = lock.variable_context_changed(
                    active_var_files, active_variables
                )

            results = engine.sync(
                dry_run=dry_run,
                secret_names=secrets,
                ignore_foreign_context_targets=variable_context_changed,
                refresh=refresh,
            )

            if not dry_run and (results["secrets_stored"] > 0 or results.get("secretfile_changed")):
                lock.track_variable_context(active_var_files, active_variables)
                lock.save(paths.lockfile)

            payload = _sanitize_payload(
                {
                    "dry_run": dry_run,
                    "secrets_stored": results["secrets_stored"],
                    "secrets_skipped": results["secrets_skipped"],
                    "secrets_generated": results["secrets_generated"],
                    "errors": results.get("errors", []),
                    "details": results.get("details", []),
                    "variable_context_changed": variable_context_changed,
                    "selected_environment": paths.environment,
                    "resolved_var_files": [str(p) for p in paths.var_files],
                    "resolved_lockfile": str(paths.lockfile),
                    "resolved_target_profile": paths.target_profile,
                    "refresh": results.get("refresh"),
                    "provider_identity": collect_provider_identity_rows(config),
                }
            )
            return payload

    @mcp.tool(name="sz_discover", description=_SZ_DISCOVER_DESC)
    def sz_discover(
        path: str | None = None,
        dry_run: bool = False,
        local_only: bool | None = None,
        provider: str | None = None,
        model: str | None = None,
        no_llm: bool = False,
        threshold: float | None = None,
        workspace: str | None = None,
        reveal: bool = False,
    ) -> dict[str, Any]:
        _reject_reveal_params(reveal=reveal)
        from secretzero.cli_config import get_effective_config
        from secretzero.discovery import DiscoveryAgent

        ws = _resolve_workspace(workspace)
        scan_root = Path(path) if path else ws
        if not scan_root.is_absolute():
            scan_root = (ws / scan_root).resolve()

        secretfile_path = scan_root / "Secretfile.yml"
        effective = get_effective_config(secretfile_path=secretfile_path)
        cli_cfg = effective.config
        mcp_cfg = cli_cfg.mcp
        if threshold is not None:
            cli_cfg.discovery.confidence_threshold = threshold

        local_only_eff = (
            local_only if local_only is not None else mcp_cfg.discover_local_only
        )
        provider_eff = provider if provider is not None else mcp_cfg.discover_provider

        agent = DiscoveryAgent(config=cli_cfg)
        with workspace_context(ws):
            result = agent.discover(
                project_root=str(scan_root),
                dry_run=dry_run,
                use_llm=not no_llm,
                local_only=local_only_eff,
                provider=provider_eff,
                model=model,
                verbose=False,
            )

        return _sanitize_payload(
            {
                "files_scanned": result.files_scanned,
                "total_secrets": result.total_secrets,
                "dry_run": result.dry_run,
                "output_path": str(result.output_path) if result.output_path else None,
                "llm_used": result.llm_provider is not None and not no_llm,
                "llm_provider": result.llm_provider,
                "llm_model": result.llm_model,
                "workspace": str(ws),
                "scan_root": str(scan_root),
                "secrets": _discover_candidates_payload(result),
            }
        )

    @mcp.tool(name="sz_status", description=_SZ_STATUS_DESC)
    def sz_status(
        environment: str | None = None,
        secretfile: str | None = None,
        lockfile: str | None = None,
        var_files: list[str] | None = None,
        workspace: str | None = None,
        reveal: bool = False,
    ) -> dict[str, Any]:
        _reject_reveal_params(reveal=reveal)
        paths = resolve_mcp_paths(
            workspace=workspace,
            secretfile=secretfile,
            lockfile=lockfile,
            environment=environment,
            var_files=var_files,
        )
        with workspace_context(paths.workspace):
            config, secretfile_content = _load_secretfile(paths)
            lock = Lockfile.load(paths.lockfile)
            return _build_status_payload(paths, config, lock, secretfile_content)

    @mcp.tool(name="sz_rotate", description=_SZ_ROTATE_DESC)
    def sz_rotate(
        secrets: list[str] | None = None,
        force: bool = False,
        dry_run: bool = False,
        environment: str | None = None,
        secretfile: str | None = None,
        lockfile: str | None = None,
        var_files: list[str] | None = None,
        workspace: str | None = None,
        reveal: bool = False,
    ) -> dict[str, Any]:
        _reject_reveal_params(reveal=reveal)
        _enforce_sandbox_sync()
        paths = resolve_mcp_paths(
            workspace=workspace,
            secretfile=secretfile,
            lockfile=lockfile,
            environment=environment,
            var_files=var_files,
        )
        with workspace_context(paths.workspace):
            config, secretfile_content = _load_secretfile(paths)
            lock = Lockfile.load(paths.lockfile)

            secrets_to_check = config.secrets
            if secrets:
                known = {s.name for s in config.secrets}
                missing = [n for n in secrets if n not in known]
                if missing:
                    raise ValueError(
                        f"Secret(s) not found in Secretfile: {', '.join(repr(n) for n in missing)}"
                    )
                order = {n: i for i, n in enumerate(secrets)}
                secrets_to_check = sorted(
                    [s for s in config.secrets if s.name in order],
                    key=lambda s: order[s.name],
                )

            secrets_to_rotate = []
            rotation_details: list[dict[str, Any]] = []
            for secret in secrets_to_check:
                if not secret.rotation_period:
                    continue
                entry = lock.get_secret_info(secret.name)
                if not entry:
                    continue
                if secret.one_time:
                    rotation_details.append(
                        {"name": secret.name, "status": "skipped", "reason": "one_time secret"}
                    )
                    continue
                should_rotate_flag, reason = should_rotate_secret(
                    secret.rotation_period,
                    entry.last_rotated,
                    entry.created_at,
                )
                if should_rotate_flag or force:
                    secrets_to_rotate.append(secret)
                    rotation_details.append(
                        {"name": secret.name, "status": "needs_rotation", "reason": reason}
                    )
                else:
                    rotation_details.append({"name": secret.name, "status": "ok", "reason": reason})

            if not secrets_to_rotate:
                return _sanitize_payload(
                    {
                        "dry_run": dry_run,
                        "secrets_rotated": 0,
                        "details": rotation_details,
                        "errors": [],
                    }
                )

            if dry_run:
                return _sanitize_payload(
                    {
                        "dry_run": True,
                        "secrets_rotated": 0,
                        "would_rotate": [s.name for s in secrets_to_rotate],
                        "details": rotation_details,
                        "errors": [],
                    }
                )

            engine = _build_sync_engine(paths, config, lock, secretfile_content)
            original_secrets = config.secrets
            config.secrets = secrets_to_rotate
            try:
                results = engine.sync(dry_run=False, force_rotation=True)
            finally:
                config.secrets = original_secrets

            lock.save(paths.lockfile)
            return _sanitize_payload(
                {
                    "dry_run": False,
                    "secrets_rotated": results.get("secrets_generated", 0),
                    "details": rotation_details,
                    "errors": results.get("errors", []),
                }
            )

    @mcp.tool(name="sz_drift_check", description=_SZ_DRIFT_CHECK_DESC)
    def sz_drift_check(
        secret_name: str | None = None,
        environment: str | None = None,
        secretfile: str | None = None,
        lockfile: str | None = None,
        var_files: list[str] | None = None,
        workspace: str | None = None,
        reveal: bool = False,
    ) -> dict[str, Any]:
        _reject_reveal_params(reveal=reveal)
        paths = resolve_mcp_paths(
            workspace=workspace,
            secretfile=secretfile,
            lockfile=lockfile,
            environment=environment,
            var_files=var_files,
        )
        with workspace_context(paths.workspace):
            if not paths.lockfile.exists():
                raise ValueError(f"Lockfile not found: {paths.lockfile}. Run sz_sync first.")

            detector = DriftDetector(
                paths.secretfile,
                paths.lockfile,
                environment=paths.environment,
            )
            results = detector.check_drift(secret_name)
            drift_found = any(r.has_drift for r in results)
            return _sanitize_payload(
                {
                    "drift_detected": drift_found,
                    "environment": paths.environment,
                    "lockfile": str(paths.lockfile),
                    "results": [
                        {
                            "secret_name": r.secret_name,
                            "has_drift": r.has_drift,
                            "message": r.message,
                            "details": r.details or {},
                        }
                        for r in results
                    ],
                }
            )

    return mcp


def run_stdio_server() -> None:
    """Start the MCP stdio server (blocks until the host disconnects)."""
    ensure_agent_mode()
    server = create_mcp_server()
    server.run(transport="stdio")


def run() -> None:
    """Backward-compatible entry point for ``secretzero-mcp``."""
    from secretzero.cli_mcp import run_legacy_entrypoint

    run_legacy_entrypoint()


if __name__ == "__main__":
    run()
