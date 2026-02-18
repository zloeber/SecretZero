"""Azure target implementations for SecretZero."""

from typing import Any

from secretzero.targets.base import BaseTarget


class KeyVaultTarget(BaseTarget):
    """Azure Key Vault target."""

    def __init__(
        self,
        provider: Any,
        config: dict[str, Any] | None = None,
    ):
        """Initialize Key Vault target.

        Args:
            provider: Azure provider instance
            config: Target configuration including:
                - vault_url: Key Vault URL (e.g., https://myvault.vault.azure.net)
                - secret_name: Name of the secret in Key Vault
        """
        super().__init__(provider, config)

    def store(self, secret_name: str, secret_value: Any) -> bool:
        """Store secret in Azure Key Vault.

        Args:
            secret_name: Name of the secret
            secret_value: Value to store

        Returns:
            True if successful, False otherwise
        """
        try:
            from azure.core.exceptions import AzureError
            from azure.keyvault.secrets import SecretClient
        except ImportError:
            raise ValueError("Azure SDK not installed. Install with: pip install secretzero[azure]")

        from secretzero.providers.azure import AzureAuth

        if not isinstance(self.provider.auth, AzureAuth):
            return False

        credential = self.provider.auth.get_client()
        if not credential:
            return False

        vault_url = self.config.get("vault_url")
        if not vault_url:
            return False

        kv_secret_name = self.config.get("secret_name", secret_name)

        # Convert value to string if it's a dict
        if isinstance(secret_value, dict):
            import json

            value_str = json.dumps(secret_value)
        else:
            value_str = str(secret_value)

        try:
            client = SecretClient(vault_url=vault_url, credential=credential)
            client.set_secret(kv_secret_name, value_str)
            return True
        except AzureError:
            return False

    def retrieve(self, secret_name: str) -> Any | None:
        """Retrieve secret from Azure Key Vault.

        Args:
            secret_name: Name of the secret

        Returns:
            Secret value or None if not found
        """
        try:
            from azure.core.exceptions import ResourceNotFoundError
            from azure.keyvault.secrets import SecretClient
        except ImportError:
            return None

        from secretzero.providers.azure import AzureAuth

        if not isinstance(self.provider.auth, AzureAuth):
            return None

        credential = self.provider.auth.get_client()
        if not credential:
            return None

        vault_url = self.config.get("vault_url")
        if not vault_url:
            return None

        kv_secret_name = self.config.get("secret_name", secret_name)

        try:
            client = SecretClient(vault_url=vault_url, credential=credential)
            secret = client.get_secret(kv_secret_name)
            return secret.value
        except ResourceNotFoundError:
            return None

    def delete(self, secret_name: str) -> bool:
        """Delete secret from Azure Key Vault.

        Args:
            secret_name: Name of the secret

        Returns:
            True if successful, False otherwise
        """
        try:
            from azure.core.exceptions import AzureError
            from azure.keyvault.secrets import SecretClient
        except ImportError:
            return False

        from secretzero.providers.azure import AzureAuth

        if not isinstance(self.provider.auth, AzureAuth):
            return False

        credential = self.provider.auth.get_client()
        if not credential:
            return False

        vault_url = self.config.get("vault_url")
        if not vault_url:
            return False

        kv_secret_name = self.config.get("secret_name", secret_name)

        try:
            client = SecretClient(vault_url=vault_url, credential=credential)
            # Begin delete operation (soft delete)
            delete_operation = client.begin_delete_secret(kv_secret_name)
            delete_operation.wait()

            # Purge the secret (permanent deletion)
            client.purge_deleted_secret(kv_secret_name)
            return True
        except AzureError:
            return False
