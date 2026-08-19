"""GitLab group access token generator for SecretZero."""

from __future__ import annotations

from typing import Any

from secretzero.generators.base import BaseGenerator
from secretzero.models import AgentInstructions, AgentInstructionStep
from secretzero.providers.gitlab import GITLAB_PROJECT_TOKEN_SCOPES


class GitLabGroupTokenGenerator(BaseGenerator):
    """Generate scoped GitLab group access tokens via the GitLab provider."""

    PROVIDER_CONFIG_KEY: str = "provider"
    PROVIDER_INJECTION_KEY: str = "_provider_instance"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self._provider_name: str = config.get("provider", "gitlab")

    def generate(self) -> str:
        provider = self.config.get("_provider_instance")
        if provider is None:
            raise RuntimeError(
                f"GitLabGroupTokenGenerator requires a resolved provider instance. "
                f"Ensure provider '{self._provider_name}' is configured in the Secretfile."
            )

        manifest: dict[str, Any] = {
            k: v for k, v in self.config.items() if not k.startswith("_") and k != "provider"
        }
        if "token_name" not in manifest:
            raise ValueError("gitlab_group_token requires config.token_name")
        if "scopes" not in manifest:
            raise ValueError("gitlab_group_token requires config.scopes")

        if manifest.get("revoke_existing") is None:
            manifest["revoke_existing"] = True

        return provider.generate_group_access_token_with_manifest(manifest)

    def validate_configuration(self) -> tuple[bool, str | None]:
        token_name = self.config.get("token_name")
        if not token_name:
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

        token_name = self.config.get("token_name", "secretzero-token")
        scopes = self.config.get("scopes", ["api"])
        group = self.config.get("group", "auto")

        return AgentInstructions(
            summary=(
                "Automatic GitLab group access token generation failed. "
                "Create a group access token manually in GitLab."
            ),
            steps=[
                AgentInstructionStep(
                    action="Open GitLab → Group → Settings → Access Tokens",
                    description="Navigate to group access token settings",
                ),
                AgentInstructionStep(
                    action=f"Select group '{group}' (or resolve from project namespace)",
                    description="Group access tokens require Owner role on the group",
                ),
                AgentInstructionStep(
                    action=f"Set token name to '{token_name}'",
                    description="Use a descriptive token name",
                ),
                AgentInstructionStep(
                    action=f"Select scopes: {', '.join(scopes)}",
                    description="Grant only the required scopes",
                ),
                AgentInstructionStep(
                    action="Create the token and copy the value immediately",
                    description="GitLab shows the token only once",
                ),
            ],
            prerequisites=[
                "Owner access to the GitLab group",
                "A personal access token with api scope for SecretZero bootstrap auth",
            ],
            estimated_time="5 minutes",
            automation_hint=(
                "Configure providers.gitlab with a personal access token (GITLAB_TOKEN) "
                "and use kind: gitlab_group_token with group: auto."
            ),
            documentation_url="https://docs.gitlab.com/user/group/settings/group_access_tokens/",
        )
