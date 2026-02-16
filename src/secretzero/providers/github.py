"""GitHub provider for GitHub Actions secrets."""

from typing import Any, Optional

from secretzero.providers.base import BaseProvider, ProviderAuth


class GitHubAuth(ProviderAuth):
    """GitHub authentication handler."""

    def __init__(self, config: dict[str, Any]):
        """Initialize GitHub authentication.

        Args:
            config: Authentication configuration containing:
                - token: GitHub personal access token
                - api_url: Optional GitHub API URL (default: https://api.github.com)
        """
        super().__init__(config)
        self._client: Optional[Any] = None

    def authenticate(self) -> bool:
        """Authenticate with GitHub.

        Returns:
            True if authentication successful, False otherwise.
        """
        try:
            from github import Github
        except ImportError:
            return False

        token = self.config.get("token")
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


class GitHubProvider(BaseProvider):
    """GitHub provider for Actions secrets."""

    def __init__(
        self,
        name: str,
        config: Optional[dict[str, Any]] = None,
        auth: Optional[GitHubAuth] = None,
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

    def test_connection(self) -> tuple[bool, Optional[str]]:
        """Test GitHub API connectivity.

        Returns:
            Tuple of (success, details).
        """
        try:
            from github import Github
        except ImportError:
            return False, "PyGithub not installed (pip install PyGithub)"

        if not self.auth or not self.auth.authenticate():
            return False, "Authentication failed"

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
