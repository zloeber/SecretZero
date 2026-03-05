"""GitHub PAT generator for SecretZero.

Thin generator that delegates to the GitHub provider's ``generate_pat``
capability.  All GitHub-specific logic (JWT minting, API calls, permission
validation) lives inside ``secretzero.providers.github`` so that
provider-specific code stays co-located.

Example Secretfile usage::

    secrets:
      - name: ci_deploy_token
        kind: github_pat
        config:
          provider: github          # references a configured provider
          permissions:
            contents: read
            pull_requests: write
            actions: read
          repositories:
            - my-repo
          token_name: ci-deploy
          expires_in_hours: 1
"""

from typing import Any

from secretzero.generators.base import BaseGenerator
from secretzero.models import AgentInstructions, AgentInstructionStep


class GitHubPATGenerator(BaseGenerator):
    """Generator that creates scoped GitHub App installation tokens.

    .. rubric:: Bundle provider injection protocol

    The sync engine inspects the following class attributes to determine how
    to inject the resolved provider instance before instantiating a generator:

    * ``PROVIDER_CONFIG_KEY`` – the key in ``config`` that holds the provider
      *name* (a string referencing a configured provider).
    * ``PROVIDER_INJECTION_KEY`` – the key under which the resolved provider
      *instance* will be injected into ``config``.

    Setting these attributes on a custom generator class is the standard way
    to declare that the generator requires a live provider instance.

    Configuration keys (passed via ``config`` dict):

    * **provider** – *reserved*: at runtime the sync engine injects the
      resolved :class:`~secretzero.providers.github.GitHubProvider` instance
      under the ``_provider_instance`` key.  When missing the generator
      raises at generation time.
    * **permissions** – ``dict[str, str]`` mapping permission scope to
      access level (e.g. ``{"contents": "read"}``).
    * **repositories** – optional ``list[str]`` of repo names to scope.
    * **repository** – optional single ``owner/repo`` shorthand.
    * **token_name** – human label (tracked in lockfile, not sent to API).
    * **expires_in_hours** – token lifetime (default ``1``).
    """

    #: Key in the generator config dict that holds the provider *name* string.
    #: Used by the sync engine to resolve the provider instance.
    PROVIDER_CONFIG_KEY: str = "provider"

    #: Key under which the sync engine injects the resolved provider *instance*
    #: into the config before the generator is instantiated.
    PROVIDER_INJECTION_KEY: str = "_provider_instance"

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize GitHub PAT generator.

        Args:
            config: Generator configuration dictionary.

        Raises:
            ValueError: If the ``provider`` key is missing.
        """
        super().__init__(config)
        self._provider_name: str = config.get("provider", "github")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> str:
        """Generate a scoped GitHub installation access token.

        The heavy lifting is performed by
        :meth:`~secretzero.providers.github.GitHubProvider.generate_pat_with_manifest`.

        Returns:
            Installation access token string.

        Raises:
            RuntimeError: If the provider instance was not injected or the
                API call fails.
            ValueError: If permissions are invalid.
        """
        provider = self.config.get("_provider_instance")
        if provider is None:
            raise RuntimeError(
                f"GitHubPATGenerator requires a resolved provider instance. "
                f"Ensure provider '{self._provider_name}' is configured in the Secretfile."
            )

        # Build the manifest from our config, excluding internal keys
        manifest: dict[str, Any] = {
            k: v for k, v in self.config.items() if not k.startswith("_") and k != "provider"
        }

        return provider.generate_pat_with_manifest(manifest)

    def validate_configuration(self) -> tuple[bool, str | None]:
        """Validate generator configuration statically (before generation).

        Checks that permissions conform to the known GitHub permission schema.

        Returns:
            Tuple of (is_valid, error_message_or_None).
        """
        from secretzero.providers.github import validate_pat_permissions

        permissions = self.config.get("permissions")
        if permissions:
            valid, errors = validate_pat_permissions(permissions)
            if not valid:
                return False, "; ".join(errors)

        return True, None

    def get_manual_instructions(self) -> AgentInstructions:
        """Return step-by-step instructions for manually creating a GitHub PAT.

        These instructions are displayed when automatic token generation fails
        (e.g. no GitHub App configured) or when manual input is prompted.

        Returns:
            AgentInstructions with GitHub-specific PAT creation steps.
        """
        if self.manual_instructions is not None:
            return self.manual_instructions

        permissions = self.config.get("permissions", {})
        repos = self.config.get("repositories") or (
            [self.config["repository"]] if self.config.get("repository") else []
        )
        token_name = self.config.get("token_name", "secretzero-token")

        if permissions:
            perm_lines = "; ".join(f"{k}: {v}" for k, v in permissions.items())
            perm_desc = f"Required permissions: {perm_lines}"
        else:
            perm_desc = "Grant the minimum permissions needed for your use case"

        repo_desc = (
            f"Limit token to repositories: {', '.join(repos)}"
            if repos
            else "Select the repositories this token should access"
        )

        steps = [
            AgentInstructionStep(
                action="https://github.com/settings/tokens?type=beta",
                description="Open GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens",
            ),
            AgentInstructionStep(
                action="Click 'Generate new token'",
                description="Start creating a new fine-grained personal access token",
            ),
            AgentInstructionStep(
                action=f"Set token name to '{token_name}' (or any descriptive name)",
                description="Enter a name that identifies the token's purpose",
            ),
            AgentInstructionStep(
                action=repo_desc,
                description="Choose which repositories the token can access",
            ),
            AgentInstructionStep(
                action=perm_desc,
                description="Set the required repository and/or organization permissions",
            ),
            AgentInstructionStep(
                action="Click 'Generate token' and immediately copy the displayed token value",
                description="Generate the token — it will only be shown once",
            ),
        ]

        return AgentInstructions(
            summary=(
                "Automatic GitHub token generation failed. "
                "Follow these steps to create a Personal Access Token (PAT) manually."
            ),
            steps=steps,
            prerequisites=[
                "A GitHub account with access to the target repositories or organization",
            ],
            estimated_time="5 minutes",
            automation_hint=(
                "Token generation can be automated by configuring a GitHub App with the required "
                "permissions in the Secretfile providers section."
            ),
            fallback=(
                "Contact your GitHub organization admin to create a token with the required permissions."
            ),
            documentation_url=(
                "https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/"
                "managing-your-personal-access-tokens"
            ),
        )
