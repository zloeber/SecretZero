"""Infisical provider for secret retrieval and storage."""

import logging
import os
from typing import Optional

from pydantic import BaseModel, Field

from secretzero.models import AuthKind
from secretzero.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class InfisicalConfig(BaseModel):
    """Configuration for Infisical provider."""

    api_url: str = Field(
        default="https://app.infisical.com/api",
        description="Infisical API endpoint URL",
    )
    workspace_id: str = Field(description="Infisical workspace ID")
    project_id: str = Field(default="", description="Infisical project ID (optional)")
    environment: str = Field(
        default="dev", description="Target environment (dev, staging, prod, etc.)"
    )
    auth_kind: AuthKind = Field(
        default=AuthKind.TOKEN, description="Authentication method (token or service_token)"
    )
    timeout: int = Field(default=30, gt=0, description="Request timeout in seconds")


class InfisicalProvider(BaseProvider):
    """Provider for Infisical centralized secret management platform.

    Infisical is an open-source secret management platform that provides
    centralized secret storage, rotation, and access control across teams
    and environments.

    Supports both retrieving secrets from Infisical and storing secrets into it,
    making it suitable as both a secret source and target.
    """

    config: InfisicalConfig
    _client: object | None = None

    @property
    def provider_kind(self) -> str:
        """Return provider type identifier."""
        return "infisical"

    def _get_client(self) -> object:
        """Get or create HTTP client with authentication.

        Returns:
            httpx.Client: Authenticated HTTP client

        Raises:
            ValueError: If authentication fails
        """
        if self._client is None:
            try:
                import httpx

                token = self._get_auth_token()
                self._client = httpx.Client(
                    base_url=self.config.api_url,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=self.config.timeout,
                )
            except ImportError as e:
                raise ValueError(
                    "httpx library required for Infisical provider. "
                    "Install with: pip install secretzero[infisical]"
                ) from e

        return self._client

    def _get_auth_token(self) -> str:
        """Retrieve authentication token from environment.

        Checks environment variables in order:
        1. INFISICAL_TOKEN
        2. INFISICAL_SERVICE_TOKEN

        Returns:
            str: Authentication token

        Raises:
            ValueError: If no valid token environment variable is found
        """
        token = os.getenv("INFISICAL_TOKEN") or os.getenv("INFISICAL_SERVICE_TOKEN")

        if not token:
            raise ValueError(
                "Infisical authentication required. "
                "Set INFISICAL_TOKEN or INFISICAL_SERVICE_TOKEN environment variable. "
                "Get tokens from: https://app.infisical.com/settings/tokens"
            )

        return token

    def validate_connection(self) -> bool:
        """Test connectivity to Infisical API.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            import httpx

            client = self._get_client()
            response = client.get(f"/v1/workspaces/{self.config.workspace_id}")

            if response.status_code == 200:
                logger.info("Infisical connection validation successful")
                return True

            logger.warning(f"Infisical connection returned status {response.status_code}")
            return False

        except ValueError as e:
            logger.error(f"Infisical auth validation failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Infisical connection validation failed: {e}")
            return False

    def test_connection(self) -> tuple[bool, str | None]:
        """Test provider connectivity.

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            if self.validate_connection():
                return (True, None)
            return (False, "Failed to connect to Infisical API")
        except Exception as e:
            return (False, str(e))

    def get_supported_targets(self) -> list[str]:
        """Get list of supported target types for this provider.

        Infisical can be used as a target to store secrets.

        Returns:
            List of target type names
        """
        return ["infisical"]

    def get_secret(self, secret_name: str) -> str:
        """Retrieve secret value from Infisical.

        Args:
            secret_name: Name of the secret to retrieve

        Returns:
            str: Secret value

        Raises:
            ValueError: If secret retrieval fails
        """
        try:
            import httpx

            client = self._get_client()
            response = client.get(
                f"/v1/secrets/{secret_name}",
                params={
                    "workspaceId": self.config.workspace_id,
                    "environment": self.config.environment,
                },
            )
            response.raise_for_status()

            secret_data = response.json()
            secret_value = secret_data.get("secret", {}).get("secretValue", "")

            if not secret_value:
                raise ValueError(f"Secret '{secret_name}' has no value in Infisical")

            logger.debug(f"Retrieved secret '{secret_name}' from Infisical")
            return secret_value

        except httpx.HTTPError as e:
            if e.response and e.response.status_code == 404:
                raise ValueError(
                    f"Secret '{secret_name}' not found in Infisical environment '{self.config.environment}'"
                ) from e

            raise ValueError(
                f"Failed to retrieve secret '{secret_name}' from Infisical: {e}"
            ) from e
        except ImportError as e:
            raise ValueError(
                "httpx library required. Install with: pip install secretzero[infisical]"
            ) from e
        except Exception as e:
            raise ValueError(f"Unexpected error retrieving secret from Infisical: {e}") from e

    def store_secret(self, secret_name: str, secret_value: str) -> None:
        """Store secret value in Infisical.

        Args:
            secret_name: Name of the secret
            secret_value: Secret value to store

        Raises:
            ValueError: If storage fails
        """
        try:
            import httpx

            client = self._get_client()
            response = client.post(
                f"/v1/secrets/{secret_name}",
                json={
                    "secretValue": secret_value,
                    "workspaceId": self.config.workspace_id,
                    "environment": self.config.environment,
                },
            )
            response.raise_for_status()

            logger.info(
                f"Stored secret '{secret_name}' in Infisical "
                f"environment '{self.config.environment}'"
            )

        except httpx.HTTPError as e:
            raise ValueError(f"Failed to store secret '{secret_name}' in Infisical: {e}") from e
        except ImportError as e:
            raise ValueError(
                "httpx library required. Install with: pip install secretzero[infisical]"
            ) from e
        except Exception as e:
            raise ValueError(f"Unexpected error storing secret in Infisical: {e}") from e

    def delete_secret(self, secret_name: str) -> None:
        """Delete secret from Infisical.

        Args:
            secret_name: Name of the secret to delete

        Raises:
            ValueError: If deletion fails
        """
        try:
            import httpx

            client = self._get_client()
            response = client.delete(
                f"/v1/secrets/{secret_name}",
                params={
                    "workspaceId": self.config.workspace_id,
                    "environment": self.config.environment,
                },
            )
            response.raise_for_status()

            logger.info(
                f"Deleted secret '{secret_name}' from Infisical "
                f"environment '{self.config.environment}'"
            )

        except httpx.HTTPError as e:
            raise ValueError(f"Failed to delete secret '{secret_name}' from Infisical: {e}") from e
        except ImportError as e:
            raise ValueError(
                "httpx library required. Install with: pip install secretzero[infisical]"
            ) from e
        except Exception as e:
            raise ValueError(f"Unexpected error deleting secret from Infisical: {e}") from e

    def __del__(self) -> None:
        """Cleanup HTTP client on deletion."""
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Bundle manifest – makes this provider extractable as a standalone package.
# When extracted, expose this via entry_points:
#   [project.entry-points."secretzero.providers"]
#   infisical = "secretzero_infisical:BUNDLE_MANIFEST"
# ---------------------------------------------------------------------------


def _get_bundle_manifest() -> "BundleManifest":  # noqa: F821
    """Lazily construct the Infisical bundle manifest."""
    from secretzero.bundles.registry import BundleManifest

    return BundleManifest(
        name="infisical",
        version="1.0.0",
        provider_class="secretzero.providers.infisical:InfisicalProvider",
        generators={},
        targets={},
        generator_kinds=[],
        target_kinds=[],
    )
