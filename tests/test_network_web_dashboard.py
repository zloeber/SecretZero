"""Unit tests for network web dashboard row building."""

import json
from pathlib import Path

from secretzero.lockfile import Lockfile
from secretzero.models import Secret, Secretfile, TargetConfig
from secretzero.network_web_dashboard import (
    build_secret_rows,
    build_target_lane_ui,
    compute_is_unsynced,
    target_groups_show_only_unsynced_lanes,
)


def test_build_secret_rows_groups_targets_and_sync_state(tmp_path: Path) -> None:
    sf = Secretfile(
        version="1.0",
        secrets=[
            Secret(
                name="api_key",
                kind="static",
                config={"value": "x"},
                targets=[
                    TargetConfig(provider="local", kind="file", config={"path": ".env.a"}),
                    TargetConfig(provider="local", kind="file", config={"path": ".env.b"}),
                    TargetConfig(provider="vault", kind="vault_kv", config={"name": "secret/foo"}),
                ],
            )
        ],
    )
    lk_path = tmp_path / "l.lock"
    payload = {
        "version": "1.0",
        "secrets": {
            "api_key": {
                "hash": "HMAIN",
                "created_at": "t",
                "updated_at": "t",
                "targets": {
                    "local/file/.env.a": "HMAIN",
                    "local/file/.env.b": "OTHER",
                },
                "target_provenance": {
                    "local/file/.env.a": [
                        {
                            "updated_at": "t",
                            "actor": {
                                "provider": "local",
                                "os_user": "alice",
                            },
                        }
                    ]
                },
            }
        },
    }
    lk_path.write_text(json.dumps(payload) + "\n")
    lk = Lockfile.load(lk_path)

    rows = build_secret_rows(sf, lk)
    assert len(rows) == 1
    row = rows[0]
    assert row["has_targets"] is True
    groups = row["target_groups"]
    assert len(groups) == 2
    assert groups[0]["provider"] == "local"
    assert groups[0]["kind"] == "file"
    assert len(groups[0]["lanes"]) == 2
    assert groups[0]["lanes"][0]["sync_state"] == "synced"
    assert groups[0]["lanes"][1]["sync_state"] == "drift"
    assert groups[1]["lanes"][0]["sync_state"] == "pending"
    # Per-target metadata (entry key = manifest secret name for file targets)
    lane0 = groups[0]["lanes"][0]
    assert lane0["dest"] == ".env.a"
    assert any(d["label"] == "Entry key" and d["value"] == "api_key" for d in lane0["details"])
    assert lane0["actor_summary"] == "local | alice"


def test_compute_is_unsynced() -> None:
    assert compute_is_unsynced(has_targets=False, in_lock=False, target_groups=[]) is True
    assert compute_is_unsynced(has_targets=False, in_lock=True, target_groups=[]) is False
    g = [{"lanes": [{"sync_state": "synced"}, {"sync_state": "synced"}]}]
    assert compute_is_unsynced(has_targets=True, in_lock=True, target_groups=g) is False
    g2 = [{"lanes": [{"sync_state": "pending"}]}]
    assert compute_is_unsynced(has_targets=True, in_lock=True, target_groups=g2) is True


def test_build_target_lane_ui_github_secret() -> None:
    tc = TargetConfig(
        provider="github",
        kind="github_secret",
        config={
            "owner": "acme",
            "repo": "app",
            "secret_name": "CUSTOM_PYPI_TOKEN",
            "environment": "production",
        },
    )
    ui = build_target_lane_ui("pypi_prod_api_token", tc)
    assert ui["dest"] == "acme/app"
    labels = {d["label"]: d["value"] for d in ui["details"]}
    assert labels["Actions secret"] == "CUSTOM_PYPI_TOKEN"
    assert labels["Environment"] == "production"


def test_target_groups_show_only_unsynced_lanes() -> None:
    groups = [
        {
            "provider": "a",
            "kind": "file",
            "lanes": [
                {"sync_state": "synced", "dest": "x"},
                {"sync_state": "pending", "dest": "y"},
            ],
        }
    ]
    out = target_groups_show_only_unsynced_lanes(groups)
    assert len(out) == 1
    assert len(out[0]["lanes"]) == 1
    assert out[0]["lanes"][0]["sync_state"] == "pending"
