"""Jenkins provider for credentials."""

from typing import Any

from secretzero.providers.base import BaseProvider, ProviderAuth


class JenkinsAuth(ProviderAuth):
    """Jenkins authentication handler."""

    def __init__(self, config: dict[str, Any]):
        """Initialize Jenkins authentication.

        Args:
            config: Authentication configuration containing:
                - url: Jenkins server URL
                - username: Jenkins username
                - token: Jenkins API token or password
        """
        super().__init__(config)
        self._client: Any | None = None

    def authenticate(self) -> bool:
        """Authenticate with Jenkins.

        Returns:
            True if authentication successful, False otherwise.
        """
        try:
            import jenkins
        except ImportError:
            return False

        url = self.config.get("url")
        username = self.config.get("username")
        token = self.config.get("token")

        if not url or not username or not token:
            return False

        try:
            # Initialize Jenkins client
            self._client = jenkins.Jenkins(url, username=username, password=token)
            # Test authentication by getting version
            self._client.get_version()
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
        """Get the authenticated Jenkins client.

        Returns:
            python-jenkins Jenkins instance.
        """
        if not self.is_authenticated():
            self.authenticate()
        return self._client


class JenkinsProvider(BaseProvider):
    """Jenkins provider for credentials."""

    def __init__(
        self,
        name: str,
        config: dict[str, Any] | None = None,
        auth: JenkinsAuth | None = None,
    ):
        """Initialize Jenkins provider.

        Args:
            name: Provider name.
            config: Provider configuration.
            auth: Optional pre-configured auth handler.
        """
        if auth is None and config:
            auth_config = config.get("auth", {})
            # Merge top-level config into auth config
            for key in ["url", "username", "token"]:
                if key in config:
                    auth_config[key] = config[key]
            auth = JenkinsAuth(auth_config)
        super().__init__(name, config, auth)

    def test_connection(self) -> tuple[bool, str | None]:
        """Test Jenkins API connectivity.

        Returns:
            Tuple of (success, details).
        """
        try:
            import jenkins
        except ImportError:
            return False, "python-jenkins not installed (pip install python-jenkins)"

        if not self.auth or not self.auth.authenticate():
            return False, "Authentication failed"

        try:
            client = self.auth.get_client()
            version = client.get_version()
            return True, f"Connected to Jenkins v{version}"
        except Exception as e:
            return False, f"Connection test failed: {str(e)}"

    def get_supported_targets(self) -> list[str]:
        """Get list of supported target types.

        Returns:
            List of target type identifiers.
        """
        return ["jenkins_credential"]
