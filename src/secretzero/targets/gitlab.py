"""GitLab CI/CD variable targets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from secretzero.providers.gitlab_group_resolve import resolve_gitlab_group
from secretzero.providers.gitlab_project_resolve import resolve_gitlab_project
from secretzero.providers.gitlab_service_accounts import add_group_member, add_project_member
from secretzero.providers.gitlab_variables import (
    get_group_variable,
    get_project_variable,
    upsert_group_variable,
    upsert_project_variable,
)
from secretzero.targets.base import BaseTarget


class _GitLabVariableOptionsMixin:
    """Parse shared GitLab variable target options from config."""

    def _init_variable_options(self, config: dict[str, Any]) -> None:
        self.protected = config.get("protected", False)
        self.masked = config.get("masked", True)
        self.masked_and_hidden = config.get("masked_and_hidden", False)
        self.raw = config.get("raw", True)
        self.environment_scope = config.get("environment_scope", "*")
        self.variable_type = config.get("variable_type", "env_var")
        self.description = config.get("description")


class GitLabVariableTarget(_GitLabVariableOptionsMixin, BaseTarget):
    """Store secrets as GitLab project CI/CD variables."""

    def __init__(self, provider: Any, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.provider = provider
        self._init_variable_options(self.config)
        self._project_config = self.config.get("project")

    def _resolved_project(self) -> str:
        provider_config = getattr(self.provider, "config", None) or {}
        return resolve_gitlab_project(
            project=self._project_config,
            provider_config=provider_config,
            cwd=Path.cwd(),
        )

    def store(self, secret_name: str, secret_value: str) -> bool:
        try:
            client = self.provider.auth.get_client()
            upsert_project_variable(
                client,
                self._resolved_project(),
                secret_name,
                secret_value,
                protected=self.protected,
                masked=self.masked,
                masked_and_hidden=self.masked_and_hidden,
                raw=self.raw,
                environment_scope=self.environment_scope,
                variable_type=self.variable_type,
                description=self.description,
            )
            return True
        except Exception as exc:
            raise ValueError(f"Failed to store GitLab project variable: {exc}") from exc

    def retrieve(self, secret_name: str) -> str | None:
        try:
            client = self.provider.auth.get_client()
            return get_project_variable(
                client,
                self._resolved_project(),
                secret_name,
                environment_scope=self.environment_scope,
            )
        except Exception:
            return None

    def validate(self) -> tuple[bool, str | None]:
        try:
            self._resolved_project()
            return True, None
        except ValueError as exc:
            return False, str(exc)


class GitLabGroupVariableTarget(_GitLabVariableOptionsMixin, BaseTarget):
    """Store secrets as GitLab group-level CI/CD variables."""

    def __init__(self, provider: Any, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.provider = provider
        self._init_variable_options(self.config)
        self._group_config = self.config.get("group")
        if not self._group_config:
            raise ValueError("GitLab group variable target requires 'group' in config")

    def _resolved_group(self) -> str:
        provider_config = getattr(self.provider, "config", None) or {}
        return resolve_gitlab_group(
            group=self._group_config,
            provider_config=provider_config,
            cwd=Path.cwd(),
        )

    def store(self, secret_name: str, secret_value: str) -> bool:
        try:
            client = self.provider.auth.get_client()
            upsert_group_variable(
                client,
                self._resolved_group(),
                secret_name,
                secret_value,
                protected=self.protected,
                masked=self.masked,
                masked_and_hidden=self.masked_and_hidden,
                raw=self.raw,
                environment_scope=self.environment_scope,
                variable_type=self.variable_type,
                description=self.description,
            )
            return True
        except Exception as exc:
            raise ValueError(f"Failed to store GitLab group variable: {exc}") from exc

    def retrieve(self, secret_name: str) -> str | None:
        try:
            client = self.provider.auth.get_client()
            return get_group_variable(
                client,
                self._resolved_group(),
                secret_name,
                environment_scope=self.environment_scope,
            )
        except Exception:
            return None

    def validate(self) -> tuple[bool, str | None]:
        try:
            self._resolved_group()
            return True, None
        except ValueError as exc:
            return False, str(exc)


class GitLabServiceAccountMemberTarget(BaseTarget):
    """Grant GitLab group/project membership to a service account user."""

    def __init__(self, provider: Any, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.provider = provider
        self.service_account_user_id = self.config.get("service_account_user_id")
        self.resource_type = self.config.get("resource_type")
        self.resource = self.config.get("resource")
        self.access_level = int(self.config.get("access_level", 30))

    def store(self, secret_name: str, secret_value: str) -> bool:
        if self.service_account_user_id is None:
            raise ValueError("gitlab_service_account_member requires service_account_user_id")
        if self.resource_type not in {"group", "project"}:
            raise ValueError("resource_type must be 'group' or 'project'")
        if not self.resource:
            raise ValueError("resource is required for gitlab_service_account_member")

        client = self.provider.auth.get_client()
        user_id = int(self.service_account_user_id)
        resource = str(self.resource)
        if resource == "auto" and self.resource_type == "project":
            provider_config = getattr(self.provider, "config", None) or {}
            resource = resolve_gitlab_project(
                project="auto",
                provider_config=provider_config,
                cwd=Path.cwd(),
            )

        if self.resource_type == "group":
            add_group_member(client, resource, user_id, self.access_level)
        else:
            add_project_member(client, resource, user_id, self.access_level)
        return True

    def retrieve(self, secret_name: str) -> str | None:
        return None

    def validate(self) -> tuple[bool, str | None]:
        if self.service_account_user_id is None:
            return False, "service_account_user_id is required"
        if self.resource_type not in {"group", "project"}:
            return False, "resource_type must be group or project"
        if not self.resource:
            return False, "resource is required"
        return True, None
