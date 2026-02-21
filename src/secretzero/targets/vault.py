"""HashiCorp Vault target implementations for SecretZero."""

from typing import Any

from secretzero.targets.base import BaseTarget


class VaultKVTarget(BaseTarget):
    """HashiCorp Vault KV v2 target."""

    def __init__(
        self,
        provider: Any,
        config: dict[str, Any] | None = None,
    ):
        """Initialize Vault KV target.

        Args:
            provider: Vault provider instance
            config: Target configuration including:
                - path: Secret path in KV engine (e.g., "secret/data/myapp/config")
                - mount_point: KV mount point (default: "secret")
                - version: KV version (1 or 2, default: 2)
        """
        super().__init__(provider=provider, config=config)

    def store(self, secret_name: str, secret_value: Any) -> bool:
        """Store secret in Vault KV.

        Args:
            secret_name: Name of the secret
            secret_value: Value to store

        Returns:
            True if successful, False otherwise
        """
        try:
            import hvac
        except ImportError:
            raise ValueError("hvac not installed. Install with: pip install secretzero[vault]")

        from secretzero.providers.vault import VaultAuth

        if not isinstance(self.provider.auth, VaultAuth):
            return False

        client = self.provider.auth.get_client()
        if not client:
            return False

        path = self.config.get("path")
        if not path:
            return False

        mount_point = self.config.get("mount_point", "secret")
        version = self.config.get("version", 2)

        # Prepare secret data
        if isinstance(secret_value, dict):
            secret_data = secret_value
        else:
            secret_data = {"value": str(secret_value)}

        try:
            if version == 2:
                # KV v2
                client.secrets.kv.v2.create_or_update_secret(
                    path=path, secret=secret_data, mount_point=mount_point
                )
            else:
                # KV v1
                client.secrets.kv.v1.create_or_update_secret(
                    path=path, secret=secret_data, mount_point=mount_point
                )
            return True
        except Exception:
            return False

    def retrieve(self, secret_name: str) -> Any | None:
        """Retrieve secret from Vault KV.

        Args:
            secret_name: Name of the secret

        Returns:
            Secret value or None if not found
        """
        try:
            import hvac
        except ImportError:
            return None

        from secretzero.providers.vault import VaultAuth

        if not isinstance(self.provider.auth, VaultAuth):
            return None

        client = self.provider.auth.get_client()
        if not client:
            return None

        path = self.config.get("path")
        if not path:
            return None

        mount_point = self.config.get("mount_point", "secret")
        version = self.config.get("version", 2)

        try:
            if version == 2:
                # KV v2
                response = client.secrets.kv.v2.read_secret_version(
                    path=path, mount_point=mount_point
                )
                return response["data"]["data"]
            else:
                # KV v1
                response = client.secrets.kv.v1.read_secret(path=path, mount_point=mount_point)
                return response["data"]
        except Exception:
            return None

    def delete(self, secret_name: str) -> bool:
        """Delete secret from Vault KV.

        Args:
            secret_name: Name of the secret

        Returns:
            True if successful, False otherwise
        """
        try:
            import hvac
        except ImportError:
            return False

        from secretzero.providers.vault import VaultAuth

        if not isinstance(self.provider.auth, VaultAuth):
            return False

        client = self.provider.auth.get_client()
        if not client:
            return False

        path = self.config.get("path")
        if not path:
            return False

        mount_point = self.config.get("mount_point", "secret")
        version = self.config.get("version", 2)

        try:
            if version == 2:
                # KV v2: delete metadata (all versions)
                client.secrets.kv.v2.delete_metadata_and_all_versions(
                    path=path, mount_point=mount_point
                )
            else:
                # KV v1
                client.secrets.kv.v1.delete_secret(path=path, mount_point=mount_point)
            return True
        except Exception:
            return False
