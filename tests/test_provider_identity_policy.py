"""Tests for provider_identity policies (sync guardrails)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from secretzero.config import ConfigLoader
from secretzero.lockfile import Lockfile
from secretzero.policy import (
    ProviderIdentityPolicy,
    ProviderIdentityRule,
    collect_applicable_provider_identity_policies,
    evaluate_identity_rule,
    evaluate_provider_identity_policy,
)
from secretzero.sync import SyncEngine


def test_evaluate_identity_rule_glob_match() -> None:
    rule = ProviderIdentityRule(field="account", glob="123*")
    ok, msg = evaluate_identity_rule(rule, {"account": "123456789012"})
    assert ok and msg == ""


def test_evaluate_identity_rule_glob_missing() -> None:
    rule = ProviderIdentityRule(field="account", glob="123*")
    ok, msg = evaluate_identity_rule(rule, {})
    assert not ok and "missing" in msg


def test_evaluate_identity_rule_regex() -> None:
    rule = ProviderIdentityRule(field="arn", regex=r"arn:aws:iam::\d+:user/.+")
    ok, msg = evaluate_identity_rule(rule, {"arn": "arn:aws:iam::123456789012:user/alice"})
    assert ok and msg == ""


def test_evaluate_identity_rule_any_glob_list() -> None:
    rule = ProviderIdentityRule(field="scopes", any_glob=["prod-*", "admin"])
    ok, msg = evaluate_identity_rule(rule, {"scopes": ["staging", "prod-app"]})
    assert ok and msg == ""


def test_evaluate_identity_rule_any_glob_scalar_coerced() -> None:
    rule = ProviderIdentityRule(field="scopes", any_glob=["prod-*"])
    ok, msg = evaluate_identity_rule(rule, {"scopes": "prod-main"})
    assert ok and msg == ""


def test_evaluate_identity_rule_all_glob() -> None:
    rule = ProviderIdentityRule(field="scopes", all_glob=["*"])
    ok, msg = evaluate_identity_rule(rule, {"scopes": ["a", "b"]})
    assert ok and msg == ""


def test_evaluate_identity_rule_all_glob_failure() -> None:
    rule = ProviderIdentityRule(field="scopes", all_glob=["prod-*"])
    ok, msg = evaluate_identity_rule(rule, {"scopes": ["prod-a", "staging"]})
    assert not ok


def test_provider_identity_policy_match_any() -> None:
    policy = ProviderIdentityPolicy(
        name="p",
        providers=["aws"],
        match="any",
        rules=[
            ProviderIdentityRule(field="account", glob="111*"),
            ProviderIdentityRule(field="account", glob="222*"),
        ],
    )
    ok, _ = evaluate_provider_identity_policy(policy, {"account": "222999"})
    assert ok


def test_provider_identity_rule_rejects_two_matchers() -> None:
    with pytest.raises(ValidationError):
        ProviderIdentityRule(field="x", glob="*", regex=".*")


def test_collect_applicable_respects_scope(tmp_path: Path) -> None:
    sf_path = tmp_path / "Secretfile.yml"
    sf_path.write_text("""
variables: {}
providers:
  aws:
    kind: aws
    auth: { kind: ambient, config: {} }
  vault:
    kind: vault
    auth: { kind: token, config: { token: "x", url: "http://127.0.0.1:8200" } }
policies:
  aws_only:
    kind: provider_identity
    providers: [aws]
    rules:
      - { field: account, glob: "*" }
  vault_only:
    kind: provider_identity
    providers: [vault]
    rules:
      - { field: user, glob: "*" }
secrets:
  - name: s1
    kind: random_string
    config: { length: 8 }
    targets:
      - provider: vault
        kind: vault_kv
        config: { path: secret/data/x, mount_point: secret, version: 2 }
""")
    loader = ConfigLoader()
    sf = loader.load_file(sf_path)
    sec = [s for s in sf.secrets if s.name == "s1"]
    names = {n for n, _ in collect_applicable_provider_identity_policies(sf, sec)}
    assert names == {"vault_only"}


def test_validate_secretfile_rejects_bad_identity_ref(tmp_path: Path) -> None:
    sf_path = tmp_path / "Secretfile.yml"
    sf_path.write_text("""
variables: {}
providers:
  local:
    kind: local
policies:
  good:
    kind: provider_identity
    providers: [local]
    rules:
      - { field: x, glob: "*" }
secrets:
  - name: s
    kind: random_string
    config: { length: 4 }
    targets:
      - provider: local
        kind: file
        identity_policies: [nope]
        config: { path: out.env, format: dotenv }
""")
    loader = ConfigLoader()
    with pytest.raises(ValueError, match="Unknown identity_policies"):
        loader.load_file(sf_path)


class _FakeAwsProvider:
    auth = object()

    def __init__(self, actor: dict) -> None:
        self._actor = actor

    def authenticate(self) -> bool:
        return True

    def get_actor_info(self) -> dict:
        return dict(self._actor)


def test_preflight_provider_identity_matches_enforcement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sf_path = tmp_path / "Secretfile.yml"
    sf_path.write_text("""
