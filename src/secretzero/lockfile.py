"""Lockfile management for secret tracking."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class SecretLockEntry(BaseModel):
    """Lockfile entry for a single secret."""

    hash: str
    created_at: str
    updated_at: str
    last_rotated: str | None = None
    rotation_count: int = 0
    targets: dict[str, str] = Field(default_factory=dict)  # target_id -> hash


class SecretfileMetadata(BaseModel):
    """Metadata about the source Secretfile."""

    filename: str = Field(description="Relative filename of the Secretfile")
    hash: str = Field(description="SHA-256 hash of the Secretfile content")
    synced_at: str = Field(description="ISO 8601 timestamp of last sync")


class Lockfile(BaseModel):
    """Lockfile for tracking generated secrets."""

    version: str = "1.0"
    secrets: dict[str, SecretLockEntry] = Field(default_factory=dict)
    secretfile: SecretfileMetadata | None = Field(
        default=None, description="Metadata about the source Secretfile"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    def add_secret(
        self,
        secret_name: str,
        secret_value: str,
        target_id: str | None = None,
        is_rotation: bool = False,
    ) -> None:
        """Add or update a secret in the lockfile.

        Args:
            secret_name: Name of the secret
            secret_value: Value to hash and track
            target_id: Optional target identifier
            is_rotation: Whether this update is a rotation
        """
        value_hash = self._hash_value(secret_value)
        now = datetime.now(UTC).isoformat()

        if secret_name in self.secrets:
            # Update existing entry
            entry = self.secrets[secret_name]
            old_hash = entry.hash
            entry.hash = value_hash
            entry.updated_at = now

            # Track rotation if value changed
            if is_rotation and old_hash != value_hash:
                entry.last_rotated = now
                entry.rotation_count += 1
        else:
            # Create new entry
            entry = SecretLockEntry(
                hash=value_hash,
                created_at=now,
                updated_at=now,
            )
            self.secrets[secret_name] = entry

        # Track target-specific hash if provided
        if target_id:
            entry.targets[target_id] = value_hash

    def get_secret_hash(self, secret_name: str) -> str | None:
        """Get the hash of a secret.

        Args:
            secret_name: Name of the secret

        Returns:
            Hash string if found, None otherwise
        """
        entry = self.secrets.get(secret_name)
        return entry.hash if entry else None

    def has_secret(self, secret_name: str) -> bool:
        """Check if a secret exists in the lockfile.

        Args:
            secret_name: Name of the secret

        Returns:
            True if secret exists
        """
        return secret_name in self.secrets

    def should_update(self, secret_name: str, new_value: str) -> bool:
        """Check if a secret should be updated.

        Args:
            secret_name: Name of the secret
            new_value: New value to compare

        Returns:
            True if the value has changed or doesn't exist
        """
        if not self.has_secret(secret_name):
            return True

        current_hash = self.get_secret_hash(secret_name)
        new_hash = self._hash_value(new_value)

        return current_hash != new_hash

    def get_secret_info(self, secret_name: str) -> SecretLockEntry | None:
        """Get full lockfile entry for a secret.

        Args:
            secret_name: Name of the secret

        Returns:
            SecretLockEntry if found, None otherwise
        """
        return self.secrets.get(secret_name)

    def remove_secret(self, secret_name: str) -> bool:
        """Remove a secret from the lockfile.

        Args:
            secret_name: Name of the secret to remove

        Returns:
            True if secret was removed, False if it didn't exist
        """
        if secret_name in self.secrets:
            del self.secrets[secret_name]
            return True
        return False

    def track_secretfile(self, secretfile_path: Path, secretfile_content: str) -> None:
        """Track the Secretfile definition for change detection.

        Args:
            secretfile_path: Path to the Secretfile
            secretfile_content: Content of the Secretfile (typically YAML text)
        """
        relative_filename = secretfile_path.name  # Use only the filename, not full path
        content_hash = self._hash_value(secretfile_content)
        now = datetime.now(UTC).isoformat()

        self.secretfile = SecretfileMetadata(
            filename=relative_filename,
            hash=content_hash,
            synced_at=now,
        )

    def secretfile_changed(self, secretfile_path: Path, secretfile_content: str) -> bool:
        """Check if the Secretfile has changed since the last sync.

        Args:
            secretfile_path: Path to the current Secretfile
            secretfile_content: Current content of the Secretfile

        Returns:
            True if file has changed or no tracking info exists, False if unchanged
        """
        if not self.secretfile:
            # No tracking info, consider it changed
            return True

        # Check if filename matches (for renamed/moved Secretfiles)
        current_filename = secretfile_path.name
        if self.secretfile.filename != current_filename:
            return True

        # Check if content hash matches
        current_hash = self._hash_value(secretfile_content)
        return self.secretfile.hash != current_hash

    def get_secretfile_info(self) -> dict[str, str | None]:
        """Get tracked Secretfile information.

        Returns:
            Dictionary with filename and hash, or empty dict if not tracked
        """
        if not self.secretfile:
            return {}

        return {
            "filename": self.secretfile.filename,
            "hash": self.secretfile.hash,
            "synced_at": self.secretfile.synced_at,
        }

    @staticmethod
    def _hash_value(value: str) -> str:
        """Create a one-way hash of a secret value.

        Args:
            value: Value to hash

        Returns:
            SHA-256 hash string
        """
        return hashlib.sha256(value.encode()).hexdigest()

    @classmethod
    def load(cls, path: Path) -> "Lockfile":
        """Load lockfile from disk.

        Args:
            path: Path to lockfile

        Returns:
            Loaded Lockfile instance
        """
        if not path.exists():
            return cls()

        data = json.loads(path.read_text())
        return cls(**data)

    def save(self, path: Path) -> None:
        """Save lockfile to disk.

        Args:
            path: Path to save lockfile
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2))
