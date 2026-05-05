"""Unit tests for network web dashboard row building."""

import json
from pathlib import Path

from secretzero.lockfile import Lockfile
from secretzero.models import Secret, Secretfile, TargetConfig
from secretzero.network_web_dashboard import (
    _ARROW_TITLE,
    build_secret_rows,
    build_target_lane_ui,
    compute_is_unsynced,
    lane_identity_blocked,
    target_groups_show_only_unsynced_lanes,
)
from secretzero.network_web_templates_jinja import TEMPLATES


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
    assert groups[0]["lanes"][0]["arrow_css_class"] == "synced"
    assert groups[0]["lanes"][1]["sync_state"] == "drift"
    assert groups[0]["lanes"][1]["arrow_css_class"] == "drift"
    assert groups[1]["lanes"][0]["sync_state"] == "pending"
    assert groups[1]["lanes"][0]["arrow_css_class"] == "pending"
    # Per-target metadata (entry key = manifest secret name for file targets)
    lane0 = groups[0]["lanes"][0]
    assert lane0["dest"] == ".env.a"
    assert any(d["label"] == "Entry key" and d["value"] == "api_key" for d in lane0["details"])


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


def test_lane_identity_blocked_maps_failed_provider_rows() -> None:
    pf = {
        "has_policies": True,
        "all_ok": False,
        "preflight_error": False,
        "rows": [
            {
                "policy_name": "aws-account",
                "provider_alias": "aws",
                "status": "policy_failed",
                "detail": "account mismatch",
            }
        ],
    }
    blocked, reason = lane_identity_blocked("aws", pf)
    assert blocked is True
    assert "aws-account" in reason
    assert lane_identity_blocked("vault", pf)[0] is False


def test_build_secret_rows_arrow_unknown_when_identity_blocked(
    tmp_path: Path,
) -> None:
    sf = Secretfile(
        version="1.0",
        secrets=[
            Secret(
                name="s",
                kind="static",
                config={"value": "x"},
                targets=[
                    TargetConfig(provider="aws", kind="ssm_parameter", config={"name": "/x"}),
                ],
            )
        ],
    )
    lk_path = tmp_path / "l.lock"
    lk_path.write_text(
        '{"version":"1.0","secrets":{"s":{"hash":"H","created_at":"t","updated_at":"t","targets":{}}}}'
        + "\n"
    )
    lk = Lockfile.load(lk_path)
    pf = {
        "has_policies": True,
        "all_ok": False,
        "preflight_error": False,
        "rows": [
            {
                "policy_name": "p",
                "provider_alias": "aws",
                "status": "policy_failed",
                "detail": "no match",
            }
        ],
    }
    rows = build_secret_rows(sf, lk, identity_preflight=pf)
    lane = rows[0]["target_groups"][0]["lanes"][0]
    assert lane["arrow_css_class"] == "unknown"
    assert lane["lane_identity_blocked"] is True


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


def test_pending_target_status_uses_unsynced_copy() -> None:
    assert _ARROW_TITLE["pending"] == "This target is unsynced — run Sync."


def test_dashboard_legend_uses_unsynced_white_pending_color() -> None:
    dashboard_template = TEMPLATES["dashboard.html"]
    base_template = TEMPLATES["base.html"]

    assert "Pending</span>" not in dashboard_template
    assert "Unsynced</span>" in dashboard_template
    assert "--flow-pending: #fff;" in base_template


def test_build_secret_rows_marks_actions_blocked_for_policy_or_auth_failures(
    tmp_path: Path,
) -> None:
    sf = Secretfile(
        version="1.0",
        secrets=[
            Secret(
                name="cfg",
                kind="static",
                config={"value": "x"},
                targets=[
                    TargetConfig(provider="aws", kind="ssm_parameter", config={"name": "/cfg"}),
                ],
            )
        ],
    )
    lk_path = tmp_path / "l.lock"
    lk_path.write_text('{"version":"1.0","secrets":{"cfg":{"hash":"H","created_at":"t","updated_at":"t"}}}\n')
    lk = Lockfile.load(lk_path)
    pf = {
        "has_policies": True,
        "all_ok": False,
        "preflight_error": False,
        "rows": [
            {
                "policy_name": "provider-auth",
                "provider_alias": "aws",
                "status": "auth_failed",
                "detail": "Missing credentials",
            }
        ],
    }

    row = build_secret_rows(sf, lk, identity_preflight=pf)[0]
    assert row["actions_blocked"] is True
    assert "provider-auth" in row["actions_blocked_reason"]


def test_dashboard_template_has_blocked_actions_note_and_sync_gating() -> None:
    dashboard_template = TEMPLATES["dashboard.html"]
    assert "Policy/auth check failed for one or more targets." in dashboard_template
    assert "{% if row.actions_blocked %}" in dashboard_template
    assert "{% if not row.actions_blocked %}" in dashboard_template


def test_secret_edit_template_supports_show_values_toggle() -> None:
    secret_edit_template = TEMPLATES["secret_edit.html"]
    assert 'id="sz-show-values"' in secret_edit_template
    assert "Toggle visibility for password fields on this form." in secret_edit_template


def test_dashboard_template_uses_collapsed_expandable_sections() -> None:
    dashboard_template = TEMPLATES["dashboard.html"]
    assert '<details class="sz-expand">' in dashboard_template
    assert "Secretfile & runtime context" in dashboard_template
    assert "Provider identity" in dashboard_template
    assert '<details class="sz-flow-details">' in dashboard_template
