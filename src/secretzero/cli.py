"""CLI interface for SecretZero."""

from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from secretzero import __version__
from secretzero.config import ConfigLoader
from secretzero.drift import DriftDetector
from secretzero.lockfile import Lockfile
from secretzero.policy import PolicyEngine
from secretzero.rotation import format_rotation_status, should_rotate_secret
from secretzero.sync import SyncEngine

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
        "jenkins_credential": "Jenkins Credential",
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

    if not config.providers:
        console.print("[dim]No providers configured[/dim]")
        return

    all_passed = True
    for provider_name, provider_config in config.providers.items():
        console.print(f"  • {provider_name}: ", end="")
        
        # Determine provider type - provider_config is a Provider model
        provider_kind = provider_config.kind if provider_config.kind else provider_name
        
        # Create provider instance
        provider = None
        if provider_kind == "aws":
            try:
                from secretzero.providers.aws import AWSProvider
                # Convert Pydantic model to dict for provider initialization
                config_dict = provider_config.model_dump()
                provider = AWSProvider(name=provider_name, config=config_dict)
            except ImportError:
                console.print("[yellow]boto3 not installed[/yellow]")
                all_passed = False
                continue
        elif provider_kind == "azure":
            try:
                from secretzero.providers.azure import AzureProvider
                config_dict = provider_config.model_dump()
                provider = AzureProvider(name=provider_name, config=config_dict)
            except ImportError:
                console.print("[yellow]Azure SDK not installed[/yellow]")
                all_passed = False
                continue
        elif provider_kind == "vault":
            try:
                from secretzero.providers.vault import VaultProvider
                config_dict = provider_config.model_dump()
                provider = VaultProvider(name=provider_name, config=config_dict)
            except ImportError:
                console.print("[yellow]hvac not installed[/yellow]")
                all_passed = False
                continue
        elif provider_kind == "github":
            try:
                from secretzero.providers.github import GitHubProvider
                config_dict = provider_config.model_dump()
                provider = GitHubProvider(name=provider_name, config=config_dict)
            except ImportError:
                console.print("[yellow]PyGithub not installed[/yellow]")
                all_passed = False
                continue
        elif provider_kind == "gitlab":
            try:
                from secretzero.providers.gitlab import GitLabProvider
                config_dict = provider_config.model_dump()
                provider = GitLabProvider(name=provider_name, config=config_dict)
            except ImportError:
                console.print("[yellow]python-gitlab not installed[/yellow]")
                all_passed = False
                continue
        elif provider_kind == "jenkins":
            try:
                from secretzero.providers.jenkins import JenkinsProvider
                config_dict = provider_config.model_dump()
                provider = JenkinsProvider(name=provider_name, config=config_dict)
            except ImportError:
                console.print("[yellow]python-jenkins not installed[/yellow]")
                all_passed = False
                continue
        elif provider_kind == "kubernetes":
            try:
                from secretzero.providers.kubernetes import KubernetesProvider
                config_dict = provider_config.model_dump()
                provider = KubernetesProvider(name=provider_name, config=config_dict)
            except ImportError:
                console.print("[yellow]kubernetes not installed[/yellow]")
                all_passed = False
                continue
        elif provider_kind == "local":
            console.print("[green]✓ Local provider (always available)[/green]")
            continue
        else:
            console.print(f"[yellow]Unknown provider type: {provider_kind}[/yellow]")
            all_passed = False
            continue
        
        # Test connectivity
        if provider:
            success, message = provider.test_connection()
            if success:
                console.print(f"[green]✓ {message}[/green]")
            else:
                console.print(f"[red]✗ {message}[/red]")
                all_passed = False

    if all_passed:
        console.print("\n[green]All provider tests passed![/green]")
    else:
        console.print("\n[yellow]Some provider tests failed. Check the messages above.[/yellow]")


