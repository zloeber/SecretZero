"""Keeper Password Manager vault record target."""

from __future__ import annotations

from typing import Any

from secretzero.targets.base import BaseTarget


class KeeperRecordTarget(BaseTarget):
    """Store and retrieve secrets in Keeper Password Manager vault records."""

    def __init__(self, provider: Any, config: dict[str, Any] | None = None):
        super().__init__(provider, config)
        self.record_uid = self.config.get("record_uid")
        self.path = self.config.get("path")
        self.title = self.config.get("title")
        self.secret_name_override = self.config.get("secret_name")
        self.field = self.config.get("field", "password")
        self.structured = bool(self.config.get("structured"))
        self.fields = self.config.get("fields")
        self.create_if_missing = bool(self.config.get("create_if_missing"))
        self.record_type = self.config.get("record_type", "login")
        self.folder = self.config.get("folder")

        if not any(
            [
                self.record_uid,
                self.path,
                self.title,
                self.secret_name_override,
                self.create_if_missing,
            ]
        ):
            raise ValueError(
                "Keeper target requires one of: record_uid, path, title, secret_name, "
                "or create_if_missing: true"
            )

    def _operation_kwargs(self, secret_name: str) -> dict[str, Any]:
        return {
            "record_uid": self.record_uid,
            "path": self.path,
            "title": self.title,
            "name": self.secret_name_override or secret_name,
            "field": self.field,
            "structured": self.structured,
            "fields": self.fields,
            "create_if_missing": self.create_if_missing,
            "record_type": self.record_type,
            "folder": self.folder,
        }

    def resolve_target_id(self, secret_name: str) -> str | None:
        uid = getattr(self.provider, "last_record_uid", None)
        if not uid:
            return None
        provider_name = getattr(self.provider, "name", "keeper")
        return f"{provider_name}/keeper_record/{uid}"

    def store(self, secret_name: str, secret_value: str) -> bool:
        return self.provider.store_secret(
            secret_name=secret_name,
            secret_value=secret_value,
            **self._operation_kwargs(secret_name),
        )

    def retrieve(self, secret_name: str) -> str | None:
        try:
            return self.provider.retrieve_secret(
                secret_name=secret_name,
                **self._operation_kwargs(secret_name),
            )
        except Exception:
            return None
