"""Tests for environment and target-profile resolution."""

from pathlib import Path

from secretzero.environment_resolution import apply_target_profile, resolve_environment_context
from secretzero.models import Secretfile


def _secretfile_with_environments() -> Secretfile:
    return Secretfile(
        variables={"env": "base"},
        policies={
            "aws_prod_identity": {"kind": "provider_identity", "providers": ["aws"], "rules": []}
        },
        environments={
            "default": "dev",
            "profiles": {
                "dev": {
                    "var_files": ["env/dev.szvar"],
                    "lockfile": ".gitsecrets.dev.lock",
                },
                "prod": {
                    "var_files": ["env/prod.szvar"],
                    "lockfile": ".gitsecrets.prod.lock",
                    "target_profile": "aws_prod",
                },
            },
        },
        target_profiles={
            "aws_prod": {
                "identity_policies": ["aws_prod_identity"],
                "target_overrides": {
                    "secrets_manager": {"name": "/prod/default"},
                },
            }
        },
        providers={"aws": {"kind": "aws"}},
        secrets=[
            {
                "name": "api_token",
                "kind": "random_string",
                "config": {"length": 32},
                "targets": [
                    {
                        "provider": "aws",
                        "kind": "secrets_manager",
                        "config": {"name": "/base/token"},
                    }
                ],
            }
        ],
    )


def test_environment_default_resolution(tmp_path: Path) -> None:
    secretfile = _secretfile_with_environments()
    secretfile_path = tmp_path / "Secretfile.yml"
    secretfile_path.write_text("secrets: []\n", encoding="utf-8")

    ctx = resolve_environment_context(
        secretfile=secretfile,
        secretfile_path=secretfile_path,
        environment=None,
        runtime_var_files=[],
        runtime_lockfile=None,
    )
    assert ctx.selected_environment == "dev"
    assert str(ctx.resolved_lockfile).endswith(".gitsecrets.dev.lock")
    assert any(str(p).endswith("env/dev.szvar") for p in ctx.resolved_var_files)


def test_runtime_overrides_win(tmp_path: Path) -> None:
    secretfile = _secretfile_with_environments()
    secretfile_path = tmp_path / "Secretfile.yml"
    secretfile_path.write_text("secrets: []\n", encoding="utf-8")
    override_var = tmp_path / "override.szvar"
    override_var.write_text("env: override\n", encoding="utf-8")

    ctx = resolve_environment_context(
        secretfile=secretfile,
        secretfile_path=secretfile_path,
        environment="prod",
        runtime_var_files=[override_var],
        runtime_lockfile="custom.lock",
    )
    assert str(ctx.resolved_lockfile).endswith("custom.lock")
    assert ctx.lockfile_source == "runtime_flag"
    assert ctx.resolved_var_files[-1] == override_var
    assert ctx.var_file_sources[-1] == "runtime_flag"


def test_apply_target_profile_merges_and_appends_identity_policies() -> None:
    secretfile = _secretfile_with_environments()
    resolved = apply_target_profile(secretfile, "aws_prod")
    target = resolved.secrets[0].targets[0]
    assert target.config["name"] == "/prod/default"
    assert "aws_prod_identity" in target.identity_policies
