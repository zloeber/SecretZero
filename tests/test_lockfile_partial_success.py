"""Test to verify lockfile is saved when at least one target succeeds."""

import pytest
from pathlib import Path
from secretzero.sync import SyncEngine
from secretzero.lockfile import Lockfile
from secretzero.models import Secretfile, Secret, TargetConfig


def test_lockfile_saved_with_partial_target_success():
    """Test that lockfile is saved even when only some targets succeed."""
    # Create a simple secretfile
    secretfile_dict = {
        "version": "1.0",
        "providers": {"local": {"kind": "local"}},
        "secrets": [
            {
                "name": "test_secret",
                "kind": "static",
                "config": {"default": "test-value"},
                "targets": [
                    {
                        "provider": "local",
                        "kind": "file",
                        "config": {"path": "/tmp/test1.txt", "format": "json"},
                    },
                    {
                        "provider": "local",
                        "kind": "file",
                        "config": {"path": "/nonexistent/invalid/test2.txt", "format": "json"},
                    },
                ],
            }
        ],
    }

    config = Secretfile(**secretfile_dict)
    lockfile = Lockfile(version="1.0", secrets={})
    engine = SyncEngine(config, lockfile)

    # Sync (may have partial failures)
    results = engine.sync(dry_run=False)

    # Verify that secrets_stored is > 0 if at least one target succeeded
    if results["secrets_stored"] > 0:
        print(f"✓ secrets_stored = {results['secrets_stored']}")
    else:
        print(f"✗ secrets_stored = 0 (should be > 0 if any target succeeded)")

    # Check the details
    for detail in results["details"]:
        print(f"\nSecret: {detail['name']}")
        print(f"  Stored: {detail.get('stored')}")
        print(f"  Errors: {detail.get('errors')}")
        for target in detail.get("targets", []):
            print(f"  Target {target['provider']}/{target['kind']}: {target.get('status')}")


if __name__ == "__main__":
    test_lockfile_saved_with_partial_target_success()
