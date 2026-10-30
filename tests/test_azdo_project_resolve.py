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


def test_connection_data_requests_preview_api_version():
    """connectionData rejects api-version 7.1; auth must call the preview version."""
    client = AzdoClient("myorg", "pat-token")
    response = MagicMock()
    response.status_code = 200
    response.content = b'{"authenticatedUser":{"providerDisplayName":"Test User"}}'
    response.json.return_value = {"authenticatedUser": {"providerDisplayName": "Test User"}}
    with patch.object(client._session, "get", return_value=response) as session_get:
        data = client.connection_data()

    assert data["authenticatedUser"]["providerDisplayName"] == "Test User"
    session_get.assert_called_once()
    url = session_get.call_args.args[0]
    assert url == "https://dev.azure.com/myorg/_apis/connectionData"
    assert session_get.call_args.kwargs["params"]["api-version"] == "7.1-preview.1"