@main.command()
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=True),
    default="Secretfile.yml",
    help="Path to Secretfile",
)
@click.option(
    "--lockfile",
    "-l",
    type=click.Path(),
    default=".gitsecrets.lock",
    help="Path to lockfile",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be done without making changes",
)
def sync(file: str, lockfile: str, dry_run: bool) -> None:
    """Generate and synchronize secrets to targets.

    This command generates secret values according to your Secretfile
    configuration and stores them in the specified targets (local files,
    cloud providers, etc.).
    """
    file_path = Path(file)
    lockfile_path = Path(lockfile)
    loader = ConfigLoader()

    # Load configuration
    try:
        config = loader.load_file(file_path)
    except Exception as e:
        console.print(f"[red]Error loading Secretfile:[/red] {e}")
        raise click.Abort()

    # Load lockfile
    lock = Lockfile.load(lockfile_path)

    # Create sync engine and run
    engine = SyncEngine(config, lock)

    if dry_run:
        console.print("[yellow]DRY RUN:[/yellow] No changes will be made\n")

    console.print("[bold]Synchronizing secrets...[/bold]\n")

    try:
        results = engine.sync(dry_run=dry_run)

        # Display results
        console.print(f"[green]✓[/green] Processed {results['secrets_processed']} secrets")
        console.print(f"  • Generated: {results['secrets_generated']}")
        console.print(f"  • Skipped: {results['secrets_skipped']}")
        console.print(f"  • Stored: {results['secrets_stored']}")

        if results["errors"]:
            console.print(f"\n[red]Errors:[/red]")
            for error in results["errors"]:
                console.print(f"  • {error}")

        # Show detailed results if verbose or dry-run
        if dry_run or results["secrets_generated"] > 0 or results["secrets_skipped"] > 0:
            console.print("\n[bold]Details:[/bold]")
            for detail in results["details"]:
                status = "would generate" if dry_run else "generated"
                if detail.get("skipped"):
                    status = f"skipped ({detail.get('reason', 'unknown')})"

                console.print(f"\n  {detail['name']} [{detail['kind']}]: {status}")

                # Show template fields if applicable
                if detail.get("template") and detail.get("fields"):
                    for field in detail["fields"]:
                        console.print(f"    • {field['name']}: ", end="")
                        if field["generated"]:
                            console.print("[green]generated[/green]")
                        else:
                            console.print("[yellow]skipped[/yellow]")

                # Show target information
                if detail.get("targets"):
                    for target in detail["targets"]:
                        target_status = target.get("status", "unknown")
                        console.print(
                            f"    → {target['provider']}/{target['kind']}: {target_status}"
                        )
                        if target.get("message"):
                            console.print(f"      {target['message']}")

        # Save lockfile if not dry run
        if not dry_run and results["secrets_generated"] > 0:
            lock.save(lockfile_path)
            console.print(f"\n[green]✓[/green] Lockfile saved: {lockfile_path}")

        if dry_run:
            console.print("\n[yellow]This was a dry run. Use 'secretzero sync' to apply changes.[/yellow]")

    except Exception as e:
        console.print(f"\n[red]Error during sync:[/red] {e}")
        raise click.Abort()


@main.command()
@click.argument("secret_name")
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=True),
    default="Secretfile.yml",
    help="Path to Secretfile",
)
@click.option(
    "--lockfile",
    "-l",
    type=click.Path(),
    default=".gitsecrets.lock",
    help="Path to lockfile",
)
def show(secret_name: str, file: str, lockfile: str) -> None:
    """Show information about a specific secret.

    This command displays metadata about a secret, including its
    configuration, generation status, and target storage locations.
    """
    file_path = Path(file)
    lockfile_path = Path(lockfile)
    loader = ConfigLoader()

    # Load configuration
    try:
        config = loader.load_file(file_path)
    except Exception as e:
        console.print(f"[red]Error loading Secretfile:[/red] {e}")
        raise click.Abort()

    # Load lockfile
    lock = Lockfile.load(lockfile_path)

    # Create sync engine
    engine = SyncEngine(config, lock)

    # Get secret info
    info = engine.get_secret_info(secret_name)

    if not info:
        console.print(f"[red]Error:[/red] Secret '{secret_name}' not found in Secretfile")
        raise click.Abort()

    # Display information
    console.print(f"[bold]Secret: {info['name']}[/bold]\n")

    table = Table(show_header=False, box=None)
    table.add_column("Property", style="cyan")
    table.add_column("Value")

    table.add_row("Kind", info['kind'])
    table.add_row("One-time", "Yes" if info['one_time'] else "No")

    if info.get('rotation_period'):
        table.add_row("Rotation Period", info['rotation_period'])

    table.add_row("Generated", "Yes" if info['exists_in_lockfile'] else "No")

    if info['exists_in_lockfile']:
        table.add_row("Created", info['created_at'])
        table.add_row("Updated", info['updated_at'])
        table.add_row("Hash", info['hash'][:16] + "...")

    console.print(table)

    # Show targets
    if info['targets']:
        console.print("\n[bold]Targets:[/bold]")
        for target in info['targets']:
            console.print(f"  • {target['provider']} / {target['kind']}")


