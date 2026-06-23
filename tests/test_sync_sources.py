"""Tests for secret source resolution in SyncEngine."""

import json

from secretzero.lockfile import Lockfile
from secretzero.models import Secret, SecretSource, SecretSourceKind, Secretfile, TargetConfig
from secretzero.sync import SyncEngine


class _SourceDummyProvider:
    def __init__(self) -> None:
        self._authenticated = False

    def is_authenticated(self) -> bool:
        return self._authenticated

    def authenticate(self) -> bool:
        self._authenticated = True
        return True

    def get_capabilities(self):  # pragma: no cover - only used for error paths
        from secretzero.providers.capabilities import ProviderCapabilities

        return ProviderCapabilities(provider_kind="dummy", capabilities=[])

    def retrieve_secret(
        self,
        secret_name: str,
        kind: str | None = None,
        profile: str | None = None,
        **kwargs,
    ):
        _ = kind, profile
        return {"name": secret_name, "payload": kwargs.get("payload", "value-from-provider")}


def test_env_source_required_false_falls_back_to_generator(monkeypatch) -> None:
    """Missing optional env source should fall back to normal generator flow."""
    monkeypatch.delenv("MISSING_SOURCE", raising=False)
    sf = Secretfile(
        secrets=[
            Secret(
                name="token",
                kind="random_string",
                config={"length": 12},
                source=SecretSource(
                    kind=SecretSourceKind.ENV,
                    required=False,
                    config={"name": "MISSING_SOURCE"},
                ),
                targets=[],
            )
        ]
    )
    engine = SyncEngine(sf, Lockfile())
    result = engine.sync(dry_run=True)
    detail = result["details"][0]
    assert detail["generated"] is True
    assert detail.get("source") is None


def test_env_source_required_true_reports_error(monkeypatch) -> None:
    """Missing required env source should stop that secret."""
    monkeypatch.delenv("MISSING_REQUIRED_SOURCE", raising=False)
    sf = Secretfile(
        secrets=[
            Secret(
                name="token",
                kind="random_string",
                config={"length": 8},
                source=SecretSource(
                    kind=SecretSourceKind.ENV,
                    required=True,
                    config={"name": "MISSING_REQUIRED_SOURCE"},
                ),
                targets=[],
            )
        ]
    )
    engine = SyncEngine(sf, Lockfile())
    result = engine.sync(dry_run=True)
    detail = result["details"][0]
    assert detail["skipped"] is True
    assert any("source resolution failed" in err for err in detail["errors"])


def test_secret_ref_source_uses_prior_secret_value(monkeypatch) -> None:
    """secret_ref source can reuse a previously resolved secret value."""
    monkeypatch.setenv("UPSTREAM_TOKEN", "from-env")
    sf = Secretfile(
        secrets=[
            Secret(
                name="upstream",
                kind="static",
                source=SecretSource(
                    kind=SecretSourceKind.ENV,
                    config={"name": "UPSTREAM_TOKEN"},
                ),
                targets=[],
            ),
            Secret(
                name="downstream",
                kind="static",
                source=SecretSource(
                    kind=SecretSourceKind.SECRET_REF,
                    config={"secret": "upstream"},
                ),
                targets=[],
            ),
        ]
    )
    engine = SyncEngine(sf, Lockfile())
    result = engine.sync(dry_run=False)
    info = engine.lockfile.get_secret_info("downstream")
    assert info is not None
    assert result["details"][1].get("source") == "resolved"


def test_provider_read_source_supports_cross_provider_read() -> None:
    """provider_read source resolves a value using configured provider alias."""
    sf = Secretfile(
        secrets=[
            Secret(
                name="copied_secret",
                kind="static",
                source=SecretSource(
                    kind=SecretSourceKind.PROVIDER_READ,
                    config={
                        "provider": "aws_src",
                        "kind": "secrets_manager",
                        "read": {"name": "/prod/app/token", "payload": "cross-provider-value"},
                        "field": "payload",
                    },
                ),
                targets=[],
            )
        ]
    )
    engine = SyncEngine(sf, Lockfile())
    engine._providers["aws_src"] = _SourceDummyProvider()

    result = engine.sync(dry_run=False)
    detail = result["details"][0]
    assert detail.get("source") == "resolved"
    assert engine.lockfile.has_secret("copied_secret")


def test_provider_read_source_iam_credentials_dict_to_target_payload(monkeypatch) -> None:
    """provider_read can resolve dict payloads from IAM-credential style provider methods."""

    class _IamSourceProvider(_SourceDummyProvider):
        def retrieve_iam_user_credentials(self, user_name: str, **kwargs):
            _ = kwargs
            return {
                "access_key_id": f"AKIA-{user_name}",
                "secret_access_key": "secret-key-value",
                "region": "us-east-1",
            }

    sf = Secretfile(
        secrets=[
            Secret(
                name="aws_creds_bundle",
                kind="static",
                source=SecretSource(
                    kind=SecretSourceKind.PROVIDER_READ,
                    config={
                        "provider": "aws_src",
                        "kind": "iam_user",
                        "method": "retrieve_iam_user_credentials",
                        "read": {"name": "svc-bot"},
                    },
                ),
                targets=[TargetConfig(provider="local", kind="file", config={"path": ".env.test"})],
            )
        ]
    )
    engine = SyncEngine(sf, Lockfile())
    engine._providers["aws_src"] = _IamSourceProvider()

    captured: dict[str, str] = {}

    def _capture_store(secret_name, secret_value, target_config):
        _ = target_config
        captured[secret_name] = secret_value
        return {
            "provider": "local",
            "kind": "file",
            "status": "stored",
            "target_id": "local/file/.env",
        }

    monkeypatch.setattr(engine, "_store_in_target", _capture_store)
    result = engine.sync(dry_run=False)
    detail = result["details"][0]
    assert detail.get("source") == "resolved"
    # Source dicts are normalized to JSON payload text for target compatibility.
    payload = json.loads(captured.get("aws_creds_bundle", "{}"))
    assert payload["access_key_id"] == "AKIA-svc-bot"
    assert payload["secret_access_key"] == "secret-key-value"
