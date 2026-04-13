"""Static generator: dict values and static_payload_needs_prompt."""

import pytest

from secretzero.generators.static import StaticGenerator, static_payload_needs_prompt


def test_static_payload_needs_prompt_top_level() -> None:
    assert static_payload_needs_prompt(None) is True
    assert static_payload_needs_prompt("") is False
    assert static_payload_needs_prompt("  ") is False
    assert static_payload_needs_prompt("${MISSING}") is True
    assert static_payload_needs_prompt("ok") is False


def test_static_payload_needs_prompt_nested_empty_string() -> None:
    assert static_payload_needs_prompt({"a": ""}, nested=False) is True
    assert static_payload_needs_prompt({"a": "x", "b": ""}, nested=False) is True
    assert static_payload_needs_prompt({"a": "x"}, nested=False) is False


def test_static_dict_prompts_sorted_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dict leaves prompt in sorted key order; instructions only before first prompt."""
    # Sorted keys: client_id, client_secret, tenant_id
    inputs = iter(["cid", "csecret", "tid"])

    def fake_input(_prompt: str) -> str:
        return next(inputs)

    monkeypatch.setattr("builtins.input", fake_input)
    gen = StaticGenerator(
        {
            "value": {
                "tenant_id": None,
                "client_id": "",
                "client_secret": "${UNSET}",
            },
            "prompt_on_empty": True,
        }
    )
    gen.field_description = "Secret: entra"
    gen.hide_input = False
    out = gen.generate()
    assert out == {
        "client_id": "cid",
        "client_secret": "csecret",
        "tenant_id": "tid",
    }


def test_static_dict_no_prompt_when_prompt_disabled() -> None:
    gen = StaticGenerator(
        {"value": {"tenant_id": None}, "prompt_on_empty": False},
    )
    with pytest.raises(ValueError, match="tenant_id"):
        gen.generate()


def test_static_dict_preserves_prefilled_leaves(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _: "only-secret")
    gen = StaticGenerator(
        {
            "value": {
                "tenant_id": "00000000-0000-0000-0000-000000000001",
                "client_secret": None,
            },
            "prompt_on_empty": True,
        }
    )
    gen.hide_input = False
    out = gen.generate()
    assert out["tenant_id"] == "00000000-0000-0000-0000-000000000001"
    assert out["client_secret"] == "only-secret"


def test_static_dict_rejects_list_values() -> None:
    gen = StaticGenerator({"value": {"items": [1, 2]}, "prompt_on_empty": False})
    with pytest.raises(ValueError, match="list"):
        gen.generate()
