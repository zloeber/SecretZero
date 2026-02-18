"""GitLab provider for CI/CD variables."""

from typing import Any

from secretzero.providers.base import BaseProvider, ProviderAuth


class GitLabAuth(ProviderAuth):
    """GitLab authentication handler."""

    def __init__(self, config: dict[str, Any]):
        """Initialize GitLab authentication.

        Args:
            config: Authentication configuration containing:
                - token: GitLab personal access token or OAuth token
                - url: Optional GitLab instance URL (default: https://gitlab.com)
        """
        super().__init__(config)
        self._client: Any | None = None

    def authenticate(self) -> bool:
        """Authenticate with GitLab.

        Returns:
            True if authentication successful, False otherwise.
        """
        try:
            import gitlab
        except ImportError:
            return False

        token = self.config.get("token")
        if not token:
            return False

        url = self.config.get("url", "https://gitlab.com")

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
            # Merge top-level config into auth config for token
            if "token" in config:
                auth_config = {**auth_config, "token": config["token"]}
            auth = GitLabAuth(auth_config)
        super().__init__(name, config, auth)

    def test_connection(self) -> tuple[bool, str | None]:
        """Test GitLab API connectivity.

        Returns:
            Tuple of (success, details).
        """
        try:
            import gitlab
        except ImportError:
            return False, "python-gitlab not installed (pip install python-gitlab)"

        if not self.auth or not self.auth.authenticate():
            return False, "Authentication failed"

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
