"""Generator for Entra Agent ID blueprint orchestration."""

from __future__ import annotations

import json
from typing import Any

from secretzero.generators.base import BaseGenerator
from secretzero.models import AgentInstructions, AgentInstructionStep
from secretzero.providers.entra_agent_id import EntraAgentIdProvider


class EntraAgentBlueprintGenerator(BaseGenerator):
    """Generate/manage Entra Agent ID blueprints via provider operations."""

    PROVIDER_CONFIG_KEY = "provider"
    PROVIDER_INJECTION_KEY = "_provider_instance"

    def generate(self) -> str:
        """Create/update blueprint and return metadata JSON."""
        provider = self.config.get(self.PROVIDER_INJECTION_KEY)
        if not isinstance(provider, EntraAgentIdProvider):
            raise ValueError(
                "entra-agent-blueprint generator requires provider injection; "
                "set config.provider to an Entra Agent ID provider alias"
            )
        secret_name = str(self.config.get("secret_name", "entra-agent-blueprint"))
        spec = dict(self.config.get("spec", {}))
        if not spec:
            raise ValueError("entra-agent-blueprint generator requires config.spec")
        result = provider.store_blueprint(secret_name, spec)
        return json.dumps(result, separators=(",", ":"), sort_keys=True)

    def get_manual_instructions(self) -> AgentInstructions:
        """Manual fallback steps for sponsor/approval-driven operations."""
        if self.manual_instructions is not None:
            return self.manual_instructions
        return AgentInstructions(
            summary=(
                "Automatic Entra Agent ID blueprint sync requires sponsor approval or missing "
                "Graph permissions. Complete the approval path and re-run sync."
            ),
            prerequisites=[
                "Microsoft Graph app registration with required AgentIdentityBlueprint permissions",
                "Directory role permitting application and service principal changes",
            ],
            steps=[
                AgentInstructionStep(
                    action="Open Microsoft Entra admin center and review pending approvals",
                    description="Approve the blueprint sponsor/owner actions for this environment",
                ),
                AgentInstructionStep(
                    action="Verify app registration has required Graph permissions and consent",
                    description=(
                        "Confirm AgentIdentityBlueprint.Create, "
                        "AgentIdentityBlueprint.AddRemoveCreds.All, "
                        "AgentIdentityBlueprint.UpdateAuthProperties.All, "
                        "Application.ReadWrite.All, and Directory.ReadWrite.All"
                    ),
                ),
                AgentInstructionStep(
                    action="Re-run `secretzero agent sync --json`",
                    description="Validate no pending or failed blueprint operations remain",
                ),
            ],
            required_tools=["entra admin center", "secretzero"],
            documentation_url="https://learn.microsoft.com/graph/api/resources/agentidentityblueprint",
        )
