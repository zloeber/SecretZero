"""Regression tests for falsey JSON values retrieved during partial sync."""

from __future__ import annotations

import json
from pathlib import Path

from secretzero.config import ConfigLoader
from secretzero.lockfile import Lockfile
from secretzero.models import Secret, Secretfile, TargetConfig, Template, TemplateField
from secretzero.sync import SyncEngine


def _write_two_file_secretfile(tmp_path: Path) -> Path:
    """Create a manifest with one secret and two local file targets."""
    a = tmp_path / "a.env"
    b = tmp_path / "b.env"
    a.write_text("shared_secret=abcdefgh\n", encoding="utf-8")
    b.write_text("shared_secret=abcdefgh\n", encoding="utf-8")
    p = tmp_path / "Secretfile.yml"
    p.write_text(f"""
version: '1.0'
providers:
  local:
    kind: local
secrets:
  - name: shared_secret
    kind: random_string
    config:
      length: 8
    targets:
      - provider: local
        kind: file
        config:
          path: {a}
          format: dotenv
      - provider: local
        kind: file
        config:
          path: {b}
          format: dotenv
""")
    return p


def test_partial_sync_treats_empty_object_as_retrieved_value(tmp_path: Path, monkeypatch) -> None:
    """An empty JSON object from a target is still a successfully retrieved value."""
    secretfile_path = _write_two_file_secretfile(tmp_path)
    loader = ConfigLoader()
    config = loader.load_file(secretfile_path)
    secret = config.secrets[0]
    tracked_target_id = SyncEngine._build_target_id(secret.targets[0])
    lock_path = tmp_path / "t.lock"
    lock_path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "secrets": {
                    "shared_secret": {
                        "hash": "H",
                        "created_at": "2020-01-01T00:00:00Z",
                        "updated_at": "2020-01-01T00:00:00Z",
                        "targets": {tracked_target_id: "H"},
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    engine = SyncEngine(config, Lockfile.load(lock_path))
    monkeypatch.setattr(engine, "_retrieve_from_target", lambda _name, _tc: {})

    result = engine.sync(dry_run=True, secret_names=["shared_secret"])

    detail = result["details"][0]
    assert detail.get("retrieved_from_existing") is True
    assert detail.get("skipped") is not True


def test_template_partial_sync_treats_empty_list_as_retrieved_value(monkeypatch) -> None:
    """A falsey JSON array from a template target should not be treated as missing."""
    tracked_target = TargetConfig(
        provider="local", kind="file", config={"path": ".tmpl", "format": "json"}
    )
    untracked_target = TargetConfig(
        provider="local", kind="file", config={"path": ".tmpl-2", "format": "json"}
    )
    secretfile = Secretfile(
        templates={
            "svc": Template(
                description="service template",
                fields={
                    "settings": TemplateField(
                        description="settings",
                        generator={"kind": "static", "config": {"value": "x"}},
                        targets=[tracked_target, untracked_target],
                    )
                },
            )
        },
        secrets=[Secret(name="svc_secret", kind="templates.svc", config={})],
    )
    lock = Lockfile()
    lock.add_secret(
        "svc_secret.settings",
        "existing",
        target_id=SyncEngine._build_target_id(tracked_target),
    )
    engine = SyncEngine(secretfile, lock)
    monkeypatch.setattr(engine, "_retrieve_from_target", lambda _name, _tc: [])

    result = engine.sync(dry_run=True, secret_names=["svc_secret"])

    field = result["details"][0]["fields"][0]
    assert field.get("retrieved_from_existing") is True
    assert field.get("skipped") is not True
