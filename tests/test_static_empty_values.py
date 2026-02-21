"""Test static generator behavior with empty/unresolved values."""

import pytest
from secretzero.generators.static import StaticGenerator


def test_static_generator_unresolved_variable_no_prompt():
    """Test that unresolved variables raise error when prompting is disabled."""
    config = {"value": "${UNSET_VAR}", "prompt_on_empty": False}
    gen = StaticGenerator(config)

    with pytest.raises(ValueError) as exc_info:
        gen.generate()

    assert "unresolved environment variable" in str(exc_info.value).lower()


def test_static_generator_empty_value_no_prompt():
    """Test that empty values raise error when prompting is disabled."""
    config = {"value": None, "prompt_on_empty": False}
    gen = StaticGenerator(config)

    with pytest.raises(ValueError) as exc_info:
        gen.generate()

    assert "required but not provided" in str(exc_info.value).lower()


def test_static_generator_valid_value_no_prompt():
    """Test that valid values work when prompting is disabled."""
    config = {"value": "my-secret-value", "prompt_on_empty": False}
    gen = StaticGenerator(config)

    result = gen.generate()
    assert result == "my-secret-value"


def test_static_generator_supports_both_value_and_default():
    """Test that both 'value' and 'default' config keys are supported."""
    config1 = {"value": "test1"}
    gen1 = StaticGenerator(config1)
    assert gen1.default_value == "test1"

    config2 = {"default": "test2"}
    gen2 = StaticGenerator(config2)
    assert gen2.default_value == "test2"

    # 'default' takes precedence if both are set
    config3 = {"default": "test3", "value": "ignored"}
    gen3 = StaticGenerator(config3)
    assert gen3.default_value == "test3"


def test_static_generator_validation_pattern():
    """Test that validation pattern works correctly."""
    config = {"value": "invalid", "validation": r"^[0-9]+$", "prompt_on_empty": False}
    gen = StaticGenerator(config)

    with pytest.raises(ValueError) as exc_info:
        gen.generate()

    assert "does not match validation pattern" in str(exc_info.value)


def test_static_generator_unresolved_variable_with_prompt():
    """Test that unresolved variables would prompt when prompting enabled."""
    config = {"value": "${UNSET_VAR}", "prompt_on_empty": True}  # Would prompt in interactive mode
    gen = StaticGenerator(config)

    # We can't actually test the prompt in a pytest context,
    # but we can verify the generator is configured correctly
    assert gen.prompt_on_empty is True
    assert gen.default_value == "${UNSET_VAR}"
