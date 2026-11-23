"""Tests for Azure DevOps provider registration."""

import inspect
import json

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


def test_azure_devops_provider_kind_is_a_string():
    from secretzero.providers.azure_devops import AzureDevOpsProvider

    provider = AzureDevOpsProvider("azdo", config={"organization": "org"})
    assert provider.provider_kind == "azure_devops"
    actor = provider.get_actor_info()
    assert actor["provider"] == "azure_devops"
    json.dumps(actor)


def test_registered_provider_kinds_are_properties():
    from secretzero.bundles.registry import get_bundle_registry

    registry = get_bundle_registry()
    kinds = registry.list_provider_kinds()
    assert "azure_devops" in kinds
    for kind in kinds:
        cls = registry.get_provider_class(kind)
        assert cls is not None
        attr = inspect.getattr_static(cls, "provider_kind")
        assert isinstance(attr, property), f"{kind}.provider_kind must be a @property"
