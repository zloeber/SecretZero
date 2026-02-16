"""Tests for configuration loading and variable interpolation."""

from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from secretzero.config import ConfigLoader


def test_load_file_not_found() -> None:
    """Test loading a non-existent file."""
    loader = ConfigLoader()
    with pytest.raises(FileNotFoundError):
        loader.load_file(Path("nonexistent.yml"))


def test_load_empty_file() -> None:
    """Test loading an empty file."""
    loader = ConfigLoader()
    with NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write("")
        path = Path(f.name)

    try:
        with pytest.raises(ValueError):
            loader.load_file(path)
    finally:
        path.unlink()


def test_load_valid_file() -> None:
    """Test loading a valid Secretfile."""
    loader = ConfigLoader()
    content = """
version: '1.0'
variables:
  environment: test
providers:
  local:
    kind: local
secrets:
  - name: test_secret
    kind: random_password
    targets:
      - provider: local
        kind: file
        config:
          path: .env
templates: {}
"""
    with NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(content)
        path = Path(f.name)

    try:
        config = loader.load_file(path)
        assert config.version == "1.0"
        assert config.variables["environment"] == "test"
        assert "local" in config.providers
        assert len(config.secrets) == 1
    finally:
        path.unlink()


def test_variable_interpolation() -> None:
    """Test variable interpolation in configuration."""
    loader = ConfigLoader()
    content = """
version: '1.0'
variables:
  region: us-west-2
  environment: prod
providers:
  aws:
    kind: aws
    config:
      region: "{{var.region}}"
secrets: []
templates: {}
"""
    with NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(content)
        path = Path(f.name)

    try:
        config = loader.load_file(path)
        assert config.providers["aws"].config["region"] == "us-west-2"
    finally:
        path.unlink()


def test_variable_interpolation_with_default() -> None:
    """Test variable interpolation with default values."""
    loader = ConfigLoader()
    content = """
version: '1.0'
variables:
  environment: dev
providers:
  aws:
    kind: aws
    config:
      region: "{{var.region or 'us-east-1'}}"
secrets: []
templates: {}
"""
    with NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(content)
        path = Path(f.name)

    try:
        config = loader.load_file(path)
        assert config.providers["aws"].config["region"] == "us-east-1"
    finally:
        path.unlink()


def test_validate_file() -> None:
    """Test file validation."""
    loader = ConfigLoader()
    content = """
version: '1.0'
variables: {}
providers: {}
secrets: []
templates: {}
"""
    with NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(content)
        path = Path(f.name)

    try:
        is_valid, message = loader.validate_file(path)
        assert is_valid
        assert "Valid" in message
    finally:
        path.unlink()


def test_validate_invalid_file() -> None:
    """Test validation of invalid file."""
    loader = ConfigLoader()
    content = """
invalid: yaml
no: version
"""
    with NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(content)
        path = Path(f.name)

    try:
        is_valid, message = loader.validate_file(path)
        assert not is_valid
        assert "error" in message.lower()
    finally:
        path.unlink()
