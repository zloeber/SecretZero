"""Ansible Vault provider for local encrypted file-based secrets."""

import io
import json
import os
from pathlib import Path
from typing import Any

import yaml

from secretzero.providers.base import BaseProvider, ProviderAuth


class AnsibleVaultAuth(ProviderAuth):
    """Ansible Vault authentication handler.

    The vault password is the only credential required.  It can be supplied
    directly in the provider config or via an environment variable.

    Environment variables checked:
    - ANSIBLE_VAULT_PASSWORD: Vault password (default env var name)
    """

    # Default environment variable for the vault password
    ENV_PASSWORD = "ANSIBLE_VAULT_PASSWORD"

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize Ansible Vault authentication.

        Args:
            config: Authentication configuration containing:
                - vault_password: Vault encryption password
                    (or set ANSIBLE_VAULT_PASSWORD env var)
                - vault_password_env: Override the default env-var name
        """
        super().__init__(config)

    def authenticate(self) -> bool:
        """Verify that a vault password is available.

        Returns:
            True if a password is available, False otherwise.
        """
        return self.get_password() is not None

    def is_authenticated(self) -> bool:
        """Check if a vault password is available.

        Returns:
            True if a password is available, False otherwise.
        """
        return self.authenticate()

    def get_password(self) -> str | None:
        """Return the vault password from config or environment.

        Returns:
            Vault password string, or None if not configured.
        """
        # Explicit password takes precedence
        password = self.config.get("vault_password")
        if password:
            return str(password)

        # Optional custom env-var name
        env_var = self.config.get("vault_password_env", self.ENV_PASSWORD)
        return os.environ.get(env_var)


class AnsibleVaultProvider(BaseProvider):
    """Local file provider that transparently encrypts/decrypts files with Ansible Vault.

    This provider stores and retrieves secrets from a local file that is
    encrypted at rest using Ansible Vault.  It supports the same file formats
    as the built-in file target (dotenv, json, yaml) and auto-decrypts on
    reads and auto-encrypts on writes.

    Configuration options:
        vault_file (str): Path to the Ansible Vault encrypted file.
        format (str): Data format inside the vault: "yaml" (default), "json",
            or "dotenv".

    Authentication (via ``auth`` config or top-level config):
        vault_password (str): Vault password.
        vault_password_env (str): Name of the env-var that holds the password
            (default: ``ANSIBLE_VAULT_PASSWORD``).

    Example Secretfile provider block::

        providers:
          my_vault:
            kind: ansible_vault
            vault_file: secrets/vault.yml
            vault_password_env: MY_VAULT_PASS
            format: yaml
    """

    display_name = "Ansible Vault"
    description = "Ansible Vault encrypted file storage"
    required_package = ("ansible_vault", "secretzero[ansible_vault]")
    auth_class = AnsibleVaultAuth
    auth_methods = {
        "password": "Use Ansible Vault password",
        "password_env": "Use environment variable for vault password",
    }
    config_options = {
        "vault_file": "Path to the Ansible Vault encrypted file",
        "format": "Data format: yaml, json, or dotenv (default: yaml)",
    }
    config_example = """providers:
  my_vault:
    kind: ansible_vault
    vault_file: secrets/vault.yml
    vault_password_env: MY_VAULT_PASS
    format: yaml"""
    target_details = {}

    def __init__(
        self,
        name: str,
        config: dict[str, Any] | None = None,
        auth: AnsibleVaultAuth | None = None,
    ):
        """Initialize Ansible Vault provider.

        Args:
            name: Provider name.
            config: Provider configuration.
            auth: Optional pre-configured auth handler.
        """
        if auth is None:
            cfg = config or {}
            auth_config: dict[str, Any] = dict(cfg.get("auth", {}))
            # Allow vault_password / vault_password_env at the top level
            for key in ("vault_password", "vault_password_env"):
                if key in cfg:
                    auth_config[key] = cfg[key]
            auth = AnsibleVaultAuth(auth_config)

        super().__init__(name, config, auth)

    @property
    def provider_kind(self) -> str:
        """Return provider type identifier."""
        return "ansible_vault"

    def get_actor_info(self) -> dict[str, Any]:
        """Return information about the local actor using Ansible Vault."""
        # Ansible Vault operates locally; rely on base local actor info.
        return super().get_actor_info()

    def test_connection(self) -> tuple[bool, str | None]:
        """Verify provider configuration and vault file accessibility.

        Returns:
            Tuple of (success, message).
        """
        try:
            import ansible_vault  # noqa: F401
        except ImportError:
            return (
                False,
                "ansible-vault not installed. Install with: pip install secretzero[ansible_vault]",
            )

        vault_file = self._get_vault_file()
        if vault_file is None:
            return False, "vault_file not configured"

        password = self._get_password()
        if not password:
            return (
                False,
                "No vault password found. Set 'vault_password' in config or "
                f"{AnsibleVaultAuth.ENV_PASSWORD} env var",
            )

        # If the file already exists, verify we can decrypt it
        if vault_file.exists():
            try:
                self._read_vault(vault_file, password)
            except Exception as e:
                return False, f"Failed to decrypt vault file '{vault_file}': {e}"

        return True, f"Ansible Vault provider ready (file: {vault_file})"

    def get_supported_targets(self) -> list[str]:
        """Return supported target types.

        Returns:
            List of supported target type identifiers.
        """
        return ["file"]

    # ============================================================================
    # Capability Methods: Retrieve
    # ============================================================================

    def retrieve_secret(self, secret_name: str) -> str:
        """Retrieve a single secret value from the encrypted vault file.

        Args:
            secret_name: Key of the secret to retrieve.

        Returns:
            Secret value as a string.

        Raises:
            ValueError: If the vault file does not exist, the password is
                missing, or the key is not found.
        """
        vault_file = self._get_vault_file()
        if vault_file is None:
            raise ValueError("vault_file not configured")
        if not vault_file.exists():
            raise ValueError(f"Vault file not found: {vault_file}")

        password = self._get_password()
        if not password:
            raise ValueError("vault_password not configured")

        data = self._read_vault(vault_file, password)
        if secret_name not in data:
            raise ValueError(f"Secret '{secret_name}' not found in vault file '{vault_file}'")

        return str(data[secret_name])

    # ============================================================================
    # Capability Methods: Store
    # ============================================================================

    def store_secret(self, secret_name: str, secret_value: str) -> bool:
        """Store a secret in the encrypted vault file.

        If the vault file already exists it is decrypted, the key is
        updated (or added), and the file is re-encrypted.  If the file does
        not exist it is created and encrypted from scratch.

        Args:
            secret_name: Key of the secret.
            secret_value: Value to store.

        Returns:
            True if the operation succeeded.

        Raises:
            ValueError: If the vault file path or password is not configured.
        """
        vault_file = self._get_vault_file()
        if vault_file is None:
            raise ValueError("vault_file not configured")

        password = self._get_password()
        if not password:
            raise ValueError("vault_password not configured")

        # Read existing secrets (if any)
        data: dict[str, str] = {}
        if vault_file.exists():
            data = self._read_vault(vault_file, password)

        data[secret_name] = secret_value
        self._write_vault(vault_file, password, data)
        return True

    # ============================================================================
    # Capability Methods: Delete
    # ============================================================================

    def delete_secret(self, secret_name: str) -> bool:
        """Remove a secret from the encrypted vault file.

        Args:
            secret_name: Key of the secret to delete.

        Returns:
            True if the key was present and removed, False if not found.

        Raises:
            ValueError: If the vault file does not exist or password is missing.
        """
        vault_file = self._get_vault_file()
        if vault_file is None:
            raise ValueError("vault_file not configured")
        if not vault_file.exists():
            raise ValueError(f"Vault file not found: {vault_file}")

        password = self._get_password()
        if not password:
            raise ValueError("vault_password not configured")

        data = self._read_vault(vault_file, password)
        if secret_name not in data:
            return False

        del data[secret_name]
        self._write_vault(vault_file, password, data)
        return True

    # ============================================================================
    # Private helpers
    # ============================================================================

    def _get_vault_file(self) -> Path | None:
        """Return the configured vault file path, or None if not set."""
        vault_file = self.config.get("vault_file")
        return Path(vault_file) if vault_file else None

    def _get_password(self) -> str | None:
        """Return the vault password via the auth handler."""
        if isinstance(self.auth, AnsibleVaultAuth):
            return self.auth.get_password()
        return None

    def _read_vault(self, vault_file: Path, password: str) -> dict[str, str]:
        """Decrypt the vault file and return its contents as a dictionary.

        Args:
            vault_file: Path to the encrypted vault file.
            password: Vault password for decryption.

        Returns:
            Dictionary of secret key/value pairs.

        Raises:
            ValueError: If the vault file content cannot be decrypted or parsed.
        """
        try:
            from ansible_vault import Vault
        except ImportError:
            raise ValueError(
                "ansible-vault not installed. Install with: pip install secretzero[ansible_vault]"
            )

        try:
            vault = Vault(password)
            content = vault_file.read_text()
            plain_text = vault.load_raw(content)
            if isinstance(plain_text, bytes):
                plain_text = plain_text.decode("utf-8")
        except Exception as e:
            raise ValueError(f"Failed to decrypt vault file: {e}") from e

        fmt = self.config.get("format", "yaml")

        try:
            if fmt == "yaml":
                data = yaml.safe_load(plain_text) or {}
            elif fmt == "json":
                data = json.loads(plain_text) if plain_text.strip() else {}
            elif fmt == "dotenv":
                data = self._parse_dotenv(plain_text)
            else:
                raise ValueError(f"Unsupported format: {fmt}")
        except (yaml.YAMLError, json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"Failed to parse decrypted vault content as {fmt}: {e}") from e

        if data is None:
            return {}
        if not isinstance(data, dict):
            raise ValueError(
                f"Vault file must contain a {fmt} mapping at the top level, "
                f"got {type(data).__name__}"
            )

        return {str(k): str(v) for k, v in data.items()}

    def _write_vault(self, vault_file: Path, password: str, data: dict[str, str]) -> None:
        """Serialize *data* and write it to *vault_file* encrypted with Ansible Vault.

        Args:
            vault_file: Destination path for the encrypted file.
            password: Vault password for encryption.
            data: Dictionary of secret key/value pairs to encrypt.

        Raises:
            ValueError: If the ansible-vault library is not installed or
                encryption fails.
        """
        try:
            from ansible_vault import Vault
        except ImportError:
            raise ValueError(
                "ansible-vault not installed. Install with: pip install secretzero[ansible_vault]"
            )

        fmt = self.config.get("format", "yaml")

        if fmt == "yaml":
            plain_text = yaml.dump(
                data,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )
        elif fmt == "json":
            plain_text = json.dumps(data, indent=2)
        elif fmt == "dotenv":
            plain_text = self._format_dotenv(data)
        else:
            raise ValueError(f"Unsupported format: {fmt}")

        try:
            vault = Vault(password)
            stream = io.StringIO()
            vault.dump_raw(plain_text, stream)
            encrypted = stream.getvalue()
        except Exception as e:
            raise ValueError(f"Failed to encrypt vault file: {e}") from e

        vault_file.parent.mkdir(parents=True, exist_ok=True)
        vault_file.write_text(encrypted)

    @staticmethod
    def _parse_dotenv(content: str) -> dict[str, str]:
        """Parse dotenv-format text into a dictionary.

        Args:
            content: dotenv-formatted string.

        Returns:
            Dictionary of key/value pairs.
        """
        result: dict[str, str] = {}
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if value and value[0] in ('"', "'") and value[-1] == value[0]:
                    value = value[1:-1]
                result[key] = value
        return result

    @staticmethod
    def _format_dotenv(data: dict[str, str]) -> str:
        """Format a dictionary as dotenv content.

        Args:
            data: Key/value pairs to format.

        Returns:
            dotenv-formatted string.
        """
        lines = []
        for key, value in data.items():
            if " " in value or any(c in value for c in ['"', "'", "$", "\\", "\n"]):
                value = f'"{value}"'
            lines.append(f"{key}={value}")
        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Bundle manifest – makes this provider extractable as a standalone package.
# When extracted, expose this via entry_points:
#   [project.entry-points."secretzero.providers"]
#   ansible_vault = "secretzero_ansible_vault:BUNDLE_MANIFEST"
# ---------------------------------------------------------------------------


def _get_bundle_manifest() -> "BundleManifest":  # noqa: F821
    """Lazily construct the Ansible Vault bundle manifest."""
    from secretzero.bundles.registry import BundleManifest

    return BundleManifest(
        name="ansible_vault",
        version="1.0.0",
        provider_class="secretzero.providers.ansible_vault:AnsibleVaultProvider",
        generators={},
        targets={},
        generator_kinds=[],
        target_kinds=[],
        terraform_provider=None,
    )
