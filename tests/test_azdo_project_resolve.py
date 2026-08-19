"""Tests for Azure DevOps client and project resolution."""

from unittest.mock import MagicMock, patch

import pytest

from secretzero.providers.azdo_client import AzdoClient
from secretzero.providers.azdo_project_resolve import (
    parse_azdo_remote_project,
    resolve_azdo_project,
)


def test_parse_azdo_remote_project_https():
    project = parse_azdo_remote_project(
        "https://dev.azure.com/myorg/my-project/_git/my-repo",
        organization="myorg",
    )
    assert project == "my-project"


def test_resolve_azdo_project_explicit():
    assert resolve_azdo_project(project="my-project", organization="myorg") == "my-project"


def test_resolve_azdo_project_from_ci_env():
    with patch.dict("os.environ", {"SYSTEM_TEAMPROJECT": "pipeline-project"}, clear=False):
        assert resolve_azdo_project(project="auto", organization="myorg") == "pipeline-project"


def test_azdo_client_connection_data():
    client = AzdoClient("myorg", "pat-token")
    client.get = MagicMock(return_value={"authenticatedUser": {"providerDisplayName": "Test User"}})
    data = client.connection_data()
    assert data["authenticatedUser"]["providerDisplayName"] == "Test User"
