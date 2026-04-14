"""Generator traits and azure_app_reg kind."""

from __future__ import annotations

from secretzero.agent import AgentSecretSynchronizer
from secretzero.bundles.registry import get_bundle_registry
from secretzero.generators.azure_app_reg import AzureAppRegGenerator
from secretzero.generators.static import StaticGenerator
from secretzero.generators.traits import secret_prompts_like_static
from secretzero.lockfile import Lockfile
from secretzero.models import Secret, Secretfile


def test_secret_prompts_like_static_builtin_static() -> None:
    sec = Secret(name="a", kind="static", config={"value": "x"}, targets=[])
    assert secret_prompts_like_static(sec) is True


def test_secret_prompts_like_static_azure_app_reg() -> None:
    reg = get_bundle_registry()
    assert reg.get_generator_class("azure_app_reg") is AzureAppRegGenerator
    sec = Secret(name="a", kind="azure_app_reg", config={"value": {"x": None}}, targets=[])
    assert secret_prompts_like_static(sec) is True


def test_secret_prompts_like_static_unknown_kind() -> None:
    sec = Secret(name="a", kind="not_a_real_kind_xyz", config={}, targets=[])
    assert secret_prompts_like_static(sec) is False


def test_azure_app_reg_subclasses_static_generator() -> None:
    assert issubclass(AzureAppRegGenerator, StaticGenerator)


def test_agent_auto_sync_treats_azure_app_reg_like_static() -> None:
    sf = Secretfile(
        secrets=[
            Secret(
                name="entra",
                kind="azure_app_reg",
                config={"value": {"tenant_id": "t", "client_id": "c", "client_secret": None}},
                targets=[],
            )
        ],
    )
    syncer = AgentSecretSynchronizer(sf, Lockfile(), dry_run=True)
    assert syncer._can_auto_sync(sf.secrets[0]) is False


def test_agent_auto_sync_fully_filled_azure_app_reg() -> None:
    sf = Secretfile(
        secrets=[
            Secret(
                name="entra",
                kind="azure_app_reg",
                config={
                    "value": {
                        "tenant_id": "t",
                        "client_id": "c",
                        "client_secret": "s",
                    }
                },
                targets=[],
            )
        ],
    )
    syncer = AgentSecretSynchronizer(sf, Lockfile(), dry_run=True)
    assert syncer._can_auto_sync(sf.secrets[0]) is True
