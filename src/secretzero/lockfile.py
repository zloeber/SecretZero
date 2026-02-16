"""Lockfile management for secret tracking."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field


class SecretLockEntry(BaseModel):
    """Lockfile entry for a single secret."""

    hash: str
    created_at: str
    updated_at: str
    targets: dict[str, str] = Field(default_factory=dict)  # target_id -> hash


class Lockfile(BaseModel):
    """Lockfile for tracking generated secrets."""

    version: str = "1.0"
    secrets: dict[str, SecretLockEntry] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def add_secret(
        self,
        secret_name: str,
        secret_value: str,
        target_id: Optional[str] = None,
    ) -> None:
        """Add or update a secret in the lockfile.

        Args:
            secret_name: Name of the secret
            secret_value: Value to hash and track
            target_id: Optional target identifier
        """
        value_hash = self._hash_value(secret_value)
        now = datetime.now(UTC).isoformat()

        if secret_name in self.secrets:
            # Update existing entry
            entry = self.secrets[secret_name]
            entry.hash = value_hash
            entry.updated_at = now
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

    def get_secret_hash(self, secret_name: str) -> Optional[str]:
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
