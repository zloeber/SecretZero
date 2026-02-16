"""CLI interface for SecretZero."""

from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from secretzero import __version__
from secretzero.config import ConfigLoader

console = Console()


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """SecretZero: Secrets orchestration, lifecycle, and bootstrap engine.

    SecretZero helps automate the creation, seeding, and lifecycle management
    of project secrets through a declarative, schema-driven workflow.
    """
    pass


@main.command()
@click.option(
    "--template-type",
    type=click.Choice(["basic", "aws", "azure", "vault", "kubernetes"]),
    default="basic",
    help="Template type to use for initialization",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="Secretfile.yml",
    help="Output file path",
)
def init(template_type: str, output: str) -> None:
    """Create a new Secretfile from a template.

    This command generates a starter Secretfile.yml with example configurations
    for different provider types.
    """
    output_path = Path(output)

    if output_path.exists():
        console.print(f"[red]Error:[/red] File already exists: {output}")
        raise click.Abort()

    # Basic template
    template = """# Secretfile.yml
version: '1.0'

# Variables for dynamic configuration
variables:
  environment: local
  region: us-east-1

# Optional metadata
metadata:
  project: my-project
  owner: platform-team
  environments:
    - dev
    - prod
  compliance:
    - soc2

# Provider configurations
providers:
  local:
    kind: local
    config: {}

# Secret definitions
secrets:
  - name: example_password
    kind: random_password
    config:
      length: 32
      special: true
      upper: true
      lower: true
      number: true
    targets:
      - provider: local
        kind: file
        config:
          path: .env.local
          format: dotenv
          merge: true

# Secret templates for complex secrets
templates: {}

# Reserved for future use
policies: {}
labels: {}
annotations: {}
"""

    output_path.write_text(template)
    console.print(f"[green]✓[/green] Created Secretfile: {output}")
    console.print("\nNext steps:")
    console.print("  1. Edit the Secretfile.yml to add your secrets")
    console.print("  2. Run 'secretzero validate' to check the configuration")
    console.print("  3. Run 'secretzero sync --dry-run' to test secret generation")


@main.command()
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=True),
    default="Secretfile.yml",
    help="Path to Secretfile",
)
def validate(file: str) -> None:
    """Validate Secretfile configuration.

    This command checks the syntax and structure of your Secretfile.yml,
    ensuring all required fields are present and properly formatted.
    """
    file_path = Path(file)
    loader = ConfigLoader()

    console.print(f"Validating: {file_path}")

    is_valid, message = loader.validate_file(file_path)

    if is_valid:
        console.print(f"[green]✓[/green] {message}")

        # Show summary of configuration
        config = loader.load_file(file_path)
        console.print("\n[bold]Configuration Summary:[/bold]")
        console.print(f"  Version: {config.version}")
        console.print(f"  Variables: {len(config.variables)}")
        console.print(f"  Providers: {len(config.providers)}")
        console.print(f"  Secrets: {len(config.secrets)}")
        console.print(f"  Templates: {len(config.templates)}")
    else:
        console.print(f"[red]✗[/red] {message}")
        raise click.Abort()


@main.command("secret-types")
@click.option(
    "--type",
    "-t",
    help="Show details for a specific secret type",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed information",
)
def secret_types(type: Optional[str], verbose: bool) -> None:
    """List supported secret types and generators.

    Shows all available secret generator types that can be used in your
    Secretfile configuration, along with their supported parameters.
    """
    if type:
        # Show details for specific type
        _show_type_details(type)
    else:
        # List all types
        _list_all_types(verbose)


def _list_all_types(verbose: bool) -> None:
    """List all available secret types."""
    console.print("[bold]Available Secret Generator Types:[/bold]\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Type", style="green")
    table.add_column("Description")

    generators = {
        "random_password": "Generate random passwords with configurable complexity",
        "random_string": "Generate random alphanumeric strings",
        "static": "Static value with optional validation",
        "script": "Execute external script to generate value",
        "api": "Fetch value from external API endpoint",
    }

    for gen_type, description in generators.items():
        table.add_row(gen_type, description)

    console.print(table)

    console.print("\n[bold]Available Target Types:[/bold]\n")

    target_table = Table(show_header=True, header_style="bold cyan")
    target_table.add_column("Type", style="green")
    target_table.add_column("Description")

    targets = {
        "file": "Store in local file (dotenv, json, yaml, toml)",
        "ssm_parameter": "AWS Systems Manager Parameter Store",
        "secrets_manager": "AWS Secrets Manager",
        "vault_kv": "HashiCorp Vault KV engine",
        "azure_keyvault": "Azure Key Vault",
        "kubernetes_secret": "Kubernetes Secret",
        "github_secret": "GitHub Actions Secret",
        "gitlab_variable": "GitLab CI/CD Variable",
    }

    for target_type, description in targets.items():
        target_table.add_row(target_type, description)

    console.print(target_table)

    if not verbose:
        console.print("\nUse --type <type> --verbose for detailed configuration options")


def _show_type_details(type_name: str) -> None:
    """Show detailed information about a specific type."""
    console.print(f"[bold]Secret Type: {type_name}[/bold]\n")

    type_details = {
        "random_password": {
            "description": "Generate cryptographically secure random passwords",
            "config": {
                "length": "Password length (default: 32)",
                "upper": "Include uppercase letters (default: true)",
                "lower": "Include lowercase letters (default: true)",
                "number": "Include numbers (default: true)",
                "special": "Include special characters (default: true)",
                "exclude_characters": "Characters to exclude from generation",
            },
            "example": """secrets:
  - name: db_password
    kind: random_password
    config:
      length: 32
      special: true
      exclude_characters: '"@/\\`'
    targets:
      - provider: local
        kind: file
        config:
          path: .env
          format: dotenv""",
        },
        "static": {
            "description": "Use a static value with optional validation",
            "config": {
                "default": "Default value to use",
                "validation": "Regex pattern for validation",
                "rotation_period": "Rotation period (e.g., 90d)",
            },
            "example": """secrets:
  - name: api_key
    kind: static
    config:
      validation: ^[a-zA-Z0-9]{40}$
      default: your-api-key-here
    targets:
      - provider: aws
        kind: ssm_parameter
        config:
          name: /app/api-key""",
        },
    }

    if type_name in type_details:
        details = type_details[type_name]
        console.print(f"[cyan]Description:[/cyan] {details['description']}\n")

        console.print("[cyan]Configuration Options:[/cyan]")
        for option, desc in details["config"].items():
            console.print(f"  • {option}: {desc}")

        console.print("\n[cyan]Example:[/cyan]")
        console.print(f"[dim]{details['example']}[/dim]")
    else:
        console.print(f"[red]Unknown type:[/red] {type_name}")
        console.print("\nRun 'secretzero secret-types' to see available types")


@main.command()
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=True),
    default="Secretfile.yml",
    help="Path to Secretfile",
)
def test(file: str) -> None:
    """Test provider connectivity and authentication.

    This command validates that all configured providers can be authenticated
    and accessed successfully.
    """
    file_path = Path(file)
    loader = ConfigLoader()

    try:
        config = loader.load_file(file_path)
    except Exception as e:
        console.print(f"[red]Error loading Secretfile:[/red] {e}")
        raise click.Abort()

    console.print("[bold]Testing Provider Connectivity:[/bold]\n")

    for provider_name, provider in config.providers.items():
        console.print(f"  • {provider_name}: ", end="")
        console.print("[yellow]Not implemented yet[/yellow]")

    console.print("\n[dim]Note: Provider testing will be implemented in a future phase[/dim]")


if __name__ == "__main__":
    main()
