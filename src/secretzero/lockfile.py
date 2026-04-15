"""Lockfile management for secret tracking."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from secretzero.models import SECRETFILE_MANIFEST_SPEC_VERSION


class TargetUpdate(BaseModel):
    """Provenance information for a single target update."""

    updated_at: str = Field(description="ISO 8601 timestamp of the update")
    actor: dict[str, Any] = Field(
        default_factory=dict,
        description="Information about the actor/user that performed the update",
    )


class SecretLockEntry(BaseModel):
    """Lockfile entry for a single secret."""

    hash: str
    created_at: str
    updated_at: str
    last_rotated: str | None = None
    rotation_count: int = 0
    targets: dict[str, str] = Field(default_factory=dict)  # target_id -> hash
    target_provenance: dict[str, list[TargetUpdate]] = Field(
        default_factory=dict,
        description="Per-target provenance history (up to last 3 updates per target)",
    )


class LockfileSyncIdentity(BaseModel):
    """Who and what environment performed the last successful lockfile write (no secret values)."""

    client: str = Field(description="Invocation surface (cli, api, agent, network_web, …)")
    secretzero_version: str | None = Field(
        default=None, description="secretzero package version when the sync ran"
    )
    os_user: str | None = Field(default=None, description="OS login name (e.g. getpass.getuser())")
    os_uid: int | None = Field(default=None, description="Real user id when available (Unix)")
    os_euid: int | None = Field(default=None, description="Effective user id when available (Unix)")
    hostname: str | None = Field(default=None, description="Short hostname from the OS")
    host_fqdn: str | None = Field(
        default=None, description="Fully qualified hostname when available"
    )
    platform: str | None = Field(default=None, description="platform.platform() string")
    environment_label: str | None = Field(
        default=None,
        description="Optional deploy/env label from SZ_SYNC_ENVIRONMENT, ENVIRONMENT, ENV, …",
    )
    git_user_name: str | None = Field(default=None, description="git config user.name at sync cwd")
    git_user_email: str | None = Field(
        default=None, description="git config user.email at sync cwd"
    )
    git_commit_sha: str | None = Field(
        default=None, description="Short git HEAD commit at sync cwd when in a repo"
    )
    ci_system: str | None = Field(
        default=None, description="Detected CI vendor (github_actions, gitlab_ci, …)"
    )
    ci_actor: str | None = Field(default=None, description="CI user or bot that triggered the job")
    ci_repository: str | None = Field(default=None, description="Repository slug or path in CI")
    ci_job_id: str | None = Field(default=None, description="Pipeline / build / run identifier")
    ci_run_url: str | None = Field(default=None, description="Link to the CI run when available")
    ci_workflow_name: str | None = Field(default=None, description="Workflow or job name in CI")
    ci_pipeline_name: str | None = Field(default=None, description="Pipeline or project name in CI")


class SecretfileMetadata(BaseModel):
    """Metadata about the source Secretfile and variable context."""

    filename: str = Field(description="Relative filename of the Secretfile")
    hash: str = Field(description="SHA-256 hash of the Secretfile content")
    synced_at: str = Field(description="ISO 8601 timestamp of last sync")
    var_files: list[str] = Field(
        default_factory=list,
        description="Ordered list of .szvar variable file basenames used on last sync",
    )
    variables_hash: str | None = Field(
        default=None,
        description="SHA-256 hash of merged variables dict used on last sync",
    )
    sync_identity: LockfileSyncIdentity | None = Field(
        default=None,
        description="Identity context for the operator or automation that last updated this lockfile",
    )
    manifest_spec_version: str | None = Field(
        default=None,
        description="Secretfile manifest spec version captured during lockfile tracking",
    )


class Lockfile(BaseModel):
    """Lockfile for tracking generated secrets."""

    version: str = "1.0"
    secrets: dict[str, SecretLockEntry] = Field(default_factory=dict)
    secretfile: SecretfileMetadata | None = Field(
        default=None, description="Metadata about the source Secretfile"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    def is_semantically_empty(self) -> bool:
        """Return True when the lockfile has no persisted state.

        A lockfile with no secret entries, no tracked source metadata, and no
        extra metadata should not be written to disk as an empty skeleton.
        """
        return not self.secrets and self.secretfile is None and not self.metadata

    def add_secret(
        self,
        secret_name: str,
        secret_value: Any,
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

    def should_update(self, secret_name: str, new_value: Any) -> bool:
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

    def track_secretfile(
        self,
        secretfile_path: Path,
        secretfile_content: str,
        *,
        sync_identity: LockfileSyncIdentity | None = None,
    ) -> None:
        """Track the Secretfile definition for change detection.

        Args:
            secretfile_path: Path to the Secretfile
            secretfile_content: Content of the Secretfile (typically YAML text)
            sync_identity: Optional captured operator / environment identity for this sync
        """
        relative_filename = secretfile_path.name  # Use only the filename, not full path
        content_hash = self._hash_value(secretfile_content)
        now = datetime.now(UTC).isoformat()

        if self.secretfile is None:
            self.secretfile = SecretfileMetadata(
                filename=relative_filename,
                hash=content_hash,
                synced_at=now,
                sync_identity=sync_identity,
                manifest_spec_version=SECRETFILE_MANIFEST_SPEC_VERSION,
            )
        else:
            # Preserve any existing variable context fields
            self.secretfile.filename = relative_filename
            self.secretfile.hash = content_hash
            self.secretfile.synced_at = now
            self.secretfile.manifest_spec_version = SECRETFILE_MANIFEST_SPEC_VERSION
            if sync_identity is not None:
                self.secretfile.sync_identity = sync_identity

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

    def track_variable_context(self, var_files: list[Path], variables: dict[str, Any]) -> None:
        """Track the variable context (.szvar files and merged variables) used for sync.

        Args:
            var_files: List of .szvar variable file paths used for this run.
            variables: Final merged variables dict from the Secretfile and var_files.
        """
        if self.secretfile is None:
            # Initialize a minimal metadata record if none exists yet
            now = datetime.now(UTC).isoformat()
            self.secretfile = SecretfileMetadata(
                filename="",
                hash="",
                synced_at=now,
                manifest_spec_version=SECRETFILE_MANIFEST_SPEC_VERSION,
            )

        # Store only basenames to keep the lockfile stable across machines
        self.secretfile.var_files = [vf.name for vf in var_files]

        # Hash of the merged variables dict (order independent)
        variables_json = json.dumps(variables, sort_keys=True, default=str)
        self.secretfile.variables_hash = self._hash_value(variables_json)

    def variable_context_changed(self, var_files: list[Path], variables: dict[str, Any]) -> bool:
        """Return True if the active variable context differs from the tracked one.

        Args:
            var_files: .szvar files for the current run.
            variables: Final merged variables dict for the current run.
        """
        if self.secretfile is None:
            # No prior context recorded, treat as changed
            return True

        # Compare var_files by basename
        current_var_files = [vf.name for vf in var_files]
        if self.secretfile.var_files != current_var_files:
            return True

        # No variables baseline (legacy lockfile or not yet persisted): we cannot detect a
        # *change* in merged variables vs last sync, so do not treat as changed. Otherwise
        # ``variables_hash: null`` compares unequal to every computed hash and forces
        # ``ignore_foreign_context_targets`` on every run (spurious re-generation / prompts).
        if self.secretfile.variables_hash is None:
            return False

        variables_json = json.dumps(variables, sort_keys=True, default=str)
        current_hash = self._hash_value(variables_json)
        if self.secretfile.variables_hash != current_hash:
            return True

        return False

    def record_target_update(
        self,
        secret_name: str,
        target_id: str,
        actor: dict[str, Any] | None = None,
    ) -> None:
        """Record provenance for an update to a specific target.

        Keeps only the last three updates per target to avoid unbounded
        growth of the lockfile.

        Args:
            secret_name: Name of the secret being updated.
            target_id: Fully-qualified target identifier.
            actor: Optional actor information dictionary.
        """
        entry = self.secrets.get(secret_name)
        if entry is None:
            return

        now = datetime.now(UTC).isoformat()
        history = entry.target_provenance.setdefault(target_id, [])
        history.append(TargetUpdate(updated_at=now, actor=actor or {}))

        # Keep only the last three updates for this target
        if len(history) > 3:
            entry.target_provenance[target_id] = history[-3:]

    @staticmethod
    def _hash_value(value: Any) -> str:
        """Create a one-way hash of a secret value.

        Args:
            value: Value to hash (string or structured value)

        Returns:
            SHA-256 hash string
        """
        if isinstance(value, str):
            normalized = value
        else:
            # Use canonical JSON for stable hashing of dict/list values.
            normalized = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(normalized.encode()).hexdigest()

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
        if self.is_semantically_empty():
            # Never persist an empty skeleton lockfile. If one already exists,
            # remove it so sync processing cannot leave behind empty files.
            if path.exists():
                path.unlink()
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.model_dump(mode="json")
        payload = self._scrub_nullable_metadata(payload)
        path.write_text(json.dumps(payload, indent=2))

    @staticmethod
    def _drop_none_values(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: Lockfile._drop_none_values(v) for k, v in value.items() if v is not None}
        if isinstance(value, list):
            return [Lockfile._drop_none_values(v) for v in value]
        return value

    @classmethod
    def _scrub_nullable_metadata(cls, payload: dict[str, Any]) -> dict[str, Any]:
        """Remove ``None`` fields from persisted sync_identity and actor metadata."""
        secretfile_meta = payload.get("secretfile")
        if isinstance(secretfile_meta, dict) and isinstance(
            secretfile_meta.get("sync_identity"), dict
        ):
            secretfile_meta["sync_identity"] = cls._drop_none_values(
                secretfile_meta["sync_identity"]
            )

        secrets = payload.get("secrets")
        if isinstance(secrets, dict):
            for secret_entry in secrets.values():
                if not isinstance(secret_entry, dict):
                    continue
                provenance = secret_entry.get("target_provenance")
                if not isinstance(provenance, dict):
                    continue
                for updates in provenance.values():
                    if not isinstance(updates, list):
                        continue
                    for update in updates:
                        if isinstance(update, dict) and isinstance(update.get("actor"), dict):
                            update["actor"] = cls._drop_none_values(update["actor"])

        return payload
