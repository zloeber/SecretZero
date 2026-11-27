"""HashiCorp Vault target implementations for SecretZero."""

from typing import Any

from secretzero.targets.base import BaseTarget


class VaultKVTarget(BaseTarget):
    """HashiCorp Vault KV target.

    Without ``config.field``, a write replaces the whole document. Strings are
    stored under the key ``value``. With ``field``, a write updates only that
    key and leaves sibling keys in place. KV v2 uses read plus check-and-set.
    KV v1 has no CAS, so the same read-modify-write is last-writer-wins.
    """

    def __init__(
        self,
        provider: Any,
        config: dict[str, Any] | None = None,
    ):
        """Initialize Vault KV target.

        Args:
            provider: Vault provider instance
            config: Target configuration including:
                - path: Secret path in the KV engine
                - mount_point: KV mount point (default: "secret")
                - version: KV version (1 or 2, default: 2)
                - field: Optional key to merge into an existing document
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
        _ = secret_name
        try:
            client = self._client()
            if client is None:
                return False
            location = self._location()
            if location is None:
                return False
            path, mount_point, version = location
            field = self._field_name()
            if field is None:
                return self._write_document(
                    client,
                    path,
                    mount_point,
                    version,
                    self._whole_document(secret_value),
                    cas=None,
                )

            current, cas = self._read_for_merge(client, path, mount_point, version)
            merged = dict(current)
            merged[field] = self._field_value(secret_value)
            return self._write_document(
                client,
                path,
                mount_point,
                version,
                merged,
                cas=cas if version == 2 else None,
            )
        except Exception:
            return False

    def retrieve(self, secret_name: str) -> Any | None:
        """Retrieve secret from Vault KV.

        Args:
            secret_name: Name of the secret

        Returns:
            Secret value or None if not found. With ``field`` set, returns that
            key only so status and drift compare the same value that was stored.
        """
        _ = secret_name
        try:
            client = self._client()
            if client is None:
                return None
            location = self._location()
            if location is None:
                return None
            path, mount_point, version = location
            found, data, _version = self._read_map(client, path, mount_point, version)
            if not found or data is None:
                return None
            field = self._field_name()
            if field is None:
                return data
            return data.get(field)
        except Exception:
            return None

    def delete(self, secret_name: str) -> bool:
        """Delete secret from Vault KV.

        Args:
            secret_name: Name of the secret

        Returns:
            True if successful, False otherwise
        """
        _ = secret_name
        try:
            client = self._client()
            if client is None:
                return False
            location = self._location()
            if location is None:
                return False
            path, mount_point, version = location
            field = self._field_name()
            if field is None:
                return self._delete_path(client, path, mount_point, version)

            found, data, current_version = self._read_map(client, path, mount_point, version)
            if not found or data is None or field not in data:
                return True
            remaining = {key: value for key, value in data.items() if key != field}
            if not remaining:
                return self._delete_path(client, path, mount_point, version)
            return self._write_document(
                client,
                path,
                mount_point,
                version,
                remaining,
                cas=current_version if version == 2 else None,
            )
        except Exception:
            return False

    def _client(self) -> Any | None:
        try:
            import hvac  # noqa: F401
        except ImportError:
            return None

        from secretzero.providers.vault import VaultAuth

        auth = getattr(self.provider, "auth", None)
        if not isinstance(auth, VaultAuth):
            return None
        return auth.get_client() or None

    def _location(self) -> tuple[str, str, int] | None:
        path = self.config.get("path")
        if not path:
            return None
        mount_point = self.config.get("mount_point", "secret")
        version = self.config.get("version", 2)
        return str(path), str(mount_point), version

    def _field_name(self) -> str | None:
        raw = self.config.get("field")
        if raw is None:
            return None
        text = str(raw).strip()
        return text or None

    @staticmethod
    def _whole_document(secret_value: Any) -> dict[str, Any]:
        if isinstance(secret_value, dict):
            return secret_value
        return {"value": str(secret_value)}

    @staticmethod
    def _field_value(secret_value: Any) -> str:
        if isinstance(secret_value, str):
            return secret_value
        return str(secret_value)

    def _read_for_merge(
        self,
        client: Any,
        path: str,
        mount_point: str,
        version: int,
    ) -> tuple[dict[str, Any], int]:
        """Return the current map and the CAS version to send on write.

        A missing path is an empty map with CAS 0 (create only if absent).
        Other read errors propagate so the caller does not invent a document.
        """
        found, data, current_version = self._read_map(client, path, mount_point, version)
        if not found or data is None:
            return {}, 0
        return data, current_version

    def _read_map(
        self,
        client: Any,
        path: str,
        mount_point: str,
        version: int,
    ) -> tuple[bool, dict[str, Any] | None, int]:
        from hvac.exceptions import InvalidPath

        try:
            if version == 2:
                response = client.secrets.kv.v2.read_secret_version(
                    path=path, mount_point=mount_point
                )
            else:
                response = client.secrets.kv.v1.read_secret(path=path, mount_point=mount_point)
        except InvalidPath:
            return False, None, 0

        if not isinstance(response, dict):
            raise ValueError("Vault KV read returned an unexpected payload")

        if version == 2:
            wrapped = response.get("data", {})
            if not isinstance(wrapped, dict):
                raise ValueError("Vault KV v2 read returned an unexpected payload")
            data = wrapped.get("data", {})
            metadata = wrapped.get("metadata", {})
            if not isinstance(data, dict) or not isinstance(metadata, dict):
                raise ValueError("Vault KV v2 read returned an unexpected payload")
            raw_version = metadata.get("version")
            if raw_version is None:
                raise ValueError("KV v2 secret is missing metadata.version")
            return True, dict(data), int(raw_version)

        data = response.get("data", {})
        if not isinstance(data, dict):
            raise ValueError("Vault KV v1 read returned an unexpected payload")
        return True, dict(data), 0

    @staticmethod
    def _write_document(
        client: Any,
        path: str,
        mount_point: str,
        version: int,
        secret_data: dict[str, Any],
        *,
        cas: int | None,
    ) -> bool:
        if version == 2:
            kwargs: dict[str, Any] = {
                "path": path,
                "secret": secret_data,
                "mount_point": mount_point,
            }
            if cas is not None:
                kwargs["cas"] = cas
            client.secrets.kv.v2.create_or_update_secret(**kwargs)
            return True

        client.secrets.kv.v1.create_or_update_secret(
            path=path, secret=secret_data, mount_point=mount_point
        )
        return True

    @staticmethod
    def _delete_path(client: Any, path: str, mount_point: str, version: int) -> bool:
        if version == 2:
            client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=path, mount_point=mount_point
            )
        else:
            client.secrets.kv.v1.delete_secret(path=path, mount_point=mount_point)
        return True
