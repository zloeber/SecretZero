"""Tests for lockfile sync identity collection and persistence."""

import json
from pathlib import Path
from unittest.mock import patch

from secretzero.lockfile import Lockfile, LockfileSyncIdentity
from secretzero.sync_identity import collect_lockfile_sync_identity


class TestCollectLockfileSyncIdentity:
    def test_github_actions_fields(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.setenv("GITHUB_ACTOR", "octocat")
        monkeypatch.setenv("GITHUB_REPOSITORY", "acme/demo")
        monkeypatch.setenv("GITHUB_RUN_ID", "42")
        monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
        monkeypatch.setenv("GITHUB_WORKFLOW", "sync")
        monkeypatch.setenv("GITHUB_JOB", "deploy")

        ident = collect_lockfile_sync_identity(client="cli", cwd=tmp_path)
        assert ident.client == "cli"
        assert ident.ci_system == "github_actions"
        assert ident.ci_actor == "octocat"
        assert ident.ci_repository == "acme/demo"
        assert ident.ci_job_id == "42"
        assert ident.ci_run_url == "https://github.com/acme/demo/actions/runs/42"
        assert ident.ci_workflow_name == "sync"
        assert ident.ci_pipeline_name == "deploy"

    def test_explicit_override_model_roundtrip(self, tmp_path: Path) -> None:
        lock = Lockfile()
        custom = LockfileSyncIdentity(
            client="test",
            os_user="alice",
            git_commit_sha="abc1234",
        )
        sf = tmp_path / "Secretfile.yml"
        sf.write_text("version: '1.0'\nsecrets: []\n")
        lock.track_secretfile(sf, sf.read_text(), sync_identity=custom)
        assert lock.secretfile is not None
        assert lock.secretfile.sync_identity is not None
        assert lock.secretfile.sync_identity.client == "test"
        assert lock.secretfile.sync_identity.os_user == "alice"

        out = tmp_path / ".gitsecrets.lock"
        lock.save(out)
        loaded = Lockfile.load(out)
        assert loaded.secretfile and loaded.secretfile.sync_identity
        assert loaded.secretfile.sync_identity.model_dump() == custom.model_dump()

    def test_track_preserves_identity_when_not_passed(self, tmp_path: Path) -> None:
        lock = Lockfile()
        first = LockfileSyncIdentity(client="cli", os_user="bob")
        sf = tmp_path / "Secretfile.yml"
        content = "version: '1.0'\nsecrets: []\n"
        sf.write_text(content)
        lock.track_secretfile(sf, content, sync_identity=first)
        lock.track_secretfile(sf, content + "\n# x\n", sync_identity=None)
        assert lock.secretfile is not None
        assert lock.secretfile.sync_identity is not None
        assert lock.secretfile.sync_identity.os_user == "bob"

    def test_load_legacy_lockfile_without_sync_identity(self, tmp_path: Path) -> None:
        legacy = {
            "version": "1.0",
            "secrets": {},
            "secretfile": {
                "filename": "Secretfile.yml",
                "hash": "abc",
                "synced_at": "2020-01-01T00:00:00+00:00",
                "var_files": [],
                "variables_hash": None,
            },
            "metadata": {},
        }
        p = tmp_path / "legacy.lock"
        p.write_text(json.dumps(legacy))
        lock = Lockfile.load(p)
        assert lock.secretfile is not None
        assert lock.secretfile.sync_identity is None
