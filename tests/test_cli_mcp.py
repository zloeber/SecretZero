"""Tests for secretzero mcp CLI subcommand."""

from __future__ import annotations

from click.testing import CliRunner

from secretzero.cli import main


def test_mcp_serve_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["mcp", "serve", "--help"])
    assert result.exit_code == 0
    assert "stdio" in result.output.lower()


def test_mcp_config_generate_json() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["mcp", "config", "generate", "--format", "cursor"])
    assert result.exit_code == 0
    assert '"servers"' in result.output
    assert '"mcp"' in result.output
    assert '"serve"' in result.output
