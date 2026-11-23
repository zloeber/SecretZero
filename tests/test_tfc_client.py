"""Tests for the Terraform Cloud JSON:API client."""

from unittest.mock import MagicMock

import pytest

from secretzero.providers.tfc_client import (
    TfcApiError,
    TfcClient,
    api_error_detail,
    normalize_hostname,
)


def test_normalize_hostname_strips_scheme_and_slash():
    assert normalize_hostname(None) == "app.terraform.io"
    assert normalize_hostname(" https://tfe.example.com/ ") == "tfe.example.com"


def test_api_error_detail_uses_detail_and_truncates():
    assert api_error_detail({"errors": [{"detail": "name taken"}]}) == "name taken"
    long_detail = "x" * 400
    trimmed = api_error_detail({"errors": [{"detail": long_detail}]})
    assert trimmed is not None
    assert len(trimmed) == 300
    assert trimmed.endswith("...")


def test_client_create_error_omits_secret_value():
    client = TfcClient(hostname="app.terraform.io", token="test-token")
    response = MagicMock()
    response.status_code = 422
    response.content = b"{}"
    response.json.return_value = {"errors": [{"detail": "category is invalid"}]}
    session = MagicMock()
    session.post.return_value = response
    client._session = session

    with pytest.raises(TfcApiError, match="category is invalid") as exc_info:
        client.create_workspace_variable(
            "ws-1",
            key="API_TOKEN",
            value="super-secret-value",
            category="env",
            sensitive=True,
        )

    message = str(exc_info.value)
    assert "super-secret-value" not in message
    sent = session.post.call_args.kwargs["json"]
    assert sent["data"]["attributes"]["value"] == "super-secret-value"
    assert session.post.call_args.args[0].endswith("/workspaces/ws-1/vars")


def test_client_follows_next_page():
    client = TfcClient(hostname="app.terraform.io", token="test-token")
    first = MagicMock()
    first.status_code = 200
    first.content = b"{}"
    first.json.return_value = {
        "data": [{"id": "varset-1", "attributes": {"name": "one"}}],
        "links": {"next": "https://app.terraform.io/api/v2/organizations/acme/varsets?page=2"},
    }
    second = MagicMock()
    second.status_code = 200
    second.content = b"{}"
    second.json.return_value = {
        "data": [{"id": "varset-2", "attributes": {"name": "two"}}],
        "links": {},
    }
    session = MagicMock()
    session.get.side_effect = [first, second]
    client._session = session

    pages = client.list_varsets("acme")

    assert [item["id"] for item in pages] == ["varset-1", "varset-2"]
    assert session.get.call_count == 2
