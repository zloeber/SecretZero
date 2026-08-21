"""Tests for Azure DevOps provider registration."""

import pytest


def test_import_azure_devops_provider():
    from secretzero.providers.azure_devops import AzureDevOpsProvider, _get_bundle_manifest

    manifest = _get_bundle_manifest()
    assert manifest.name == "azure_devops"
    assert "azdo_variable_group" in manifest.target_kinds
    assert "azdo_pat" in manifest.generator_kinds
    assert AzureDevOpsProvider is not None


def test_azure_devops_provider_rejects_server_config():
    from secretzero.providers.azure_devops import AzureDevOpsProvider

    with pytest.raises(ValueError, match="Azure DevOps Server is not supported"):
        AzureDevOpsProvider(
            "azdo",
            config={"server": "tfs.corp.local", "organization": "corp"},
        )
