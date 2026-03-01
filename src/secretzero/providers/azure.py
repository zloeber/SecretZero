"""Azure provider implementation for SecretZero."""

import os
import secrets
import string
from typing import Any

from secretzero.providers.base import BaseProvider, ProviderAuth


class AzureAuth(ProviderAuth):
    """Azure authentication handler.

    Supports authentication via:
    - DefaultAzureCredential (uses Azure CLI, managed identity, etc.)
    - Explicit credentials in config
    - Environment variables: AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET
    """

    # Environment variables for service principal auth
    ENV_TENANT_ID = "AZURE_TENANT_ID"
    ENV_CLIENT_ID = "AZURE_CLIENT_ID"
    ENV_CLIENT_SECRET = "AZURE_CLIENT_SECRET"

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize Azure authentication.

        Args:
            config: Authentication configuration including:
                - kind: Authentication method (managed_identity, default, cli, service_principal)
                - tenant_id: Azure tenant ID (or set AZURE_TENANT_ID env var)
                - client_id: Client ID for service principal (or set AZURE_CLIENT_ID env var)
                - client_secret: Client secret for service principal (or set AZURE_CLIENT_SECRET env var)

        Notes:
            DefaultAzureCredential checks credentials in this order:
            1. Environment variables (AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET)
            2. Managed identity
            3. Shared token cache
            4. Azure CLI credentials
        """
        super().__init__(config)
        self._credential = None

    def authenticate(self) -> bool:
        """Authenticate with Azure.

        Returns:
            True if authentication successful, False otherwise

        Attempts to authenticate using:
            1. Explicit auth kind from config
            2. Environment variables for service principal
            3. DefaultAzureCredential (checks multiple auth methods)
        """
        try:
            from azure.core.exceptions import ClientAuthenticationError
            from azure.identity import (
                AzureCliCredential,
                ClientSecretCredential,
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
            elif auth_kind == "service_principal":
                # Use explicit service principal credentials from config or environment
                tenant_id = self.config.get("tenant_id") or os.environ.get(self.ENV_TENANT_ID)
                client_id = self.config.get("client_id") or os.environ.get(self.ENV_CLIENT_ID)
                client_secret = self.config.get("client_secret") or os.environ.get(
                    self.ENV_CLIENT_SECRET
                )

                if not tenant_id or not client_id or not client_secret:
                    return False

                self._credential = ClientSecretCredential(
                    tenant_id=tenant_id,
                    client_id=client_id,
                    client_secret=client_secret,
                )
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

    display_name = "Microsoft Azure"
    description = "Azure Key Vault and services"
    required_package = ("azure.identity", "secretzero[azure]")
    auth_class = AzureAuth

    def __init__(
        self,
        name: str = "azure",
        config: dict[str, Any] | None = None,
        auth: AzureAuth | None = None,
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

    @property
    def provider_kind(self) -> str:
        """Return provider type identifier."""
        return "azure"

    def test_connection(self) -> tuple[bool, str | None]:
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
        return ["key_vault", "azure_deployment", "kubernetes"]

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

    def retrieve_secret(self, secret_name: str, version: str | None = None) -> str:
        """Retrieve a secret from Azure Key Vault.

        Args:
            secret_name: Name of the secret to retrieve.
            version: Optional version ID of the secret.

        Returns:
            str: The secret value.

        Raises:
            ValueError: If the secret cannot be retrieved.
        """
        from azure.keyvault.secrets import SecretClient

        try:
            client = SecretClient(
                vault_url=self.config.get("vault_url"),
                credential=self.auth.get_client(),
            )

            if version:
                secret = client.get_secret(secret_name, version=version)
            else:
                secret = client.get_secret(secret_name)

            return secret.value
        except Exception as e:
            raise ValueError(f"Failed to retrieve secret from Azure Key Vault: {e}")

    # ===== STORE CAPABILITY =====

    def store_secret(
        self,
        secret_name: str,
        secret_value: str,
        tags: dict[str, str] | None = None,
    ) -> bool:
        """Store a secret in Azure Key Vault.

        Args:
            secret_name: Name of the secret to store.
            secret_value: The secret value.
            tags: Optional tags to apply to the secret.

        Returns:
            bool: True if successful.

        Raises:
            ValueError: If the secret cannot be stored.
        """
        from azure.keyvault.secrets import SecretClient

        try:
            client = SecretClient(
                vault_url=self.config.get("vault_url"),
                credential=self.auth.get_client(),
            )

            # Create or update the secret
            client.set_secret(secret_name, secret_value, tags=tags)
            return True
        except Exception as e:
            raise ValueError(f"Failed to store secret in Azure Key Vault: {e}")

    # ===== ROTATE CAPABILITY =====

    def rotate_secret(self, secret_name: str, new_value: str) -> bool:
        """Rotate a secret by updating its value.

        Args:
            secret_name: Name of the secret to rotate.
            new_value: The new secret value.

        Returns:
            bool: True if successful.

        Raises:
            ValueError: If the secret cannot be rotated.
        """
        from azure.keyvault.secrets import SecretClient

        try:
            client = SecretClient(
                vault_url=self.config.get("vault_url"),
                credential=self.auth.get_client(),
            )

            # Update the secret value
            client.set_secret(secret_name, new_value)
            return True
        except Exception as e:
            raise ValueError(f"Failed to rotate secret in Azure Key Vault: {e}")

    # ===== DELETE CAPABILITY =====

    def delete_secret(self, secret_name: str, purge: bool = True) -> bool:
        """Delete a secret from Azure Key Vault.

        Args:
            secret_name: Name of the secret to delete.
            purge: If True, permanently deletes. If False, soft-deletes.
                Defaults to True.

        Returns:
            bool: True if successful.

        Raises:
            ValueError: If the secret cannot be deleted.
        """
        from azure.keyvault.secrets import SecretClient

        try:
            client = SecretClient(
                vault_url=self.config.get("vault_url"),
                credential=self.auth.get_client(),
            )

            # Delete the secret (soft delete by default)
            delete_operation = client.begin_delete_secret(secret_name)
            delete_operation.wait()

            # Purge permanently if requested
            if purge:
                client.purge_deleted_secret(secret_name)

            return True
        except Exception as e:
            raise ValueError(f"Failed to delete secret from Azure Key Vault: {e}")
