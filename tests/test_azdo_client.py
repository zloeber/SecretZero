"""Tests for Azure DevOps REST error reporting."""

from unittest.mock import MagicMock

import pytest
import requests

from secretzero.providers.azdo_client import AzdoClient, ado_error_message


def _http_error(
    message: str = "400 Client Error: Bad Request for url: https://dev.azure.com/org/p",
):
    response = MagicMock()
    response.raise_for_status.side_effect = requests.HTTPError(message)
    return response


def test_put_error_includes_ado_message_only():
    client = AzdoClient("org", "pat-token")
    response = _http_error()
    response.json.return_value = {
        "message": "Project information name is not valid for variable group.",
        "typeKey": "ArgumentException",
        "value": "secret-value-should-not-leak",
    }
    client._session.put = MagicMock(return_value=response)

    with pytest.raises(requests.HTTPError) as exc_info:
        client.put("https://dev.azure.com/org/proj/_apis/distributedtask/variablegroups/1")

    text = str(exc_info.value)
    assert "Project information name is not valid for variable group." in text
    assert "typeKey" not in text
    assert "secret-value-should-not-leak" not in text


def test_put_error_ignores_non_json_body():
    client = AzdoClient("org", "pat-token")
    response = _http_error()
    response.json.side_effect = ValueError("not json")
    response.text = "secret-value-should-not-leak"
    client._session.put = MagicMock(return_value=response)

    with pytest.raises(requests.HTTPError) as exc_info:
        client.put("https://dev.azure.com/org/_apis/distributedtask/variablegroups/1")

    assert "secret-value-should-not-leak" not in str(exc_info.value)


def test_ado_error_message_truncates():
    response = MagicMock()
    response.json.return_value = {"message": "x" * 400}
    detail = ado_error_message(response)
    assert detail is not None
    assert len(detail) == 300
    assert detail.endswith("...")


def test_organization_url_omits_project():
    client = AzdoClient("my org", "pat-token")
    assert (
        client.organization_url("_apis/distributedtask/variablegroups/7")
        == "https://dev.azure.com/my org/_apis/distributedtask/variablegroups/7"
    )
    assert "/proj/" not in client.organization_url("_apis/distributedtask/variablegroups")
