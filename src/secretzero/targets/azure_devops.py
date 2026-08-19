"""Azure DevOps pipeline targets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from secretzero.providers.azdo_environments import upsert_environment_variable
from secretzero.providers.azdo_pipeline_vars import upsert_pipeline_variable
from secretzero.providers.azdo_project_resolve import resolve_azdo_project
from secretzero.providers.azdo_secure_files import get_secure_file_by_name, upload_secure_file
from secretzero.providers.azdo_variable_groups import (
    upsert_variable_group_secret,
    variable_group_has_secret,
)
from secretzero.targets.base import BaseTarget


class _AzdoProjectMixin:
    provider: Any

    def _resolved_project(self) -> str:
        provider_config = getattr(self.provider, "config", None) or {}
        return resolve_azdo_project(
            project=self.config.get("project"),
            provider_config=provider_config,
            organization=getattr(self.provider.auth, "organization", None),
            cwd=Path.cwd(),
        )

    def _client(self):
        return self.provider.auth.get_client()


class AzdoVariableGroupTarget(_AzdoProjectMixin, BaseTarget):
    """Store secrets in an Azure DevOps Library variable group."""

    def __init__(self, provider: Any, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.provider = provider
        self.variable_group = self.config.get("variable_group")
        self.variable_name = self.config.get("variable_name")
        self.is_secret = self.config.get("is_secret", True)
        self.allow_override = self.config.get("allow_override", False)
        self.create_if_missing = self.config.get("create_if_missing", True)
        self.description = self.config.get("description")

    def store(self, secret_name: str, secret_value: str) -> bool:
        variable_name = self.variable_name or secret_name
        upsert_variable_group_secret(
            self._client(),
            self._resolved_project(),
            self.variable_group,
            variable_name,
            secret_value,
            create_if_missing=self.create_if_missing,
            is_secret=self.is_secret,
            allow_override=self.allow_override,
            description=self.description,
        )
        return True

    def retrieve(self, secret_name: str) -> str | None:
        if not self.is_secret:
            return None
        variable_name = self.variable_name or secret_name
        if variable_group_has_secret(
            self._client(),
            self._resolved_project(),
            self.variable_group,
            variable_name,
        ):
            return None
        return None

    def validate(self) -> tuple[bool, str | None]:
        if not self.variable_group:
            return False, "variable_group is required"
        return True, None


class AzdoPipelineVariableTarget(_AzdoProjectMixin, BaseTarget):
    """Store secrets on an Azure DevOps pipeline definition."""

    def __init__(self, provider: Any, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.provider = provider
        self.pipeline = self.config.get("pipeline")
        self.variable_name = self.config.get("variable_name")
        self.is_secret = self.config.get("is_secret", True)
        self.allow_override = self.config.get("allow_override", False)

    def store(self, secret_name: str, secret_value: str) -> bool:
        upsert_pipeline_variable(
            self._client(),
            self._resolved_project(),
            self.pipeline,
            self.variable_name or secret_name,
            secret_value,
            is_secret=self.is_secret,
            allow_override=self.allow_override,
        )
        return True

    def retrieve(self, secret_name: str) -> str | None:
        return None

    def validate(self) -> tuple[bool, str | None]:
        if not self.pipeline:
            return False, "pipeline is required"
        return True, None


class AzdoEnvironmentVariableTarget(_AzdoProjectMixin, BaseTarget):
    """Store secrets scoped to an Azure DevOps environment."""

    def __init__(self, provider: Any, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.provider = provider
        self.environment = self.config.get("environment")
        self.variable_name = self.config.get("variable_name")
        self.is_secret = self.config.get("is_secret", True)
        self.create_if_missing = self.config.get("create_if_missing", True)

    def store(self, secret_name: str, secret_value: str) -> bool:
        upsert_environment_variable(
            self._client(),
            self._resolved_project(),
            self.environment,
            self.variable_name or secret_name,
            secret_value,
            is_secret=self.is_secret,
            create_if_missing=self.create_if_missing,
        )
        return True

    def retrieve(self, secret_name: str) -> str | None:
        return None

    def validate(self) -> tuple[bool, str | None]:
        if not self.environment:
            return False, "environment is required"
        return True, None


class AzdoSecureFileTarget(_AzdoProjectMixin, BaseTarget):
    """Upload secret content as an Azure DevOps secure file."""

    def __init__(self, provider: Any, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.provider = provider
        self.file_name = self.config.get("file_name")

    def store(self, secret_name: str, secret_value: str) -> bool:
        upload_secure_file(
            self._client(),
            self._resolved_project(),
            self.file_name or secret_name,
            secret_value.encode("utf-8"),
        )
        return True

    def retrieve(self, secret_name: str) -> str | None:
        entry = get_secure_file_by_name(
            self._client(),
            self._resolved_project(),
            self.file_name or secret_name,
        )
        return None if entry else None

    def validate(self) -> tuple[bool, str | None]:
        return True, None


class AzdoKeyVaultVariableGroupTarget(_AzdoProjectMixin, BaseTarget):
    """Ensure a Key Vault-linked variable group maps a secret name."""

    def __init__(self, provider: Any, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.provider = provider
        self.variable_group = self.config.get("variable_group")
        self.service_connection = self.config.get("service_connection")
        self.vault_name = self.config.get("vault_name")
        self.secret_name = self.config.get("secret_name")
        self.create_if_missing = self.config.get("create_if_missing", True)

    def store(self, secret_name: str, secret_value: str) -> bool:
        client = self._client()
        project = self._resolved_project()
        mapped_name = self.secret_name or secret_name
        body = {
            "name": self.variable_group,
            "type": "AzureKeyVault",
            "providerData": {
                "serviceEndpointId": self.service_connection,
                "vault": self.vault_name,
            },
            "variables": {
                mapped_name: {
                    "isSecret": True,
                    "enabled": True,
                }
            },
            "variableGroupProjectReferences": [
                {
                    "name": self.variable_group,
                    "projectReference": {"name": project},
                }
            ],
        }
        url = client.project_url(project, "_apis/distributedtask/variablegroups")
        client.post(url, json=body, params={"api-version": "7.1"})
        return True

    def retrieve(self, secret_name: str) -> str | None:
        return None

    def validate(self) -> tuple[bool, str | None]:
        missing = [
            name
            for name, value in (
                ("variable_group", self.variable_group),
                ("service_connection", self.service_connection),
                ("vault_name", self.vault_name),
            )
            if not value
        ]
        if missing:
            return False, f"Missing required config: {', '.join(missing)}"
        return True, None
