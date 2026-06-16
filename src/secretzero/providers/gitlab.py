"""GitLab provider for CI/CD variables and project access tokens."""

from __future__ import annotations

import os
import secrets
import string
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from secretzero.providers.base import BaseProvider, ProviderAuth
from secretzero.providers.gitlab_project_resolve import resolve_gitlab_project

GITLAB_PROJECT_TOKEN_SCOPES = frozenset(
    {
        "api",
        "read_api",
        "read_registry",
        "write_registry",
        "read_repository",
        "write_repository",
        "create_runner",
        "manage_runner",
        "ai_features",
        "k8s_proxy",
        "self_rotate",
    }
)


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

    def get_token_info(self) -> dict[str, Any]:
        """Return identity metadata for the configured GitLab token."""
        if not self._client:
            if not self.authenticate():
                raise RuntimeError("GitLab authentication failed")
        try:
            user = self._client.user
            return {
                "user": getattr(user, "username", None),
                "name": getattr(user, "name", None),
                "email": getattr(user, "email", None),
                "user_id": getattr(user, "id", None),
                "scopes": [],
                "token_type": "gitlab_pat",
            }
        except Exception:
            return {
                "user": None,
                "name": None,
                "email": None,
                "user_id": None,
                "scopes": [],
                "token_type": "gitlab_project_access_token",
            }


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
    generator_details = {
        "gitlab_project_token": {
            "description": "Create a scoped GitLab project access token via the GitLab API",
            "config": {
                "provider": "Provider alias from providers: (required)",
                "project": "GitLab project ID or path, or auto (default: auto)",
                "token_name": "Token name in GitLab (required)",
                "scopes": "List of GitLab scopes, e.g. [api, read_repository] (required)",
                "access_level": "GitLab access level integer (default: 40 Maintainer)",
                "expires_in_days": "Days until expiration (default: 90)",
                "description": "Optional token description (max 255 chars)",
                "revoke_existing": "Revoke prior tokens with the same name first (default: true)",
            },
            "example": """secrets:
  - name: ci_deploy_token
    kind: gitlab_project_token
    config:
      provider: gitlab
      project: auto
      token_name: secretzero-ci-deploy
      scopes: [read_repository, write_repository]""",
        },
    }
    target_details = {
        "gitlab_variable": {
            "description": "GitLab CI/CD project variable",
            "config": {
                "project": "GitLab project ID or path (or 'auto')",
                "protected": "Whether the variable is protected (default: false)",
                "masked": "Whether the variable is masked in logs (default: true)",
                "environment_scope": "Environment scope (default: *)",
                "variable_type": "env_var or file (default: env_var)",
            },
            "example": """targets:
  - provider: gitlab
    kind: gitlab_variable
    config:
      project: auto
      masked: true""",
        },
        "gitlab_group_variable": {
            "description": "GitLab CI/CD group variable",
            "config": {
                "group": "GitLab group ID or path",
                "protected": "Whether the variable is protected (default: false)",
                "masked": "Whether the variable is masked in logs (default: true)",
            },
            "example": """targets:
  - provider: gitlab
    kind: gitlab_group_variable
    config:
      group: mygroup
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

    def get_actor_info(self) -> dict[str, Any]:
        """Return information about the current GitLab user."""
        info = super().get_actor_info()
        url = (
            (self.config or {}).get("url")
            or os.environ.get(GitLabAuth.ENV_URL)
            or "https://gitlab.com"
        )
        info.setdefault("api_url", url)
        return info

    def test_connection(self) -> tuple[bool, str | None]:
        """Test GitLab API connectivity.

        Returns:
            Tuple of (success, details).
        """
        # If the python-gitlab library is missing, treat this as an
        # authentication-related failure so callers can handle it in
        # the same way as other auth issues.
        try:
            import gitlab  # noqa: F401
        except ImportError:
            return (
                False,
                "Authentication failed - python-gitlab not installed (pip install python-gitlab)",
            )

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

    # ===== PROJECT ACCESS TOKEN CAPABILITY =====

    def revoke_project_access_tokens_by_name(
        self,
        token_name: str,
        project: str | None = None,
    ) -> int:
        """Revoke active project access tokens that match ``token_name``.

        Args:
            token_name: GitLab project access token name.
            project: Project path/ID (resolved when omitted or ``auto``).

        Returns:
            Number of tokens revoked.
        """
        resolved_project = resolve_gitlab_project(
            project=project or "auto",
            provider_config=self.config or {},
            cwd=Path.cwd(),
        )
        client = self.auth.get_client()
        if not client:
            raise ValueError("GitLab authentication failed")

        gl_project = client.projects.get(resolved_project, lazy=True)
        revoked = 0
        for token in gl_project.access_tokens.list():
            if getattr(token, "name", None) == token_name:
                token.delete()
                revoked += 1
        return revoked

    def generate_project_access_token(
        self,
        *,
        token_name: str,
        scopes: list[str],
        project: str | None = None,
        access_level: int = 40,
        expires_in_days: int = 90,
        description: str | None = None,
        revoke_existing: bool = False,
    ) -> str:
        """Create a GitLab project access token.

        Requires a personal access token for authentication.

        Args:
            token_name: Token name in GitLab.
            scopes: GitLab token scopes.
            project: Project path/ID or ``auto``.
            access_level: GitLab access level integer (default Maintainer).
            expires_in_days: Days until expiration.
            description: Optional token description.
            revoke_existing: Revoke prior tokens with the same name first.

        Returns:
            One-time project access token string.

        Raises:
            ValueError: If configuration is invalid.
            RuntimeError: If the GitLab API call fails.
        """
        if not token_name:
            raise ValueError("token_name is required for gitlab_project_token")
        if not scopes:
            raise ValueError("scopes is required for gitlab_project_token")

        unknown = [scope for scope in scopes if scope not in GITLAB_PROJECT_TOKEN_SCOPES]
        if unknown:
            raise ValueError(f"Unknown GitLab project token scopes: {', '.join(unknown)}")

        resolved_project = resolve_gitlab_project(
            project=project or "auto",
            provider_config=self.config or {},
            cwd=Path.cwd(),
        )

        client = self.auth.get_client()
        if not client:
            raise ValueError("GitLab authentication failed")

        if revoke_existing:
            self.revoke_project_access_tokens_by_name(token_name, project=resolved_project)

        expires_at = (datetime.now(UTC) + timedelta(days=expires_in_days)).strftime("%Y-%m-%d")
        payload: dict[str, Any] = {
            "name": token_name,
            "scopes": scopes,
            "expires_at": expires_at,
            "access_level": access_level,
        }
        if description:
            payload["description"] = description

        gl_project = client.projects.get(resolved_project, lazy=True)
        try:
            created = gl_project.access_tokens.create(payload)
        except Exception as exc:
            raise RuntimeError(f"GitLab project access token creation failed: {exc}") from exc

        token_value = getattr(created, "token", None)
        if not token_value:
            raise RuntimeError("GitLab API response missing project access token value")
        return token_value

    def generate_project_access_token_with_manifest(
        self,
        manifest: dict[str, Any],
    ) -> str:
        """Create a project access token from a generator manifest."""
        return self.generate_project_access_token(
            token_name=manifest["token_name"],
            scopes=manifest["scopes"],
            project=manifest.get("project", "auto"),
            access_level=manifest.get("access_level", 40),
            expires_in_days=manifest.get("expires_in_days", 90),
            description=manifest.get("description"),
            revoke_existing=manifest.get("revoke_existing", False),
        )


# ---------------------------------------------------------------------------
# Bundle manifest – makes this provider extractable as a standalone package.
# When extracted, expose this via entry_points:
#   [project.entry-points."secretzero.providers"]
#   gitlab = "secretzero_gitlab:BUNDLE_MANIFEST"
# ---------------------------------------------------------------------------


def _get_bundle_manifest() -> BundleManifest:  # noqa: F821
    """Lazily construct the GitLab bundle manifest."""
    from secretzero.bundles.registry import BundleManifest

    return BundleManifest(
        name="gitlab",
        version="1.0.0",
        provider_class="secretzero.providers.gitlab:GitLabProvider",
        generators={
            "gitlab_project_token": (
                "secretzero.generators.gitlab_project_token:GitLabProjectTokenGenerator"
            ),
        },
        targets={
            "gitlab_variable": "secretzero.targets.gitlab:GitLabVariableTarget",
            "gitlab_group_variable": "secretzero.targets.gitlab:GitLabGroupVariableTarget",
        },
        generator_kinds=["gitlab_project_token"],
        target_kinds=["gitlab_variable", "gitlab_group_variable"],
        terraform_provider={
            "name": "gitlab",
            "source": "gitlabhq/gitlab",
            "version": "~> 16.0",
            "default_config": {},
        },
    )
