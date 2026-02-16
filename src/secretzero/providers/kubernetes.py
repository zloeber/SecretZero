"""Kubernetes provider for cluster-based secret management."""

from typing import Any, Optional

from secretzero.providers.base import BaseProvider, ProviderAuth


class KubernetesAuth(ProviderAuth):
    """Kubernetes authentication handler."""

    def __init__(self, config: dict[str, Any]):
        """Initialize Kubernetes authentication.

        Args:
            config: Authentication configuration containing:
                - kubeconfig: Optional path to kubeconfig file
                - context: Optional kubeconfig context name
                - token: Optional bearer token for token-based auth
                - in_cluster: Optional bool to use in-cluster config (default: False)
        """
        super().__init__(config)
        self._client: Optional[Any] = None
        self._api_client: Optional[Any] = None

    def authenticate(self) -> bool:
        """Authenticate with Kubernetes cluster.

        Returns:
            True if authentication successful, False otherwise.
        """
        try:
            from kubernetes import client, config
        except ImportError:
            return False

        try:
            # Determine authentication method
            if self.config.get("in_cluster", False):
                # Use in-cluster config (ServiceAccount)
                config.load_incluster_config()
            else:
                # Use kubeconfig file
                kubeconfig = self.config.get("kubeconfig")
                context = self.config.get("context")
                config.load_kube_config(
                    config_file=kubeconfig,
                    context=context
                )
            
            # Create API client
            self._api_client = client.ApiClient()
            self._client = client.CoreV1Api(self._api_client)
            
            # Test authentication by listing namespaces
            self._client.list_namespace(limit=1)
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
        """Get the authenticated Kubernetes CoreV1Api client.

        Returns:
            Kubernetes CoreV1Api instance.
        """
        if not self.is_authenticated():
            self.authenticate()
        return self._client

    def get_api_client(self) -> Any:
        """Get the authenticated Kubernetes ApiClient.

        Returns:
            Kubernetes ApiClient instance.
        """
        if not self.is_authenticated():
            self.authenticate()
        return self._api_client


class KubernetesProvider(BaseProvider):
    """Kubernetes provider for cluster secret management."""

    def __init__(
        self,
        name: str,
        config: Optional[dict[str, Any]] = None,
        auth: Optional[KubernetesAuth] = None,
    ):
        """Initialize Kubernetes provider.

        Args:
            name: Provider name.
            config: Provider configuration.
            auth: Optional pre-configured auth handler.
        """
        if auth is None and config:
            auth_config = config.get("auth", {})
            auth = KubernetesAuth(auth_config)
        super().__init__(name, config, auth)

    def test_connection(self) -> tuple[bool, Optional[str]]:
        """Test Kubernetes cluster connectivity.

        Returns:
            Tuple of (success, details).
        """
        try:
            from kubernetes import client
        except ImportError:
            return False, "kubernetes not installed (pip install kubernetes)"

        if not self.auth or not self.auth.authenticate():
            return False, "Authentication failed"

        try:
            api = self.auth.get_client()
            # Get cluster version info
            version = api.api_client.call_api(
                '/version', 'GET',
                auth_settings=['BearerToken'],
                response_type='object'
            )
            version_info = version[0] if version else {}
            git_version = version_info.get('gitVersion', 'unknown')
            return True, f"Connected to cluster (version: {git_version})"
        except Exception as e:
            return False, f"Connection test failed: {str(e)}"

    def get_supported_targets(self) -> list[str]:
        """Get list of supported target types.

        Returns:
            List of target type identifiers.
        """
        return ["kubernetes_secret", "external_secret"]
