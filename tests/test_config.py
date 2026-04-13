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


def test_load_var_file() -> None:
    """Test loading a .szvar variable file."""
    loader = ConfigLoader()
    var_content = """
environment: dev
region: us-east-1
database:
  host: dev-db.example.com
  port: 5432
"""
    with NamedTemporaryFile(mode="w", suffix=".szvar", delete=False) as f:
        f.write(var_content)
        var_path = Path(f.name)

    try:
        variables = loader.load_var_file(var_path)
        assert variables["environment"] == "dev"
        assert variables["region"] == "us-east-1"
        assert variables["database"]["host"] == "dev-db.example.com"
        assert variables["database"]["port"] == 5432
    finally:
        var_path.unlink()


def test_load_var_file_not_found() -> None:
    """Test loading a non-existent .szvar file."""
    loader = ConfigLoader()
    with pytest.raises(FileNotFoundError):
        loader.load_var_file(Path("nonexistent.szvar"))


def test_load_var_file_invalid() -> None:
    """Test loading an invalid .szvar file (not a dictionary)."""
    loader = ConfigLoader()
    var_content = """
- item1
- item2
"""
    with NamedTemporaryFile(mode="w", suffix=".szvar", delete=False) as f:
        f.write(var_content)
        var_path = Path(f.name)

    try:
        with pytest.raises(ValueError, match="must contain a dictionary"):
            loader.load_var_file(var_path)
    finally:
        var_path.unlink()


def test_merge_variables_flat() -> None:
    """Test merging flat variable dictionaries."""
    loader = ConfigLoader()
    base = {"environment": "local", "region": "us-east-1", "debug": False}
    override = {"environment": "dev", "debug": True}

    merged = loader.merge_variables(base, override)

    assert merged["environment"] == "dev"  # overridden
    assert merged["region"] == "us-east-1"  # preserved
    assert merged["debug"] is True  # overridden


def test_merge_variables_nested() -> None:
    """Test deep merging of nested variable dictionaries."""
    loader = ConfigLoader()
    base = {
        "database": {"host": "localhost", "port": 5432, "name": "myapp"},
        "features": {"debug": False},
    }
    override = {
        "database": {"host": "dev-db.example.com"},
        "features": {"debug": True, "log_level": "debug"},
    }

    merged = loader.merge_variables(base, override)

    # Check database values
    assert merged["database"]["host"] == "dev-db.example.com"  # overridden
    assert merged["database"]["port"] == 5432  # preserved
    assert merged["database"]["name"] == "myapp"  # preserved

    # Check features values
    assert merged["features"]["debug"] is True  # overridden
    assert merged["features"]["log_level"] == "debug"  # added


def test_load_file_with_single_var_file() -> None:
    """Test loading Secretfile with a single .szvar file."""
    loader = ConfigLoader()

    # Create base Secretfile
    secretfile_content = """
version: '1.0'
variables:
  environment: local
  region: us-east-1
providers:
  local:
    kind: local
secrets:
  - name: test_secret
    kind: static
    config:
      value: "env={{var.environment}} region={{var.region}}"
    targets:
      - provider: local
        kind: file
        config:
          path: ".env.{{var.environment}}"
templates: {}
"""

    # Create var file
    var_content = """
environment: dev
region: us-west-2
"""

    with (
        NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as sf,
        NamedTemporaryFile(mode="w", suffix=".szvar", delete=False) as vf,
    ):
        sf.write(secretfile_content)
        secretfile_path = Path(sf.name)

        vf.write(var_content)
        var_path = Path(vf.name)

    try:
        config = loader.load_file(secretfile_path, var_files=[var_path])

        # Check that variables were merged
        assert config.variables["environment"] == "dev"  # overridden
        assert config.variables["region"] == "us-west-2"  # overridden

        # Check that interpolation used the merged variables
        secret = config.secrets[0]
        assert secret.config["value"] == "env=dev region=us-west-2"
        assert secret.targets[0].config["path"] == ".env.dev"
    finally:
        secretfile_path.unlink()
        var_path.unlink()


