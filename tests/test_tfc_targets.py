"""Tests for Terraform Cloud targets and lockfile ids."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from secretzero.sync import SyncEngine
from secretzero.targets.terraform_cloud import TfcVarsetVariableTarget, TfcWorkspaceVariableTarget


def test_workspace_target_stores_and_hides_sensitive_value():
    provider = MagicMock()
    provider.read_variable.return_value = {
        "key": "API_TOKEN",
        "sensitive": True,
        "value": None,
    }
    target = TfcWorkspaceVariableTarget(
        provider,
        {"workspace": "network-prod", "key": "API_TOKEN", "category": "env"},
    )

    assert target.store("API_TOKEN", "example-value") is True
    provider.upsert_workspace_variable.assert_called_once()
    kwargs = provider.upsert_workspace_variable.call_args.kwargs
    assert kwargs["workspace"] == "network-prod"
    assert kwargs["key"] == "API_TOKEN"
    assert kwargs["sensitive"] is True
    assert target.retrieve("API_TOKEN") is None


def test_varset_target_returns_nonsensitive_value():
    provider = MagicMock()
    provider.read_variable.return_value = {
        "key": "LOG_LEVEL",
        "sensitive": False,
        "value": "debug",
    }
    target = TfcVarsetVariableTarget(
        provider,
        {"varset": "shared-prod", "key": "LOG_LEVEL", "sensitive": False},
    )

    assert target.retrieve("LOG_LEVEL") == "debug"
    assert target.validate() == (True, None)


def test_workspace_target_requires_workspace():
    target = TfcWorkspaceVariableTarget(MagicMock(), {})
    ok, message = target.validate()
    assert ok is False
    assert message is not None
    assert "workspace" in message


def test_target_ids_use_workspace_and_varset():
    workspace = SimpleNamespace(
        provider="tfc",
        kind="tfc_workspace_variable",
        config={"workspace": "network-prod", "key": "API_TOKEN"},
    )
    varset = SimpleNamespace(
        provider="tfc",
        kind="tfc_varset_variable",
        config={"varset": "shared-prod", "key": "API_TOKEN"},
    )
    assert SyncEngine._build_target_id(workspace) == "tfc/tfc_workspace_variable/network-prod"
    assert SyncEngine._build_target_id(varset) == "tfc/tfc_varset_variable/shared-prod"
