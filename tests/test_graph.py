"""Tests for graph visualization functionality."""

from pathlib import Path

import pytest

from secretzero.graph import SecretGraphGenerator, generate_graph


@pytest.fixture
def sample_secretfile(tmp_path: Path) -> Path:
    """Create a sample Secretfile for testing.

    Args:
        tmp_path: Pytest temporary directory

    Returns:
        Path to sample Secretfile
    """
    secretfile = tmp_path / "Secretfile.yml"
    secretfile.write_text("""
version: '1.0'

metadata:
  project: TestProject
  owner: test-team
  description: Test secretfile for graph generation

providers:
  local:
    kind: local
  github:
    kind: github
    auth:
      kind: token
      config:
        token: ${GITHUB_TOKEN}

secrets:
  - name: db_password
    kind: random_password
    config:
      length: 32
      special: true
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv

  - name: api_key
    kind: random_string
    config:
      length: 64
      charset: hex
    targets:
      - provider: local
        kind: file
        config:
          path: .secrets/api_key
          format: json
      - provider: github
        kind: github_secret
        config:
          owner: test-org
          repo: test-repo
          secret_name: API_KEY
""")
    return secretfile


def test_graph_generator_initialization(sample_secretfile: Path):
    """Test graph generator initializes correctly."""
    generator = SecretGraphGenerator(sample_secretfile)

    assert generator.secretfile is not None
    assert len(generator.secretfile.secrets) == 2
    assert generator.secretfile.metadata.project == "TestProject"


def test_generate_flow_diagram(sample_secretfile: Path):
    """Test flow diagram generation."""
    generator = SecretGraphGenerator(sample_secretfile)
    diagram = generator.generate_flow_diagram()

    # Verify mermaid syntax
    assert "```mermaid" in diagram
    assert "flowchart LR" in diagram
    assert "```" in diagram

    # Verify secret nodes
    assert "db_password" in diagram
    assert "api_key" in diagram

    # Verify generator nodes
    assert "random_password" in diagram.lower()
    assert "random_string" in diagram.lower()

    # Verify connections
    assert "generates" in diagram
    assert "syncs to" in diagram

    # Verify styling
    assert "generatorStyle" in diagram
    assert "secretStyle" in diagram
    assert "targetStyle" in diagram


def test_generate_detailed_diagram(sample_secretfile: Path):
    """Test detailed diagram generation."""
    generator = SecretGraphGenerator(sample_secretfile)
    diagram = generator.generate_detailed_diagram()

    # Verify mermaid syntax
    assert "```mermaid" in diagram
    assert "flowchart TB" in diagram

    # Verify secret nodes with emoji
    assert "🔐 db_password" in diagram
    assert "🔐 api_key" in diagram

    # Verify target information
    assert "Target:" in diagram
    assert "local/file" in diagram
    assert "github/github_secret" in diagram


def test_generate_architecture_diagram(sample_secretfile: Path):
    """Test architecture diagram generation."""
    generator = SecretGraphGenerator(sample_secretfile)
    diagram = generator.generate_architecture_diagram()

    # Verify mermaid syntax
    assert "```mermaid" in diagram
    assert "graph TB" in diagram

    # Verify subgraphs
    assert "subgraph Sources" in diagram
    assert "subgraph Secrets" in diagram
    assert "subgraph Targets" in diagram

    # Verify SecretZero engine node
    assert "SecretZero" in diagram

    # Verify connections
    assert "SecretZero" in diagram


def test_generate_terminal_summary(sample_secretfile: Path):
    """Test terminal summary generation."""
    generator = SecretGraphGenerator(sample_secretfile)
    summary = generator.generate_terminal_summary()

    # Verify structure
    assert "SecretZero Configuration Summary" in summary
    assert "=" * 80 in summary

    # Verify metadata
    assert "Metadata:" in summary
    assert "Project: TestProject" in summary
    assert "Owner: test-team" in summary

    # Verify providers
    assert "Providers (2):" in summary
    assert "local (local)" in summary
    assert "github (github)" in summary

    # Verify secrets
    assert "Secrets (2):" in summary
    assert "db_password" in summary
    assert "api_key" in summary
    assert "Generator: random_password" in summary
    assert "Generator: random_string" in summary

    # Verify targets
    assert "Targets" in summary
    assert "→ local/file" in summary
    assert "→ github/github_secret" in summary


