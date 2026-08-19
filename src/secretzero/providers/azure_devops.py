"""Azure DevOps Services provider for Azure Pipelines secrets."""

from __future__ import annotations

import os
from typing import Any

from secretzero.providers.azdo_client import AzdoClient
from secretzero.providers.azdo_project_resolve import resolve_azdo_project
from secretzero.providers.azdo_variable_groups import upsert_variable_group_secret
from secretzero.providers.base import BaseProvider, ProviderAuth

_ON_PREM_KEYS = frozenset({"server", "collection", "is_on_premises", "host"})


class AzureDevOpsAuth(ProviderAuth):
    """Azure DevOps PAT authentication."""

    ENV_PAT = "AZDO_PAT"
    ENV_PAT_ALT = "AZURE_DEVOPS_EXT_PAT"
    ENV_ORG = "AZDO_ORGANIZATION"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.organization: str | None = config.get("organization") or os.environ.get(self.ENV_ORG)
        self._client: AzdoClient | None = None

    def authenticate(self) -> bool:
        token = self.config.get("token") or os.environ.get(self.ENV_PAT) or os.environ.get(
            self.ENV_PAT_ALT
        )
        if not token or not self.organization:
            return False
        try:
            client = AzdoClient(self.organization, token)
            client.connection_data()
            self._client = client
            return True
        except Exception:
            return False

    def is_authenticated(self) -> bool:
        return self._client is not None

    def get_client(self) -> AzdoClient:
        if not self.is_authenticated():
            self.authenticate()
        if self._client is None:
            raise RuntimeError("Azure DevOps authentication failed")
        return self._client

    def get_token_info(self) -> dict[str, Any]:
        client = self.get_client()
        data = client.connection_data()
        user = data.get("authenticatedUser") or {}
        return {
            "user": user.get("providerDisplayName") or user.get("customDisplayName"),
            "organization": self.organization,
            "scopes": [],
            "token_type": "azdo_pat",
        }


class AzureDevOpsProvider(BaseProvider):
    """Azure DevOps Services provider."""

    display_name = "Azure DevOps"
    description = "Azure DevOps Services pipeline library secrets"
    required_package = ("requests", "secretzero[azure-devops]")
    auth_class = AzureDevOpsAuth
    auth_methods = {"token": "Use Azure DevOps personal access token"}
    config_options = {
        "organization": "Azure DevOps organization name (required)",
        "project": "Default project name (optional)",
    }
    config_example = """providers:
  azdo:
    kind: azure_devops
    auth:
      kind: token
      config:
        token: ${AZDO_PAT}
        organization: myorg"""

    def __init__(
        self,
        name: str,
        config: dict[str, Any] | None = None,
        auth: AzureDevOpsAuth | None = None,
    ):
        if config:
            blocked = [key for key in _ON_PREM_KEYS if key in config or key in (config.get("auth") or {}).get("config", {})]
            if blocked:
                raise ValueError(
                    "Azure DevOps Server is not supported in v1. "
                    f"Remove unsupported config keys: {', '.join(blocked)}"
                )
        if auth is None and config:
            auth_config = dict(config.get("auth", {}).get("config", {}))
            if "token" in config:
                auth_config["token"] = config["token"]
            if "organization" in config:
                auth_config["organization"] = config["organization"]
            auth = AzureDevOpsAuth(auth_config)
        super().__init__(name, config, auth)

    def provider_kind(self) -> str:
        return "azure_devops"

    def test_connection(self) -> tuple[bool, str | None]:
        try:
            self.auth.get_client().connection_data()
            return True, None
        except Exception as exc:
            return False, str(exc)

    def get_supported_targets(self) -> list[str]:
        return [
            "azdo_variable_group",
            "azdo_pipeline_variable",
            "azdo_environment_variable",
            "azdo_secure_file",
            "azdo_keyvault_variable_group",
        ]

    def create_pat_with_manifest(self, manifest: dict[str, Any]) -> str:
        client = self.auth.get_client()
        body = {
            "displayName": manifest["display_name"],
            "scope": manifest["scopes"],
            "validTo": manifest.get("valid_to"),
        }
        try:
            response = client.post(
                client._url("_apis/tokens/pats"),
                json=body,
                params={"api-version": "7.1-preview.1"},
            )
        except Exception as exc:
            raise RuntimeError(
                "Azure DevOps PAT minting failed. Create a PAT manually and retry."
            ) from exc
        token = (response or {}).get("patToken", {}).get("token")
        if not token:
            raise RuntimeError("Azure DevOps PAT API response missing token")
        return token


def _get_bundle_manifest() -> "BundleManifest":  # noqa: F821
    from secretzero.bundles.registry import BundleManifest

    return BundleManifest(
        name="azure_devops",
        version="1.0.0",
        provider_class="secretzero.providers.azure_devops:AzureDevOpsProvider",
        generators={
            "azdo_pat": "secretzero.generators.azdo_pat:AzureDevOpsPATGenerator",
        },
        targets={
            "azdo_variable_group": "secretzero.targets.azure_devops:AzdoVariableGroupTarget",
            "azdo_pipeline_variable": "secretzero.targets.azure_devops:AzdoPipelineVariableTarget",
            "azdo_environment_variable": (
                "secretzero.targets.azure_devops:AzdoEnvironmentVariableTarget"
            ),
            "azdo_secure_file": "secretzero.targets.azure_devops:AzdoSecureFileTarget",
            "azdo_keyvault_variable_group": (
                "secretzero.targets.azure_devops:AzdoKeyVaultVariableGroupTarget"
            ),
        },
        generator_kinds=["azdo_pat"],
        target_kinds=[
            "azdo_variable_group",
            "azdo_pipeline_variable",
            "azdo_environment_variable",
            "azdo_secure_file",
            "azdo_keyvault_variable_group",
        ],
        terraform_provider={
            "name": "azuredevops",
            "source": "microsoft/azuredevops",
            "version": "~> 1.0",
            "default_config": {},
        },
        requires=["requests>=2.32.0"],
    )
