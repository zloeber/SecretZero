"""Gated live validation for Azure DevOps Services.

Skipped unless ``AZDO_PAT``, ``AZDO_ORG``, and ``AZDO_TEST_PROJECT`` are set.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    not (
        os.environ.get("AZDO_PAT")
        and os.environ.get("AZDO_ORG")
        and os.environ.get("AZDO_TEST_PROJECT")
    ),
    reason="Requires AZDO_PAT, AZDO_ORG, and AZDO_TEST_PROJECT",
)


@pytest.fixture
def azdo_provider():
    from secretzero.providers.azure_devops import AzureDevOpsProvider

    provider = AzureDevOpsProvider(
        "azdo",
        config={
            "auth": {
                "kind": "token",
                "config": {
                    "token": os.environ["AZDO_PAT"],
                    "organization": os.environ["AZDO_ORG"],
                },
            },
            "project": os.environ["AZDO_TEST_PROJECT"],
            "organization": os.environ["AZDO_ORG"],
        },
    )
    ok, message = provider.test_connection()
    assert ok, message or "Azure DevOps connection failed"
    return provider


def test_live_azdo_connection_and_identity(azdo_provider):
    info = azdo_provider.auth.get_token_info()
    assert isinstance(info, dict)
    assert info.get("organization") == os.environ["AZDO_ORG"]
    assert info.get("token_type") == "azdo_pat"
    # No plaintext PAT in identity metadata.
    for key, value in info.items():
        if key == "token_type":
            continue
        assert "pat" not in str(value).lower() or key == "token_type"


def test_live_azdo_project_resolve(azdo_provider):
    from secretzero.providers.azdo_project_resolve import resolve_azdo_project

    project = resolve_azdo_project(
        project="auto",
        provider_config=azdo_provider.config or {},
        organization=os.environ["AZDO_ORG"],
    )
    assert project == os.environ["AZDO_TEST_PROJECT"]


def test_live_azdo_variable_group_upsert_and_metadata(azdo_provider):
    """Upsert a secret variable; retrieve must stay metadata-only (None)."""
    from secretzero.providers.azdo_variable_groups import (
        upsert_variable_group_secret,
        variable_group_has_secret,
    )
    from secretzero.targets.azure_devops import AzdoVariableGroupTarget

    client = azdo_provider.auth.get_client()
    project = os.environ["AZDO_TEST_PROJECT"]
    group_name = os.environ.get("AZDO_TEST_VARIABLE_GROUP", "secretzero-live-validation")
    variable_name = "SECRETZERO_LIVE_CHECK"

    upsert_variable_group_secret(
        client,
        project,
        group_name,
        variable_name,
        "live-validation-placeholder",
        create_if_missing=True,
        is_secret=True,
        description="SecretZero gated live validation",
    )
    assert variable_group_has_secret(client, project, group_name, variable_name) is True

    target = AzdoVariableGroupTarget(
        azdo_provider,
        {
            "project": project,
            "variable_group": group_name,
            "variable_name": variable_name,
            "is_secret": True,
        },
    )
    # Azure DevOps never returns secret values via REST after write.
    assert target.retrieve(variable_name) is None