variables: {}
providers:
  aws:
    kind: aws
    auth: { kind: ambient, config: {} }
policies:
  must_be_prod:
    kind: provider_identity
    providers: [aws]
    rules:
      - field: account
        glob: "111111111111"
secrets:
  - name: s
    kind: random_string
    config: { length: 8 }
    targets:
      - provider: aws
        kind: secrets_manager
        config: { name: test/secret }
""")
    loader = ConfigLoader()
    config = loader.load_file(sf_path)
    lockfile = Lockfile.load(tmp_path / ".gitsecrets.lock")
    engine = SyncEngine(config, lockfile)
    monkeypatch.setattr(
        engine,
        "_validate_target_access",
        lambda: {"accessible_count": 1, "total_count": 1, "results": []},
    )
    engine._providers["aws"] = _FakeAwsProvider(
        {"provider": "aws", "provider_name": "aws", "account": "999999999999"}
    )
    pre = engine.preflight_provider_identity_policies()
    assert pre["has_policies"] is True
    assert pre["all_ok"] is False
    assert pre["blocking"] is True
    assert any(i["status"] == "policy_failed" for i in pre["rows"])


def test_sync_enforces_provider_identity(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sf_path = tmp_path / "Secretfile.yml"
    sf_path.write_text("""
variables: {}
providers:
  aws:
    kind: aws
    auth: { kind: ambient, config: {} }
policies:
  must_be_prod:
    kind: provider_identity
    providers: [aws]
    rules:
      - field: account
        glob: "111111111111"
secrets:
  - name: s
    kind: random_string
    config: { length: 8 }
    targets:
      - provider: aws
        kind: secrets_manager
        config: { name: test/secret }
""")
    loader = ConfigLoader()
    config = loader.load_file(sf_path)
    lockfile = Lockfile.load(tmp_path / ".gitsecrets.lock")
    engine = SyncEngine(
        config, lockfile, secretfile_path=sf_path, secretfile_content=sf_path.read_text()
    )

    monkeypatch.setattr(
        engine,
        "_validate_target_access",
        lambda: {
            "accessible_count": 1,
            "total_count": 1,
            "results": [("aws", True, None)],
        },
    )
    engine._providers["aws"] = _FakeAwsProvider(
        {"provider": "aws", "provider_name": "aws", "account": "999999999999"}
    )

    with pytest.raises(RuntimeError, match="must_be_prod"):
        engine.sync(dry_run=True)


def test_preflight_sync_readiness_blocked_on_policy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sf_path = tmp_path / "Secretfile.yml"
    sf_path.write_text("""
variables: {}
providers:
  aws:
    kind: aws
    auth: { kind: ambient, config: {} }
policies:
  must_be_prod:
    kind: provider_identity
    providers: [aws]
    rules:
      - field: account
        glob: "111111111111"
secrets:
  - name: s
    kind: random_string
    config: { length: 8 }
    targets:
      - provider: aws
        kind: secrets_manager
        config: { name: test/secret }
""")
    loader = ConfigLoader()
    config = loader.load_file(sf_path)
    lockfile = Lockfile.load(tmp_path / ".gitsecrets.lock")
    engine = SyncEngine(config, lockfile)
    monkeypatch.setattr(
        engine,
        "_validate_target_access",
        lambda: {"accessible_count": 1, "total_count": 1, "results": [("aws", True, None)]},
    )
    engine._providers["aws"] = _FakeAwsProvider(
        {"provider": "aws", "provider_name": "aws", "account": "999999999999"}
    )
    r = engine.preflight_sync_readiness()
    assert r["sync_blocked"] is True
    assert "provider_identity_policy" in r["blocking_reasons"]
    assert "no_accessible_targets" not in r["blocking_reasons"]


def test_preflight_sync_readiness_blocked_on_no_accessible_targets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sf_path = tmp_path / "Secretfile.yml"
    sf_path.write_text("""
variables: {}
providers:
  aws:
    kind: aws
    auth: { kind: ambient, config: {} }
secrets:
  - name: s
    kind: random_string
    config: { length: 8 }
    targets:
      - provider: aws
        kind: secrets_manager
        config: { name: test/secret }
""")
    loader = ConfigLoader()
    config = loader.load_file(sf_path)
    lockfile = Lockfile.load(tmp_path / ".gitsecrets.lock")
    engine = SyncEngine(config, lockfile)
    monkeypatch.setattr(
        engine,
        "_validate_target_access",
        lambda: {
            "accessible_count": 0,
            "total_count": 1,
            "results": [("aws", False, "auth failed")],
        },
    )
    r = engine.preflight_sync_readiness()
    assert r["sync_blocked"] is True
    assert "no_accessible_targets" in r["blocking_reasons"]
