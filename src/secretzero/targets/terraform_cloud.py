"""HCP Terraform workspace and variable-set targets."""

from __future__ import annotations

from typing import Any

from secretzero.targets.base import BaseTarget


class TfcWorkspaceVariableTarget(BaseTarget):
    """Store a secret as a Terraform Cloud workspace variable."""

    def __init__(self, provider: Any, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.provider = provider
        self.organization = self.config.get("organization")
        self.workspace = self.config.get("workspace")
        self.workspace_id = self.config.get("workspace_id")
        self.key = self.config.get("key")
        self.category = self.config.get("category", "env")
        self.sensitive = self.config.get("sensitive", True)
        self.hcl = self.config.get("hcl", False)
        self.description = self.config.get("description")
        self.create_if_missing = self.config.get("create_if_missing", True)

    def store(self, secret_name: str, secret_value: str) -> bool:
        self.provider.upsert_workspace_variable(
            organization=self.organization,
            workspace=self.workspace,
            workspace_id=self.workspace_id,
            key=self.key or secret_name,
            value=secret_value,
            category=self.category,
            sensitive=self.sensitive,
            hcl=self.hcl,
            description=self.description,
            create_if_missing=self.create_if_missing,
        )
        return True

    def retrieve(self, secret_name: str) -> str | None:
        found = self.provider.read_variable(
            key=self.key or secret_name,
            organization=self.organization,
            workspace=self.workspace,
            workspace_id=self.workspace_id,
            category=self.category,
            kind="tfc_workspace_variable",
        )
        if not isinstance(found, dict) or found.get("sensitive") or found.get("value") is None:
            return None
        return str(found.get("value"))

    def validate(self) -> tuple[bool, str | None]:
        if not self.workspace and not self.workspace_id:
            return False, "workspace or workspace_id is required"
        return True, None


class TfcVarsetVariableTarget(BaseTarget):
    """Store a secret as a Terraform Cloud variable-set variable."""

    def __init__(self, provider: Any, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.provider = provider
        self.organization = self.config.get("organization")
        self.varset = self.config.get("varset")
        self.varset_id = self.config.get("varset_id")
        self.key = self.config.get("key")
        self.category = self.config.get("category", "env")
        self.sensitive = self.config.get("sensitive", True)
        self.hcl = self.config.get("hcl", False)
        self.description = self.config.get("description")
        self.create_if_missing = self.config.get("create_if_missing", True)
        self.create_set = self.config.get("create_set", False)
        self.global_set = self.config.get("global", False)
        self.priority = self.config.get("priority", False)
        self.workspaces = self.config.get("workspaces")

    def store(self, secret_name: str, secret_value: str) -> bool:
        self.provider.upsert_varset_variable(
            organization=self.organization,
            varset=self.varset,
            varset_id=self.varset_id,
            key=self.key or secret_name,
            value=secret_value,
            category=self.category,
            sensitive=self.sensitive,
            hcl=self.hcl,
            description=self.description,
            create_if_missing=self.create_if_missing,
            create_set=self.create_set,
            global_set=self.global_set,
            priority=self.priority,
            workspaces=self.workspaces,
        )
        return True

    def retrieve(self, secret_name: str) -> str | None:
        found = self.provider.read_variable(
            key=self.key or secret_name,
            organization=self.organization,
            varset=self.varset,
            varset_id=self.varset_id,
            category=self.category,
            kind="tfc_varset_variable",
        )
        if not isinstance(found, dict) or found.get("sensitive") or found.get("value") is None:
            return None
        return str(found.get("value"))

    def validate(self) -> tuple[bool, str | None]:
        if not self.varset and not self.varset_id:
            return False, "varset or varset_id is required"
        return True, None
