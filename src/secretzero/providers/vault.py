"""HashiCorp Vault provider implementation for SecretZero."""

import os
from typing import Any

from secretzero.providers.base import BaseProvider, ProviderAuth


class VaultAuth(ProviderAuth):
    """HashiCorp Vault authentication handler."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize Vault authentication.

        Args:
            config: Authentication configuration including:
                - kind: Authentication method (token, approle, kubernetes)
                - url: Vault server URL
                - token: Vault token (for token auth)
                - role_id: Role ID (for approle auth)
                - secret_id: Secret ID (for approle auth)
                - namespace: Vault namespace (optional)
        """
        super().__init__(config)
        self._client = None

    def authenticate(self) -> bool:
        """Authenticate with Vault.

        Returns:
            True if authentication successful, False otherwise
        """
        try:
            import hvac
        except ImportError:
            return False

        try:
            auth_kind = self.config.get("kind", "token")
            url = self.config.get("url", os.environ.get("VAULT_ADDR", "http://localhost:8200"))
            namespace = self.config.get("namespace")

            self._client = hvac.Client(url=url, namespace=namespace)

            if auth_kind == "token":
                token = self.config.get("token", os.environ.get("VAULT_TOKEN"))
                if not token:
                    return False
                self._client.token = token

            elif auth_kind == "approle":
                role_id = self.config.get("role_id")
                secret_id = self.config.get("secret_id")
                if not role_id or not secret_id:
                    return False

                response = self._client.auth.approle.login(role_id=role_id, secret_id=secret_id)
                self._client.token = response["auth"]["client_token"]

            # Test authentication
            return self._client.is_authenticated()

        except Exception:
            return False

    def is_authenticated(self) -> bool:
        """Check if authenticated.

        Returns:
            True if authenticated, False otherwise
        """
        if not self._client:
            return False

        try:
            return self._client.is_authenticated()
        except Exception:
            return False

    def get_client(self) -> Any:
        """Get Vault client.

        Returns:
            HVAC client instance or None
        """
        return self._client


class VaultProvider(BaseProvider):
    """HashiCorp Vault provider for SecretZero."""

    def __init__(
        self,
        name: str = "vault",
        config: dict[str, Any] | None = None,
        auth: VaultAuth | None = None,
    ):
        """Initialize Vault provider.

        Args:
            name: Provider name
            config: Provider configuration
            auth: Vault authentication instance
        """
        if auth is None and config:
            auth_config = config.get("auth", {})
            auth = VaultAuth(auth_config)

        super().__init__(name, config, auth)

    def test_connection(self) -> tuple[bool, str | None]:
        """Test Vault connectivity.

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            import hvac
        except ImportError:
            return False, "hvac not installed. Install with: pip install secretzero[vault]"

        if not self.is_authenticated():
            auth_success = self.authenticate()
            if not auth_success:
                return False, "Vault authentication failed. Check credentials and configuration."

        try:
            # Test connectivity
            if isinstance(self.auth, VaultAuth):
                client = self.auth.get_client()
                if client and client.is_authenticated():
                    # Get seal status to verify connection
                    seal_status = client.sys.read_health_status()
                    return True, f"Connected to Vault (Sealed: {seal_status.get('sealed', False)})"
            return False, "Invalid auth instance"

        except Exception as e:
            return False, f"Vault connection test failed: {str(e)}"

    def get_supported_targets(self) -> list[str]:
        """Get supported target types.

        Returns:
            List of supported target type names
        """
        return ["kv"]