def test_generate_graph_flow(sample_secretfile: Path):
    """Test generate_graph function with flow type."""
    diagram = generate_graph(sample_secretfile, graph_type="flow", output_format="mermaid")

    assert "```mermaid" in diagram
    assert "flowchart LR" in diagram
    assert "db_password" in diagram


def test_generate_graph_detailed(sample_secretfile: Path):
    """Test generate_graph function with detailed type."""
    diagram = generate_graph(sample_secretfile, graph_type="detailed", output_format="mermaid")

    assert "```mermaid" in diagram
    assert "flowchart TB" in diagram
    assert "🔐" in diagram


def test_generate_graph_architecture(sample_secretfile: Path):
    """Test generate_graph function with architecture type."""
    diagram = generate_graph(sample_secretfile, graph_type="architecture", output_format="mermaid")

    assert "```mermaid" in diagram
    assert "graph TB" in diagram
    assert "SecretZero" in diagram


def test_generate_graph_terminal(sample_secretfile: Path):
    """Test generate_graph function with terminal format."""
    summary = generate_graph(sample_secretfile, graph_type="flow", output_format="terminal")

    assert "SecretZero Configuration Summary" in summary
    assert "=" * 80 in summary
    assert "db_password" in summary


def test_safe_id_conversion(sample_secretfile: Path):
    """Test safe ID conversion for Mermaid nodes."""
    generator = SecretGraphGenerator(sample_secretfile)

    # Test various inputs
    assert generator._safe_id("simple-name") == "simple_name"
    assert generator._safe_id("name.with.dots") == "name_with_dots"
    assert generator._safe_id("name with spaces") == "name_with_spaces"
    assert "name" in generator._safe_id("name-with-special!@#").lower()


def test_format_generator_label(sample_secretfile: Path):
    """Test generator label formatting."""
    generator = SecretGraphGenerator(sample_secretfile)

    assert "📝" in generator._format_generator_label("random_password")
    assert "Random Password" in generator._format_generator_label("random_password")
    assert "Static" in generator._format_generator_label("static")


def test_multiple_secrets_flow(tmp_path: Path):
    """Test flow diagram with multiple secrets and targets."""
    secretfile = tmp_path / "Secretfile.yml"
    secretfile.write_text("""
version: '1.0'

secrets:
  - name: secret1
    kind: random_password
    config:
      length: 16
    targets:
      - provider: local
        kind: file
        config:
          path: secret1.txt

  - name: secret2
    kind: random_string
    config:
      length: 32
    targets:
      - provider: local
        kind: file
        config:
          path: secret2.txt
      - provider: local
        kind: file
        config:
          path: secret2_copy.txt

  - name: secret3
    kind: static
    config:
      default: static_value
    targets:
      - provider: local
        kind: file
        config:
          path: secret3.txt
""")

    generator = SecretGraphGenerator(secretfile)
    diagram = generator.generate_flow_diagram()

    # Verify all secrets are present
    assert "secret1" in diagram
    assert "secret2" in diagram
    assert "secret3" in diagram

    # Verify all generators are present
    assert "random_password" in diagram.lower()
    assert "random_string" in diagram.lower()
    assert "static" in diagram.lower()


def test_graph_without_metadata(tmp_path: Path):
    """Test graph generation without metadata section."""
    secretfile = tmp_path / "Secretfile.yml"
    secretfile.write_text("""
version: '1.0'

secrets:
  - name: simple_secret
    kind: random_password
    config:
      length: 16
    targets:
      - provider: local
        kind: file
        config:
          path: secret.txt
""")

    generator = SecretGraphGenerator(secretfile)
    summary = generator.generate_terminal_summary()

    # Should not crash without metadata
    assert "SecretZero Configuration Summary" in summary
    assert "simple_secret" in summary


def test_graph_without_providers(tmp_path: Path):
    """Test graph generation without explicit providers section."""
    secretfile = tmp_path / "Secretfile.yml"
    secretfile.write_text("""
version: '1.0'

secrets:
  - name: simple_secret
    kind: random_password
    config:
      length: 16
    targets:
      - provider: local
        kind: file
        config:
          path: secret.txt
""")

    generator = SecretGraphGenerator(secretfile)
    diagram = generator.generate_flow_diagram()

    # Should use local provider by default
    assert "local/file" in diagram or "local" in diagram.lower()


def test_invalid_graph_type(sample_secretfile: Path):
    """Test error handling for invalid graph type."""
    with pytest.raises(ValueError, match="Unknown graph type"):
        generate_graph(sample_secretfile, graph_type="invalid", output_format="mermaid")  # type: ignore
