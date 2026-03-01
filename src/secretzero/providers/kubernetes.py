"""Kubernetes provider for cluster-based secret management."""

import json
import os
import secrets
import string
from typing import Any

from secretzero.providers.base import BaseProvider, ProviderAuth


class KubernetesAuth(ProviderAuth):
    """Kubernetes authentication handler.

    Supports authentication via:
    - Explicit kubeconfig path in config
    - Environment variable: KUBECONFIG (checked automatically if not in config)
    - In-cluster service account config
    """

    # Environment variable to check for kubeconfig path
    ENV_KUBECONFIG = "KUBECONFIG"

    def __init__(self, config: dict[str, Any]):
        """Initialize Kubernetes authentication.

        Args:
            config: Authentication configuration containing:
                - kubeconfig: Optional path to kubeconfig file (or set KUBECONFIG env var)
                - context: Optional kubeconfig context name
                - token: Optional bearer token for token-based auth
                - in_cluster: Optional bool to use in-cluster config (default: False)
        """
        super().__init__(config)
        self._client: Any | None = None
        self._api_client: Any | None = None

    def authenticate(self) -> bool:
        """Authenticate with Kubernetes cluster.

        Returns:
            True if authentication successful, False otherwise.

        Attempts to authenticate using:
            1. In-cluster config (if in_cluster=True)
            2. Explicit kubeconfig path from config
            3. KUBECONFIG environment variable
            4. Default kubeconfig (~/.kube/config)
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
                # Use kubeconfig file - check config first, then environment
                kubeconfig = self.config.get("kubeconfig") or os.environ.get(self.ENV_KUBECONFIG)
                context = self.config.get("context")
                config.load_kube_config(config_file=kubeconfig, context=context)

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

    display_name = "Kubernetes"
    description = "Kubernetes cluster secret management"
    required_package = ("kubernetes", "secretzero[kubernetes]")
    auth_class = KubernetesAuth
    auth_methods = {
        "ambient": "Use in-cluster service account",
        "kubeconfig": "Use local kubeconfig file",
    }
    config_options = {
        "context": "Kubeconfig context",
        "namespace": "Default namespace",
    }
    config_example = """providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient
      config:
        namespace: default"""
    target_details = {
        "kubernetes_secret": {
            "description": "Kubernetes Secret",
            "config": {
                "namespace": "Kubernetes namespace (default: default)",
                "name": "Secret name in Kubernetes",
                "secret_type": "Secret type: Opaque, docker-json, etc. (default: Opaque)",
            },
            "example": """targets:
  - provider: kubernetes
    kind: kubernetes_secret
    config:
      namespace: production
      name: database-credentials
      secret_type: Opaque""",
        },
    }

    def __init__(
        self,
        name: str,
        config: dict[str, Any] | None = None,
        auth: KubernetesAuth | None = None,
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

    @property
    def provider_kind(self) -> str:
        """Return provider type identifier."""
        return "kubernetes"

    def test_connection(self) -> tuple[bool, str | None]:
        """Test Kubernetes cluster connectivity.

        Returns:
            Tuple of (success, details).
        """
        try:
            from kubernetes import client
        except ImportError:
            return False, "kubernetes not installed (pip install kubernetes)"

        # Check if kubeconfig is available in config, auth config, or environment
        kubeconfig = (
            self.config.get("kubeconfig")
            or (self.auth.config.get("kubeconfig") if self.auth else None)
            or os.environ.get(KubernetesAuth.ENV_KUBECONFIG)
        )
        in_cluster = self.config.get("in_cluster") or (
            self.auth.config.get("in_cluster") if self.auth else False
        )

        if in_cluster:
            kubeconfig = "in-cluster"

        if not kubeconfig:
            return (
                False,
                f"No kubeconfig found. Set config 'kubeconfig', {KubernetesAuth.ENV_KUBECONFIG} env var, or use 'in_cluster: true'",
            )

        if not self.auth or not self.auth.authenticate():
            return False, "Authentication failed - invalid kubeconfig or credentials"

        try:
            api = self.auth.get_client()
            # Get cluster version info
            version = api.api_client.call_api(
                "/version", "GET", auth_settings=["BearerToken"], response_type="object"
            )
            version_info = version[0] if version else {}
            git_version = version_info.get("gitVersion", "unknown")
            return True, f"Connected to cluster (version: {git_version})"
        except Exception as e:
            return False, f"Connection test failed: {str(e)}"

    def get_supported_targets(self) -> list[str]:
        """Get list of supported target types.

        Returns:
            List of target type identifiers.
        """
        return ["kubernetes_secret", "external_secret"]

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

    def retrieve_secret(self, secret_name: str, namespace: str = "default") -> str:
        """Retrieve a secret from Kubernetes.

        Args:
            secret_name: Name of the secret.
            namespace: Kubernetes namespace. Defaults to 'default'.

        Returns:
            str: JSON string of secret data.

        Raises:
            ValueError: If the secret cannot be retrieved.
        """
        try:
            api = self.auth.get_client()
            if not api:
                raise ValueError("Kubernetes authentication failed")

            # Get the secret
            secret = api.read_namespaced_secret(secret_name, namespace)
            if secret and secret.data:
                return json.dumps(secret.data)
            return "{}"

        except Exception as e:
            raise ValueError(f"Failed to retrieve secret from Kubernetes: {e}")

    # ===== STORE CAPABILITY =====

    def store_secret(
        self,
        secret_name: str,
        secret_data: dict[str, str],
        namespace: str = "default",
        secret_type: str = "Opaque",
        labels: dict[str, str] | None = None,
    ) -> bool:
        """Store a secret in Kubernetes.

        Args:
            secret_name: Name of the secret.
            secret_data: Dictionary of key-value pairs for secret data.
            namespace: Kubernetes namespace. Defaults to 'default'.
            secret_type: Type of secret (Opaque, BasicAuth, etc). Defaults to 'Opaque'.
            labels: Optional labels to apply to the secret.

        Returns:
            bool: True if successful.

        Raises:
            ValueError: If the secret cannot be stored.
        """
        try:
            from kubernetes import client

            api = self.auth.get_client()
            if not api:
                raise ValueError("Kubernetes authentication failed")

            # Create secret object
            metadata = client.V1ObjectMeta(
                name=secret_name,
                namespace=namespace,
                labels=labels or {},
            )

            secret = client.V1Secret(
                api_version="v1",
                kind="Secret",
                metadata=metadata,
                type=secret_type,
                data=secret_data,
            )

            # Try to update existing secret, or create new one
            try:
                api.patch_namespaced_secret(secret_name, namespace, secret)
            except Exception:
                api.create_namespaced_secret(namespace, secret)

            return True

        except Exception as e:
            raise ValueError(f"Failed to store secret in Kubernetes: {e}")

    # ===== ROTATE CAPABILITY =====

    def rotate_secret(
        self,
        secret_name: str,
        secret_data: dict[str, str],
        namespace: str = "default",
    ) -> bool:
        """Rotate a secret by updating its data.

        Args:
            secret_name: Name of the secret.
            secret_data: New secret data dictionary.
            namespace: Kubernetes namespace. Defaults to 'default'.

        Returns:
            bool: True if successful.

        Raises:
            ValueError: If the secret cannot be rotated.
        """
        try:
            from kubernetes import client

            api = self.auth.get_client()
            if not api:
                raise ValueError("Kubernetes authentication failed")

            # Get existing secret
            secret = api.read_namespaced_secret(secret_name, namespace)

            # Update data
            secret.data = secret_data

            # Patch the secret
            api.patch_namespaced_secret(secret_name, namespace, secret)
            return True

        except Exception as e:
            raise ValueError(f"Failed to rotate secret in Kubernetes: {e}")

    # ===== DELETE CAPABILITY =====

    def delete_secret(self, secret_name: str, namespace: str = "default") -> bool:
        """Delete a secret from Kubernetes.

        Args:
            secret_name: Name of the secret to delete.
            namespace: Kubernetes namespace. Defaults to 'default'.

        Returns:
            bool: True if successful.

        Raises:
            ValueError: If the secret cannot be deleted.
        """
        try:
            api = self.auth.get_client()
            if not api:
                raise ValueError("Kubernetes authentication failed")

            # Delete the secret
            api.delete_namespaced_secret(secret_name, namespace)
            return True

        except Exception as e:
            raise ValueError(f"Failed to delete secret from Kubernetes: {e}")


# ---------------------------------------------------------------------------
# Bundle manifest – makes this provider extractable as a standalone package.
# When extracted, expose this via entry_points:
#   [project.entry-points."secretzero.providers"]
#   kubernetes = "secretzero_kubernetes:BUNDLE_MANIFEST"
# ---------------------------------------------------------------------------


def _get_bundle_manifest() -> "BundleManifest":  # noqa: F821
    """Lazily construct the Kubernetes bundle manifest."""
    from secretzero.bundles.registry import BundleManifest

    return BundleManifest(
        name="kubernetes",
        version="1.0.0",
        provider_class="secretzero.providers.kubernetes:KubernetesProvider",
        generators={},
        targets={
            "kubernetes_secret": "secretzero.targets.kubernetes:KubernetesSecretTarget",
            "external_secret": "secretzero.targets.kubernetes:ExternalSecretTarget",
        },
        generator_kinds=[],
        target_kinds=["kubernetes_secret", "external_secret"],
    )
