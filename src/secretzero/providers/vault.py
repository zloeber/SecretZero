"""HashiCorp Vault provider implementation for SecretZero."""

import json
import os
import secrets
from typing import Any

from secretzero.providers.base import BaseProvider, ProviderAuth

_KV_KIND_ALIASES = frozenset({"kv", "vault_kv", "kv2", "kv-v2", "kvv2"})
_KV1_KIND_ALIASES = frozenset({"kv1", "kv-v1", "kvv1"})
_CUBBYHOLE_ENGINES = frozenset({"cubbyhole", "cubby"})
_GENERIC_ENGINES = frozenset({"generic", "logical", "raw", "identity", "transit"})


def _nonempty_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def flatten_vault_auth_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Collapse Secretfile provider/auth shapes into a flat VaultAuth dict.

    Accepts nested ``auth.config``, sibling fields on ``auth`` (documented in
    examples as ``url`` / ``token`` next to ``kind``), ``address`` as an alias
    of ``url``, and top-level unit-test keys. Provider ``kind: vault`` is not
    treated as an authentication method.
    """
    src = dict(raw or {})
    merged: dict[str, Any] = {}

    def _merge_map(data: dict[str, Any]) -> None:
        for key, value in data.items():
            if key in {"config", "profiles", "fallback_generator", "auth"}:
                continue
            if value is None:
                continue
            merged[key] = value

    auth_block = src.get("auth")
    if isinstance(auth_block, dict):
        nested = auth_block.get("config")
        if isinstance(nested, dict):
            _merge_map(nested)
        _merge_map(auth_block)
    elif isinstance(src.get("config"), dict) and "auth" not in src:
        _merge_map(src["config"])

    for key in ("url", "address", "token", "namespace", "role_id", "secret_id"):
        if src.get(key) is not None and key not in merged:
            merged[key] = src[key]
    kind = src.get("kind")
    if kind is not None and "kind" not in merged and str(kind).lower() != "vault":
        merged["kind"] = kind

    if not _nonempty_str(merged.get("url")) and _nonempty_str(merged.get("address")):
        merged["url"] = merged["address"]
    return merged


def _normalize_kv_path(path: str, mount_point: str) -> str:
    """Strip mount / KV v2 ``data`` prefixes so hvac receives a relative path."""
    raw = path.strip().lstrip("/")
    mount = mount_point.strip().strip("/")
    prefixes = [f"{mount}/data/", f"{mount}/", "data/"]
    for prefix in prefixes:
        if raw.startswith(prefix):
            return raw[len(prefix) :]
    return raw


def _payload_from_logical_read(response: Any) -> dict[str, Any]:
    """Normalize ``client.read()`` / cubbyhole responses into a data mapping."""
    if not isinstance(response, dict):
        return {}
    data = response.get("data", response)
    return data if isinstance(data, dict) else {}


class VaultAuth(ProviderAuth):
    """HashiCorp Vault authentication handler.

    Supports authentication via:
    - Token / ambient (VAULT_TOKEN, config token, or ``~/.vault-token``)
    - AppRole authentication

    Environment variables checked:
    - VAULT_ADDR: Vault server URL
    - VAULT_TOKEN: Vault token (for token/ambient authentication)
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
                - kind: Authentication method (token, ambient, approle)
                - url / address: Vault server URL (or set VAULT_ADDR env var)
                - token: Vault token (or set VAULT_TOKEN env var, for token auth)
                - role_id: Role ID (for approle auth)
                - secret_id: Secret ID (for approle auth)
                - namespace: Vault namespace (or set VAULT_NAMESPACE env var, optional)
        """
        super().__init__(flatten_vault_auth_config(config))
        self._client = None

    def authenticate(self) -> bool:
        """Authenticate with Vault.

        Returns:
            True if authentication successful, False otherwise

        Attempts to authenticate using:
            1. Explicit credentials from config (flat or nested ``auth.config``)
            2. Environment variables (VAULT_ADDR, VAULT_TOKEN, VAULT_NAMESPACE)
            3. HVAC default token file (``~/.vault-token``) when no token is set
        """
        try:
            import hvac
        except ImportError:
            return False

        try:
            settings = flatten_vault_auth_config(self.config)
            auth_kind = str(settings.get("kind") or "token").lower()
            url = (
                _nonempty_str(settings.get("url"))
                or _nonempty_str(settings.get("address"))
                or _nonempty_str(os.environ.get(self.ENV_ADDR))
                or "http://localhost:8200"
            )
            namespace = _nonempty_str(settings.get("namespace")) or _nonempty_str(
                os.environ.get(self.ENV_NAMESPACE)
            )
            client_kwargs: dict[str, Any] = {"url": url}
            if namespace:
                client_kwargs["namespace"] = namespace

            if auth_kind == "approle":
                role_id = _nonempty_str(settings.get("role_id"))
                secret_id = _nonempty_str(settings.get("secret_id"))
                if not role_id or not secret_id:
                    return False
                self._client = hvac.Client(**client_kwargs)
                response = self._client.auth.approle.login(role_id=role_id, secret_id=secret_id)
                self._client.token = response["auth"]["client_token"]
            else:
                # token, ambient, default, or unknown: prefer explicit token, else env,
                # else let hvac read VAULT_TOKEN / ~/.vault-token.
                token = _nonempty_str(settings.get("token")) or _nonempty_str(
                    os.environ.get(self.ENV_TOKEN)
                )
                if token:
                    client_kwargs["token"] = token
                self._client = hvac.Client(**client_kwargs)

            return bool(self._client.is_authenticated())

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
        """Get Vault client, authenticating lazily when needed.

        Returns:
            HVAC client instance or None
        """
        if self._client is None or not self.is_authenticated():
            self.authenticate()
        return self._client

    def get_token_info(self) -> dict[str, Any]:
        """Return Vault token metadata via ``lookup-self`` (no secret values)."""
        if not self._client:
            raise RuntimeError("Not authenticated with Vault")
        if not self.is_authenticated():
            raise RuntimeError("Vault client is not authenticated")
        try:
            resp = self._client.auth.token.lookup_self()
        except Exception as e:
            raise RuntimeError(f"Vault token lookup-self failed: {e}") from e
        body: dict[str, Any]
        try:
            if hasattr(resp, "status_code") and getattr(resp, "status_code", 200) != 200:
                raise RuntimeError(f"Vault lookup-self HTTP {resp.status_code}")
            if hasattr(resp, "json"):
                parsed = resp.json()
            elif isinstance(resp, dict):
                parsed = resp
            else:
                raise RuntimeError("Unexpected Vault lookup-self response shape")
            if not isinstance(parsed, dict):
                raise RuntimeError("Unexpected Vault lookup-self response shape")
            body = parsed
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Vault lookup-self parse failed: {e}") from e

        data = body.get("data", body)
        if not isinstance(data, dict):
            data = {}
        policies: list[str] = []
        for key in ("policies", "identity_policies"):
            p = data.get(key)
            if isinstance(p, list):
                policies.extend(str(x) for x in p)
        user = data.get("display_name") or data.get("entity_id") or data.get("id")
        return {
            "user": user,
            "scopes": sorted(set(policies)),
            "token_type": str(data.get("type", "vault_token")),
            "renewable": data.get("renewable"),
        }


class VaultProvider(BaseProvider):
    """HashiCorp Vault provider for SecretZero."""

    display_name = "HashiCorp Vault"
    description = "Secret storage and management"
    required_package = ("hvac", "secretzero[vault]")
    auth_class = VaultAuth
    auth_methods = {
        "token": "Use Vault token authentication (VAULT_TOKEN or auth.config.token)",
        "ambient": "Use VAULT_ADDR / VAULT_TOKEN / ~/.vault-token (vault login)",
        "approle": "Use AppRole role_id and secret_id",
    }
    config_options = {
        "url": "Vault server URL (or VAULT_ADDR; address is accepted as an alias)",
        "namespace": "Vault namespace (Enterprise, or VAULT_NAMESPACE)",
        "token": "Vault token (or VAULT_TOKEN; omitted for ambient/user login)",
    }
    config_example = """providers:
  vault:
    kind: vault
    auth:
      kind: ambient
      config:
        url: ${VAULT_ADDR}"""
    target_details = {
        "vault_kv": {
            "description": "HashiCorp Vault KV Secret Engine",
            "config": {
                "path": "Secret path in KV engine (e.g., secret/data/myapp/config)",
                "mount_point": "KV mount point (default: secret)",
                "version": "KV version: 1 or 2 (default: 2)",
            },
            "example": """targets:
  - provider: vault
    kind: vault_kv
    config:
      path: secret/data/prod/database
      mount_point: secret
      version: 2""",
        },
    }

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
        if auth is None:
            auth = VaultAuth(flatten_vault_auth_config(config))

        super().__init__(name, config, auth)

    @property
    def provider_kind(self) -> str:
        """Return provider type identifier."""
        return "vault"

    def get_actor_info(self) -> dict[str, Any]:
        """Return information about the current Vault client/context."""
        info = super().get_actor_info()

        settings = flatten_vault_auth_config(
            self.auth.config if isinstance(self.auth, VaultAuth) else self.config
        )
        url = (
            _nonempty_str(settings.get("url"))
            or _nonempty_str((self.config or {}).get("url"))
            or os.environ.get(VaultAuth.ENV_ADDR)
        )
        namespace = (
            _nonempty_str(settings.get("namespace"))
            or _nonempty_str((self.config or {}).get("namespace"))
            or os.environ.get(VaultAuth.ENV_NAMESPACE)
        )
        if url:
            info.setdefault("url", url)
        if namespace:
            info.setdefault("namespace", namespace)

        return info

    def test_connection(self) -> tuple[bool, str | None]:
        """Test Vault connectivity.

        Returns:
            Tuple of (success: bool, error_message: Optional[str])

        Checks:
        - Vault server URL (VAULT_ADDR env var or config)
        - Authentication credentials (VAULT_TOKEN env var or config)
        """
        try:
            import hvac as _hvac
        except ImportError:
            return False, "hvac not installed. Install with: pip install secretzero[vault]"
        _ = _hvac

        if self.auth is None:
            self.auth = VaultAuth(flatten_vault_auth_config(self.config))

        if not self.is_authenticated():
            auth_success = self.authenticate()
            if not auth_success:
                return (
                    False,
                    "Vault authentication failed. Set VAULT_ADDR and VAULT_TOKEN "
                    "(or complete `vault login` so ~/.vault-token exists), "
                    "or configure auth.token / AppRole credentials.",
                )

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
        return ["kv", "vault_kv"]

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
        *,
        path: str | None = None,
        name: str | None = None,
        mount_point: str | None = None,
        kv_version: int | None = None,
        secret_version: int | None = None,
        engine: str | None = None,
        kind: str | None = None,
        profile: str | None = None,
        **_: Any,
    ) -> str:
        """Retrieve a secret from Vault KV or another logical path.

        Args:
            secret_path: Path to secret (e.g., "secret/myapp/api-key")
            field: Specific field to retrieve from secret data
            version: KV v2 secret version (existing capability API)
            path: Alternate locator used by ``provider_read`` ``read.path``
            name: Alternate locator used by ``provider_read`` ``read.name``
            mount_point: KV mount (default: ``secret``)
            kv_version: KV engine version 1 or 2 (default: 2)
            secret_version: Explicit KV v2 secret version
            engine: ``kv`` / ``kv1`` / ``cubbyhole`` / ``generic``
            kind: ``provider_read`` target kind (ignored except as engine hint)
            profile: ``provider_read`` profile (ignored)

        Returns:
            Secret value as string

        Raises:
            ValueError: If secret not found or authentication fails
        """
        _ = profile
        try:
            client = self._vault_client()
            locator = _nonempty_str(path) or _nonempty_str(name) or _nonempty_str(secret_path) or ""
            if not locator:
                raise ValueError("Vault retrieve requires a path, name, or secret_path")

            payload = self._read_vault_payload(
                client,
                locator=locator,
                mount_point=_nonempty_str(mount_point) or "secret",
                kv_version=kv_version,
                secret_version=secret_version if secret_version is not None else version,
                engine=engine,
                kind=kind,
            )
            if field is None:
                return json.dumps(payload)
            if field not in payload:
                raise ValueError(f"Field '{field}' not found in secret")
            value = payload[field]
            return str(value) if value is not None else ""

        except Exception as e:
            raise ValueError(f"Failed to retrieve secret from Vault: {str(e)}") from e

    def _vault_client(self) -> Any:
        if not isinstance(self.auth, VaultAuth):
            raise ValueError("Invalid authentication configuration")
        client = self.auth.get_client()
        if not client:
            raise ValueError("Not authenticated with Vault")
        return client

    def _read_vault_payload(
        self,
        client: Any,
        *,
        locator: str,
        mount_point: str,
        kv_version: int | None,
        secret_version: int | None,
        engine: str | None,
        kind: str | None,
    ) -> dict[str, Any]:
        engine_name = (engine or "").strip().lower()
        kind_name = (kind or "").strip().lower()
        if engine_name in _CUBBYHOLE_ENGINES or locator.startswith("cubbyhole/"):
            read_path = locator if locator.startswith("cubbyhole/") else f"cubbyhole/{locator}"
            return _payload_from_logical_read(client.read(read_path))
        if engine_name in _GENERIC_ENGINES or (
            kind_name in _GENERIC_ENGINES and kind_name not in _KV_KIND_ALIASES
        ):
            return _payload_from_logical_read(client.read(locator))

        use_v1 = (
            kv_version == 1 or engine_name in _KV1_KIND_ALIASES or kind_name in _KV1_KIND_ALIASES
        )
        kv_path = _normalize_kv_path(locator, mount_point)
        if use_v1:
            response = client.secrets.kv.v1.read_secret(path=kv_path, mount_point=mount_point)
            data = response.get("data", response) if isinstance(response, dict) else {}
            return data if isinstance(data, dict) else {}

        kwargs: dict[str, Any] = {"path": kv_path, "mount_point": mount_point}
        if secret_version is not None:
            kwargs["version"] = secret_version
        response = client.secrets.kv.v2.read_secret_version(**kwargs)
        wrapped = response.get("data", {}) if isinstance(response, dict) else {}
        data = wrapped.get("data", wrapped) if isinstance(wrapped, dict) else {}
        return data if isinstance(data, dict) else {}

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


# ---------------------------------------------------------------------------
# Bundle manifest – makes this provider extractable as a standalone package.
# When extracted, expose this via entry_points:
#   [project.entry-points."secretzero.providers"]
#   vault = "secretzero_vault:BUNDLE_MANIFEST"
# ---------------------------------------------------------------------------


def _get_bundle_manifest() -> "BundleManifest":  # noqa: F821
    """Lazily construct the Vault bundle manifest."""
    from secretzero.bundles.registry import BundleManifest

    return BundleManifest(
        name="vault",
        version="1.0.0",
        provider_class="secretzero.providers.vault:VaultProvider",
        generators={},
        targets={
            "vault_kv": "secretzero.targets.vault:VaultKVTarget",
            "kv": "secretzero.targets.vault:VaultKVTarget",
        },
        generator_kinds=[],
        target_kinds=["vault_kv", "kv"],
        terraform_provider={
            "name": "vault",
            "source": "hashicorp/vault",
            "version": "~> 4.0",
            "default_config": {},
        },
    )
