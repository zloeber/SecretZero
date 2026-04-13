"""Tests for provider identity collection."""

from pathlib import Path

import pytest

from secretzero.config import ConfigLoader
from secretzero.provider_identity import (
    collect_provider_identity_rows,
    primary_identity_label,
    secondary_identity_hint,
)


def test_primary_and_secondary_helpers() -> None:
    assert primary_identity_label({"user": "alice", "arn": "arn:aws:..."}) == "alice"
    assert primary_identity_label({"arn": "arn:aws:sts::123:role/x"}) == "arn:aws:sts::123:role/x"
    hint = secondary_identity_hint({"token_type": "aws_iam", "account": "123"})
    assert "aws_iam" in hint and "123" in hint


def test_collect_empty_providers() -> None:
    from secretzero.models import Secretfile

    sf = Secretfile.model_validate({"version": "1.0", "secrets": []})
    assert collect_provider_identity_rows(sf) == []


@pytest.mark.parametrize(
    "text,expect_local",
    [
        (
            """
version: "1.0"
secrets: []
providers:
  files:
    kind: local
""",
            True,
        ),
    ],
)
def test_collect_local_provider(tmp_path: Path, text: str, expect_local: bool) -> None:
    p = tmp_path / "Secretfile.yml"
    p.write_text(text.strip())
    config = ConfigLoader().load_file(p)
    rows = collect_provider_identity_rows(config)
    assert len(rows) >= 1
    if expect_local:
        assert any(r["status"] == "local" for r in rows)
