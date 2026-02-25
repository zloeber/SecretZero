"""Agent-specific functionality for autonomous secret synchronization."""

import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from secretzero.lockfile import Lockfile
from secretzero.models import AgentInstructions, AutomationLevel, Secret, Secretfile
from secretzero.sync import SyncEngine

logger = logging.getLogger(__name__)

# Generator kinds that can be fully automated (no external input needed)
_AUTO_GENERATOR_KINDS = {"random_password", "random_string", "uuid"}


class AgentSyncResult(BaseModel):
    """Result of agent sync operation."""

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

    def sync(self) -> AgentSyncResult:
        """Perform agent-aware secret synchronization.

        Returns:
            AgentSyncResult with synced, pending, and failed secrets
        """
        result = AgentSyncResult()
        already_synced = []

        # Separate secrets into auto-syncable and manual
        auto_secrets = []
        for secret in self.secretfile.secrets:
            # Check if secret already exists in lockfile
            lockfile_entry = self.lockfile.get_secret_info(secret.name)
            if lockfile_entry:
                # Secret already exists in lockfile, skip it
                already_synced.append(secret.name)
                logger.debug("Secret '%s' already exists in lockfile, skipping", secret.name)
                continue

            if self._can_auto_sync(secret):
                auto_secrets.append(secret.name)
            else:
                if secret.agent_instructions:
                    result.pending_secrets[secret.name] = secret.agent_instructions
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
            )
            try:
                sync_results = engine.sync(dry_run=self.dry_run, secret_names=auto_secrets)
                result.sync_results = sync_results
                result.synced_secrets = auto_secrets
                logger.info("Synced %d secrets automatically", len(auto_secrets))
            except Exception as exc:
                for secret_name in auto_secrets:
                    result.failed_secrets[secret_name] = str(exc)
                logger.error("Failed to sync secrets: %s", exc)

        # Track already synced secrets
        result.already_synced = already_synced

        result.automation_summary = {
            "fully_synced": len(result.synced_secrets),
            "already_synced": len(result.already_synced),
            "requires_intervention": len(result.pending_secrets),
            "failed": len(result.failed_secrets),
        }
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

        # Static secrets need a value to be present
        if secret.kind == "static":
            value = secret.config.get("value")
            if value:
                return True
            return False

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
