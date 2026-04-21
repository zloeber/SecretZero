"""Vercel environment variable target."""

from __future__ import annotations

from typing import Any

from secretzero.targets.base import BaseTarget


class VercelEnvTarget(BaseTarget):
    """Store secrets as Vercel project environment variables."""

    def __init__(self, provider: Any, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.provider = provider
        self.project_id = self.config.get("project_id")
        self.secret_name_override = self.config.get("secret_name")
        self.environments = self.config.get("environments")

        if not self.project_id:
            raise ValueError("Vercel target requires 'project_id' in config")

    def store(self, secret_name: str, secret_value: str) -> bool:
        name = self.secret_name_override or secret_name
        return self.provider.store_secret(
            secret_name=name,
            secret_value=secret_value,
            project_id=self.project_id,
            environments=self.environments,
        )

    def retrieve(self, secret_name: str) -> str | None:
        name = self.secret_name_override or secret_name
        try:
            return self.provider.retrieve_secret(
                secret_name=name,
                project_id=self.project_id,
            )
        except Exception:
            return None
