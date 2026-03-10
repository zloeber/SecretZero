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
