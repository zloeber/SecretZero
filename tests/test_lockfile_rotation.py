"""Tests for lockfile rotation tracking."""

import pytest
from datetime import UTC, datetime
from pathlib import Path
import tempfile
import json

from secretzero.lockfile import Lockfile, SecretLockEntry


class TestSecretLockEntryRotation:
    """Tests for rotation tracking in lock entries."""
    
    def test_new_entry_no_rotation(self):
        """Test that new entries have no rotation history."""
        entry = SecretLockEntry(
            hash="abc123",
            created_at=datetime.now(UTC).isoformat(),
            updated_at=datetime.now(UTC).isoformat(),
        )
        
        assert entry.last_rotated is None
        assert entry.rotation_count == 0
    
    def test_entry_with_rotation(self):
        """Test entry with rotation history."""
        now = datetime.now(UTC).isoformat()
        entry = SecretLockEntry(
            hash="abc123",
            created_at=now,
            updated_at=now,
            last_rotated=now,
            rotation_count=2,
        )
        
        assert entry.last_rotated == now
        assert entry.rotation_count == 2


class TestLockfileRotation:
    """Tests for lockfile rotation tracking."""
    
    def test_add_secret_without_rotation(self):
        """Test adding a secret without rotation flag."""
        lockfile = Lockfile()
        lockfile.add_secret("test", "value123", is_rotation=False)
        
        entry = lockfile.get_secret_info("test")
        assert entry is not None
        assert entry.rotation_count == 0
        assert entry.last_rotated is None
    
    def test_add_secret_with_rotation(self):
        """Test adding a secret with rotation flag."""
        lockfile = Lockfile()
        
        # Add initial secret
        lockfile.add_secret("test", "value123", is_rotation=False)
        entry1 = lockfile.get_secret_info("test")
        initial_hash = entry1.hash
        
        # Rotate secret
        lockfile.add_secret("test", "newvalue456", is_rotation=True)
        entry2 = lockfile.get_secret_info("test")
        
        assert entry2.rotation_count == 1
        assert entry2.last_rotated is not None
        assert entry2.hash != initial_hash
    
    def test_rotation_not_counted_if_value_unchanged(self):
        """Test that rotation count doesn't increment if value is the same."""
        lockfile = Lockfile()
        
        # Add initial secret
        lockfile.add_secret("test", "value123", is_rotation=False)
        
        # "Rotate" with same value
        lockfile.add_secret("test", "value123", is_rotation=True)
        entry = lockfile.get_secret_info("test")
        
        # Rotation count should not increment for unchanged value
        assert entry.rotation_count == 0
        assert entry.last_rotated is None
    
    def test_multiple_rotations(self):
        """Test multiple rotations increment count."""
        lockfile = Lockfile()
        
        # Add initial secret
        lockfile.add_secret("test", "value1", is_rotation=False)
        
        # Rotate multiple times
        lockfile.add_secret("test", "value2", is_rotation=True)
        lockfile.add_secret("test", "value3", is_rotation=True)
        lockfile.add_secret("test", "value4", is_rotation=True)
        
        entry = lockfile.get_secret_info("test")
        assert entry.rotation_count == 3
        assert entry.last_rotated is not None
    
    def test_update_without_rotation_flag(self):
        """Test that updating without rotation flag doesn't affect count."""
        lockfile = Lockfile()
        
        # Add initial secret
        lockfile.add_secret("test", "value1", is_rotation=False)
        
        # Update without rotation flag
        lockfile.add_secret("test", "value2", is_rotation=False)
        
        entry = lockfile.get_secret_info("test")
        assert entry.rotation_count == 0
        assert entry.last_rotated is None
    
    def test_get_secret_info(self):
        """Test retrieving secret info."""
        lockfile = Lockfile()
        lockfile.add_secret("test", "value123")
        
        info = lockfile.get_secret_info("test")
        assert info is not None
        assert info.hash is not None
        
        # Non-existent secret
        assert lockfile.get_secret_info("nonexistent") is None
    
    def test_lockfile_persistence(self):
        """Test that rotation data persists across save/load."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lockfile_path = Path(tmpdir) / ".gitsecrets.lock"
            
            # Create and populate lockfile
            lockfile1 = Lockfile()
            lockfile1.add_secret("test", "value1", is_rotation=False)
            lockfile1.add_secret("test", "value2", is_rotation=True)
            lockfile1.save(lockfile_path)
            
            # Load and verify
            lockfile2 = Lockfile.load(lockfile_path)
            entry = lockfile2.get_secret_info("test")
            
            assert entry.rotation_count == 1
            assert entry.last_rotated is not None
    
    def test_lockfile_version_compatibility(self):
        """Test that lockfiles with new fields are compatible."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lockfile_path = Path(tmpdir) / ".gitsecrets.lock"
            
            # Create lockfile with old format (no rotation fields)
            now = datetime.now(UTC).isoformat()
            old_format = {
                "version": "1.0",
                "secrets": {
                    "test": {
                        "hash": "abc123",
                        "created_at": now,
                        "updated_at": now,
                        "targets": {}
                    }
                },
                "metadata": {}
            }
            
            lockfile_path.write_text(json.dumps(old_format, indent=2))
            
            # Load should work with defaults
            lockfile = Lockfile.load(lockfile_path)
            entry = lockfile.get_secret_info("test")
            
            assert entry.rotation_count == 0
            assert entry.last_rotated is None
