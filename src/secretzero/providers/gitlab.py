"""GitLab provider for CI/CD variables."""

import os
import secrets
import string
from typing import Any

from secretzero.providers.base import BaseProvider, ProviderAuth


class GitLabAuth(ProviderAuth):
    """GitLab authentication handler.

    Supports authentication via:
    - Explicit token in config
    - Environment variable: GITLAB_TOKEN (checked automatically if not in config)
    """

    # Environment variables to check for token and URL
    ENV_TOKEN = "GITLAB_TOKEN"
    ENV_URL = "GITLAB_URL"

    def __init__(self, config: dict[str, Any]):
        """Initialize GitLab authentication.

        Args:
            config: Authentication configuration containing:
                - token: GitLab personal access token (or set GITLAB_TOKEN env var)
                - url: Optional GitLab instance URL (or set GITLAB_URL env var, default: https://gitlab.com)
        """
        super().__init__(config)
        self._client: Any | None = None

    def authenticate(self) -> bool:
        """Authenticate with GitLab.

        Returns:
            True if authentication successful, False otherwise.

        Attempts to authenticate using:
            1. Explicit token from config
            2. GITLAB_TOKEN environment variable
        """
        try:
            import gitlab
        except ImportError:
            return False

        token = self.config.get("token") or os.environ.get(self.ENV_TOKEN)
        if not token:
            return False

        url = self.config.get("url") or os.environ.get(self.ENV_URL, "https://gitlab.com")

        try:
            # Initialize GitLab client
            self._client = gitlab.Gitlab(url=url, private_token=token)
            # Test authentication by fetching current user
            self._client.auth()
            return True
        except Exception:
            return False

    def is_authenticated(self) -> bool:
        """Check if currently authenticated.

        Returns:
            True if authenticated, False otherwise.
        """
        return self._client is not None

    def get_client(self) -> Any:
        """Get the authenticated GitLab client.

        Returns:
            python-gitlab Gitlab instance.
        """
        if not self.is_authenticated():
            self.authenticate()
        return self._client


