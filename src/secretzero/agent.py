"""Agent-specific functionality for autonomous secret synchronization."""

import logging
from typing import Any

from pydantic import BaseModel, Field

from secretzero.models import AgentInstructions, AutomationLevel, Secret, Secretfile

logger = logging.getLogger(__name__)

# Generator kinds that can be fully automated (no external input needed)
_AUTO_GENERATOR_KINDS = {"random_password", "random_string", "uuid"}


class AgentSyncResult(BaseModel):
    """Result of agent sync operation."""

    synced_secrets: list[str] = Field(
        default_factory=list, description="Successfully synced secrets"
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


class AgentSecretSynchronizer:
    """Synchronizer with agent-specific intelligence."""

    def __init__(self, secretfile: Secretfile, dry_run: bool = False) -> None:
        """Initialize synchronizer.

        Args:
            secretfile: Loaded Secretfile configuration
            dry_run: If True, preview changes without applying
        """
        self.secretfile = secretfile
        self.dry_run = dry_run

    def sync(self) -> AgentSyncResult:
        """Perform agent-aware secret synchronization.

        Returns:
            AgentSyncResult with synced, pending, and failed secrets
        """
        result = AgentSyncResult()

        for secret in self.secretfile.secrets:
            try:
                if self._can_auto_sync(secret):
                    if not self.dry_run:
                        self._sync_secret(secret)
                    result.synced_secrets.append(secret.name)
                    logger.info("Secret '%s' synced automatically", secret.name)
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
            except Exception as exc:
                result.failed_secrets[secret.name] = str(exc)
                logger.error("Failed to sync '%s': %s", secret.name, exc)

        result.automation_summary = {
            "fully_synced": len(result.synced_secrets),
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

    def _sync_secret(self, secret: Secret) -> None:
        """Perform actual secret synchronization using the SyncEngine.

        Args:
            secret: Secret to sync
        """
        from secretzero.lockfile import Lockfile
        from secretzero.sync import SyncEngine

        lockfile = Lockfile()
        engine = SyncEngine(
            secretfile=self.secretfile,
            lockfile=lockfile,
            hide_input=True,
            prompt_on_empty=False,
        )
        engine._sync_secret(secret)  # type: ignore[attr-defined]


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
