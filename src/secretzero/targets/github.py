"""GitHub Actions secret targets."""

from typing import Any

from secretzero.targets.base import BaseTarget


class GitHubSecretTarget(BaseTarget):
    """Store secrets in GitHub Actions.

    Important: Classic Personal Access Tokens (PATs) cannot manage environment secrets.
    For environment secrets, use Fine-grained Personal Access Tokens with appropriate permissions.
    """

    def __init__(self, provider: Any, config: dict[str, Any] | None = None):
        """Initialize GitHub secret target.

        Args:
            provider: GitHub provider instance.
            config: Target configuration containing:
                - owner: Repository owner (username or organization)
                - repo: Repository name
                - environment: Optional environment name for environment-specific secrets
                  (requires Fine-grained PAT, not Classic PAT)
                - secret_name: Optional custom secret name (overrides default)
                - create_environment: Auto-create environment if it doesn't exist (default: False)
        """
        super().__init__(config)
        self.provider = provider
        self.owner = self.config.get("owner")
        self.repo = self.config.get("repo")
        self.environment = self.config.get("environment")
        self.secret_name_override = self.config.get("secret_name")
        self.create_environment = self.config.get("create_environment", False)

        if not self.owner or not self.repo:
            raise ValueError("GitHub target requires 'owner' and 'repo' in config")

    def store(self, secret_name: str, secret_value: str) -> bool:
        """Store secret in GitHub Actions.

        Args:
            secret_name: Name of the secret.
            secret_value: Value of the secret.

        Returns:
            True if storage successful, False otherwise.
        """
        try:
            client = self.provider.auth.get_client()

            # Debug: print the repository being accessed
            repo_full_name = f"{self.owner}/{self.repo}"

            try:
                repo = client.get_repo(repo_full_name)
            except Exception as e:
                # Provide more helpful error message if repo not found
                error_msg = str(e)
                if "404" in error_msg:
                    print(
                        f"Failed to store secret in GitHub: Repository '{repo_full_name}' not found or inaccessible."
                    )
                    print(f"  - Verify owner ('{self.owner}') and repo ('{self.repo}') are correct")
                    print(
                        "  - Verify GITHUB_TOKEN has access to this repository (needs 'repo' scope)"
                    )
                    print(f"  - Full error: {error_msg}")
                else:
                    print(f"Failed to store secret in GitHub: {error_msg}")
                return False

            # Use custom secret name if provided, otherwise use default
            actual_secret_name = self.secret_name_override or secret_name

            if self.environment:
                # Create environment if requested and it doesn't exist
                if self.create_environment:
                    try:
                        repo.get_environment(self.environment)
                    except Exception:
                        # Environment doesn't exist, create it
                        try:
                            repo.create_environment(self.environment)
                        except Exception as e:
                            print(
                                f"Failed to create environment '{self.environment}' in GitHub: {e}"
                            )
                            return False

                # Store as environment secret
                # PyGithub handles encryption automatically
                # Note: Requires Fine-grained PAT with Environments permission
                try:
                    repo.get_environment(self.environment).create_secret(
                        secret_name=actual_secret_name, unencrypted_value=secret_value
                    )
                except Exception as e:
                    error_msg = str(e)
                    if (
                        "Resource not accessible by personal access token" in error_msg
                        or "403" in error_msg
                    ):
                        print(
                            f"Failed to create environment secret '{actual_secret_name}' in GitHub: {e}"
                        )
                        print(
                            "  ⚠️  Classic Personal Access Tokens cannot manage environment secrets."
                        )
                        print(
                            "  Solution 1: Remove 'environment' field to use repository-level secrets instead"
                        )
                        print(
                            "  Solution 2: Create a Fine-grained PAT at https://github.com/settings/tokens?type=beta"
                        )
                        print(
                            "              with 'Actions', 'Secrets', and 'Environments' permissions"
                        )
                    else:
                        print(
                            f"Failed to create environment secret '{actual_secret_name}' in GitHub: {e}"
                        )
                    return False
            else:
                # Store as repository secret
                # PyGithub handles encryption automatically
                try:
                    repo.create_secret(
                        secret_name=actual_secret_name, unencrypted_value=secret_value
                    )
                except Exception as e:
                    print(
                        f"Failed to create repository secret '{actual_secret_name}' in GitHub: {e}"
                    )
                    return False

            return True
        except Exception as e:
            print(f"Failed to store secret in GitHub: {e}")
            return False

    def retrieve(self, secret_name: str) -> str | None:
        """Retrieve secret from GitHub Actions.

        Note: GitHub API does not allow retrieving secret values.

        Args:
            secret_name: Name of the secret.

        Returns:
            None (secrets cannot be retrieved from GitHub Actions).
        """
        # GitHub API does not expose secret values
        return None


class GitHubOrganizationSecretTarget(BaseTarget):
    """Store secrets in GitHub Organization-level Actions."""

    def __init__(self, provider: Any, config: dict[str, Any] | None = None):
        """Initialize GitHub organization secret target.

        Args:
            provider: GitHub provider instance.
            config: Target configuration containing:
                - org: Organization name
                - visibility: Secret visibility (all, private, selected)
                - selected_repository_ids: List of repo IDs if visibility is 'selected'
        """
        super().__init__(config)
        self.provider = provider
        self.org = self.config.get("org")
        self.visibility = self.config.get("visibility", "all")
        self.selected_repository_ids = self.config.get("selected_repository_ids", [])

        if not self.org:
            raise ValueError("GitHub organization target requires 'org' in config")

    def store(self, secret_name: str, secret_value: str) -> bool:
        """Store secret in GitHub Organization Actions.

        Args:
            secret_name: Name of the secret.
            secret_value: Value of the secret.

        Returns:
            True if storage successful, False otherwise.
        """
        try:
            client = self.provider.auth.get_client()
            org = client.get_organization(self.org)

            # Create or update organization secret
            # PyGithub handles encryption automatically
            org.create_secret(
                secret_name=secret_name, unencrypted_value=secret_value, visibility=self.visibility
            )

            return True
        except Exception as e:
            print(f"Failed to store secret in GitHub organization: {e}")
            return False

    def retrieve(self, secret_name: str) -> str | None:
        """Retrieve secret from GitHub Organization Actions.

        Note: GitHub API does not allow retrieving secret values.

        Args:
            secret_name: Name of the secret.

        Returns:
            None (secrets cannot be retrieved from GitHub Actions).
        """
        # GitHub API does not expose secret values
        return None
