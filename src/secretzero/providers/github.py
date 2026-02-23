"""GitHub provider for GitHub Actions secrets."""

import os
import secrets
from typing import Any

from secretzero.providers.base import BaseProvider, ProviderAuth


class GitHubAuth(ProviderAuth):
    """GitHub authentication handler.

    Supports authentication via:
    - Explicit token in config
    - Environment variable: GITHUB_TOKEN (checked automatically if not in config)
    """

    # Environment variable to check for token
    ENV_TOKEN = "GITHUB_TOKEN"

    def __init__(self, config: dict[str, Any]):
        """Initialize GitHub authentication.

        Args:
            config: Authentication configuration containing:
                - token: GitHub personal access token (or set GITHUB_TOKEN env var)
                - api_url: Optional GitHub API URL (default: https://api.github.com)

        Notes:
            If 'token' is not provided in config, will check GITHUB_TOKEN environment variable.
        """
        super().__init__(config)
        self._client: Any | None = None

    def authenticate(self) -> bool:
        """Authenticate with GitHub.

        Returns:
            True if authentication successful, False otherwise.

        Attempts to authenticate using:
            1. Explicit token from config
            2. GITHUB_TOKEN environment variable
        """
        try:
            from github import Github
        except ImportError:
            return False

        # Try to get token from config or environment
        token = self.config.get("token") or os.environ.get(self.ENV_TOKEN)
        if not token:
            return False

        api_url = self.config.get("api_url", "https://api.github.com")

        try:
            # Initialize GitHub client
            self._client = Github(token, base_url=api_url)
            # Test authentication by fetching user info
            self._client.get_user().login
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
        """Get the authenticated GitHub client.

        Returns:
            PyGithub Github instance.
        """
        if not self.is_authenticated():
            self.authenticate()
        return self._client

    def get_token_info(self) -> dict[str, Any]:
        """Get information about the authenticated token.

        Uses GitHub REST API directly (doesn't require PyGithub client).

        Returns:
            Dictionary containing:
                - user: GitHub username
                - scopes: List of OAuth scopes granted to the token
                - token_type: Type of token (e.g., 'OAuth', 'PAT')

        Raises:
            RuntimeError: If token is not available or API request fails
        """
        try:
            import requests

            # Get token for API request
            token = self.config.get("token") or os.environ.get(self.ENV_TOKEN)
            if not token:
                raise RuntimeError(
                    "No GitHub token found in config or GITHUB_TOKEN environment variable"
                )

            api_url = self.config.get("api_url", "https://api.github.com")

            # Make authenticated request to /user endpoint
            headers = {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
            }

            response = requests.get(f"{api_url}/user", headers=headers, timeout=10)
            response.raise_for_status()

            user_data = response.json()

            # Get scopes from header
            scopes_header = response.headers.get("X-OAuth-Scopes", "")
            scopes = [s.strip() for s in scopes_header.split(",") if s.strip()]

            return {
                "user": user_data.get("login", "unknown"),
                "name": user_data.get("name"),
                "email": user_data.get("email"),
                "scopes": scopes,
                "token_type": response.headers.get("X-GitHub-SSO", "PAT"),
            }
        except Exception as e:
            raise RuntimeError(f"Failed to get token info: {e}")


