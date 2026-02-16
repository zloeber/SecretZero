"""GitHub Actions secret targets."""

import base64
from typing import Any, Optional

from secretzero.targets.base import BaseTarget


class GitHubSecretTarget(BaseTarget):
    """Store secrets in GitHub Actions."""

    def __init__(self, provider: Any, config: Optional[dict[str, Any]] = None):
        """Initialize GitHub secret target.

        Args:
            provider: GitHub provider instance.
            config: Target configuration containing:
                - owner: Repository owner (username or organization)
                - repo: Repository name
                - environment: Optional environment name for environment-specific secrets
        """
        super().__init__(config)
        self.provider = provider
        self.owner = self.config.get("owner")
        self.repo = self.config.get("repo")
        self.environment = self.config.get("environment")

        if not self.owner or not self.repo:
            raise ValueError("GitHub target requires 'owner' and 'repo' in config")

    def _encrypt_secret(self, public_key: str, secret_value: str) -> str:
        """Encrypt a secret using the repository's public key.

        Args:
            public_key: Base64-encoded public key from GitHub.
            secret_value: Secret value to encrypt.

        Returns:
            Base64-encoded encrypted value.
        """
        try:
            from nacl import encoding, public
        except ImportError:
            raise ImportError("PyNaCl not installed (pip install PyNaCl)")

        # Decode the public key
        public_key_bytes = base64.b64decode(public_key)
        sealed_box = public.SealedBox(public.PublicKey(public_key_bytes))
        
        # Encrypt the secret
        encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
        
        # Base64 encode the encrypted value
        return base64.b64encode(encrypted).decode("utf-8")

    def store(self, secret_name: str, secret_value: str) -> bool:
        """Store secret in GitHub Actions.

        Args:
            secret_name: Name of the secret.
            secret_value: Value of the secret.

        Returns:
            True if storage successful, False otherwise.
        """
        try:
            client = self.provider.auth.get_client()
            repo = client.get_repo(f"{self.owner}/{self.repo}")

            if self.environment:
                # Store as environment secret
                # Get public key for environment
                public_key = repo.get_environment(self.environment).get_secrets_public_key()
                encrypted_value = self._encrypt_secret(public_key.key, secret_value)
                
                # Create or update environment secret
                repo.get_environment(self.environment).create_secret(
                    secret_name=secret_name,
                    unencrypted_value=secret_value
                )
            else:
                # Store as repository secret
                # Get public key for repository
                public_key = repo.get_public_key()
                encrypted_value = self._encrypt_secret(public_key.key, secret_value)
                
                # Create or update repository secret
                repo.create_secret(
                    secret_name=secret_name,
                    unencrypted_value=secret_value
                )
            
            return True
        except Exception as e:
            print(f"Failed to store secret in GitHub: {e}")
            return False

    def retrieve(self, secret_name: str) -> Optional[str]:
        """Retrieve secret from GitHub Actions.

        Note: GitHub API does not allow retrieving secret values.
        
        Args:
            secret_name: Name of the secret.

        Returns:
            None (secrets cannot be retrieved from GitHub Actions).
        """
        # GitHub API does not expose secret values
        return None


class GitHubOrganizationSecretTarget(BaseTarget):
    """Store secrets in GitHub Organization-level Actions."""

    def __init__(self, provider: Any, config: Optional[dict[str, Any]] = None):
        """Initialize GitHub organization secret target.

        Args:
            provider: GitHub provider instance.
            config: Target configuration containing:
                - org: Organization name
                - visibility: Secret visibility (all, private, selected)
                - selected_repository_ids: List of repo IDs if visibility is 'selected'
        """
        super().__init__(config)
        self.provider = provider
        self.org = self.config.get("org")
        self.visibility = self.config.get("visibility", "all")
        self.selected_repository_ids = self.config.get("selected_repository_ids", [])

        if not self.org:
            raise ValueError("GitHub organization target requires 'org' in config")

    def _encrypt_secret(self, public_key: str, secret_value: str) -> str:
        """Encrypt a secret using the organization's public key.

        Args:
            public_key: Base64-encoded public key from GitHub.
            secret_value: Secret value to encrypt.

        Returns:
            Base64-encoded encrypted value.
        """
        try:
            from nacl import encoding, public
        except ImportError:
            raise ImportError("PyNaCl not installed (pip install PyNaCl)")

        # Decode the public key
        public_key_bytes = base64.b64decode(public_key)
        sealed_box = public.SealedBox(public.PublicKey(public_key_bytes))
        
        # Encrypt the secret
        encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
        
        # Base64 encode the encrypted value
        return base64.b64encode(encrypted).decode("utf-8")

    def store(self, secret_name: str, secret_value: str) -> bool:
        """Store secret in GitHub Organization Actions.

        Args:
            secret_name: Name of the secret.
            secret_value: Value of the secret.

        Returns:
            True if storage successful, False otherwise.
        """
        try:
            client = self.provider.auth.get_client()
            org = client.get_organization(self.org)

            # Get public key for organization
            public_key = org.get_public_key()
            encrypted_value = self._encrypt_secret(public_key.key, secret_value)
            
            # Create or update organization secret
            org.create_secret(
                secret_name=secret_name,
                unencrypted_value=secret_value,
                visibility=self.visibility
            )
            
            return True
        except Exception as e:
            print(f"Failed to store secret in GitHub organization: {e}")
            return False

    def retrieve(self, secret_name: str) -> Optional[str]:
        """Retrieve secret from GitHub Organization Actions.

        Note: GitHub API does not allow retrieving secret values.
        
        Args:
            secret_name: Name of the secret.

        Returns:
            None (secrets cannot be retrieved from GitHub Actions).
        """
        # GitHub API does not expose secret values
        return None