@main.command()
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=True),
    default="Secretfile.yml",
    help="Path to Secretfile",
)
@click.option(
    "--lockfile",
    "-l",
    type=click.Path(),
    default=".gitsecrets.lock",
    help="Path to lockfile",
)
@click.option(
    "--force",
    is_flag=True,
    help="Force rotation even if not due",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be rotated without making changes",
)
@click.argument("secret_name", required=False)
def rotate(file: str, lockfile: str, force: bool, dry_run: bool, secret_name: Optional[str]) -> None:
    """Rotate secrets based on rotation policies.

    This command checks which secrets need rotation and regenerates them.
    Respects rotation_period settings and one_time flags.
    """
    file_path = Path(file)
    lockfile_path = Path(lockfile)
    loader = ConfigLoader()

    # Load configuration
    try:
        config = loader.load_file(file_path)
    except Exception as e:
        console.print(f"[red]Error loading Secretfile:[/red] {e}")
        raise click.Abort()

    # Load lockfile
    lock = Lockfile.load(lockfile_path)

    console.print("[bold]Checking secrets for rotation...[/bold]\n")

    # Filter secrets
    secrets_to_check = config.secrets
    if secret_name:
        secrets_to_check = [s for s in config.secrets if s.name == secret_name]
        if not secrets_to_check:
            console.print(f"[red]Error:[/red] Secret '{secret_name}' not found")
            raise click.Abort()

    secrets_to_rotate = []
    
    for secret in secrets_to_check:
        # Check if secret has rotation period
        if not secret.rotation_period:
            continue
        
        # Get lockfile entry
        entry = lock.get_secret_info(secret.name)
        if not entry:
            continue
        
        # Check if one_time secret
        if secret.one_time:
            console.print(f"  ⚠️  {secret.name}: one_time secret (rotation disabled)")
            continue
        
        # Check if rotation needed
        should_rotate_flag, reason = should_rotate_secret(
            secret.rotation_period,
            entry.last_rotated,
            entry.created_at,
        )
        
        if should_rotate_flag or force:
            secrets_to_rotate.append(secret)
            status = "⚠️" if should_rotate_flag else "ℹ️"
            console.print(f"  {status}  {secret.name}: {reason}")
        else:
            console.print(f"  ✓  {secret.name}: {reason}")

    if not secrets_to_rotate:
        console.print("\n[green]No secrets need rotation.[/green]")
        return

    console.print(f"\n[yellow]Found {len(secrets_to_rotate)} secret(s) to rotate[/yellow]")

    if dry_run:
        console.print("\n[yellow]DRY RUN:[/yellow] No changes will be made")
        for secret in secrets_to_rotate:
            console.print(f"  Would rotate: {secret.name}")
        return

    # Perform rotation via sync with force flag
    console.print("\n[bold]Rotating secrets...[/bold]\n")
    
    engine = SyncEngine(config, lock)
    
    # Filter secrets for rotation
    original_secrets = config.secrets
    config.secrets = secrets_to_rotate
    
    try:
        results = engine.sync(dry_run=False, force_rotation=True)
        
        console.print(f"[green]✓[/green] Rotated {results['secrets_generated']} secrets")
        
        if results["errors"]:
            console.print(f"\n[red]Errors:[/red]")
            for error in results["errors"]:
                console.print(f"  • {error}")
        
        # Save lockfile
        lock.save(lockfile_path)
        console.print(f"\n[green]✓[/green] Lockfile updated: {lockfile_path}")
        
    except Exception as e:
        console.print(f"\n[red]Error during rotation:[/red] {e}")
        raise click.Abort()
    finally:
        # Restore original secrets list
        config.secrets = original_secrets


