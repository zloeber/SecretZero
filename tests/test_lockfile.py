"""Tests for lockfile management."""

import tempfile
from pathlib import Path

from secretzero.lockfile import Lockfile


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
