"""Tests for manifest plaintext policy."""

from pathlib import Path

import pytest
import yaml

from secretzero.config import ConfigLoader
from secretzero.manifest_plaintext import list_manifest_plaintext_violations


def test_strict_allows_placeholder_only(tmp_path: Path) -> None:
    p = tmp_path / "Secretfile.yml"
    p.write_text(
        yaml.dump(
            {
                "secrets": [
                    {
                        "name": "a",
                        "kind": "static",
                        "config": {"default": "${API_TOKEN}"},
                        "targets": [
                            {"provider": "local", "kind": "file", "config": {"path": ".env"}}
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    loader = ConfigLoader()
    sf = loader.load_file(p)
    assert list_manifest_plaintext_violations(sf) == []


def test_strict_flags_literal_scalar(tmp_path: Path) -> None:
    p = tmp_path / "Secretfile.yml"
    p.write_text(
        yaml.dump(
            {
                "secrets": [
                    {
                        "name": "a",
                        "kind": "static",
                        "config": {"default": "sk_live_actual"},
                        "targets": [
                            {"provider": "local", "kind": "file", "config": {"path": ".env"}}
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    loader = ConfigLoader()
    sf = loader.load_file(p)
    v = list_manifest_plaintext_violations(sf)
    assert len(v) == 1
    assert "sk_live_actual" not in v[0]


def test_strict_allows_null_dict_leaves(tmp_path: Path) -> None:
    p = tmp_path / "Secretfile.yml"
    p.write_text(
        yaml.dump(
            {
                "secrets": [
                    {
                        "name": "a",
                        "kind": "static",
                        "config": {"value": {"client_id": None, "client_secret": None}},
                        "targets": [
                            {"provider": "local", "kind": "file", "config": {"path": ".env"}}
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    loader = ConfigLoader()
    sf = loader.load_file(p)
    assert list_manifest_plaintext_violations(sf) == []
