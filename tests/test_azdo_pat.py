"""Tests for Azure DevOps PAT generator."""

from unittest.mock import MagicMock

from secretzero.generators.azdo_pat import AzureDevOpsPATGenerator


def test_azdo_pat_generator_delegates():
    provider = MagicMock()
    provider.create_pat_with_manifest.return_value = "ado-pat-token"
    generator = AzureDevOpsPATGenerator(
        {
            "provider": "azdo",
            "_provider_instance": provider,
            "display_name": "secretzero-automation",
            "scopes": ["vso.variablegroups_write"],
        }
    )

    assert generator.generate() == "ado-pat-token"
    provider.create_pat_with_manifest.assert_called_once()
