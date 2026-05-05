"""Unit tests for backup create/restore helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from secretzero.backup import (
    collect_backup_entries,
    resolve_backup_age_recipients,
    restore_backup_entries,
)
from secretzero.lockfile import Lockfile
from secretzero.models import Secret, Secretfile, TargetConfig, Template, TemplateField


class _FakeEngine:
    def __init__(self, lockfile: Lockfile, values: dict[tuple[str, str], str]) -> None:
        self.lockfile = lockfile
        self._values = values

    def _build_target_id(self, target: TargetConfig) -> str:
        ident = target.config.get("path", "") if str(target.kind) == "file" else target.config.get("name", "")
        return f"{target.provider}/{target.kind}/{ident}"

    def _retrieve_from_target(self, secret_name: str, target: TargetConfig) -> str | None:
        return self._values.get((secret_name, self._build_target_id(target)))


class _FakeRestoreEngine:
    def __init__(self, lockfile: Lockfile) -> None:
        self.lockfile = lockfile

    def _store_in_target(self, secret_name: str, secret_value: str, target: TargetConfig) -> dict[str, Any]:
        _ = (secret_name, secret_value, target)
        return {"status": "stored", "actor": {"provider": "local", "username": "tester"}}

    def _target_provenance_actor(self, actor: dict[str, Any] | None) -> dict[str, Any]:
        return actor or {}

    def _sync_actor_dict(self) -> dict[str, Any]:
        return {"client": "cli"}


def test_collect_backup_entries_from_synced_plain_and_template_targets() -> None:
    secretfile = Secretfile(
        version="1.0",
        templates={
            "svc": Template(
                description="svc template",
                fields={
                    "token": TemplateField(
                        description="token",
                        generator={"kind": "static", "config": {"value": "x"}},
                        targets=[TargetConfig(provider="local", kind="file", config={"path": ".tmpl"})],
                    )
                },
            )
        },
        secrets=[
            Secret(
                name="api_key",
                kind="static",
                config={"value": "x"},
                targets=[TargetConfig(provider="local", kind="file", config={"path": ".env"})],
            ),
            Secret(name="svc_secret", kind="templates.svc", config={}),
        ],
    )
    lock = Lockfile()
    lock.add_secret("api_key", "A", target_id="local/file/.env")
    lock.add_secret("svc_secret.token", "B", target_id="local/file/.tmpl")
    values = {
        ("api_key", "local/file/.env"): "A",
        ("token", "local/file/.tmpl"): "B",
    }
    engine = _FakeEngine(lock, values)

    out = collect_backup_entries(engine=engine, secretfile=secretfile)
    entries = out["entries"]
    assert len(entries) == 2
    assert any(e["secret_ref"] == "api_key" and e["target_secret_key"] == "api_key" for e in entries)
    assert any(
        e["secret_ref"] == "svc_secret.token" and e["target_secret_key"] == "token" for e in entries
    )


def test_restore_backup_entries_supports_import_only_selectors() -> None:
    lock = Lockfile()
    engine = _FakeRestoreEngine(lock)
    entries = [
        {
            "entry_id": "e1",
            "secret_ref": "api_key",
            "target_secret_key": "api_key",
            "target_id": "local/file/.env",
            "provider": "local",
            "kind": "file",
            "target_config": {"path": ".env"},
            "value": "A",
        },
        {
            "entry_id": "e2",
            "secret_ref": "svc_secret.token",
            "target_secret_key": "token",
            "target_id": "local/file/.tmpl",
            "provider": "local",
            "kind": "file",
            "target_config": {"path": ".tmpl"},
            "value": "B",
        },
    ]

    out = restore_backup_entries(
        engine=engine,
        entries=entries,
        import_only_selectors={"svc_secret.token@local/file/.tmpl"},
    )
    assert out["restored"] == 1
    assert out["imported_only"] == 1
    assert out["errors"] == []
    assert lock.get_secret_info("api_key") is not None
    assert lock.get_secret_info("svc_secret.token") is not None


def test_resolve_backup_age_recipients_uses_keyfile_public_key(tmp_path: Path) -> None:
    key_file = tmp_path / "backup.agekey"
    key_file.write_text(
        "# created: now\n# public key: age1examplepublickey\nAGE-SECRET-KEY-1EXAMPLEPRIVATEKEY\n"
    )
    recipients, generated = resolve_backup_age_recipients(
        output_file=tmp_path / "backup.enc.json",
        explicit_recipients=(),
        age_key_file=key_file,
    )
    assert generated is None
    assert recipients == ["age1examplepublickey"]
