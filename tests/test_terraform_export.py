"""Tests for Terraform export functionality."""

from pathlib import Path
from tempfile import TemporaryDirectory

from secretzero.bundles import get_bundle_registry
from secretzero.config import ConfigLoader
from secretzero.terraform_export import (
    TerraformGeneratorOptions,
    TerraformOutputFormat,
    generate_terraform,
)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_generate_terraform_from_secretfile_test() -> None:
    """Terraform export produces resources for the test Secretfile."""

    secretfile_path = _project_root() / "Secretfile.test.yml"
    assert secretfile_path.exists()

    loader = ConfigLoader()
    secretfile = loader.load_file(secretfile_path)

    registry = get_bundle_registry()

    with TemporaryDirectory() as tmpdir:
        options = TerraformGeneratorOptions(
            output_dir=Path(tmpdir),
            format=TerraformOutputFormat.JSON,
            include_static_secrets=False,
        )

        project = generate_terraform(secretfile, options, registry=registry)

        # AWS provider should be detected from targets
        assert any(rp.name == "aws" for rp in project.required_providers.values())

        # At least one random_* generator resource should be present
        resource_types = {r.type for r in project.resources}
        assert "random_password" in resource_types or "random_string" in resource_types

        # At least one AWS target resource should be present
        assert (
            "aws_ssm_parameter" in resource_types
            or "aws_secretsmanager_secret_version" in resource_types
        )

        # Write JSON and ensure it is valid Terraform JSON structure
        written = project.write_files(options.output_dir, options.format)
        assert written, "Expected at least one Terraform file to be written"
        main_file = written[0]
        assert main_file.exists()
        data = main_file.read_text()
        assert '"resource"' in data or '"provider"' in data or '"terraform"' in data


def test_terraform_always_creates_static_secret_variable() -> None:
    """Static secrets should always render Terraform variables."""
    with TemporaryDirectory() as tmpdir:
        secretfile_path = Path(tmpdir) / "Secretfile.yml"
        secretfile_path.write_text("""
version: "1.0"
providers:
  aws:
    kind: aws
secrets:
  - name: static_api_key
    kind: static
    config:
      default: keep-me-out-of-code
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /test/static_api_key
""")
        loader = ConfigLoader()
        secretfile = loader.load_file(secretfile_path)
        registry = get_bundle_registry()
        options = TerraformGeneratorOptions(
            output_dir=Path(tmpdir),
            format=TerraformOutputFormat.JSON,
            include_static_secrets=False,
        )
        project = generate_terraform(secretfile, options, registry=registry)

    static_secret = next(s for s in secretfile.secrets if str(s.kind) == "static")
    var_cfg = next(
        cfg
        for cfg in project.variables.values()
        if cfg.get("description") == f"Value for static secret '{static_secret.name}'."
    )
    assert var_cfg["sensitive"] is True
    assert var_cfg["type"] == "string"
    assert "default" not in var_cfg


def test_terraform_static_dict_variable_type_and_default() -> None:
    """Static dict secrets should map to `any` variable type and keep default when requested."""
    secretfile_path = _project_root() / "examples" / "azure-appreg-to-aws-sm.yml"
    loader = ConfigLoader()
    secretfile = loader.load_file(secretfile_path)
    registry = get_bundle_registry()

    with TemporaryDirectory() as tmpdir:
        options = TerraformGeneratorOptions(
            output_dir=Path(tmpdir),
            format=TerraformOutputFormat.JSON,
            include_static_secrets=True,
        )
        project = generate_terraform(secretfile, options, registry=registry)

    azure_secret = next(s for s in secretfile.secrets if str(s.kind) == "azure_app_reg")
    var_cfg = next(
        cfg
        for cfg in project.variables.values()
        if cfg.get("description") == f"Value for static secret '{azure_secret.name}'."
    )
    assert var_cfg["type"] == "any"
    assert isinstance(var_cfg.get("default"), dict)
