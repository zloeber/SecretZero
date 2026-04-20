"""Target adapter for storing secrets via the Ansible Vault provider."""

from __future__ import annotations

from typing import Any

from secretzero.providers.ansible_vault import AnsibleVaultProvider
from secretzero.targets.base import BaseTarget


class AnsibleVaultFileTarget(BaseTarget):
    """Store/retrieve secrets in an Ansible Vault encrypted file.

    This target delegates to :class:`AnsibleVaultProvider` capability methods,
    allowing provider-backed encrypted file workflows to run through normal
    ``secretzero sync`` target dispatch.
    """

    def __init__(self, provider: Any, config: dict[str, Any] | None = None) -> None:
        super().__init__(provider, config or {})
        if not isinstance(self.provider, AnsibleVaultProvider):
            raise ValueError("ansible_vault_file target requires an ansible_vault provider")

    def _entry_key(self, secret_name: str) -> str:
        override = self.config.get("key")
        if override is not None and str(override).strip():
            return str(override).strip()
        return secret_name

    def store(self, secret_name: str, secret_value: str) -> bool:
        key = self._entry_key(secret_name)
        return self.provider.store_secret(key, secret_value)

    def retrieve(self, secret_name: str) -> str | None:
        key = self._entry_key(secret_name)
        try:
            return self.provider.retrieve_secret(key)
        except Exception:
            return None

    def validate(self) -> tuple[bool, str | None]:
        return self.provider.test_connection()
