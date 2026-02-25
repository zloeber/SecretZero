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


class GitHubPATGenerator(BaseGenerator):
    """Generator that creates scoped GitHub App installation tokens.

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
