"""Agent sync and instructions helpers for MCP backends."""

from __future__ import annotations

from typing import Any

from secretzero.agent import (
    AgentSecretSynchronizer,
    build_agent_sync_json_payload,
    env_sz_agent,
    resolve_resolved_mode_label,
)
from secretzero.agent_instructions_report import (
    InstructionScope,
    build_instructions_json_payload,
    collect_instruction_entries,
)
from secretzero.agent_webui import start_web_session_server, web_session_registry
from secretzero.mcp.config import McpConfig
from secretzero.mcp.workspace import load_workspace
from secretzero.models import AgentMode


def _resolve_sz_agent(cfg: McpConfig, override: bool | None = None) -> bool:
    if override is not None:
        return override
    return cfg.sz_agent or env_sz_agent()


def run_agent_sync(
    cfg: McpConfig,
    *,
    dry_run: bool = False,
    refresh: bool = True,
    web: bool = False,
    sz_agent: bool | None = None,
) -> dict[str, Any]:
    """Run unified agent sync and return metadata-only JSON payload."""
    ws = load_workspace(cfg)
    sz_eff = _resolve_sz_agent(cfg, sz_agent)
    agent_cfg = ws.secretfile.effective_agent_config()
    use_web = (web or agent_cfg.mode == AgentMode.WEB) and not sz_eff

    synchronizer = AgentSecretSynchronizer(
        ws.secretfile,
        ws.lockfile,
        dry_run=dry_run,
        secretfile_path=ws.secretfile_path,
        secretfile_content=ws.secretfile_content,
    )
    result = synchronizer.sync(sz_agent=sz_eff, refresh=refresh)
    resolved = resolve_resolved_mode_label(ws.secretfile, cli_web=web, sz_agent=sz_eff)
    payload = build_agent_sync_json_payload(
        result,
        dry_run=dry_run,
        sz_agent=sz_eff,
        resolved_mode=resolved,
    )
    payload["selected_environment"] = ws.env_ctx.selected_environment
    payload["resolved_var_files"] = [str(p) for p in ws.env_ctx.resolved_var_files]
    payload["resolved_lockfile"] = str(ws.lockfile_path)
    payload["resolved_target_profile"] = ws.env_ctx.resolved_target_profile

    if use_web and result.pending_secrets and not dry_run:
        payload["status"] = "awaiting_web_input"
        payload["web_hint"] = (
            "Call agent_sync_web_start to obtain a localhost form URL for pending secrets."
        )

    if not dry_run:
        ws.lockfile.save(ws.lockfile_path)

    return payload


def run_agent_sync_web_start(
    cfg: McpConfig,
    *,
    dry_run: bool = False,
    refresh: bool = True,
) -> dict[str, Any]:
    """Run agent sync and start a non-blocking Vector 2 localhost web session."""
    ws = load_workspace(cfg)
    sz_eff = _resolve_sz_agent(cfg, None)
    synchronizer = AgentSecretSynchronizer(
        ws.secretfile,
        ws.lockfile,
        dry_run=dry_run,
        secretfile_path=ws.secretfile_path,
        secretfile_content=ws.secretfile_content,
    )
    result = synchronizer.sync(sz_agent=sz_eff, refresh=refresh)

    if not result.pending_secrets:
        resolved = resolve_resolved_mode_label(ws.secretfile, cli_web=True, sz_agent=sz_eff)
        payload = build_agent_sync_json_payload(
            result,
            dry_run=dry_run,
            sz_agent=sz_eff,
            resolved_mode=resolved,
        )
        payload["message"] = "No pending secrets require web input"
        if not dry_run:
            ws.lockfile.save(ws.lockfile_path)
        return payload

    if dry_run:
        return {
            "status": "dry_run",
            "pending_secret_names": list(result.pending_secrets.keys()),
            "message": "Web session not started under dry_run",
        }

    agent_cfg = ws.secretfile.effective_agent_config()
    sess = web_session_registry.create(list(result.pending_secrets.keys()))
    url, _port = start_web_session_server(
        session_id=sess.session_id,
        pending_secret_names=list(result.pending_secrets.keys()),
        secretfile=ws.secretfile,
        lockfile=ws.lockfile,
        lockfile_path=ws.lockfile_path,
        secretfile_path=ws.secretfile_path,
        secretfile_content=ws.secretfile_content,
        dry_run=False,
        port_min=agent_cfg.web_port_min,
        port_max=agent_cfg.web_port_max,
        registry=web_session_registry,
    )
    ws.lockfile.save(ws.lockfile_path)
    return {
        "status": "awaiting_web_input",
        "web_url": url,
        "web_session_id": sess.session_id,
        "pending_secret_names": list(result.pending_secrets.keys()),
    }


def run_agent_sync_web_poll(session_id: str) -> dict[str, Any]:
    """Poll Vector 2 web session completion (no secret values)."""
    sess = web_session_registry.get(session_id)
    if sess is None:
        raise ValueError(f"Unknown web session: {session_id}")
    return {
        "session_id": session_id,
        "done": sess.done,
        "error": sess.error,
        "result": sess.result_payload,
    }


def run_agent_instructions(
    cfg: McpConfig,
    *,
    show_all: bool = False,
    detailed: bool = False,
    secret_names: list[str] | None = None,
) -> dict[str, Any]:
    """Return agent instruction steps for pending or all configured secrets."""
    ws = load_workspace(cfg)
    scope = InstructionScope.ALL if show_all else InstructionScope.PENDING
    name_filter = frozenset(secret_names) if secret_names else None
    entries = collect_instruction_entries(
        ws.secretfile,
        ws.lockfile,
        scope=scope,
        secret_names=name_filter,
    )
    return build_instructions_json_payload(entries, scope=scope, detailed=detailed)
