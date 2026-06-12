"""GitLab CI/CD variable targets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from secretzero.providers.gitlab_project_resolve import resolve_gitlab_project
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
        self.group = self.config.get("group")
        if not self.group:
            raise ValueError("GitLab group variable target requires 'group' in config")

    def store(self, secret_name: str, secret_value: str) -> bool:
        try:
            client = self.provider.auth.get_client()
            upsert_group_variable(
                client,
                self.group,
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
                self.group,
                secret_name,
                environment_scope=self.environment_scope,
            )
        except Exception:
            return None
