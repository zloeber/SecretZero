"""Azure DevOps PAT generator."""

from __future__ import annotations

from typing import Any

from secretzero.generators.base import BaseGenerator
from secretzero.models import AgentInstructions, AgentInstructionStep


class AzureDevOpsPATGenerator(BaseGenerator):
    """Generate Azure DevOps personal access tokens when org policy allows."""

    PROVIDER_CONFIG_KEY: str = "provider"
    PROVIDER_INJECTION_KEY: str = "_provider_instance"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self._provider_name: str = config.get("provider", "azdo")

    def generate(self) -> str:
        provider = self.config.get("_provider_instance")
        if provider is None:
            raise RuntimeError(
                "AzureDevOpsPATGenerator requires a resolved provider instance. "
                f"Ensure provider '{self._provider_name}' is configured in the Secretfile."
            )
        manifest = {
            k: v for k, v in self.config.items() if not k.startswith("_") and k != "provider"
        }
        if "display_name" not in manifest:
            raise ValueError("azdo_pat requires config.display_name")
        if "scopes" not in manifest:
            raise ValueError("azdo_pat requires config.scopes")
        if manifest.get("revoke_existing") is None:
            manifest["revoke_existing"] = True
        return provider.create_pat_with_manifest(manifest)

    def validate_configuration(self) -> tuple[bool, str | None]:
        if not self.config.get("display_name"):
            return False, "display_name is required"
        scopes = self.config.get("scopes")
        if not scopes or not isinstance(scopes, list):
            return False, "scopes must be a non-empty list"
        return True, None

    def get_manual_instructions(self) -> AgentInstructions:
        display_name = self.config.get("display_name", "secretzero-automation")
        return AgentInstructions(
            summary="Automatic Azure DevOps PAT creation failed. Create a PAT manually.",
            steps=[
                AgentInstructionStep(
                    action="Open Azure DevOps → User settings → Personal access tokens",
                    description="Create a new token",
                ),
                AgentInstructionStep(
                    action=f"Set name to '{display_name}'",
                    description="Use a descriptive automation token name",
                ),
                AgentInstructionStep(
                    action="Select required scopes for variable groups and pipelines",
                    description="Grant least privilege",
                ),
            ],
            prerequisites=["Permission to create PATs in the Azure DevOps organization"],
            estimated_time="5 minutes",
            automation_hint="Set AZDO_PAT and use kind: azdo_pat when token minting API is enabled.",
            documentation_url="https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate",
        )
