"""HCP Terraform and Terraform Enterprise provider."""

from __future__ import annotations

import os
from typing import Any

from secretzero.providers.base import BaseProvider, ProviderAuth
from secretzero.providers.tfc_client import TfcApiError, TfcClient

_CATEGORIES = frozenset({"env", "terraform"})


class TerraformCloudAuth(ProviderAuth):
    """Token authentication for HCP Terraform or Terraform Enterprise."""

    ENV_TOKEN = "TFE_TOKEN"
    ENV_ORG = "TFE_ORGANIZATION"
    ENV_HOSTNAME = "TFE_HOSTNAME"

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.organization: str | None = self.config.get("organization") or os.environ.get(
            self.ENV_ORG
        )
        self.hostname: str | None = self.config.get("hostname") or os.environ.get(self.ENV_HOSTNAME)
        self._client: TfcClient | None = None
        self._token: str | None = None

    def _token_value(self) -> str | None:
        token = self._token or self.config.get("token") or os.environ.get(self.ENV_TOKEN)
        if not token:
            return None
        return str(token)

    def authenticate(self) -> bool:
        token = self._token_value()
        if not token:
            return False
        self._token = token
        try:
            self.get_client().account_details()
            return True
        except Exception:
            self._client = None
            return False

    def is_authenticated(self) -> bool:
        return self._client is not None

    def get_client(self) -> TfcClient:
        if self._client is None:
            token = self._token_value()
            if not token:
                raise RuntimeError("Terraform Cloud authentication failed")
            self._token = token
            self._client = TfcClient(hostname=self.hostname, token=token)
        return self._client

    def get_token_info(self) -> dict[str, Any]:
        details = self.get_client().account_details()
        info = {
            "user": details.get("username"),
            "organization": self.organization,
            "scopes": [],
            "token_type": "tfc_token",
        }
        if details.get("email"):
            info["email"] = details.get("email")
        return info


