"""Tests for lockfile management."""

import tempfile
from pathlib import Path

import json
from datetime import UTC, datetime

from secretzero.lockfile import Lockfile, SecretfileMetadata


class TestLockfile:
    """Test lockfile management."""

    def test_create_empty_lockfile(self):
        """Test creating an empty lockfile."""
        lock = Lockfile()

        assert lock.version == "1.0"
        assert len(lock.secrets) == 0

    def test_add_secret(self):
        """Test adding a secret to lockfile."""
        lock = Lockfile()
        lock.add_secret("test_secret", "secret_value_123")

        assert "test_secret" in lock.secrets
        entry = lock.secrets["test_secret"]
        assert entry.hash
        assert entry.created_at
        assert entry.updated_at

    def test_get_secret_hash(self):
        """Test retrieving secret hash."""
        lock = Lockfile()
        lock.add_secret("test_secret", "secret_value_123")

        hash_value = lock.get_secret_hash("test_secret")
        assert hash_value is not None
        assert len(hash_value) == 64  # SHA-256 hex

    def test_has_secret(self):
        """Test checking if secret exists."""
        lock = Lockfile()
        lock.add_secret("test_secret", "secret_value_123")

        assert lock.has_secret("test_secret")
        assert not lock.has_secret("nonexistent")

    def test_should_update_new_secret(self):
        """Test that new secrets should be updated."""
        lock = Lockfile()

        assert lock.should_update("new_secret", "value")

    def test_should_update_unchanged_secret(self):
        """Test that unchanged secrets should not be updated."""
        lock = Lockfile()
        lock.add_secret("test_secret", "secret_value")

        assert not lock.should_update("test_secret", "secret_value")

    def test_should_update_changed_secret(self):
        """Test that changed secrets should be updated."""
        lock = Lockfile()
        lock.add_secret("test_secret", "old_value")

        assert lock.should_update("test_secret", "new_value")

    def test_update_existing_secret(self):
        """Test updating an existing secret."""
        lock = Lockfile()
        lock.add_secret("test_secret", "old_value")

        old_hash = lock.get_secret_hash("test_secret")
        old_updated = lock.secrets["test_secret"].updated_at

        # Update secret
        lock.add_secret("test_secret", "new_value")

        new_hash = lock.get_secret_hash("test_secret")
        new_updated = lock.secrets["test_secret"].updated_at

        # Hash and timestamp should change
        assert new_hash != old_hash
        assert new_updated != old_updated

    def test_add_secret_with_target(self):
        """Test adding a secret with target tracking."""
        lock = Lockfile()
        lock.add_secret("test_secret", "secret_value", target_id="local/file")

        entry = lock.secrets["test_secret"]
        assert "local/file" in entry.targets
        assert entry.targets["local/file"] == entry.hash

    def test_add_secret_with_dict_value(self):
        """Lockfile hashing should support structured secret values."""
        lock = Lockfile()
        value = {"tenant_id": "t1", "client_id": "c1", "client_secret": "s1"}

        lock.add_secret("entra_app_registration", value)

        assert lock.has_secret("entra_app_registration")
        assert len(lock.get_secret_hash("entra_app_registration") or "") == 64

    def test_save_and_load_lockfile(self):
        """Test saving and loading lockfile."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lockfile_path = Path(tmpdir) / ".gitsecrets.lock"

            # Create and save lockfile
            lock1 = Lockfile()
            lock1.add_secret("secret1", "value1")
            lock1.add_secret("secret2", "value2")
            lock1.save(lockfile_path)

            # Load lockfile
            lock2 = Lockfile.load(lockfile_path)

            assert len(lock2.secrets) == 2
            assert lock2.has_secret("secret1")
            assert lock2.has_secret("secret2")
            assert lock2.get_secret_hash("secret1") == lock1.get_secret_hash("secret1")

    def test_load_nonexistent_lockfile(self):
        """Test loading non-existent lockfile returns empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lockfile_path = Path(tmpdir) / "nonexistent.lock"

            lock = Lockfile.load(lockfile_path)

            assert len(lock.secrets) == 0

    def test_hash_consistency(self):
        """Test that same values produce same hashes."""
        lock = Lockfile()
        lock.add_secret("secret1", "same_value")
        lock.add_secret("secret2", "same_value")

        hash1 = lock.get_secret_hash("secret1")
        hash2 = lock.get_secret_hash("secret2")

        assert hash1 == hash2

    def test_hash_different_values(self):
        """Test that different values produce different hashes."""
        lock = Lockfile()
        lock.add_secret("secret1", "value1")
        lock.add_secret("secret2", "value2")

        hash1 = lock.get_secret_hash("secret1")
        hash2 = lock.get_secret_hash("secret2")

        assert hash1 != hash2

    def test_variable_context_unchanged_when_variables_hash_missing(self) -> None:
        """``variables_hash: null`` must not compare unequal to every current hash forever."""
        lock = Lockfile()
        lock.secretfile = SecretfileMetadata(
            filename="Secretfile.yml",
            hash="abc",
            synced_at=datetime.now(UTC).isoformat(),
            var_files=[],
            variables_hash=None,
        )
        assert not lock.variable_context_changed([], {"environment": "prod"})

    def test_variable_context_changed_when_variables_hash_differs(self) -> None:
        lock = Lockfile()
        vars_a = {"environment": "prod"}
        vars_hash = lock._hash_value(json.dumps(vars_a, sort_keys=True, default=str))
        lock.secretfile = SecretfileMetadata(
            filename="Secretfile.yml",
            hash="abc",
            synced_at=datetime.now(UTC).isoformat(),
            var_files=[],
            variables_hash=vars_hash,
        )
        assert not lock.variable_context_changed([], vars_a)
        assert lock.variable_context_changed([], {"environment": "dev"})

    def test_variable_context_changed_when_var_files_differ(self) -> None:
        lock = Lockfile()
        lock.secretfile = SecretfileMetadata(
            filename="Secretfile.yml",
            hash="abc",
            synced_at=datetime.now(UTC).isoformat(),
            var_files=["previous.szvar"],
            variables_hash="deadbeef",
        )
        assert lock.variable_context_changed([], {"a": 1})
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "other.szvar"
            p.write_text("x: y\n", encoding="utf-8")
            assert lock.variable_context_changed([p], {"a": 1})