def test_load_file_with_multiple_var_files() -> None:
    """Test loading Secretfile with multiple .szvar files (later takes precedence)."""
    loader = ConfigLoader()

    # Create base Secretfile
    secretfile_content = """
version: '1.0'
variables:
  environment: local
  region: us-east-1
  namespace: default
providers:
  local:
    kind: local
secrets:
  - name: test_secret
    kind: static
    config:
      value: "{{var.environment}}-{{var.region}}-{{var.namespace}}"
    targets:
      - provider: local
        kind: file
        config:
          path: .env
templates: {}
"""

    # Create first var file
    var1_content = """
environment: staging
region: us-west-1
"""

    # Create second var file (should override first)
    var2_content = """
environment: prod
namespace: production
"""

    with (
        NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as sf,
        NamedTemporaryFile(mode="w", suffix=".szvar", delete=False) as vf1,
        NamedTemporaryFile(mode="w", suffix=".szvar", delete=False) as vf2,
    ):
        sf.write(secretfile_content)
        secretfile_path = Path(sf.name)

        vf1.write(var1_content)
        var1_path = Path(vf1.name)

        vf2.write(var2_content)
        var2_path = Path(vf2.name)

    try:
        config = loader.load_file(secretfile_path, var_files=[var1_path, var2_path])

        # Check merge order: base < var1 < var2
        assert config.variables["environment"] == "prod"  # from var2 (overrides var1)
        assert config.variables["region"] == "us-west-1"  # from var1 (not in var2)
        assert config.variables["namespace"] == "production"  # from var2 (overrides base)

        # Check interpolation result
        secret = config.secrets[0]
        assert secret.config["value"] == "prod-us-west-1-production"
    finally:
        secretfile_path.unlink()
        var1_path.unlink()
        var2_path.unlink()


def test_load_file_with_nested_var_override() -> None:
    """Test loading Secretfile with nested variable overrides."""
    loader = ConfigLoader()

    # Create base Secretfile with nested variables
    secretfile_content = """
version: '1.0'
variables:
  database:
    host: localhost
    port: 5432
    credentials:
      username: admin
      password: secret
providers:
  local:
    kind: local
secrets:
  - name: db_config
    kind: static
    config:
      value: "{{var.database.host}}:{{var.database.port}}"
    targets:
      - provider: local
        kind: file
        config:
          path: .env
templates: {}
"""

    # Create var file that partially overrides nested structure
    var_content = """
database:
  host: dev-db.example.com
  credentials:
    username: dev_admin
"""

    with (
        NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as sf,
        NamedTemporaryFile(mode="w", suffix=".szvar", delete=False) as vf,
    ):
        sf.write(secretfile_content)
        secretfile_path = Path(sf.name)

        vf.write(var_content)
        var_path = Path(vf.name)

    try:
        config = loader.load_file(secretfile_path, var_files=[var_path])

        # Check deep merge
        assert config.variables["database"]["host"] == "dev-db.example.com"  # overridden
        assert config.variables["database"]["port"] == 5432  # preserved from base
        assert config.variables["database"]["credentials"]["username"] == "dev_admin"  # overridden
        assert (
            config.variables["database"]["credentials"]["password"] == "secret"
        )  # preserved from base

        # Check interpolation
        secret = config.secrets[0]
        assert secret.config["value"] == "dev-db.example.com:5432"
    finally:
        secretfile_path.unlink()
        var_path.unlink()


def test_validate_file_with_var_file() -> None:
    """Test validating Secretfile with var file."""
    loader = ConfigLoader()

    secretfile_content = """
version: '1.0'
variables:
  environment: local
providers:
  local:
    kind: local
secrets: []
templates: {}
"""

    var_content = """
environment: dev
"""

    with (
        NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as sf,
        NamedTemporaryFile(mode="w", suffix=".szvar", delete=False) as vf,
    ):
        sf.write(secretfile_content)
        secretfile_path = Path(sf.name)

        vf.write(var_content)
        var_path = Path(vf.name)

    try:
        is_valid, message = loader.validate_file(secretfile_path, var_files=[var_path])
        assert is_valid
        assert "Valid" in message
    finally:
        secretfile_path.unlink()
        var_path.unlink()