@main.command()
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=True),
    default="Secretfile.yml",
    help="Path to Secretfile",
)
@click.option(
    "--lockfile",
    "-l",
    type=click.Path(),
    default=".gitsecrets.lock",
    help="Path to lockfile",
)
@click.option(
    "--fail-on-warning",
    is_flag=True,
    help="Exit with error code on policy warnings",
)
def policy(file: str, lockfile: str, fail_on_warning: bool) -> None:
    """Check secrets against policy rules.

    This command validates secrets against rotation, compliance, and
    access control policies defined in the Secretfile.
    """
    file_path = Path(file)
    lockfile_path = Path(lockfile)
    loader = ConfigLoader()

    # Load configuration
    try:
        config = loader.load_file(file_path)
    except Exception as e:
        console.print(f"[red]Error loading Secretfile:[/red] {e}")
        raise click.Abort()

    # Load lockfile
    lock = None
    if lockfile_path.exists():
        lock = Lockfile.load(lockfile_path)

    console.print("[bold]Checking policy compliance...[/bold]\n")

    # Create policy engine
    engine = PolicyEngine(config)
    
    # Validate all secrets
    violations = engine.validate_all(lock)

    if not violations:
        console.print("[green]✓ All secrets comply with policies[/green]")
        return

    # Group violations by severity
    errors = [v for v in violations if v.severity == "error"]
    warnings = [v for v in violations if v.severity == "warning"]
    infos = [v for v in violations if v.severity == "info"]

    # Display violations
    if errors:
        console.print("[red bold]Errors:[/red bold]")
        for violation in errors:
            console.print(f"  ✗ {violation.secret_name}: {violation.message}")
            if violation.suggestion:
                console.print(f"    → {violation.suggestion}")
        console.print()

    if warnings:
        console.print("[yellow bold]Warnings:[/yellow bold]")
        for violation in warnings:
            console.print(f"  ⚠  {violation.secret_name}: {violation.message}")
            if violation.suggestion:
                console.print(f"    → {violation.suggestion}")
        console.print()

    if infos:
        console.print("[blue bold]Info:[/blue bold]")
        for violation in infos:
            console.print(f"  ℹ  {violation.secret_name}: {violation.message}")
        console.print()

    # Summary
    console.print(f"[bold]Summary:[/bold]")
    console.print(f"  Errors: {len(errors)}")
    console.print(f"  Warnings: {len(warnings)}")
    console.print(f"  Info: {len(infos)}")

    # Exit with error if needed
    if errors or (fail_on_warning and warnings):
        raise click.Abort()


@main.command()
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=True),
    default="Secretfile.yml",
    help="Path to Secretfile",
)
@click.option(
    "--lockfile",
    "-l",
    type=click.Path(),
    default=".gitsecrets.lock",
    help="Path to lockfile",
)
@click.argument("secret_name", required=False)
def drift(file: str, lockfile: str, secret_name: Optional[str]) -> None:
    """Detect drift between lockfile and actual targets.

    This command checks if secrets have been modified outside of
    SecretZero's control.
    """
    file_path = Path(file)
    lockfile_path = Path(lockfile)

    if not lockfile_path.exists():
        console.print(f"[red]Error:[/red] Lockfile not found: {lockfile_path}")
        console.print("Run 'secretzero sync' first to generate secrets")
        raise click.Abort()

    console.print("[bold]Checking for drift...[/bold]\n")

    detector = DriftDetector(file_path, lockfile_path)
    results = detector.check_drift(secret_name)

    # Display results
    drift_found = False
    for result in results:
        if result.has_drift:
            drift_found = True
            console.print(f"  ⚠️  {result.secret_name}: {result.message}")
            if result.details:
                for key, value in result.details.items():
                    console.print(f"      {key}: {value}")
        else:
            console.print(f"  ✓  {result.secret_name}: {result.message}")

    if drift_found:
        console.print("\n[yellow]Drift detected. Run 'secretzero sync --force' to remediate.[/yellow]")
    else:
        console.print("\n[green]No drift detected.[/green]")


if __name__ == "__main__":
    main()
