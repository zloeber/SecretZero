"""GitLab group service account generator for SecretZero."""

from __future__ import annotations

from typing import Any

from secretzero.generators.base import BaseGenerator
from secretzero.models import AgentInstructions, AgentInstructionStep
from secretzero.providers.gitlab import GITLAB_PROJECT_TOKEN_SCOPES


class GitLabGroupServiceAccountGenerator(BaseGenerator):
    """Provision a GitLab group service account and PAT via the GitLab provider."""

    PROVIDER_CONFIG_KEY: str = "provider"
    PROVIDER_INJECTION_KEY: str = "_provider_instance"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self._provider_name: str = config.get("provider", "gitlab")

    def generate(self) -> dict[str, Any]:
        provider = self.config.get("_provider_instance")
        if provider is None:
            raise RuntimeError(
                "GitLabGroupServiceAccountGenerator requires a resolved provider instance. "
                f"Ensure provider '{self._provider_name}' is configured in the Secretfile."
            )

        manifest: dict[str, Any] = {
            k: v for k, v in self.config.items() if not k.startswith("_") and k != "provider"
        }
        for required in ("service_account_name", "token_name", "scopes"):
            if required not in manifest:
                raise ValueError(f"gitlab_group_service_account requires config.{required}")

        if manifest.get("rotate_existing") is None:
            manifest["rotate_existing"] = True

        return provider.provision_group_service_account_with_manifest(manifest)

    def validate_configuration(self) -> tuple[bool, str | None]:
        if not self.config.get("service_account_name"):
            return False, "service_account_name is required"
        if not self.config.get("token_name"):
            return False, "token_name is required"
        scopes = self.config.get("scopes")
        if not scopes or not isinstance(scopes, list):
            return False, "scopes must be a non-empty list"
        unknown = [scope for scope in scopes if scope not in GITLAB_PROJECT_TOKEN_SCOPES]
        if unknown:
            return False, f"Unknown scopes: {', '.join(unknown)}"
        return True, None

    def get_manual_instructions(self) -> AgentInstructions:
        if self.manual_instructions is not None:
            return self.manual_instructions

        sa_name = self.config.get("service_account_name", "secretzero-bot")
        token_name = self.config.get("token_name", "secretzero-token")

        return AgentInstructions(
            summary=(
                "Automatic GitLab group service account provisioning failed. "
                "Create the service account and PAT manually in GitLab."
            ),
            steps=[
                AgentInstructionStep(
                    action="Open GitLab → Top-level group → Settings → Service accounts",
                    description="Service accounts require a top-level group",
                ),
                AgentInstructionStep(
                    action=f"Create service account '{sa_name}'",
                    description="Use a descriptive automation identity name",
                ),
                AgentInstructionStep(
                    action=f"Create a PAT named '{token_name}' for the service account",
                    description="Copy the token immediately; GitLab shows it once",
                ),
            ],
            prerequisites=[
                "Owner access to the top-level GitLab group",
                "Bootstrap personal access token with api scope for SecretZero",
            ],
            estimated_time="10 minutes",
            automation_hint=(
                "Configure providers.gitlab with GITLAB_TOKEN and use "
                "kind: gitlab_group_service_account with group: auto."
            ),
            documentation_url="https://docs.gitlab.com/user/profile/service_accounts/",
        )
