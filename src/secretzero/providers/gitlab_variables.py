"""Shared helpers for GitLab CI/CD variable targets."""

from __future__ import annotations

from typing import Any

try:
    from gitlab.exceptions import GitlabError, GitlabGetError
except ImportError:

    class GitlabGetError(Exception):
        """Fallback when python-gitlab is not installed."""

    class GitlabError(Exception):
        """Fallback when python-gitlab is not installed."""


def validate_masked_value(value: str, *, masked: bool) -> None:
    """Validate a value against GitLab masked-variable rules.

    Args:
        value: Variable value to store.
        masked: Whether the variable will be masked.

    Raises:
        ValueError: If the value cannot be stored as a masked variable.
    """
    if not masked:
        return
    if "\n" in value or "\r" in value:
        raise ValueError("Masked GitLab variables must be a single line")
    if len(value) < 8:
        raise ValueError("Masked GitLab variables must be at least 8 characters")


def _variable_payload(
    key: str,
    value: str,
    *,
    protected: bool,
    masked: bool,
    environment_scope: str,
    variable_type: str,
    masked_and_hidden: bool = False,
    raw: bool = True,
    description: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "key": key,
        "value": value,
        "protected": protected,
        "masked": masked,
        "environment_scope": environment_scope,
        "variable_type": variable_type,
        "raw": raw,
    }
    if masked_and_hidden:
        payload["masked_and_hidden"] = masked_and_hidden
    if description is not None:
        payload["description"] = description
    return payload


def _apply_scope_filter(variable: Any, environment_scope: str) -> None:
    if environment_scope != "*":
        variable.filter = {"environment_scope": environment_scope}


def upsert_project_variable(
    client: Any,
    project: str,
    key: str,
    value: str,
    *,
    protected: bool = False,
    masked: bool = True,
    environment_scope: str = "*",
    variable_type: str = "env_var",
    masked_and_hidden: bool = False,
    raw: bool = True,
    description: str | None = None,
) -> None:
    """Create or update a project CI/CD variable."""
    validate_masked_value(value, masked=masked)
    gl_project = client.projects.get(project, lazy=True)
    payload = _variable_payload(
        key,
        value,
        protected=protected,
        masked=masked,
        environment_scope=environment_scope,
        variable_type=variable_type,
        masked_and_hidden=masked_and_hidden,
        raw=raw,
        description=description,
    )

    try:
        variable = gl_project.variables.get(key, filter={"environment_scope": environment_scope})
        _apply_scope_filter(variable, environment_scope)
        for field, field_value in payload.items():
            if field != "key":
                setattr(variable, field, field_value)
        variable.save()
    except GitlabGetError:
        gl_project.variables.create(payload)


def get_project_variable(
    client: Any,
    project: str,
    key: str,
    *,
    environment_scope: str = "*",
) -> str | None:
    """Retrieve a project CI/CD variable value."""
    try:
        gl_project = client.projects.get(project, lazy=True)
        variable = gl_project.variables.get(key, filter={"environment_scope": environment_scope})
        return variable.value
    except GitlabError:
        return None


def upsert_group_variable(
    client: Any,
    group: str,
    key: str,
    value: str,
    *,
    protected: bool = False,
    masked: bool = True,
    environment_scope: str = "*",
    variable_type: str = "env_var",
    masked_and_hidden: bool = False,
    raw: bool = True,
    description: str | None = None,
) -> None:
    """Create or update a group CI/CD variable."""
    validate_masked_value(value, masked=masked)
    gl_group = client.groups.get(group, lazy=True)
    payload = _variable_payload(
        key,
        value,
        protected=protected,
        masked=masked,
        environment_scope=environment_scope,
        variable_type=variable_type,
        masked_and_hidden=masked_and_hidden,
        raw=raw,
        description=description,
    )

    try:
        variable = gl_group.variables.get(key, filter={"environment_scope": environment_scope})
        _apply_scope_filter(variable, environment_scope)
        for field, field_value in payload.items():
            if field != "key":
                setattr(variable, field, field_value)
        variable.save()
    except GitlabGetError:
        gl_group.variables.create(payload)


def get_group_variable(
    client: Any,
    group: str,
    key: str,
    *,
    environment_scope: str = "*",
) -> str | None:
    """Retrieve a group CI/CD variable value."""
    try:
        gl_group = client.groups.get(group, lazy=True)
        variable = gl_group.variables.get(key, filter={"environment_scope": environment_scope})
        return variable.value
    except GitlabError:
        return None
