"""Azure provider implementation for SecretZero."""

import os
from typing import Any, Dict, Optional

from secretzero.providers.base import BaseProvider, ProviderAuth


class AzureAuth(ProviderAuth):
    """Azure authentication handler."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize Azure authentication.
        
        Args:
            config: Authentication configuration including:
                - kind: Authentication method (managed_identity, default, cli)
                - tenant_id: Azure tenant ID (optional)
                - client_id: Client ID for service principal (optional)
                - client_secret: Client secret for service principal (optional)
        """
        super().__init__(config)
        self._credential = None

    def authenticate(self) -> bool:
        """Authenticate with Azure.
        
        Returns:
            True if authentication successful, False otherwise
        """
        try:
            from azure.core.exceptions import ClientAuthenticationError
            from azure.identity import (
                AzureCliCredential,
                DefaultAzureCredential,
                ManagedIdentityCredential,
            )
        except ImportError:
            return False

        try:
            auth_kind = self.config.get("kind", "default")

            if auth_kind == "managed_identity":
                client_id = self.config.get("client_id")
                if client_id:
                    self._credential = ManagedIdentityCredential(client_id=client_id)
                else:
                    self._credential = ManagedIdentityCredential()
            elif auth_kind == "cli":
                self._credential = AzureCliCredential()
            else:  # default
                self._credential = DefaultAzureCredential()

            # Test authentication by getting token
            self._credential.get_token("https://vault.azure.net/.default")
            return True

        except (ClientAuthenticationError, Exception):
            return False

    def is_authenticated(self) -> bool:
        """Check if authenticated.
        
        Returns:
            True if authenticated, False otherwise
        """
        if not self._credential:
            return False

        try:
            self._credential.get_token("https://vault.azure.net/.default")
            return True
        except Exception:
            return False

    def get_client(self) -> Any:
        """Get Azure credential.
        
        Returns:
            Azure credential instance or None
        """
        return self._credential


class AzureProvider(BaseProvider):
    """Azure provider for SecretZero."""

    def __init__(
        self,
        name: str = "azure",
        config: Optional[Dict[str, Any]] = None,
        auth: Optional[AzureAuth] = None,
    ):
        """Initialize Azure provider.
        
        Args:
            name: Provider name
            config: Provider configuration
            auth: Azure authentication instance
        """
        if auth is None and config:
            auth_config = config.get("auth", {})
            auth = AzureAuth(auth_config)

        super().__init__(name, config, auth)

    def test_connection(self) -> tuple[bool, Optional[str]]:
        """Test Azure connectivity.
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            from azure.core.exceptions import ClientAuthenticationError
        except ImportError:
            return (
                False,
                "Azure SDK not installed. Install with: pip install secretzero[azure]",
            )

        if not self.is_authenticated():
            auth_success = self.authenticate()
            if not auth_success:
                return False, "Azure authentication failed. Check credentials and configuration."

        try:
            # Test authentication
            if isinstance(self.auth, AzureAuth):
                credential = self.auth.get_client()
                if credential:
                    credential.get_token("https://vault.azure.net/.default")
                    return True, "Connected to Azure"
            return False, "Invalid auth instance"

        except (ClientAuthenticationError, Exception) as e:
            return False, f"Azure connection test failed: {str(e)}"

    def get_supported_targets(self) -> list[str]:
        """Get supported target types.
        
        Returns:
            List of supported target type names
        """
        return ["key_vault"]
