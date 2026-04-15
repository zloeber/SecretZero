"""Agent-specific functionality for autonomous secret synchronization."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from secretzero.lockfile import Lockfile
from secretzero.models import AgentInstructions, AutomationLevel, Secret, Secretfile
from secretzero.sync import SyncEngine

logger = logging.getLogger(__name__)

# Generator kinds that can be fully automated (no external input needed)
_AUTO_GENERATOR_KINDS = {"random_password", "random_string", "uuid"}

_SZ_AGENT_MANUAL_FAIL = (
    "Manual intervention required while SZ_AGENT is enabled; unset SZ_AGENT or resolve secrets "
    "outside the agent workflow"
)


class AgentSyncResult(BaseModel):
    """Result of agent sync operation."""

    status: str = Field(
        default="complete",
        description="complete | pending_manual | failed | partial",
    )
    synced_secrets: list[str] = Field(
        default_factory=list, description="Successfully synced secrets"
    )
    already_synced: list[str] = Field(
        default_factory=list, description="Secrets already in lockfile (skipped)"
    )
    pending_secrets: dict[str, AgentInstructions] = Field(
        default_factory=dict,
        description="Secrets requiring manual intervention with instructions",
    )
    failed_secrets: dict[str, str] = Field(
        default_factory=dict, description="Secrets that failed to sync"
    )
    automation_summary: dict[str, int] = Field(
        default_factory=dict, description="Count by automation level"
    )
    sync_results: dict[str, Any] = Field(
        default_factory=dict, description="Detailed sync results from SyncEngine"
    )


def env_sz_agent() -> bool:
    """True when ``SZ_AGENT`` requests non-interactive automation semantics."""
    return os.environ.get("SZ_AGENT", "").strip().lower() in ("1", "true", "yes", "on")


def resolve_resolved_mode_label(
    secretfile: Secretfile,
    *,
    cli_web: bool,
    sz_agent: bool,
) -> str:
    """Human-readable mode label for JSON (CLI flags + manifest + env)."""
    if sz_agent:
        return "auto"
    if cli_web:
        return "web"
    return secretfile.effective_agent_config().mode.value


def build_agent_sync_json_payload(
    result: AgentSyncResult,
    *,
    dry_run: bool,
    sz_agent: bool,
    resolved_mode: str,
    web_url: str | None = None,
    web_session_id: str | None = None,
) -> dict[str, Any]:
    """Shape CLI/API JSON output (no secret values)."""
    return {
        "status": result.status,
        "synced_secrets": result.synced_secrets,
        "already_synced": result.already_synced,
        "pending_secrets": {
            k: v.model_dump(exclude_none=True) for k, v in result.pending_secrets.items()
        },
        "failed_secrets": result.failed_secrets,
        "automation_summary": result.automation_summary,
        "sync_results": result.sync_results,
        "dry_run": dry_run,
        "sz_agent": sz_agent,
        "resolved_mode": resolved_mode,
        "web_url": web_url,
        "web_session_id": web_session_id,
    }


def _finalize_status(result: AgentSyncResult) -> None:
    """Set ``result.status`` from pending/failed counts."""
    if result.failed_secrets and result.pending_secrets:
        result.status = "partial"
    elif result.failed_secrets:
        result.status = "failed"
    elif result.pending_secrets:
        result.status = "pending_manual"
    else:
        result.status = "complete"


class AgentSecretSynchronizer:
    """Synchronizer with agent-specific intelligence."""

    def __init__(
        self,
        secretfile: Secretfile,
        lockfile: Lockfile,
        dry_run: bool = False,
        secretfile_path: Path | None = None,
        secretfile_content: str | None = None,
    ) -> None:
        """Initialize synchronizer.

        Args:
            secretfile: Loaded Secretfile configuration
            lockfile: Lockfile for tracking secret state
            dry_run: If True, preview changes without applying
            secretfile_path: Path to Secretfile for change detection
            secretfile_content: Content of Secretfile for change detection
        """
        self.secretfile = secretfile
        self.lockfile = lockfile
        self.dry_run = dry_run
        self.secretfile_path = secretfile_path
        self.secretfile_content = secretfile_content

    def sync(self, *, sz_agent: bool = False, refresh: bool = True) -> AgentSyncResult:
        """Perform agent-aware secret synchronization.

        Args:
            sz_agent: When True, secrets that would require manual follow-up are reported in
                ``failed_secrets`` instead of ``pending_secrets`` (Vector 3 / automation-only).

        Returns:
            AgentSyncResult with synced, pending, and failed secrets
        """
        result = AgentSyncResult()
        already_synced: list[str] = []
        mismatched_secrets: set[str] = set()

        if refresh:
            refresh_engine = SyncEngine(
                self.secretfile,
                self.lockfile,
                secretfile_path=self.secretfile_path,
                secretfile_content=self.secretfile_content,
                hide_input=True,
                prompt_on_empty=False,
                sync_client="agent",
            )
            refresh_report = refresh_engine.refresh_lockfile_targets(dry_run=self.dry_run)
            result.sync_results["refresh"] = refresh_report
            mismatched_secrets = {row["secret"] for row in refresh_report.get("rows", [])}

        # Separate secrets into auto-syncable and manual
        auto_secrets: list[str] = []
        for secret in self.secretfile.secrets:
            # Check if secret already exists in lockfile
            lockfile_entry = self.lockfile.get_secret_info(secret.name)
            if lockfile_entry and secret.name not in mismatched_secrets:
                # Secret already exists in lockfile, skip it
                already_synced.append(secret.name)
                logger.debug("Secret '%s' already exists in lockfile, skipping", secret.name)
                continue

            if self._can_auto_sync(secret):
                auto_secrets.append(secret.name)
            else:
                if secret.agent_instructions:
                    rendered = secret.agent_instructions.render_for_secret(
                        variables=self.secretfile.variables,
                        secret_name=secret.name,
                        secret=secret,
                    )
                    result.pending_secrets[secret.name] = rendered
                    logger.info("Secret '%s' requires manual intervention", secret.name)
                else:
                    result.failed_secrets[secret.name] = (
                        "Secret requires manual input but no agent_instructions provided"
                    )
                    logger.warning(
                        "Secret '%s' cannot be auto-synced and has no agent instructions",
                        secret.name,
                    )

        # Use SyncEngine to sync auto-syncable secrets
        if auto_secrets:
            engine = SyncEngine(
                self.secretfile,
                self.lockfile,
                secretfile_path=self.secretfile_path,
                secretfile_content=self.secretfile_content,
                hide_input=True,
                prompt_on_empty=False,
                sync_client="agent",
            )
            try:
                sync_results = engine.sync(
                    dry_run=self.dry_run,
                    secret_names=auto_secrets,
                    refresh=refresh,
                )
                if result.sync_results:
                    result.sync_results.update(sync_results)
                else:
                    result.sync_results = sync_results
                result.synced_secrets = auto_secrets
                logger.info("Synced %d secrets automatically", len(auto_secrets))
            except Exception as exc:
                for secret_name in auto_secrets:
                    result.failed_secrets[secret_name] = str(exc)
                logger.error("Failed to sync secrets: %s", exc)

        # Track already synced secrets
        result.already_synced = already_synced

        if sz_agent:
            for name in list(result.pending_secrets.keys()):
                result.failed_secrets[name] = _SZ_AGENT_MANUAL_FAIL
                del result.pending_secrets[name]

        result.automation_summary = {
            "fully_synced": len(result.synced_secrets),
            "already_synced": len(result.already_synced),
            "requires_intervention": len(result.pending_secrets),
            "failed": len(result.failed_secrets),
        }
        _finalize_status(result)
        return result

    def _can_auto_sync(self, secret: Secret) -> bool:
        """Determine if a secret can be automatically synced.

        Args:
            secret: Secret configuration

        Returns:
            True if the secret can be generated without external input
        """
        # Auto-generating kinds require no external input
        if secret.kind in _AUTO_GENERATOR_KINDS:
            return True

        # Static-like secrets: auto-sync only when no interactive fill is required
        from secretzero.generators.static import static_payload_needs_prompt
        from secretzero.generators.traits import secret_prompts_like_static

        if secret_prompts_like_static(secret):
            if "default" in secret.config:
                value = secret.config["default"]
            else:
                value = secret.config.get("value")
            return not static_payload_needs_prompt(value, nested=False)

        # Script / api generators may succeed — attempt them
        if secret.kind in {"script", "api"}:
            return True

        return False


def detect_automation_level(secret: Secret) -> AutomationLevel:
    """Detect the automation level for a secret based on its configuration.

    Args:
        secret: Secret configuration to analyse

    Returns:
        The automation level for this secret
    """
    if not secret.agent_instructions:
        if secret.kind in _AUTO_GENERATOR_KINDS:
            return AutomationLevel.FULLY_AUTOMATED
        return AutomationLevel.MANUAL_ONLY

    hint = secret.agent_instructions.automation_hint or ""
    hint_lower = hint.lower()

    if "fully automat" in hint_lower:
        return AutomationLevel.FULLY_AUTOMATED
    if "cannot be" in hint_lower or "manual only" in hint_lower or "manual" in hint_lower:
        return AutomationLevel.MANUAL_ONLY
    if "approval" in hint_lower:
        return AutomationLevel.REQUIRES_APPROVAL

    return AutomationLevel.SEMI_AUTOMATED


def format_instructions_as_dict(instructions: AgentInstructions) -> dict[str, Any]:
    """Return a plain dictionary representation suitable for JSON output.

    Args:
        instructions: Agent instructions to convert

    Returns:
        Dictionary with all non-None fields populated
    """
    return instructions.model_dump(exclude_none=True)
