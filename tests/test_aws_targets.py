"""Tests for AWS target formatting behavior."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from secretzero.providers.aws import AWSAuth, AWSProvider
from secretzero.targets.aws import SecretsManagerTarget, SSMParameterTarget


def _provider_with_mocked_auth(client_name: str, client: MagicMock) -> SimpleNamespace:
    """Build a minimal provider object with AWSAuth for target tests."""
    auth = AWSAuth({"region": "us-east-1"})
    auth.get_client = MagicMock(return_value=client)
    return SimpleNamespace(auth=auth, name="aws", provider_kind="aws")


def test_ssm_parameter_target_json_format_serializes_dict_payload() -> None:
    """`format: json` should store object values as JSON in SSM Parameter Store."""
    ssm = MagicMock()
    provider = _provider_with_mocked_auth("ssm", ssm)
    target = SSMParameterTarget(provider, {"name": "/app/config", "format": "json"})

    assert target.store("app_config", {"enabled": True, "retries": 3}) is True

    ssm.put_parameter.assert_called_once()
    assert json.loads(ssm.put_parameter.call_args.kwargs["Value"]) == {
        "enabled": True,
        "retries": 3,
    }


def test_secrets_manager_target_json_format_rejects_invalid_json_string() -> None:
    """`format: json` should reject invalid JSON payloads for Secrets Manager."""
    sm = MagicMock()
    provider = _provider_with_mocked_auth("secretsmanager", sm)
    target = SecretsManagerTarget(provider, {"name": "app/config", "format": "json"})

    with pytest.raises(ValueError, match="Invalid JSON"):
        target.store("app_config", "{invalid-json")

    sm.create_secret.assert_not_called()
    sm.update_secret.assert_not_called()


def test_ssm_parameter_target_json_format_rejects_invalid_json_string() -> None:
    """`format: json` should reject invalid JSON payloads for SSM Parameter Store."""
    ssm = MagicMock()
    provider = _provider_with_mocked_auth("ssm", ssm)
    target = SSMParameterTarget(provider, {"name": "/app/config", "format": "json"})

    with pytest.raises(ValueError, match="Invalid JSON"):
        target.store("app_config", "{invalid-json")

    ssm.put_parameter.assert_not_called()


def test_ssm_parameter_target_json_format_retrieves_object_payload() -> None:
    """`format: json` should parse stored JSON back into an object for round-tripping."""
    ssm = MagicMock()
    ssm.get_parameter.return_value = {"Parameter": {"Value": '{"enabled": true, "retries": 3}'}}
    provider = _provider_with_mocked_auth("ssm", ssm)
    target = SSMParameterTarget(provider, {"name": "/app/config", "format": "json"})

    result = target.retrieve("app_config")

    assert result == {"enabled": True, "retries": 3}


def test_secrets_manager_target_json_format_retrieves_object_payload() -> None:
    """`format: json` should parse stored JSON back into an object for round-tripping."""
    sm = MagicMock()
    sm.get_secret_value.return_value = {"SecretString": '{"enabled": true, "retries": 3}'}
    provider = _provider_with_mocked_auth("secretsmanager", sm)
    target = SecretsManagerTarget(provider, {"name": "app/config", "format": "json"})

    result = target.retrieve("app_config")

    assert result == {"enabled": True, "retries": 3}


def test_aws_provider_target_details_document_json_format() -> None:
    """AWS provider help metadata should advertise JSON target formatting."""
    ssm_config = AWSProvider.target_details["ssm_parameter"]["config"]
    secrets_config = AWSProvider.target_details["secrets_manager"]["config"]

    assert "format" in ssm_config
    assert "json" in str(ssm_config["format"]).lower()
    assert "format" in secrets_config
    assert "json" in str(secrets_config["format"]).lower()
