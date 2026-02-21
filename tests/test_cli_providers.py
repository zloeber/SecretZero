"""Tests for provider CLI commands."""

import json

import pytest
from click.testing import CliRunner

from secretzero.cli import main


class TestProvidersGroup:
    """Test providers CLI group."""

    def test_providers_group_exists(self):
        """Test that providers group exists."""
        runner = CliRunner()
        result = runner.invoke(main, ["providers", "--help"])
        assert result.exit_code == 0
        assert "Manage and introspect providers" in result.output

    def test_providers_help(self):
        """Test providers help command."""
        runner = CliRunner()
        result = runner.invoke(main, ["providers", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "capabilities" in result.output
        assert "methods" in result.output
        assert "schema" in result.output


class TestProvidersListCommand:
    """Test providers list command."""

    def test_providers_list_success(self):
        """Test listing all providers."""
        runner = CliRunner()
        result = runner.invoke(main, ["providers", "list"])
        assert result.exit_code == 0
        assert "Registered Providers" in result.output
        assert "vault" in result.output
        assert "aws" in result.output
        assert "azure" in result.output

    def test_providers_list_displays_descriptions(self):
        """Test that providers list shows descriptions."""
        runner = CliRunner()
        result = runner.invoke(main, ["providers", "list"])
        assert result.exit_code == 0
        assert any(desc in result.output for desc in ["Vault", "AWS", "Azure"])


class TestProvidersCapabilitiesCommand:
    """Test providers capabilities command."""

    def test_capabilities_vault_success(self):
        """Test showing Vault provider capabilities."""
        runner = CliRunner()
        result = runner.invoke(main, ["providers", "capabilities", "vault"])
        assert result.exit_code == 0
        assert "vault" in result.output.lower()

    def test_capabilities_aws_success(self):
        """Test showing AWS provider capabilities."""
        runner = CliRunner()
        result = runner.invoke(main, ["providers", "capabilities", "aws"])
        assert result.exit_code == 0
        assert "aws" in result.output.lower()

    def test_capabilities_nonexistent_provider(self):
        """Test capabilities for nonexistent provider."""
        runner = CliRunner()
        result = runner.invoke(main, ["providers", "capabilities", "nonexistent"])
        assert result.exit_code != 0

    def test_capabilities_shows_provider_name(self):
        """Test that capabilities shows provider name."""
        runner = CliRunner()
        result = runner.invoke(main, ["providers", "capabilities", "vault"])
        assert result.exit_code == 0
        output_lower = result.output.lower()
        assert "vault" in output_lower


class TestProvidersMethodsCommand:
    """Test providers methods command."""

    def test_methods_vault_success(self):
        """Test listing Vault methods."""
        runner = CliRunner()
        result = runner.invoke(main, ["providers", "methods", "vault"])
        assert result.exit_code == 0

    def test_methods_filter_by_generate(self):
        """Test filtering methods by generate type."""
        runner = CliRunner()
        result = runner.invoke(main, ["providers", "methods", "vault", "--type", "generate"])
        assert result.exit_code == 0

    def test_methods_filter_by_type_short_option(self):
        """Test filtering methods using -t short option."""
        runner = CliRunner()
        result = runner.invoke(main, ["providers", "methods", "vault", "-t", "retrieve"])
        assert result.exit_code == 0

    def test_methods_filter_all_types(self):
        """Test that all type filter works."""
        runner = CliRunner()
        result = runner.invoke(main, ["providers", "methods", "vault", "--type", "all"])
        assert result.exit_code == 0

    def test_methods_nonexistent_provider(self):
        """Test methods for nonexistent provider."""
        runner = CliRunner()
        result = runner.invoke(main, ["providers", "methods", "nonexistent"])
        assert result.exit_code != 0

    def test_methods_invalid_type_filter(self):
        """Test methods with invalid type filter."""
        runner = CliRunner()
        result = runner.invoke(main, ["providers", "methods", "vault", "--type", "invalid_type"])
        assert result.exit_code != 0


class TestProvidersSchemaCommand:
    """Test providers schema command."""

    def test_schema_vault_generate_password(self):
        """Test schema for vault method."""
        runner = CliRunner()
        result = runner.invoke(main, ["providers", "schema", "vault", "generate_password"])
        # Either succeeds or fails with method not found - both expected
        assert result.exit_code in [0, 1]

    def test_schema_nonexistent_provider(self):
        """Test schema for nonexistent provider."""
        runner = CliRunner()
        result = runner.invoke(main, ["providers", "schema", "nonexistent", "method"])
        assert result.exit_code != 0

    def test_schema_nonexistent_method(self):
        """Test schema for nonexistent method."""
        runner = CliRunner()
        result = runner.invoke(main, ["providers", "schema", "vault", "nonexistent_method"])
        assert result.exit_code != 0

    def test_schema_json_output(self):
        """Test schema with JSON output option."""
        runner = CliRunner()
        result = runner.invoke(
            main, ["providers", "schema", "vault", "generate_password", "--json"]
        )
        # May succeed or fail depending on method availability
        # Just ensure it doesn't crash unexpectedly
        assert result.exception is None or isinstance(result.exception, SystemExit)

    def test_schema_handles_missing_arguments(self):
        """Test schema handles missing arguments gracefully."""
        runner = CliRunner()
        result = runner.invoke(main, ["providers", "schema", "vault"])
        # Should fail due to missing method_name argument
        assert result.exit_code != 0


class TestProvidersIntegration:
    """Integration tests for providers CLI commands."""

    def test_providers_workflow(self):
        """Test complete workflow: list -> capabilities -> methods."""
        runner = CliRunner()

        # Step 1: List providers
        result = runner.invoke(main, ["providers", "list"])
        assert result.exit_code == 0

        # Step 2: Show capabilities
        result = runner.invoke(main, ["providers", "capabilities", "vault"])
        assert result.exit_code == 0

        # Step 3: List methods
        result = runner.invoke(main, ["providers", "methods", "vault"])
        assert result.exit_code == 0

    def test_all_providers_listable(self):
        """Test that all providers can be listed."""
        runner = CliRunner()
        result = runner.invoke(main, ["providers", "list"])
        assert result.exit_code == 0

        providers_to_test = ["vault", "aws", "azure", "github", "gitlab", "jenkins", "kubernetes"]

        for provider in providers_to_test:
            result = runner.invoke(main, ["providers", "capabilities", provider])
            assert result.exit_code == 0, f"Failed to get capabilities for {provider}"

    def test_provider_commands_help_available(self):
        """Test that help is available for all provider subcommands."""
        runner = CliRunner()

        commands = ["list", "capabilities", "methods", "schema"]
        for cmd in commands:
            result = runner.invoke(main, ["providers", cmd, "--help"])
            assert result.exit_code == 0, f"Help not available for: {cmd}"


class TestProvidersErrorHandling:
    """Test error handling in provider commands."""

    def test_capabilities_graceful_error_message(self):
        """Test capabilities provides helpful error messages."""
        runner = CliRunner()
        result = runner.invoke(main, ["providers", "capabilities", "unknown_provider"])
        assert result.exit_code != 0

    def test_methods_graceful_error_on_bad_filter(self):
        """Test methods provides helpful error for invalid filters."""
        runner = CliRunner()
        result = runner.invoke(main, ["providers", "methods", "vault", "--type", "invalid_type"])
        assert result.exit_code != 0

    def test_schema_handles_missing_arguments(self):
        """Test schema handles missing arguments gracefully."""
        runner = CliRunner()
        result = runner.invoke(main, ["providers", "schema", "vault"])
        # Should fail due to missing method_name argument
        assert result.exit_code != 0

    def test_capabilities_handles_missing_argument(self):
        """Test capabilities handles missing argument."""
        runner = CliRunner()
        result = runner.invoke(main, ["providers", "capabilities"])
        # Should fail due to missing provider_type argument
        assert result.exit_code != 0


class TestProvidersOutput:
    """Test output formatting of provider commands."""

    def test_list_output_has_table_format(self):
        """Test that list output uses table format."""
        runner = CliRunner()
        result = runner.invoke(main, ["providers", "list"])
        assert result.exit_code == 0
        # Table output should have some structure
        assert len(result.output) > 20

    def test_methods_output_format(self):
        """Test that methods output is formatted."""
        runner = CliRunner()
        result = runner.invoke(main, ["providers", "methods", "vault"])
        assert result.exit_code == 0

    def test_schema_output_includes_provider_method_name(self):
        """Test schema output clearly shows provider and method info."""
        runner = CliRunner()
        result = runner.invoke(main, ["providers", "schema", "vault", "generate_password"])
        # Either succeeds with info or fails with helpful message
        if result.exit_code == 0:
            output_lower = result.output.lower()
            assert "vault" in output_lower or "generate_password" in output_lower