class TerraformCloudProvider(BaseProvider):
    """Provider for HCP Terraform workspace and variable-set variables."""

    display_name = "Terraform Cloud"
    description = "HCP Terraform and Terraform Enterprise workspace and variable-set variables"
    required_package = ("requests", "secretzero[terraform-cloud]")
    auth_class = TerraformCloudAuth
    auth_methods = {"token": "Use a Terraform Cloud or Terraform Enterprise team or user token"}
    config_options = {
        "organization": "Organization name (required)",
        "hostname": "API hostname (default app.terraform.io)",
    }
    config_example = """providers:
  tfc:
    kind: terraform_cloud
    auth:
      kind: token
      config:
        token: ${TFE_TOKEN}
        organization: example-org"""
    target_details = {
        "tfc_workspace_variable": {
            "description": "Workspace variable. Sensitive values are write-only.",
            "config": {
                "workspace": "Workspace name",
                "workspace_id": "Workspace id, used when name is omitted",
                "key": "Variable key (defaults to the secret name)",
                "category": "env or terraform (default env)",
                "sensitive": "Write-only when true (default true)",
            },
        },
        "tfc_varset_variable": {
            "description": "Organization variable-set variable. Sensitive values are write-only.",
            "config": {
                "varset": "Variable set name",
                "varset_id": "Variable set id, used when name is omitted",
                "create_set": "Create the set when it is missing (default false)",
                "key": "Variable key (defaults to the secret name)",
                "category": "env or terraform (default env)",
            },
        },
    }

    def __init__(
        self,
        name: str,
        config: dict[str, Any] | None = None,
        auth: TerraformCloudAuth | None = None,
    ):
        if auth is None and config:
            auth_config = dict(config.get("auth", {}).get("config", {}))
            for key in ("token", "organization", "hostname"):
                if key in config and key not in auth_config:
                    auth_config[key] = config[key]
            if "organization" not in auth_config and config.get("organization"):
                auth_config["organization"] = config["organization"]
            auth = TerraformCloudAuth(auth_config)
        super().__init__(name, config, auth)
        self._tfc: TfcClient | None = None

    @property
    def provider_kind(self) -> str:
        return "terraform_cloud"

    def get_supported_targets(self) -> list[str]:
        return ["tfc_workspace_variable", "tfc_varset_variable"]

    def test_connection(self) -> tuple[bool, str | None]:
        try:
            self._client().account_details()
            return True, None
        except Exception as exc:
            return False, str(exc)

    def get_token_info(self) -> dict[str, Any]:
        details = self._client().account_details()
        organization = None
        if isinstance(self.auth, TerraformCloudAuth):
            organization = self.auth.organization
        info = {
            "user": details.get("username"),
            "organization": organization or self._organization(None),
            "scopes": [],
            "token_type": "tfc_token",
        }
        if details.get("email"):
            info["email"] = details.get("email")
        return info

    def _client(self) -> TfcClient:
        if self._tfc is not None:
            return self._tfc
        if not isinstance(self.auth, TerraformCloudAuth):
            raise RuntimeError("Terraform Cloud authentication failed")
        return self.auth.get_client()

    def _organization(self, override: str | None) -> str:
        organization = override or (self.config or {}).get("organization")
        if not organization and isinstance(self.auth, TerraformCloudAuth):
            organization = self.auth.organization
        if not organization:
            organization = os.environ.get(TerraformCloudAuth.ENV_ORG)
        if not organization:
            raise ValueError("organization is required for Terraform Cloud")
        return str(organization)

    def upsert_workspace_variable(
        self,
        *,
        organization: str | None,
        workspace: str | None,
        workspace_id: str | None,
        key: str,
        value: str,
        category: str = "env",
        sensitive: bool = True,
        hcl: bool = False,
        description: str | None = None,
        create_if_missing: bool = True,
    ) -> dict[str, Any]:
        client = self._client()
        org = self._organization(organization)
        category = _category(category)
        resolved_id = self._workspace_id(client, org, workspace, workspace_id)
        existing = _find_variable(client.list_workspace_variables(resolved_id), key, category)
        if existing is None:
            if not create_if_missing:
                raise ValueError(f"Terraform Cloud variable not found: {key}")
            return client.create_workspace_variable(
                resolved_id,
                key=key,
                value=value,
                category=category,
                sensitive=sensitive,
                hcl=hcl,
                description=description,
            )
        _ensure_compatible(existing, key=key, hcl=hcl, sensitive=sensitive)
        return client.update_workspace_variable(
            resolved_id,
            str(existing.get("id")),
            _update_attributes(value, sensitive=sensitive, description=description),
        )

    def upsert_varset_variable(
        self,
        *,
        organization: str | None,
        varset: str | None,
        varset_id: str | None,
        key: str,
        value: str,
        category: str = "env",
        sensitive: bool = True,
        hcl: bool = False,
        description: str | None = None,
        create_if_missing: bool = True,
        create_set: bool = False,
        global_set: bool = False,
        priority: bool = False,
        workspaces: list[str] | None = None,
    ) -> dict[str, Any]:
        client = self._client()
        org = self._organization(organization)
        category = _category(category)
        resolved_id = self._varset_id(
            client,
            org,
            varset,
            varset_id,
            create_set=create_set,
            description=description,
            global_set=global_set,
            priority=priority,
            workspaces=workspaces,
        )
        existing = _find_variable(client.list_varset_variables(resolved_id), key, category)
        if existing is None:
            if not create_if_missing:
                raise ValueError(f"Terraform Cloud variable not found: {key}")
            return client.create_varset_variable(
                resolved_id,
                key=key,
                value=value,
                category=category,
                sensitive=sensitive,
                hcl=hcl,
                description=description,
            )
        _ensure_compatible(existing, key=key, hcl=hcl, sensitive=sensitive)
        return client.update_varset_variable(
            resolved_id,
            str(existing.get("id")),
            _update_attributes(value, sensitive=sensitive, description=description),
        )

    def read_variable(
        self,
        *,
        key: str,
        organization: str | None = None,
        workspace: str | None = None,
        workspace_id: str | None = None,
        varset: str | None = None,
        varset_id: str | None = None,
        category: str = "env",
        kind: str | None = None,
    ) -> dict[str, Any] | None:
        client = self._client()
        org = self._organization(organization)
        category = _category(category)
        if kind == "tfc_varset_variable" or varset or varset_id:
            resolved = self._varset_id(
                client,
                org,
                varset,
                varset_id,
                create_set=False,
                description=None,
                global_set=False,
                priority=False,
                workspaces=None,
            )
            variables = client.list_varset_variables(resolved)
        else:
            resolved = self._workspace_id(client, org, workspace, workspace_id)
            variables = client.list_workspace_variables(resolved)
        return _find_variable(variables, key, category)

    def retrieve_secret(
        self,
        secret_name: str,
        *,
        organization: str | None = None,
        workspace: str | None = None,
        workspace_id: str | None = None,
        varset: str | None = None,
        varset_id: str | None = None,
        key: str | None = None,
        category: str = "env",
        name: str | None = None,
        path: str | None = None,
        kind: str | None = None,
        profile: str | None = None,
        **_: Any,
    ) -> str:
        _ = profile
        variable_key = key or name or path or secret_name
        found = self.read_variable(
            key=variable_key,
            organization=organization,
            workspace=workspace,
            workspace_id=workspace_id,
            varset=varset,
            varset_id=varset_id,
            category=category,
            kind=kind,
        )
        if found is None:
            raise ValueError(f"Terraform Cloud variable not found: {variable_key}")
        if found.get("sensitive") or found.get("value") is None:
            raise ValueError(
                f"Terraform Cloud variable '{variable_key}' is sensitive and write-only"
            )
        return str(found.get("value"))

    def _workspace_id(
        self,
        client: TfcClient,
        organization: str,
        workspace: str | None,
        workspace_id: str | None,
    ) -> str:
        if workspace_id:
            return workspace_id
        if not workspace:
            raise ValueError("workspace or workspace_id is required")
        try:
            found = client.get_workspace(organization, workspace)
        except TfcApiError as exc:
            if exc.status == 404:
                raise ValueError(
                    f"Terraform Cloud workspace not found: {organization}/{workspace}"
                ) from exc
            raise
        resolved = found.get("id")
        if not resolved:
            raise ValueError(f"Terraform Cloud workspace not found: {organization}/{workspace}")
        return str(resolved)

    def _varset_id(
        self,
        client: TfcClient,
        organization: str,
        varset: str | None,
        varset_id: str | None,
        *,
        create_set: bool,
        description: str | None,
        global_set: bool,
        priority: bool,
        workspaces: list[str] | None,
    ) -> str:
        if varset_id:
            return varset_id
        if not varset:
            raise ValueError("varset or varset_id is required")
        try:
            sets = client.list_varsets(organization)
        except TfcApiError as exc:
            if exc.status == 404:
                raise ValueError(f"Terraform Cloud organization not found: {organization}") from exc
            if "truncated" in exc.detail:
                raise ValueError("Terraform Cloud variable set list was truncated") from exc
            raise
        matches = [item for item in sets if item.get("name") == varset]
        if len(matches) > 1:
            raise ValueError(f"Terraform Cloud variable set name is duplicated: {varset}")
        if len(matches) == 1:
            return str(matches[0]["id"])
        if not create_set:
            raise ValueError(f"Terraform Cloud variable set not found: {varset}")
        workspace_ids: list[str] = []
        if workspaces and not global_set:
            for workspace_name in workspaces:
                workspace_ids.append(self._workspace_id(client, organization, workspace_name, None))
        created = client.create_varset(
            organization,
            name=varset,
            description=description,
            global_set=global_set,
            priority=priority,
            workspace_ids=workspace_ids or None,
        )
        created_id = created.get("id")
        if not created_id:
            raise ValueError(f"Terraform Cloud variable set was not created: {varset}")
        return str(created_id)


