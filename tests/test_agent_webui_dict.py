"""Vector 2 / network web forms for structured static secrets."""

from __future__ import annotations

import json

import pytest

from secretzero.agent_webui import (
    build_pending_static_values_from_form,
    json_bulk_field_key,
    leaf_field_key,
    static_dict_needs_leaf_prompts,
    static_secret_edit_template_vars,
)
from secretzero.models import Secret, Secretfile


def test_static_dict_needs_leaf_prompts_nested() -> None:
    sf = Secretfile(
        secrets=[
            Secret(
                name="cfg",
                kind="static",
                config={
                    "value": {"a": None, "b": {"c": ""}},
                    "prompt_on_empty": False,
                },
                targets=[],
            )
        ],
    )
    sec = sf.secrets[0]
    assert static_dict_needs_leaf_prompts(sec) is True


def test_build_pending_from_leaf_fields() -> None:
    sf = Secretfile(
        secrets=[
            Secret(
                name="cfg",
                kind="static",
                config={"value": {"client_id": None, "client_secret": None}},
                targets=[],
            )
        ],
    )
    sec = sf.secrets[0]
    k1 = leaf_field_key("cfg", ("client_id",))
    k2 = leaf_field_key("cfg", ("client_secret",))
    form = {k1: "id1", k2: "sec1"}
    vals, err = build_pending_static_values_from_form(["cfg"], sf, form)
    assert err is None
    assert vals == {"cfg": {"client_id": "id1", "client_secret": "sec1"}}


def test_build_pending_from_json_bulk() -> None:
    sf = Secretfile(
        secrets=[
            Secret(
                name="cfg",
                kind="static",
                config={"value": {"client_id": None}},
                targets=[],
            )
        ],
    )
    jk = json_bulk_field_key("cfg")
    form = {jk: json.dumps({"client_id": "from-json"})}
    vals, err = build_pending_static_values_from_form(["cfg"], sf, form)
    assert err is None
    assert vals == {"cfg": {"client_id": "from-json"}}


def test_build_pending_json_invalid() -> None:
    sf = Secretfile(
        secrets=[
            Secret(
                name="cfg",
                kind="static",
                config={"value": {"client_id": None}},
                targets=[],
            )
        ],
    )
    jk = json_bulk_field_key("cfg")
    form = {jk: "not-json"}
    vals, err = build_pending_static_values_from_form(["cfg"], sf, form)
    assert vals is None
    assert err is not None
    assert "Invalid JSON" in (err or "")


def test_static_secret_edit_template_vars() -> None:
    sec = Secret(
        name="cfg",
        kind="static",
        config={"value": {"x": None}},
        targets=[],
    )
    ctx = static_secret_edit_template_vars(sec, None)
    assert ctx["structured"] is True
    assert len(ctx["dict_leaves"]) == 1
    assert ctx["dict_leaves"][0]["label"] == "x"
    assert ctx["json_field_name"] == json_bulk_field_key("cfg")


@pytest.mark.parametrize(
    ("config", "structured"),
    [
        ({"value": "plain"}, False),
        ({"value": {"a": None}}, True),
    ],
)
def test_static_secret_edit_template_scalar_vs_dict(config: dict, structured: bool) -> None:
    sec = Secret(name="s", kind="static", config=config, targets=[])
    ctx = static_secret_edit_template_vars(sec, None)
    assert ctx["structured"] is structured
