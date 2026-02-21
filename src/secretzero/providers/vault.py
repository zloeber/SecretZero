"""HashiCorp Vault provider implementation for SecretZero."""

import os
import secrets
from typing import Any

from secretzero.providers.base import BaseProvider, ProviderAuth


class VaultAuth(ProviderAuth):
    """HashiCorp Vault authentication handler.

    Supports authentication via:
    - Token authentication
    - AppRole authentication
    - Kubernetes authentication

    Environment variables checked:
    - VAULT_ADDR: Vault server URL
    - VAULT_TOKEN: Vault token (for token authentication)
    - VAULT_NAMESPACE: Vault namespace (optional)
    """

    # Environment variables for Vault configuration
    ENV_ADDR = "VAULT_ADDR"
    ENV_TOKEN = "VAULT_TOKEN"
    ENV_NAMESPACE = "VAULT_NAMESPACE"

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize Vault authentication.

        Args:
            config: Authentication configuration including:
                - kind: Authentication method (token, approle, kubernetes)
                - url: Vault server URL (or set VAULT_ADDR env var)
                - token: Vault token (or set VAULT_TOKEN env var, for token auth)
                - role_id: Role ID (for approle auth)
                - secret_id: Secret ID (for approle auth)
                - namespace: Vault namespace (or set VAULT_NAMESPACE env var, optional)
        """
        super().__init__(config)
        self._client = None

    def authenticate(self) -> bool:
        """Authenticate with Vault.

        Returns:
            True if authentication successful, False otherwise

        Attempts to authenticate using:
            1. Explicit credentials from config
            2. Environment variables (VAULT_ADDR, VAULT_TOKEN, VAULT_NAMESPACE)
        """
        try:
            import hvac
        except ImportError:
            return False

        try:
            auth_kind = self.config.get("kind", "token")
            url = self.config.get("url") or os.environ.get(self.ENV_ADDR, "http://localhost:8200")
            namespace = self.config.get("namespace") or os.environ.get(self.ENV_NAMESPACE)

            self._client = hvac.Client(url=url, namespace=namespace)

            if auth_kind == "token":
                token = self.config.get("token") or os.environ.get(self.ENV_TOKEN)
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

    @property
    def provider_kind(self) -> str:
        """Return provider type identifier."""
        return "vault"

    def test_connection(self) -> tuple[bool, str | None]:
        """Test Vault connectivity.

        Returns:
            Tuple of (success: bool, error_message: Optional[str])

        Checks:
        - Vault server URL (VAULT_ADDR env var or config)
        - Authentication credentials (VAULT_TOKEN env var or config)
        """
        try:
            import hvac
        except ImportError:
            return False, "hvac not installed. Install with: pip install secretzero[vault]"

        # Check if URL and token are available
        _ = self.config.get("url") or os.environ.get(VaultAuth.ENV_ADDR)
        token = self.config.get("token") or os.environ.get(VaultAuth.ENV_TOKEN)

        auth_kind = self.config.get("kind", "token")
        if auth_kind == "token" and not token:
            return (
                False,
                f"No Vault token found. Set config 'token' or {VaultAuth.ENV_TOKEN} env var",
            )

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

    # ============================================================================
    # Capability Methods: Generate
    # ============================================================================

    def generate_password(
        self,
        length: int = 32,
        special_chars: bool = True,
        uppercase: bool = True,
        lowercase: bool = True,
        numbers: bool = True,
    ) -> str:
        """Generate a random password using cryptographic randomness.

        Args:
            length: Password length (min 8, max 256)
            special_chars: Include special characters (!@#$%^&*)
            uppercase: Include uppercase letters
            lowercase: Include lowercase letters
            numbers: Include digits

        Returns:
            Generated password string

        Raises:
            ValueError: If length < 8 or no character types selected
        """
        if length < 8 or length > 256:
            raise ValueError("Password length must be between 8 and 256")

        if not any([special_chars, uppercase, lowercase, numbers]):
            raise ValueError("At least one character type must be selected")

        # Build character pool
        char_pool = ""
        if uppercase:
            char_pool += "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        if lowercase:
            char_pool += "abcdefghijklmnopqrstuvwxyz"
        if numbers:
            char_pool += "0123456789"
        if special_chars:
            char_pool += "!@#$%^&*-_+=()[]{}|:;<>,.?/"

        # Generate password with cryptographic randomness
        password = "".join(secrets.choice(char_pool) for _ in range(length))
        return password

    def generate_api_token(
        self,
        token_type: str = "auth",
        ttl: str = "720h",
    ) -> str:
        """Generate an authentication token.

        Note: This is a generic token generation. For Vault integration,
        use service_auth or app_role authentication for production.

        Args:
            token_type: Token type (auth, service, oauth)
            ttl: Token TTL (e.g., "1h", "24h", "720h")

        Returns:
            Generated token string
        """
        # For now, generate a random token
        # In production, would use Vault's auth endpoints
        token = secrets.token_urlsafe(32)
        return token

    # ============================================================================
    # Capability Methods: Retrieve
    # ============================================================================

    def retrieve_secret(
        self,
        secret_path: str,
        field: str | None = None,
        version: int | None = None,
    ) -> str:
        """Retrieve a secret from Vault KV v2 engine.

        Args:
            secret_path: Path to secret (e.g., "secret/myapp/api-key")
            field: Specific field to retrieve from secret data
            version: Specific version to retrieve

        Returns:
            Secret value as string

        Raises:
            ValueError: If secret not found or authentication fails
        """
        try:
            if not isinstance(self.auth, VaultAuth):
                raise ValueError("Invalid authentication configuration")

            client = self.auth.get_client()
            if not client:
                raise ValueError("Not authenticated with Vault")

            # Read secret from KV v2
            response = client.secrets.kv.v2.read_secret_version(
                path=secret_path,
                version=version,
            )

            secret_data = response["data"]["data"]

            # Return full data as JSON string if no field specified
            if field is None:
                import json

                return json.dumps(secret_data)

            # Return specific field
            if field not in secret_data:
                raise ValueError(f"Field '{field}' not found in secret")

            value = secret_data[field]
            return str(value) if value is not None else ""

        except Exception as e:
            raise ValueError(f"Failed to retrieve secret from Vault: {str(e)}")

    # ============================================================================
    # Capability Methods: Store
    # ============================================================================

    def store_secret(
        self,
        secret_path: str,
        secret_data: dict[str, str],
        cas: int = 0,
    ) -> bool:
        """Store a secret in Vault KV v2 engine.

        Args:
            secret_path: Path to store secret at
            secret_data: Dictionary of key-value pairs to store
            cas: Check-and-set version for optimistic locking

        Returns:
            True if successful

        Raises:
            ValueError: If storage fails
        """
        try:
            if not isinstance(self.auth, VaultAuth):
                raise ValueError("Invalid authentication configuration")

            client = self.auth.get_client()
            if not client:
                raise ValueError("Not authenticated with Vault")

            # Create or update secret
            kwargs = {"path": secret_path, "secret": secret_data}
            if cas > 0:
                kwargs["cas"] = cas

            client.secrets.kv.v2.create_or_update_secret(**kwargs)
            return True

        except Exception as e:
            raise ValueError(f"Failed to store secret in Vault: {str(e)}")

    # ============================================================================
    # Capability Methods: Rotate
    # ============================================================================

    def rotate_secret(
        self,
        secret_path: str,
        new_value: str,
        field: str = "value",
    ) -> bool:
        """Rotate a secret by updating its value.

        Args:
            secret_path: Path to secret to rotate
            new_value: New secret value
            field: Field name to update (default: "value")

        Returns:
            True if successful

        Raises:
            ValueError: If rotation fails
        """
        try:
            if not isinstance(self.auth, VaultAuth):
                raise ValueError("Invalid authentication configuration")

            client = self.auth.get_client()
            if not client:
                raise ValueError("Not authenticated with Vault")

            # Read current secret
            response = client.secrets.kv.v2.read_secret_version(path=secret_path)
            secret_data = response["data"]["data"]

            # Update the specified field
            secret_data[field] = new_value

            # Store updated secret
            client.secrets.kv.v2.create_or_update_secret(
                path=secret_path,
                secret=secret_data,
            )
            return True

        except Exception as e:
            raise ValueError(f"Failed to rotate secret in Vault: {str(e)}")

    # ============================================================================
    # Capability Methods: Delete
    # ============================================================================

    def delete_secret(
        self,
        secret_path: str,
        versions: list[int] | None = None,
    ) -> bool:
        """Delete a secret or specific versions from Vault.

        Args:
            secret_path: Path to secret to delete
            versions: Specific versions to delete (None = delete all)

        Returns:
            True if successful
        """
        try:
            if not isinstance(self.auth, VaultAuth):
                raise ValueError("Invalid authentication configuration")

            client = self.auth.get_client()
            if not client:
                raise ValueError("Not authenticated with Vault")

            if versions:
                # Delete specific versions
                client.secrets.kv.v2.delete_secret_versions(
                    path=secret_path,
                    versions=versions,
                )
            else:
                # Delete entire secret
                client.secrets.kv.v2.delete_secret_metadata(path=secret_path)
            return True

        except Exception as e:
            raise ValueError(f"Failed to delete secret from Vault: {str(e)}")
