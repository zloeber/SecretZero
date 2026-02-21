"""Tests for sync by secret name functionality."""

from pathlib import Path

import pytest

from secretzero.config import ConfigLoader
from secretzero.lockfile import Lockfile
from secretzero.sync import SyncEngine


@pytest.fixture
def sample_secretfile(tmp_path: Path) -> Path:
    """Create a sample Secretfile with multiple secrets.

    Args:
        tmp_path: Pytest temporary directory

    Returns:
        Path to sample Secretfile
    """
    secretfile = tmp_path / "Secretfile.yml"
    secretfile.write_text(
        """
version: '1.0'

providers:
  local:
    kind: local

secrets:
  - name: db_password
    kind: random_password
    config:
      length: 32
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv

  - name: api_key
    kind: random_string
    config:
      length: 64
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv

  - name: jwt_secret
    kind: random_string
    config:
      length: 128
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv
"""
    )
    return secretfile


def test_sync_all_secrets(sample_secretfile: Path, tmp_path: Path):
    """Test syncing all secrets (default behavior)."""
    loader = ConfigLoader()
    config = loader.load_file(sample_secretfile)
    lockfile = Lockfile.load(tmp_path / "test.lock")

    engine = SyncEngine(config, lockfile)
    results = engine.sync(dry_run=True)

    # All 3 secrets should be processed
    assert results["secrets_processed"] == 3
    assert len(results["details"]) == 3


def test_sync_single_secret_by_name(sample_secretfile: Path, tmp_path: Path):
    """Test syncing a single secret by name."""
    loader = ConfigLoader()
    config = loader.load_file(sample_secretfile)
    lockfile = Lockfile.load(tmp_path / "test.lock")

    engine = SyncEngine(config, lockfile)
    results = engine.sync(dry_run=True, secret_names=["db_password"])

    # Only 1 secret should be processed
    assert results["secrets_processed"] == 1
    assert len(results["details"]) == 1
    assert results["details"][0]["name"] == "db_password"


def test_sync_multiple_secrets_by_name(sample_secretfile: Path, tmp_path: Path):
    """Test syncing multiple specific secrets by name."""
    loader = ConfigLoader()
    config = loader.load_file(sample_secretfile)
    lockfile = Lockfile.load(tmp_path / "test.lock")

    engine = SyncEngine(config, lockfile)
    results = engine.sync(dry_run=True, secret_names=["db_password", "jwt_secret"])

    # Only 2 specified secrets should be processed
    assert results["secrets_processed"] == 2
    assert len(results["details"]) == 2

    processed_names = {d["name"] for d in results["details"]}
    assert processed_names == {"db_password", "jwt_secret"}


def test_sync_nonexistent_secret_name(sample_secretfile: Path, tmp_path: Path):
    """Test syncing with a nonexistent secret name."""
    loader = ConfigLoader()
    config = loader.load_file(sample_secretfile)
    lockfile = Lockfile.load(tmp_path / "test.lock")

    engine = SyncEngine(config, lockfile)
    results = engine.sync(dry_run=True, secret_names=["nonexistent_secret"])

    # No secrets should be processed
    assert results["secrets_processed"] == 0

    # Should have a warning error
    assert len(results["errors"]) > 0
    assert "nonexistent_secret" in results["errors"][0]
    assert "not found" in results["errors"][0].lower()


def test_sync_partial_match(sample_secretfile: Path, tmp_path: Path):
    """Test syncing with both valid and invalid secret names."""
    loader = ConfigLoader()
    config = loader.load_file(sample_secretfile)
    lockfile = Lockfile.load(tmp_path / "test.lock")

    engine = SyncEngine(config, lockfile)
    results = engine.sync(
        dry_run=True, secret_names=["db_password", "nonexistent_secret", "api_key"]
    )

    # Only 2 valid secrets should be processed
    assert results["secrets_processed"] == 2

    processed_names = {d["name"] for d in results["details"]}
    assert processed_names == {"db_password", "api_key"}

    # Should have a warning about nonexistent secret
    assert len(results["errors"]) > 0
    assert "nonexistent_secret" in results["errors"][0]


def test_sync_case_sensitive_names(sample_secretfile: Path, tmp_path: Path):
    """Test that secret name matching is case-sensitive."""
    loader = ConfigLoader()
    config = loader.load_file(sample_secretfile)
    lockfile = Lockfile.load(tmp_path / "test.lock")

    engine = SyncEngine(config, lockfile)
    results = engine.sync(dry_run=True, secret_names=["DB_PASSWORD"])

    # Should not match due to case difference
    assert results["secrets_processed"] == 0
    assert len(results["errors"]) > 0
    assert "DB_PASSWORD" in results["errors"][0]


def test_sync_empty_name_list(sample_secretfile: Path, tmp_path: Path):
    """Test syncing with an empty name list (should sync all)."""
    loader = ConfigLoader()
    config = loader.load_file(sample_secretfile)
    lockfile = Lockfile.load(tmp_path / "test.lock")

    engine = SyncEngine(config, lockfile)
    results = engine.sync(dry_run=True, secret_names=[])

    # Empty list should sync all secrets
    assert results["secrets_processed"] == 3


def test_sync_with_duplicates(sample_secretfile: Path, tmp_path: Path):
    """Test syncing with duplicate secret names."""
    loader = ConfigLoader()
    config = loader.load_file(sample_secretfile)
    lockfile = Lockfile.load(tmp_path / "test.lock")

    engine = SyncEngine(config, lockfile)
    results = engine.sync(dry_run=True, secret_names=["db_password", "db_password"])

    # Should only process once despite duplicate
    assert results["secrets_processed"] == 1
    assert results["details"][0]["name"] == "db_password"


def test_sync_preserves_order(sample_secretfile: Path, tmp_path: Path):
    """Test that secrets are processed in Secretfile order, not request order."""
    loader = ConfigLoader()
    config = loader.load_file(sample_secretfile)
    lockfile = Lockfile.load(tmp_path / "test.lock")

    engine = SyncEngine(config, lockfile)
    # Request in different order than Secretfile
    results = engine.sync(dry_run=True, secret_names=["jwt_secret", "db_password"])

    # Should be processed in Secretfile order
    assert results["details"][0]["name"] == "db_password"
    assert results["details"][1]["name"] == "jwt_secret"
