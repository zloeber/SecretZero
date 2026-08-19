"""Tests for target value coercion in sync engine."""

import json

from secretzero.models import TargetConfig, TargetKind
from secretzero.sync import SyncEngine


def test_coerce_target_store_value_extracts_token_field():
    target = TargetConfig(
        provider="gitlab",
        kind=TargetKind.GITLAB_GROUP_VARIABLE,
        config={"group": "myorg", "value_field": "token"},
    )
    payload = json.dumps({"token": "glpat-secret", "token_id": 1})
    assert SyncEngine._coerce_target_store_value(payload, target) == "glpat-secret"