class GitHubProvider(BaseProvider):
    """GitHub provider for Actions secrets."""

    def __init__(
        self,
        name: str,
        config: dict[str, Any] | None = None,
        auth: GitHubAuth | None = None,
    ):
        """Initialize GitHub provider.

        Args:
            name: Provider name.
            config: Provider configuration.
            auth: Optional pre-configured auth handler.
        """
        if auth is None and config:
            auth_config = config.get("auth", {})
            # Merge top-level config into auth config for token
            if "token" in config:
                auth_config = {**auth_config, "token": config["token"]}
            auth = GitHubAuth(auth_config)
        super().__init__(name, config, auth)

    @property
    def provider_kind(self) -> str:
        """Return provider type identifier."""
        return "github"

    def test_connection(self) -> tuple[bool, str | None]:
        """Test GitHub API connectivity.

        Returns:
            Tuple of (success, details).
        """
        try:
            from github import Github
        except ImportError:
            return False, "PyGithub not installed (pip install PyGithub)"

        # Check if token is available in config, auth config, or environment
        token = (
            self.config.get("token")
            or (self.auth.config.get("token") if self.auth else None)
            or os.environ.get(GitHubAuth.ENV_TOKEN)
        )
        if not token:
            return (
                False,
                f"No authentication token found. Set config 'token' or {GitHubAuth.ENV_TOKEN} env var",
            )

        if not self.auth or not self.auth.authenticate():
            return False, "Authentication failed - invalid token or API URL"

        try:
            client = self.auth.get_client()
            user = client.get_user()
            return True, f"Connected as {user.login}"
        except Exception as e:
            return False, f"Connection test failed: {str(e)}"

    def get_supported_targets(self) -> list[str]:
        """Get list of supported target types.

        Returns:
            List of target type identifiers.
        """
        return ["github_secret", "github_environment_secret"]

    def get_token_permissions(self) -> dict[str, Any]:
        """Get information about the current GitHub token.

        Returns:
            Dictionary with token information including scopes/permissions.

        Raises:
            RuntimeError: If not authenticated or token info cannot be retrieved.
        """
        if not self.auth:
            raise RuntimeError("No authentication configured")

        # get_token_info() uses requests directly, doesn't need PyGithub client
        return self.auth.get_token_info()

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
            char_pool += "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        if lowercase:
            char_pool += "abcdefghijklmnopqrstuvwxyz"
        if numbers:
            char_pool += "0123456789"
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
        repository: str | None = None,
        environment: str | None = None,
    ) -> str:
        """Retrieve a secret from GitHub.

        Note: GitHub API does not return secret values for security reasons.
        This method returns a placeholder.

        Args:
            secret_name: Name of the secret to retrieve.
            repository: GitHub repository (owner/repo format).
            environment: Optional environment name for environment secrets.

        Returns:
            str: Placeholder message indicating secret exists.

        Raises:
            ValueError: If the secret cannot be retrieved or does not exist.
        """
        try:
            client = self.auth.get_client()
            if not client:
                raise ValueError("GitHub authentication failed")

            if not repository:
                repository = self.config.get("repository")
            if not repository:
                raise ValueError("Repository (owner/repo) must be specified")

            repo = client.get_repo(repository)

            if environment:
                # Check environment secret
                try:
                    _ = repo.get_environment(environment)
                    # GitHub API doesn't provide secret values
                    return f"[SECRET EXISTS in {environment}]"
                except Exception as e:
                    raise ValueError(f"Secret not found in environment {environment}: {e}")
            else:
                # Check repository secret
                try:
                    # List secrets to verify it exists
                    secrets_list = repo.get_secrets()
                    for s in secrets_list:
                        if s.name == secret_name:
                            return "[SECRET EXISTS]"
                    raise ValueError(f"Secret {secret_name} not found")
                except Exception as e:
                    raise ValueError(f"Failed to retrieve secret: {e}")

        except Exception as e:
            raise ValueError(f"Failed to retrieve secret from GitHub: {e}")

    # ===== STORE CAPABILITY =====

    def store_secret(
        self,
        secret_name: str,
        secret_value: str,
        repository: str | None = None,
        environment: str | None = None,
    ) -> bool:
        """Store a secret in GitHub.

        Args:
            secret_name: Name of the secret.
            secret_value: The secret value.
            repository: GitHub repository (owner/repo format).
            environment: Optional environment name for environment secrets.

        Returns:
            bool: True if successful.

        Raises:
            ValueError: If the secret cannot be stored.
        """
        try:
            client = self.auth.get_client()
            if not client:
                raise ValueError("GitHub authentication failed")

            if not repository:
                repository = self.config.get("repository")
            if not repository:
                raise ValueError("Repository (owner/repo) must be specified")

            repo = client.get_repo(repository)

            if environment:
                # Store as environment secret
                _ = repo.get_environment(environment)
                from github import Repository

                repo.create_environment_secret(environment, secret_name, secret_value)
            else:
                # Store as repository secret
                repo.create_secret(secret_name, secret_value)

            return True
        except Exception as e:
            raise ValueError(f"Failed to store secret in GitHub: {e}")

    # ===== DELETE CAPABILITY =====

    def delete_secret(
        self,
        secret_name: str,
        repository: str | None = None,
        environment: str | None = None,
    ) -> bool:
        """Delete a secret from GitHub.

        Args:
            secret_name: Name of the secret to delete.
            repository: GitHub repository (owner/repo format).
            environment: Optional environment name for environment secrets.

        Returns:
            bool: True if successful.

        Raises:
            ValueError: If the secret cannot be deleted.
        """
        try:
            client = self.auth.get_client()
            if not client:
                raise ValueError("GitHub authentication failed")

            if not repository:
                repository = self.config.get("repository")
            if not repository:
                raise ValueError("Repository (owner/repo) must be specified")

            repo = client.get_repo(repository)

            if environment:
                # Delete environment secret
                env = repo.get_environment(environment)
                env.delete_secret(secret_name)
            else:
                # Delete repository secret
                repo.delete_secret(secret_name)

            return True
        except Exception as e:
            raise ValueError(f"Failed to delete secret from GitHub: {e}")