def _category(value: str) -> str:
    if value not in _CATEGORIES:
        raise ValueError("category must be env or terraform")
    return value


def _find_variable(
    variables: list[dict[str, Any]], key: str, category: str
) -> dict[str, Any] | None:
    for variable in variables:
        if variable.get("key") == key and variable.get("category") == category:
            return variable
    return None


def _ensure_compatible(existing: dict[str, Any], *, key: str, hcl: bool, sensitive: bool) -> None:
    if bool(existing.get("hcl")) != bool(hcl):
        raise ValueError(
            f"Terraform Cloud variable '{key}' hcl does not match the manifest. "
            "Delete the variable in Terraform Cloud and sync again."
        )
    if bool(existing.get("sensitive")) != bool(sensitive):
        raise ValueError(
            f"Terraform Cloud variable '{key}' sensitive does not match the manifest. "
            "Delete the variable in Terraform Cloud and sync again."
        )


def _update_attributes(value: str, *, sensitive: bool, description: str | None) -> dict[str, Any]:
    if sensitive:
        return {"value": value}
    attributes: dict[str, Any] = {"value": value}
    if description:
        attributes["description"] = description
    return attributes


def _get_bundle_manifest() -> Any:
    from secretzero.bundles.registry import BundleManifest

    return BundleManifest(
        name="terraform_cloud",
        version="1.0.0",
        provider_class="secretzero.providers.terraform_cloud:TerraformCloudProvider",
        generators={},
        targets={
            "tfc_workspace_variable": (
                "secretzero.targets.terraform_cloud:TfcWorkspaceVariableTarget"
            ),
            "tfc_varset_variable": "secretzero.targets.terraform_cloud:TfcVarsetVariableTarget",
        },
        generator_kinds=[],
        target_kinds=["tfc_workspace_variable", "tfc_varset_variable"],
        terraform_provider={
            "name": "tfe",
            "source": "hashicorp/tfe",
            "version": "~> 0.60",
            "default_config": {},
        },
        requires=["requests>=2.32.0"],
    )