class GitLabProvider(BaseProvider):
    """GitLab provider for CI/CD variables."""

    display_name = "GitLab"
    description = "GitLab CI/CD variables and secrets"
    required_package = ("gitlab", "secretzero[gitlab]")
    auth_class = GitLabAuth
    auth_methods = {
        "token": "Use GitLab personal access token",
    }
    config_options = {
        "url": "GitLab instance URL (default: https://gitlab.com)",
        "project_id": "GitLab project ID or path",
    }
    config_example = """providers:
  gitlab:
    kind: gitlab
    auth:
      kind: token
      config:
        url: https://gitlab.example.com
        token: ${GITLAB_TOKEN}"""
    target_details = {
        "gitlab_variable": {
            "description": "GitLab CI/CD Variable",
            "config": {
                "project_id": "GitLab project ID or path",
                "variable_name": "Variable name (optional, uses secret.name if not provided)",
                "protected": "Whether the variable is protected (default: false)",
                "masked": "Whether the variable is masked in logs (default: true)",
            },
            "example": """targets:
  - provider: gitlab
    kind: gitlab_variable
    config:
      project_id: mygroup/myproject
      variable_name: DATABASE_PASSWORD
      masked: true""",
        },
    }

    def __init__(
        self,
        name: str,
        config: dict[str, Any] | None = None,
        auth: GitLabAuth | None = None,
    ):
        """Initialize GitLab provider.

        Args:
            name: Provider name.
            config: Provider configuration.
            auth: Optional pre-configured auth handler.
        """
        if auth is None and config:
            auth_config = config.get("auth", {})
            # Merge top-level config into auth config for token and url
            if "token" in config:
                auth_config = {**auth_config, "token": config["token"]}
            if "url" in config:
                auth_config = {**auth_config, "url": config["url"]}
            auth = GitLabAuth(auth_config)
        super().__init__(name, config, auth)

    @property
    def provider_kind(self) -> str:
        """Return provider type identifier."""
        return "gitlab"

    def test_connection(self) -> tuple[bool, str | None]:
        """Test GitLab API connectivity.

        Returns:
            Tuple of (success, details).
        """
        try:
            import gitlab
        except ImportError:
            return False, "python-gitlab not installed (pip install python-gitlab)"

        # Check if token is available in config, auth config, or environment
        token = (
            self.config.get("token")
            or (self.auth.config.get("token") if self.auth else None)
            or os.environ.get(GitLabAuth.ENV_TOKEN)
        )
        if not token:
            return (
                False,
                f"No authentication token found. Set config 'token' or {GitLabAuth.ENV_TOKEN} env var",
            )

        if not self.auth or not self.auth.authenticate():
            return False, "Authentication failed - invalid token or URL"

        try:
            client = self.auth.get_client()
            user = client.user
            return True, f"Connected as {user.username}"
        except Exception as e:
            return False, f"Connection test failed: {str(e)}"

    def get_supported_targets(self) -> list[str]:
        """Get list of supported target types.

        Returns:
            List of target type identifiers.
        """
        return ["gitlab_variable", "gitlab_group_variable"]

    # ===== GENERATE CAPABILITY =====

    def generate_password(
        self,
        length: int = 32,
        special_chars: bool = True,
        uppercase: bool = True,
        lowercase: bool = True,
        numbers: bool = True,
    ) -> str:
        """Generate a cryptographically secure password.

        Args:
            length: Length of password (8-256 characters). Defaults to 32.
            special_chars: Include special characters. Defaults to True.
            uppercase: Include uppercase letters. Defaults to True.
            lowercase: Include lowercase letters. Defaults to True.
            numbers: Include numbers. Defaults to True.

        Returns:
            str: Generated password.

        Raises:
            ValueError: If parameters are invalid.
        """
        if length < 8 or length > 256:
            raise ValueError("Password length must be between 8 and 256")

        char_pool = ""
        if uppercase:
            char_pool += string.ascii_uppercase
        if lowercase:
            char_pool += string.ascii_lowercase
        if numbers:
            char_pool += string.digits
        if special_chars:
            char_pool += "!@#$%^&*-_+=()[]{}|:;<>,.?/"

        if not char_pool:
            raise ValueError("At least one character type must be enabled")

        password = "".join(secrets.choice(char_pool) for _ in range(length))
        return password

    # ===== RETRIEVE CAPABILITY =====

    def retrieve_secret(
        self,
        secret_name: str,
        project: str | None = None,
        group: str | None = None,
    ) -> str:
        """Retrieve a CI/CD variable from GitLab.

        Args:
            secret_name: Name of the variable to retrieve.
            project: GitLab project ID or path (for project variables).
            group: GitLab group ID or path (for group variables).

        Returns:
            str: The variable value.

        Raises:
            ValueError: If the variable cannot be retrieved.
        """
        try:
            client = self.auth.get_client()
            if not client:
                raise ValueError("GitLab authentication failed")

            if group:
                # Retrieve from group
                gl_group = client.groups.get(group, lazy=True)
                variable = gl_group.variables.get(secret_name)
                return variable.value
            elif project:
                # Retrieve from project
                gl_project = client.projects.get(project, lazy=True)
                variable = gl_project.variables.get(secret_name)
                return variable.value
            else:
                project = self.config.get("project")
                if project:
                    gl_project = client.projects.get(project, lazy=True)
                    variable = gl_project.variables.get(secret_name)
                    return variable.value
                raise ValueError("Project or group must be specified")

        except Exception as e:
            raise ValueError(f"Failed to retrieve variable from GitLab: {e}")

    # ===== STORE CAPABILITY =====

    def store_secret(
        self,
        secret_name: str,
        secret_value: str,
        project: str | None = None,
        group: str | None = None,
        protected: bool = False,
        masked: bool = True,
    ) -> bool:
        """Store a CI/CD variable in GitLab.

        Args:
            secret_name: Name of the variable.
            secret_value: The variable value.
            project: GitLab project ID or path (for project variables).
            group: GitLab group ID or path (for group variables).
            protected: If True, only runs on protected branches. Defaults to False.
            masked: If True, variable is masked in logs. Defaults to True.

        Returns:
            bool: True if successful.

        Raises:
            ValueError: If the variable cannot be stored.
        """
        try:
            client = self.auth.get_client()
            if not client:
                raise ValueError("GitLab authentication failed")

            if group:
                # Store in group
                gl_group = client.groups.get(group, lazy=True)
                try:
                    variable = gl_group.variables.get(secret_name)
                    variable.value = secret_value
                    variable.protected = protected
                    variable.masked = masked
                    variable.save()
                except Exception:
                    gl_group.variables.create(
                        {
                            "key": secret_name,
                            "value": secret_value,
                            "protected": protected,
                            "masked": masked,
                        }
                    )
            elif project:
                # Store in project
                gl_project = client.projects.get(project, lazy=True)
                try:
                    variable = gl_project.variables.get(secret_name)
                    variable.value = secret_value
                    variable.protected = protected
                    variable.masked = masked
                    variable.save()
                except Exception:
                    gl_project.variables.create(
                        {
                            "key": secret_name,
                            "value": secret_value,
                            "protected": protected,
                            "masked": masked,
                        }
                    )
            else:
                project = self.config.get("project")
                if not project:
                    raise ValueError("Project or group must be specified")
                gl_project = client.projects.get(project, lazy=True)
                try:
                    variable = gl_project.variables.get(secret_name)
                    variable.value = secret_value
                    variable.protected = protected
                    variable.masked = masked
                    variable.save()
                except Exception:
                    gl_project.variables.create(
                        {
                            "key": secret_name,
                            "value": secret_value,
                            "protected": protected,
                            "masked": masked,
                        }
                    )

            return True
        except Exception as e:
            raise ValueError(f"Failed to store variable in GitLab: {e}")

    # ===== DELETE CAPABILITY =====

    def delete_secret(
        self,
        secret_name: str,
        project: str | None = None,
        group: str | None = None,
    ) -> bool:
        """Delete a CI/CD variable from GitLab.

        Args:
            secret_name: Name of the variable to delete.
            project: GitLab project ID or path (for project variables).
            group: GitLab group ID or path (for group variables).

        Returns:
            bool: True if successful.

        Raises:
            ValueError: If the variable cannot be deleted.
        """
        try:
            client = self.auth.get_client()
            if not client:
                raise ValueError("GitLab authentication failed")

            if group:
                # Delete from group
                gl_group = client.groups.get(group, lazy=True)
                gl_group.variables.delete(secret_name)
            elif project:
                # Delete from project
                gl_project = client.projects.get(project, lazy=True)
                gl_project.variables.delete(secret_name)
            else:
                project = self.config.get("project")
                if not project:
                    raise ValueError("Project or group must be specified")
                gl_project = client.projects.get(project, lazy=True)
                gl_project.variables.delete(secret_name)

            return True
        except Exception as e:
            raise ValueError(f"Failed to delete variable from GitLab: {e}")


# ---------------------------------------------------------------------------
# Bundle manifest – makes this provider extractable as a standalone package.
# When extracted, expose this via entry_points:
#   [project.entry-points."secretzero.providers"]
#   gitlab = "secretzero_gitlab:BUNDLE_MANIFEST"
# ---------------------------------------------------------------------------


def _get_bundle_manifest() -> "BundleManifest":  # noqa: F821
    """Lazily construct the GitLab bundle manifest."""
    from secretzero.bundles.registry import BundleManifest

    return BundleManifest(
        name="gitlab",
        version="1.0.0",
        provider_class="secretzero.providers.gitlab:GitLabProvider",
        generators={},
        targets={
            "gitlab_variable": "secretzero.targets.gitlab:GitLabVariableTarget",
        },
        generator_kinds=[],
        target_kinds=["gitlab_variable"],
    )
