"""CLI interface for SecretZero."""

import json
from pathlib import Path

import click
from rich import box
from rich.console import Console
from rich.table import Table

from secretzero import __version__
from secretzero.cli_providers import providers_group
from secretzero.config import ConfigLoader
from secretzero.drift import DriftDetector
from secretzero.graph import generate_graph
from secretzero.lockfile import Lockfile
from secretzero.models import Secretfile
from secretzero.policy import PolicyEngine
from secretzero.rotation import should_rotate_secret
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
def create(template_type: str, output: str) -> None:
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
    console.print("  2. Run 'secretzero init --install' to install provider dependencies")
    console.print("  3. Run 'secretzero validate' to check the configuration")
    console.print("  4. Run 'secretzero sync --dry-run' to test secret generation")


@main.command()
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=True),
    default="Secretfile.yml",
    help="Path to Secretfile",
)
@click.option(
    "--install",
    is_flag=True,
    help="Automatically install missing dependencies",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be installed without installing",
)
def init(file: str, install: bool, dry_run: bool) -> None:
    """Initialize project by checking and installing provider dependencies.

    This command reads your Secretfile, identifies configured providers,
    and checks if the required libraries are installed. It can optionally
    install missing dependencies automatically.
    """
    import subprocess
    import sys

    file_path = Path(file)

    if not file_path.exists():
        console.print(f"[red]Error:[/red] Secretfile not found: {file}")
        console.print("\nCreate one first with: [cyan]secretzero create[/cyan]")
        raise click.Abort()

    loader = ConfigLoader()

    try:
        config = loader.load_file(file_path)
    except Exception as e:
        console.print(f"[red]Error loading Secretfile:[/red] {e}")
        raise click.Abort()

    # Map provider kinds to required packages
    provider_packages = {
        "aws": ("boto3", "secretzero[aws]"),
        "azure": ("azure.identity", "secretzero[azure]"),
        "vault": ("hvac", "secretzero[vault]"),
        "kubernetes": ("kubernetes", "secretzero[kubernetes]"),
        "github": ("github", "secretzero[github]"),
        "gitlab": ("gitlab", "secretzero[gitlab]"),
        "jenkins": ("jenkins", "secretzero[jenkins]"),
    }

    console.print("[bold]Checking provider dependencies...[/bold]\n")

    missing = []
    installed = []

    for provider_name, provider_config in config.providers.items():
        provider_kind = provider_config.kind or ""

        if provider_kind in provider_packages:
            import_name, install_name = provider_packages[provider_kind]

            try:
                # Try to import the package
                if import_name == "azure.identity":
                    __import__("azure.identity")
                else:
                    __import__(import_name)
                installed.append((provider_name, provider_kind, install_name))
                console.print(
                    f"[green]✓[/green] {provider_name} ({provider_kind}): dependency installed"
                )
            except ImportError:
                missing.append((provider_name, provider_kind, install_name))
                console.print(
                    f"[yellow]✗[/yellow] {provider_name} ({provider_kind}): missing dependency"
                )

    if installed:
        console.print(f"\n[green]✓[/green] {len(installed)} provider(s) have required dependencies")

    if not missing:
        console.print("\n[green]All provider dependencies are installed![/green]")
        return

    console.print(f"\n[yellow]⚠[/yellow] {len(missing)} provider(s) missing dependencies:")
    for provider_name, provider_kind, install_name in missing:
        # Escape square brackets for Rich markup
        escaped_install_name = install_name.replace("[", "\\[").replace("]", "\\]")
        console.print(
            f"  • {provider_name} ({provider_kind}): [cyan]pip install {escaped_install_name}[/cyan]"
        )

    if dry_run:
        console.print("\n[dim]Dry run mode - no packages will be installed[/dim]")
        return

    if install:
        console.print("\n[bold]Installing missing dependencies...[/bold]")
        install_failed = False
        for provider_name, provider_kind, install_name in missing:
            try:
                console.print(f"\nInstalling {install_name}...")
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", install_name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                if result.returncode != 0:
                    install_failed = True
                    console.print(f"[red]✗[/red] Failed to install {install_name}")
                    if result.stderr:
                        console.print(f"[dim]{result.stderr}[/dim]")
                else:
                    console.print(f"[green]✓[/green] Installed {install_name}")
            except Exception as e:
                install_failed = True
                console.print(f"[red]✗[/red] Failed to install {install_name}: {e}")

        if install_failed:
            console.print("\n[red]✗ Some dependencies failed to install[/red]")
            console.print("\nTroubleshooting steps:")
            console.print("  1. Ensure pip is up to date: python -m pip install --upgrade pip")
            console.print("  2. Check your internet connection")
            console.print("  3. Try installing manually with the command shown above")
            raise click.Abort()
        else:
            console.print("\n[green]✓[/green] Dependency installation complete!")
    else:
        console.print(
            "\n[dim]Run with --install to automatically install missing dependencies[/dim]"
        )


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
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed information including target hashes",
)
def status(file: str, lockfile: str, verbose: bool) -> None:
    """Show synchronization status of secrets and targets.

    This command displays which secrets have been generated and synced to their
    configured targets, along with timestamps and rotation information.
    """
    file_path = Path(file)
    lockfile_path = Path(lockfile)

    loader = ConfigLoader()

    try:
        config = loader.load_file(file_path)
    except Exception as e:
        console.print(f"[red]Error loading Secretfile:[/red] {e}")
        raise click.Abort()

    # Load lockfile
    lock = Lockfile.load(lockfile_path)

    console.print("[bold]Secret Synchronization Status:[/bold]\n")

    if not config.secrets:
        console.print("[dim]No secrets configured[/dim]")
        return

    # Process regular secrets
    for secret in config.secrets:
        _show_secret_status(secret, config, lock, verbose)

    # Show lockfile info
    if lockfile_path.exists():
        console.print(f"\n[dim]Lockfile: {lockfile_path}[/dim]")
        console.print(f"[dim]Total tracked secrets: {len(lock.secrets)}[/dim]")
    else:
        console.print(f"\n[yellow]⚠[/yellow] No lockfile found at {lockfile_path}")
        console.print("[dim]Run 'secretzero sync' to generate secrets and create lockfile[/dim]")


def _show_secret_status(secret, config, lock: Lockfile, verbose: bool) -> None:
    """Show status for a single secret.

    Args:
        secret: Secret configuration
        config: Full Secretfile configuration
        lock: Lockfile instance
        verbose: Whether to show detailed information
    """
    # Check if this is a template secret
    is_template = secret.kind.startswith("templates.")
    secret_name = secret.name

    # Get lockfile entry (or check fields for templates)
    if is_template:
        # For templates, check if all fields are synced
        template_name = secret.kind.replace("templates.", "")
        template = config.templates.get(template_name)

        all_fields_synced = False
        if template and template.fields:
            all_fields_synced = all(
                lock.get_secret_info(f"{secret_name}.{field_name}")
                for field_name in template.fields.keys()
            )

        # Use dummy entry to show synced if all fields are synced
        lock_entry = lock.get_secret_info(secret_name) if not is_template else None
        if all_fields_synced:
            # Template itself doesn't have an entry, but show as synced if fields are
            status_icon = "[green]✓[/green]"
            status_text = "synced"
        else:
            status_icon = "[yellow]○[/yellow]"
            status_text = "not synced"
    else:
        lock_entry = lock.get_secret_info(secret_name)
        # Determine status icon
        if lock_entry:
            status_icon = "[green]✓[/green]"
            status_text = "synced"
        else:
            status_icon = "[yellow]○[/yellow]"
            status_text = "not synced"

    console.print(f"{status_icon} [bold]{secret_name}[/bold] ({secret.kind}) - {status_text}")

    # Show timestamps if synced
    if lock_entry:
        console.print(f"   [dim]Created: {lock_entry.created_at}[/dim]")
        console.print(f"   [dim]Updated: {lock_entry.updated_at}[/dim]")

        if lock_entry.last_rotated:
            console.print(
                f"   [dim]Last Rotated: {lock_entry.last_rotated} (count: {lock_entry.rotation_count})[/dim]"
            )

        if verbose:
            console.print(f"   [dim]Hash: {lock_entry.hash[:16]}...[/dim]")

    # Show template fields if applicable
    if is_template:
        template_name = secret.kind.replace("templates.", "")
        template = config.templates.get(template_name)

        if template and template.fields:
            console.print("   [cyan]Template Fields:[/cyan]")
            for field_name, field_def in template.fields.items():
                field_secret_name = f"{secret_name}.{field_name}"
                field_entry = lock.get_secret_info(field_secret_name)

                if field_entry:
                    field_icon = "[green]✓[/green]"
                    field_status = "synced"
                else:
                    field_icon = "[yellow]○[/yellow]"
                    field_status = "not synced"

                # Show field targets count
                all_field_targets = list(field_def.targets) + (
                    list(template.targets) if template.targets else []
                )
                field_targets_count = len(all_field_targets)
                console.print(
                    f"      {field_icon} {field_name} ({field_def.generator.kind.value}) - {field_status} [{field_targets_count} targets]"
                )

                if verbose and field_entry:
                    console.print(f"         [dim]Hash: {field_entry.hash[:16]}...[/dim]")
                    console.print(f"         [dim]Updated: {field_entry.updated_at}[/dim]")

                # Show field-specific targets if any
                if all_field_targets and verbose:
                    for target in all_field_targets:
                        _show_target_status(
                            field_secret_name,
                            target,
                            field_entry,
                            verbose=False,
                            indent="         ",
                        )

    # Show targets
    if secret.targets:
        console.print("   [cyan]Targets:[/cyan]")
        for target in secret.targets:
            _show_target_status(secret_name, target, lock_entry, verbose)
    elif not is_template:
        console.print("   [dim]No targets configured[/dim]")

    console.print()


def _show_target_status(
    secret_name: str, target, lock_entry, verbose: bool, indent: str = "      "
) -> None:
    """Show status for a single target.

    Args:
        secret_name: Name of the secret
        target: Target configuration
        lock_entry: Lockfile entry for the secret
        verbose: Whether to show detailed information
        indent: Indentation for display
    """
    # Build target identifier (must match sync.py logic)
    # For file targets, use path as the identifier
    if target.kind == "file":
        identifier = target.config.get("path", "")
    else:
        identifier = target.config.get("name", "")

    target_id = f"{target.provider}/{target.kind}/{identifier}"

    # Check if this target is tracked in lockfile
    is_synced = False
    target_hash = None

    if lock_entry and lock_entry.targets:
        target_hash = lock_entry.targets.get(target_id)
        is_synced = target_hash is not None

    # Status icon
    if is_synced:
        target_icon = "[green]✓[/green]"
    else:
        target_icon = "[yellow]○[/yellow]"

    # Format target display
    target_display = f"{target.provider}/{target.kind}"

    # Add target-specific info
    if target.kind == "ssm_parameter":
        param_name = target.config.get("name", "")
        target_display += f" ({param_name})"
    elif target.kind == "secrets_manager":
        secret_id = target.config.get("name", "")
        target_display += f" ({secret_id})"
    elif target.kind == "file":
        file_path = target.config.get("path", "")
        target_display += f" ({file_path})"
    elif target.kind == "key_vault":
        vault_name = target.config.get("vault_name", "")
        secret_key = target.config.get("name", "")
        target_display += f" ({vault_name}/{secret_key})"

    console.print(f"{indent}{target_icon} {target_display}")

    if verbose and target_hash:
        console.print(f"{indent}   [dim]Hash: {target_hash[:16]}...[/dim]")


@main.group()
def schema() -> None:
    """Schema utilities for Secretfile."""
    pass


@schema.command("export")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="-",
    help="Output file path or '-' for stdout",
)
def schema_export(output: str) -> None:
    """Export JSON Schema for Secretfile.yml."""
    schema_json = Secretfile.model_json_schema()
    payload = json.dumps(schema_json, indent=2)

    if output == "-" or not output:
        click.echo(payload)
        return

    Path(output).write_text(payload)
    console.print(f"[green]✓[/green] Schema written: {output}")


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
def secret_types(type: str | None, verbose: bool) -> None:
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


def _class_name_to_snake_case(name: str, suffix: str) -> str:
    """Convert a class name to snake_case type name.

    Handles acronyms properly (SSM, KV, etc.).

    Args:
        name: Class name (e.g., SSMParameterTarget)
        suffix: Suffix to remove (e.g., Target, Generator)

    Returns:
        snake_case type name (e.g., ssm_parameter)
    """
    import re

    # Remove the suffix
    name = name.replace(suffix, "")

    # Insert underscores before uppercase letters that follow lowercase letters
    # or before uppercase letters that are followed by lowercase letters
    # This handles both CamelCase and acronyms like SSMParameter or VaultKV
    name = re.sub(r"([a-z])([A-Z])", r"\1_\2", name)  # camelCase -> camel_Case
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)  # SSMParameter -> SSM_Parameter

    return name.lower()


def _list_all_types(verbose: bool) -> None:
    """List all available secret types."""
    import inspect

    from secretzero import generators, targets

    console.print("[bold]Available Secret Generator Types:[/bold]\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Type", style="green")
    table.add_column("Description")

    # Dynamically discover generators
    generator_types = {}
    for name in dir(generators):
        if name.endswith("Generator") and not name.startswith("_"):
            obj = getattr(generators, name)
            if inspect.isclass(obj) and obj != generators.BaseGenerator:
                # Convert class name to snake_case type name
                type_name = _class_name_to_snake_case(name, "Generator")

                # Get description from class docstring
                description = (obj.__doc__ or "").strip().split("\n")[0]
                generator_types[type_name] = description

    for gen_type, description in sorted(generator_types.items()):
        table.add_row(gen_type, description)

    console.print(table)

    console.print("\n[bold]Available Target Types:[/bold]\n")

    target_table = Table(show_header=True, header_style="bold cyan")
    target_table.add_column("Type", style="green")
    target_table.add_column("Description")

    # Dynamically discover targets
    target_types = {}
    for name in dir(targets):
        if name.endswith("Target") and not name.startswith("_"):
            obj = getattr(targets, name)
            if inspect.isclass(obj) and obj != targets.BaseTarget:
                # Convert class name to snake_case type name
                type_name = _class_name_to_snake_case(name, "Target")

                # Get description from class docstring
                description = (obj.__doc__ or "").strip().split("\n")[0]
                target_types[type_name] = description

    for target_type, description in sorted(target_types.items()):
        target_table.add_row(target_type, description)

    console.print(target_table)

    if not verbose:
        console.print("\nUse --type <type> --verbose for detailed configuration options")


def _show_type_details(type_name: str) -> None:
    """Show detailed information about a specific type."""
    import inspect

    from secretzero import generators, targets

    console.print(f"[bold]Secret Type: {type_name}[/bold]\n")

    # Try to find the class dynamically
    target_class = None
    is_generator = False

    # Check generators
    for name in dir(generators):
        if name.endswith("Generator") and not name.startswith("_"):
            obj = getattr(generators, name)
            if inspect.isclass(obj):
                # Convert class name to snake_case
                converted_name = _class_name_to_snake_case(name, "Generator")
                if converted_name == type_name:
                    target_class = obj
                    is_generator = True
                    break

    # Check targets
    if not target_class:
        for name in dir(targets):
            if name.endswith("Target") and not name.startswith("_"):
                obj = getattr(targets, name)
                if inspect.isclass(obj):
                    # Convert class name to snake_case
                    converted_name = _class_name_to_snake_case(name, "Target")
                    if converted_name == type_name:
                        target_class = obj
                        is_generator = False
                        break

    if not target_class:
        console.print(f"[red]Unknown type:[/red] {type_name}")
        console.print("\nRun 'secretzero secret-types' to see available types")
        return

    # Extract description from class docstring
    class_doc = (target_class.__doc__ or "").strip()
    description = class_doc.split("\n")[0] if class_doc else "No description available"

    console.print(f"[cyan]Description:[/cyan] {description}\n")

    # Extract config options from __init__ docstring
    init_doc = (target_class.__init__.__doc__ or "").strip()
    config_options = {}

    if init_doc:
        # Parse the docstring for config parameters
        lines = init_doc.split("\n")
        in_config = False
        for line in lines:
            stripped = line.strip()
            # Look for the config section
            if "config:" in stripped.lower() or "configuration with options:" in stripped.lower():
                in_config = True
                continue
            # Parse config options (lines starting with -)
            if in_config and stripped.startswith("- "):
                # Extract option name and description
                parts = stripped[2:].split(":", 1)
                if len(parts) == 2:
                    option_name = parts[0].strip()
                    option_desc = parts[1].strip()
                    config_options[option_name] = option_desc
            # Stop if we hit another section or Args/Returns
            elif in_config and stripped and not stripped.startswith("- "):
                if any(keyword in stripped for keyword in ["Args:", "Returns:", "Raises:"]):
                    break

    if config_options:
        console.print("[cyan]Configuration Options:[/cyan]")
        for option, desc in config_options.items():
            console.print(f"  • {option}: {desc}")
    else:
        console.print("[cyan]Configuration Options:[/cyan]")
        console.print("  • No configuration options documented")

    # Generate example
    console.print("\n[cyan]Example:[/cyan]")

    # Create example YAML based on type
    if is_generator:
        example_lines = [
            "secrets:",
            "  - name: my_secret",
            f"    kind: {type_name}",
        ]
        if config_options:
            example_lines.append("    config:")
            # Add example values for each config option (max 3)
            for i, (option, desc) in enumerate(list(config_options.items())[:3]):
                # Try to infer example value from description/option name
                if "length" in option.lower():
                    example_lines.append(f"      {option}: 32")
                elif "default" in option.lower():
                    example_lines.append(f"      {option}: your-value-here")
                elif option in [
                    "upper",
                    "lower",
                    "number",
                    "special",
                    "enabled",
                    "overwrite",
                    "merge",
                ]:
                    example_lines.append(f"      {option}: true")
                elif "charset" in option.lower():
                    example_lines.append(f"      {option}: alphanumeric")
                elif "validation" in option.lower():
                    example_lines.append(f"      {option}: ^[a-zA-Z0-9]+$")
                else:
                    example_lines.append(f"      {option}: value")
        example_lines.extend(
            [
                "    targets:",
                "      - provider: local",
                "        kind: file",
                "        config:",
                "          path: .env",
                "          format: dotenv",
            ]
        )
    else:
        example_lines = [
            "secrets:",
            "  - name: my_secret",
            "    kind: random_password",
            "    targets:",
            "      - provider: your_provider",
            f"        kind: {type_name}",
        ]
        if config_options:
            example_lines.append("        config:")
            # Add example values for each config option (max 3)
            for i, (option, desc) in enumerate(list(config_options.items())[:3]):
                # Try to infer example value from description/option name
                if option in ["enabled", "overwrite", "merge"]:
                    example_lines.append(f"          {option}: true")
                elif "path" in option.lower() or "name" in option.lower():
                    example_lines.append(f"          {option}: example-{option.replace('_', '-')}")
                elif "format" in option.lower():
                    example_lines.append(f"          {option}: dotenv")
                elif "type" in option.lower() and "ssm" in type_name:
                    example_lines.append(f"          {option}: SecureString")
                elif "namespace" in option.lower():
                    example_lines.append(f"          {option}: default")
                else:
                    example_lines.append(f"          {option}: value")

    example_yaml = "\n".join(example_lines)
    console.print(f"[dim]{example_yaml}[/dim]")


def _test_provider_profiles(config) -> None:
    """Test each authentication profile for configured providers.

    Args:
        config: Loaded Secretfile configuration
    """
    console.print("\n[bold]Testing Provider Profiles:[/bold]\n")

    has_profiles = False
    for provider_name, provider_config in config.providers.items():
        # Check if provider has auth profiles
        if not provider_config.auth or not provider_config.auth.profiles:
            continue

        has_profiles = True
        provider_kind = provider_config.kind if provider_config.kind else provider_name
        console.print(f"[bold cyan]{provider_name}[/bold cyan] [{provider_kind}]:")

        for profile_name, profile in provider_config.auth.profiles.items():
            console.print(f"  • {profile_name}: ", end="")

            # Create provider instance with the profile
            provider = None
            try:
                if provider_kind == "aws":
                    from secretzero.providers.aws import AWSProvider

                    config_dict = provider_config.model_dump()
                    # Set the profile to test
                    config_dict["auth"]["selected_profile"] = profile_name
                    provider = AWSProvider(name=provider_name, config=config_dict)
                elif provider_kind == "azure":
                    from secretzero.providers.azure import AzureProvider

                    config_dict = provider_config.model_dump()
                    config_dict["auth"]["selected_profile"] = profile_name
                    provider = AzureProvider(name=provider_name, config=config_dict)
                elif provider_kind == "vault":
                    from secretzero.providers.vault import VaultProvider

                    config_dict = provider_config.model_dump()
                    config_dict["auth"]["selected_profile"] = profile_name
                    provider = VaultProvider(name=provider_name, config=config_dict)
                elif provider_kind == "github":
                    from secretzero.providers.github import GitHubProvider

                    config_dict = provider_config.model_dump()
                    config_dict["auth"]["selected_profile"] = profile_name
                    provider = GitHubProvider(name=provider_name, config=config_dict)
                elif provider_kind == "gitlab":
                    from secretzero.providers.gitlab import GitLabProvider

                    config_dict = provider_config.model_dump()
                    config_dict["auth"]["selected_profile"] = profile_name
                    provider = GitLabProvider(name=provider_name, config=config_dict)
                elif provider_kind == "jenkins":
                    from secretzero.providers.jenkins import JenkinsProvider

                    config_dict = provider_config.model_dump()
                    config_dict["auth"]["selected_profile"] = profile_name
                    provider = JenkinsProvider(name=provider_name, config=config_dict)
                elif provider_kind == "kubernetes":
                    from secretzero.providers.kubernetes import KubernetesProvider

                    config_dict = provider_config.model_dump()
                    config_dict["auth"]["selected_profile"] = profile_name
                    provider = KubernetesProvider(name=provider_name, config=config_dict)
            except ImportError:
                console.print("[yellow]SDK not installed[/yellow]")
                continue
            except Exception as e:
                console.print(f"[yellow]Error: {str(e)[:50]}[/yellow]")
                continue

            # Test connectivity
            if provider:
                try:
                    success, message = provider.test_connection()
                    if success:
                        console.print(f"[green]✓ {message}[/green]")
                    else:
                        console.print(f"[red]✗ {message}[/red]")
                except Exception as e:
                    console.print(f"[red]✗ Testing failed: {str(e)[:50]}[/red]")
            else:
                console.print("[yellow]Could not initialize provider[/yellow]")

        console.print()

    if not has_profiles:
        console.print("[dim]No authentication profiles configured for any providers[/dim]")


@main.command()
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=True),
    default="Secretfile.yml",
    help="Path to Secretfile",
)
@click.option(
    "--include-profiles",
    is_flag=True,
    help="Test each defined authentication profile for providers",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed error information including stack traces",
)
def test(file: str, include_profiles: bool, verbose: bool) -> None:
    """Test provider connectivity and authentication.

    This command validates that all configured providers can be authenticated
    and accessed successfully. Use --include-profiles to also test each
    defined authentication profile for providers that support them.
    Use --verbose to see detailed error information when tests fail.
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
            except Exception as e:
                import traceback

                console.print("[red]✗ Failed to initialize provider[/red]")
                all_passed = False
                if verbose:
                    console.print(f"[dim]Error: {type(e).__name__}: {str(e)}[/dim]")
                    console.print(f"[dim]{traceback.format_exc()}[/dim]")
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
            except Exception as e:
                import traceback

                console.print("[red]✗ Failed to initialize provider[/red]")
                all_passed = False
                if verbose:
                    console.print(f"[dim]Error: {type(e).__name__}: {str(e)}[/dim]")
                    console.print(f"[dim]{traceback.format_exc()}[/dim]")
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
            except Exception as e:
                import traceback

                console.print("[red]✗ Failed to initialize provider[/red]")
                all_passed = False
                if verbose:
                    console.print(f"[dim]Error: {type(e).__name__}: {str(e)}[/dim]")
                    console.print(f"[dim]{traceback.format_exc()}[/dim]")
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
            except Exception as e:
                import traceback

                console.print("[red]✗ Failed to initialize provider[/red]")
                all_passed = False
                if verbose:
                    console.print(f"[dim]Error: {type(e).__name__}: {str(e)}[/dim]")
                    console.print(f"[dim]{traceback.format_exc()}[/dim]")
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
            except Exception as e:
                import traceback

                console.print("[red]✗ Failed to initialize provider[/red]")
                all_passed = False
                if verbose:
                    console.print(f"[dim]Error: {type(e).__name__}: {str(e)}[/dim]")
                    console.print(f"[dim]{traceback.format_exc()}[/dim]")
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
            except Exception as e:
                import traceback

                console.print("[red]✗ Failed to initialize provider[/red]")
                all_passed = False
                if verbose:
                    console.print(f"[dim]Error: {type(e).__name__}: {str(e)}[/dim]")
                    console.print(f"[dim]{traceback.format_exc()}[/dim]")
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
            except Exception as e:
                import traceback

                console.print("[red]✗ Failed to initialize provider[/red]")
                all_passed = False
                if verbose:
                    console.print(f"[dim]Error: {type(e).__name__}: {str(e)}[/dim]")
                    console.print(f"[dim]{traceback.format_exc()}[/dim]")
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
            try:
                success, message = provider.test_connection()
                if success:
                    console.print(f"[green]✓ {message}[/green]")
                else:
                    console.print(f"[red]✗ {message}[/red]")
                    all_passed = False
            except Exception as e:
                console.print("[red]✗ Connection test failed[/red]")
                all_passed = False
                if verbose:
                    console.print(f"[dim]Error type: {type(e).__name__}[/dim]")
                    console.print(f"[dim]Error message: {str(e)}[/dim]")
                    import traceback

                    console.print("[dim]Stack trace:[/dim]")
                    console.print(f"[dim]{traceback.format_exc()}[/dim]")

    if all_passed:
        console.print("\n[green]All provider tests passed![/green]")
    else:
        console.print("\n[yellow]Some provider tests failed. Check the messages above.[/yellow]")

    # Test profiles if requested
    if include_profiles:
        _test_provider_profiles(config)


@main.command()
@click.option(
    "--provider",
    "-p",
    help="Show details for a specific provider type",
)
@click.option(
    "--target",
    "-t",
    help="Show details for a specific target type (requires --provider)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed information",
)
def providers(provider: str | None, target: str | None, verbose: bool) -> None:
    """List supported provider types and authentication methods.

    Shows all available provider types that can be used in your Secretfile
    configuration, along with their authentication methods and configuration options.
    """
    if target and not provider:
        console.print("[red]Error:[/red] --target requires --provider to be specified")
        raise click.Abort()

    if provider:
        # Show details for specific provider
        _show_provider_details(provider, target, verbose)
    else:
        # List all providers
        _list_all_providers(verbose)


def _list_all_providers(verbose: bool) -> None:
    """List all available provider types."""
    console.print("[bold]Available Provider Types:[/bold]\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Provider", style="green")
    table.add_column("Description")
    table.add_column("Auth Methods")

    provider_info = {
        "aws": {
            "description": "Amazon Web Services",
            "auth": "ambient, token, assume_role",
        },
        "azure": {
            "description": "Microsoft Azure",
            "auth": "ambient, token",
        },
        "vault": {
            "description": "HashiCorp Vault",
            "auth": "token, ambient",
        },
        "github": {
            "description": "GitHub",
            "auth": "token",
        },
        "gitlab": {
            "description": "GitLab",
            "auth": "token",
        },
        "jenkins": {
            "description": "Jenkins",
            "auth": "token",
        },
        "kubernetes": {
            "description": "Kubernetes",
            "auth": "ambient, kubeconfig",
        },
        "local": {
            "description": "Local filesystem",
            "auth": "none",
        },
    }

    for prov_type, info in provider_info.items():
        table.add_row(prov_type, info["description"], info["auth"])

    console.print(table)

    if not verbose:
        console.print(
            "\nUse [bold]secretzero providers --provider <type> --verbose[/bold] for detailed configuration options"
        )


def _show_provider_details(provider_name: str, target_name: str | None, verbose: bool) -> None:
    """Show detailed information about a specific provider and optionally a target type."""
    # Target type details indexed by provider
    target_details = {
        "aws": {
            "ssm_parameter": {
                "description": "AWS Systems Manager Parameter Store",
                "config": {
                    "name": "Parameter name/path (required)",
                    "type": "Parameter type: String, SecureString, or StringList (default: SecureString)",
                    "overwrite": "Whether to overwrite existing parameter (default: true)",
                    "description": "Parameter description (optional)",
                    "tier": "Parameter tier: Standard, Advanced, or Intelligent-Tiering (default: Standard)",
                    "region": "AWS region override (optional)",
                    "endpoint_url": "Custom endpoint URL for LocalStack or other AWS-compatible services (optional)",
                },
                "example": """targets:
  - provider: aws
    kind: ssm_parameter
    config:
      name: /prod/database/password
      type: SecureString
      overwrite: true
      description: RDS master password
      tier: Standard""",
            },
            "secrets_manager": {
                "description": "AWS Secrets Manager",
                "config": {
                    "name": "Secret name (required)",
                    "description": "Secret description (optional)",
                    "kms_key_id": "KMS key ID for encryption (optional)",
                    "recovery_period": "Recovery period in days for scheduled deletion (default: 7)",
                    "region": "AWS region override (optional)",
                    "endpoint_url": "Custom endpoint URL for LocalStack or other AWS-compatible services (optional)",
                },
                "example": """targets:
  - provider: aws
    kind: secrets_manager
    config:
      name: prod/database-credentials
      description: RDS master credentials
      kms_key_id: arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012""",
            },
        },
        "azure": {
            "azure_keyvault": {
                "description": "Azure Key Vault",
                "config": {
                    "vault_url": "Key Vault URL (e.g., https://myvault.vault.azure.net)",
                    "secret_name": "Secret name in Key Vault (required)",
                    "tags": "Tags to add to the secret in Key Vault (optional)",
                },
                "example": """targets:
  - provider: azure
    kind: azure_keyvault
    config:
      vault_url: https://prod-vault.vault.azure.net
      secret_name: database-password""",
            },
        },
        "vault": {
            "vault_kv": {
                "description": "HashiCorp Vault KV Secret Engine",
                "config": {
                    "path": "Secret path in KV engine (e.g., secret/data/myapp/config)",
                    "mount_point": "KV mount point (default: secret)",
                    "version": "KV version: 1 or 2 (default: 2)",
                },
                "example": """targets:
  - provider: vault
    kind: vault_kv
    config:
      path: secret/data/prod/database
      mount_point: secret
      version: 2""",
            },
        },
        "github": {
            "github_secret": {
                "description": "GitHub Actions Secret",
                "config": {
                    "repository": "GitHub repository (owner/repo format)",
                    "secret_name": "Secret name (optional, uses secret.name if not provided)",
                },
                "example": """targets:
  - provider: github
    kind: github_secret
    config:
      repository: myorg/myrepo
      secret_name: DATABASE_PASSWORD""",
            },
        },
        "gitlab": {
            "gitlab_variable": {
                "description": "GitLab CI/CD Variable",
                "config": {
                    "project_id": "GitLab project ID or path",
                    "variable_name": "Variable name (optional, uses secret.name if not provided)",
                    "protected": "Whether the variable is protected (default: false)",
                    "masked": "Whether the variable is masked in logs (default: true)",
                },
                "example": """targets:
  - provider: gitlab
    kind: gitlab_variable
    config:
      project_id: mygroup/myproject
      variable_name: DATABASE_PASSWORD
      masked: true""",
            },
        },
        "jenkins": {
            "jenkins_credential": {
                "description": "Jenkins Secret Credential",
                "config": {
                    "credential_id": "Credential ID in Jenkins",
                    "credential_type": "Type: secret_text, username_password, or ssh_key (default: secret_text)",
                    "folder": "Jenkins folder path (optional)",
                },
                "example": """targets:
  - provider: jenkins
    kind: jenkins_credential
    config:
      credential_id: database_password
      credential_type: secret_text""",
            },
        },
        "kubernetes": {
            "kubernetes_secret": {
                "description": "Kubernetes Secret",
                "config": {
                    "namespace": "Kubernetes namespace (default: default)",
                    "name": "Secret name in Kubernetes",
                    "secret_type": "Secret type: Opaque, docker-json, etc. (default: Opaque)",
                },
                "example": """targets:
  - provider: kubernetes
    kind: kubernetes_secret
    config:
      namespace: production
      name: database-credentials
      secret_type: Opaque""",
            },
        },
        "local": {
            "file": {
                "description": "Local File",
                "config": {
                    "path": "File path to store secret",
                    "format": "File format: dotenv, json, yaml, or toml (default: dotenv)",
                    "merge": "Whether to merge with existing file content (default: true)",
                    "mode": "File permissions as octal (default: 0600)",
                },
                "example": """targets:
  - provider: local
    kind: file
    config:
      path: ./secrets.env
      format: dotenv
      mode: '0600'""",
            },
        },
    }

    if target_name:
        # Show details for specific target type
        if provider_name in target_details and target_name in target_details[provider_name]:
            target_info = target_details[provider_name][target_name]
            console.print(f"[bold]Target Type: {target_name}[/bold]\n")
            console.print(f"[cyan]Provider:[/cyan] {provider_name}")
            console.print(f"[cyan]Description:[/cyan] {target_info['description']}\n")

            console.print("[cyan]Configuration Options:[/cyan]")
            for option, desc in target_info["config"].items():
                console.print(f"  • {option}: {desc}")

            console.print("\n[cyan]Example:[/cyan]")
            console.print(f"[dim]{target_info['example']}[/dim]")
        else:
            console.print(
                f"[red]Unknown target type:[/red] {target_name} for provider {provider_name}"
            )
            console.print(
                f"\nRun [bold]secretzero providers --provider {provider_name}[/bold] to see available targets"
            )
        return  # Exit early when showing target details

    # Show provider details (when no target_name specified)
    console.print(f"[bold]Provider: {provider_name}[/bold]\n")

    provider_details = {
        "aws": {
            "description": "Amazon Web Services",
            "auth_methods": {
                "ambient": "Use AWS SDK default credential chain (environment, instance profile, etc.)",
                "token": "Use static AWS access key and secret key",
                "assume_role": "Assume an IAM role for additional permissions",
            },
            "config": {
                "region": "AWS region (default: us-east-1)",
                "profile": "AWS profile name from ~/.aws/config",
            },
            "example": """providers:
  aws:
    kind: aws
    auth:
      kind: ambient
      config:
        region: us-east-1
    fallback_generator: static
    profiles:
      default:
        kind: ambient
      admin:
        kind: assume_role
        config:
          role_arn: arn:aws:iam::123456789012:role/SecretAdmin""",
        },
        "azure": {
            "description": "Microsoft Azure",
            "auth_methods": {
                "ambient": "Use Azure SDK default credential chain",
                "token": "Use static Azure credentials",
            },
            "config": {
                "tenant_id": "Azure tenant ID",
                "subscription_id": "Azure subscription ID",
            },
            "example": """providers:
  azure:
    kind: azure
    auth:
      kind: ambient
      config:
        tenant_id: ${AZURE_TENANT_ID}
        subscription_id: ${AZURE_SUBSCRIPTION_ID}""",
        },
        "vault": {
            "description": "HashiCorp Vault",
            "auth_methods": {
                "token": "Use Vault token authentication",
                "ambient": "Use Vault ambient authentication (agent)",
            },
            "config": {
                "address": "Vault server address (e.g., https://vault.example.com)",
                "namespace": "Vault namespace (Enterprise)",
            },
            "example": """providers:
  vault:
    kind: vault
    auth:
      kind: token
      config:
        address: https://vault.example.com:8200
        token: ${VAULT_TOKEN}""",
        },
        "github": {
            "description": "GitHub",
            "auth_methods": {
                "token": "Use GitHub personal access token",
            },
            "config": {
                "owner": "GitHub organization or username",
                "repo": "Repository name",
            },
            "example": """providers:
  github:
    kind: github
    auth:
      kind: token
      config:
        token: ${GITHUB_TOKEN}""",
        },
        "gitlab": {
            "description": "GitLab",
            "auth_methods": {
                "token": "Use GitLab personal access token",
            },
            "config": {
                "url": "GitLab instance URL (default: https://gitlab.com)",
                "project_id": "GitLab project ID or path",
            },
            "example": """providers:
  gitlab:
    kind: gitlab
    auth:
      kind: token
      config:
        url: https://gitlab.example.com
        token: ${GITLAB_TOKEN}""",
        },
        "jenkins": {
            "description": "Jenkins",
            "auth_methods": {
                "token": "Use Jenkins API token",
            },
            "config": {
                "url": "Jenkins server URL",
                "username": "Jenkins username",
            },
            "example": """providers:
  jenkins:
    kind: jenkins
    auth:
      kind: token
      config:
        url: https://jenkins.example.com
        username: admin
        token: ${JENKINS_TOKEN}""",
        },
        "kubernetes": {
            "description": "Kubernetes",
            "auth_methods": {
                "ambient": "Use in-cluster service account",
                "kubeconfig": "Use local kubeconfig file",
            },
            "config": {
                "context": "Kubeconfig context",
                "namespace": "Default namespace",
            },
            "example": """providers:
  kubernetes:
    kind: kubernetes
    auth:
      kind: ambient
      config:
        namespace: default""",
        },
        "local": {
            "description": "Local filesystem",
            "auth_methods": {
                "none": "No authentication required",
            },
            "config": {
                "base_path": "Base directory for files (default: .)",
            },
            "example": """providers:
  local:
    kind: local
    config: {}""",
        },
    }

    if provider_name in provider_details:
        details = provider_details[provider_name]
        console.print(f"[cyan]Description:[/cyan] {details['description']}\n")

        console.print("[cyan]Authentication Methods:[/cyan]")
        for auth_method, description in details["auth_methods"].items():
            console.print(f"  • [green]{auth_method}[/green]: {description}")

        console.print("\n[cyan]Configuration Options:[/cyan]")
        for option, desc in details["config"].items():
            console.print(f"  • {option}: {desc}")

        console.print("\n[cyan]Example:[/cyan]")
        console.print(f"[dim]{details['example']}[/dim]")

        if verbose:
            console.print("\n[cyan]Target Types for this Provider:[/cyan]")

            # Map providers to target types
            target_map = {
                "aws": ["ssm_parameter", "secrets_manager"],
                "azure": ["azure_keyvault"],
                "vault": ["vault_kv"],
                "github": ["github_secret"],
                "gitlab": ["gitlab_variable"],
                "jenkins": ["jenkins_credential"],
                "kubernetes": ["kubernetes_secret"],
                "local": ["file"],
            }

            if provider_name in target_map:
                for target_type in target_map[provider_name]:
                    console.print(
                        f"  • [green]{target_type}[/green] - "
                        f"[dim]use [bold]secretzero providers --provider {provider_name} --target {target_type}[/bold] for details[/dim]"
                    )
    else:
        console.print(f"[red]Unknown provider:[/red] {provider_name}")
        console.print("\nRun 'secretzero providers' to see available providers")


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
@click.option(
    "--show-input",
    is_flag=True,
    help="Show secret input as plain text when prompting (default: masked)",
)
@click.option(
    "--no-prompt",
    is_flag=True,
    help="Disable interactive prompts (fail if values are missing) - useful for CI/CD",
)
@click.option(
    "--secret",
    "-s",
    "secrets",
    multiple=True,
    help="Sync only specific secrets by name (can be specified multiple times)",
)
def sync(
    file: str,
    lockfile: str,
    dry_run: bool,
    show_input: bool,
    no_prompt: bool,
    secrets: tuple[str, ...],
) -> None:
    """Generate and synchronize secrets to targets.

    This command generates secret values according to your Secretfile
    configuration and stores them in the specified targets (local files,
    cloud providers, etc.).

    By default, syncs all secrets. Use --secret to sync specific secrets only.

    Examples:

        # Sync all secrets
        secretzero sync

        # Sync only specific secrets
        secretzero sync --secret db_password --secret api_key

        # Short form
        secretzero sync -s db_password -s api_key
    """
    file_path = Path(file)

    # Generate default lockfile name from secretfile if not explicitly provided
    if lockfile == ".gitsecrets.lock":
        # Only use default if Secretfile.yml; otherwise derive from secretfile name
        if file != "Secretfile.yml":
            # Replace .yml with .lock
            lockfile_name = file_path.stem + ".lock"
            lockfile = lockfile_name

    lockfile_path = Path(lockfile)
    loader = ConfigLoader()

    # Load configuration
    try:
        config = loader.load_file(file_path)
    except Exception as e:
        console.print(f"[red]Error loading Secretfile:[/red] {e}")
        raise click.Abort()

    # Read secretfile content for change detection
    secretfile_content = file_path.read_text()

    # Load lockfile
    lock = Lockfile.load(lockfile_path)

    # Create sync engine and run with secretfile tracking
    engine = SyncEngine(
        config,
        lock,
        secretfile_path=file_path,
        secretfile_content=secretfile_content,
        hide_input=not show_input,
        prompt_on_empty=not no_prompt,
    )

    if dry_run:
        console.print("[yellow]DRY RUN:[/yellow] No changes will be made\n")

    # Prepare secret name filter
    secret_names = list(secrets) if secrets else None
    if secret_names:
        console.print(
            f"[bold]Synchronizing {len(secret_names)} secret(s):[/bold] {', '.join(secret_names)}\n"
        )
    else:
        console.print("[bold]Synchronizing secrets...[/bold]\n")

    try:
        results = engine.sync(dry_run=dry_run, secret_names=secret_names)

        # Display summary with improved visual formatting
        success_count = results["secrets_stored"]
        failed_count = len([d for d in results["details"] if d.get("errors")])
        skipped_count = results["secrets_skipped"]

        console.print("\n[bold]Summary[/bold]")
        console.print(f"[green]✓ Success:[/green] {success_count} secret(s) stored")
        if failed_count > 0:
            console.print(f"[red]✗ Failed:[/red] {failed_count} secret(s) had errors")
        if skipped_count > 0:
            console.print(f"[yellow]⊙ Skipped:[/yellow] {skipped_count} secret(s) skipped")

        # Show if secretfile changed
        if results.get("secretfile_changed"):
            console.print("\n[yellow]⚠ Secretfile has changed since last sync[/yellow]")

        # Create detailed results table
        if results["details"]:
            console.print("\n[bold]Secrets[/bold]")

            secrets_table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
            secrets_table.add_column("Status", justify="center", width=8)
            secrets_table.add_column("Secret Name", style="bold")
            secrets_table.add_column("Type", style="dim")
            secrets_table.add_column("Result", justify="left")

            for detail in results["details"]:
                secret_name = detail["name"]
                secret_kind = detail["kind"]

                # Determine overall status
                has_errors = bool(detail.get("errors"))
                is_skipped = detail.get("skipped")
                is_stored = detail.get("stored")

                if has_errors:
                    status_icon = "[red]✗[/red]"
                    result_text = "[red]Failed[/red]"
                elif is_skipped:
                    status_icon = "[yellow]⊙[/yellow]"
                    reason = detail.get("reason", "unknown")
                    result_text = f"[yellow]Skipped[/yellow] [dim]({reason})[/dim]"
                elif is_stored:
                    status_icon = "[green]✓[/green]"
                    if dry_run:
                        result_text = "[green]Would store[/green]"
                    else:
                        result_text = "[green]Stored[/green]"
                else:
                    status_icon = "[dim]•[/dim]"
                    result_text = "[dim]Processed[/dim]"

                secrets_table.add_row(status_icon, secret_name, secret_kind, result_text)

            console.print(secrets_table)

        # Show target details for each secret
        secrets_with_targets = [d for d in results["details"] if d.get("targets")]
        if secrets_with_targets:
            console.print("\n[bold]Target Details[/bold]")

            for detail in secrets_with_targets:
                secret_name = detail["name"]
                has_errors = bool(detail.get("errors"))

                # Create sub-table for targets
                targets_table = Table(
                    show_header=True,
                    header_style="bold cyan",
                    box=box.SIMPLE,
                    title=f"[bold]{secret_name}[/bold]",
                    title_style="bold blue",
                )
                targets_table.add_column("Status", justify="center", width=8)
                targets_table.add_column("Provider", style="cyan")
                targets_table.add_column("Target Type", style="cyan")
                targets_table.add_column("Result")

                for target in detail["targets"]:
                    target_status = target.get("status", "unknown")
                    provider = target["provider"]
                    kind = target["kind"]
                    message = target.get("message", "")

                    # Determine target status icon and text
                    if target_status in ["success", "stored", "would_store"]:
                        status_icon = "[green]✓[/green]"
                        status_text = "[green]Stored[/green]"
                        if dry_run:
                            status_text = "[green]Would store[/green]"
                    elif target_status in ["failed", "error"]:
                        status_icon = "[red]✗[/red]"
                        status_text = "[red]Failed[/red]"
                        if message:
                            status_text += f" [dim]- {message}[/dim]"
                    elif target_status == "skipped":
                        status_icon = "[yellow]⊙[/yellow]"
                        status_text = "[yellow]Skipped[/yellow]"
                    elif target_status == "unsupported":
                        status_icon = "[yellow]⚠[/yellow]"
                        status_text = "[yellow]Unsupported[/yellow]"
                        if message:
                            status_text += f" [dim]- {message}[/dim]"
                    else:
                        status_icon = "[dim]•[/dim]"
                        status_text = f"[dim]{target_status}[/dim]"

                    targets_table.add_row(status_icon, provider, kind, status_text)

                console.print(targets_table)
                console.print()  # Add spacing between secret target tables

        # Show errors prominently
        if results["errors"]:
            console.print("\n[bold red]Errors[/bold red]")
            error_table = Table(show_header=False, box=box.ROUNDED, border_style="red")
            error_table.add_column("Icon", justify="center", width=4)
            error_table.add_column("Error Message", style="red")

            for error in results["errors"]:
                error_table.add_row("✗", error)

            console.print(error_table)

        # Save lockfile if not dry run and secrets were stored
        if not dry_run:
            if results["secrets_stored"] > 0:
                lock.save(lockfile_path)
                console.print(f"\n[green]✓[/green] Lockfile saved: {lockfile_path}")
            else:
                # Check if lockfile was modified (secretfile tracking)
                if results.get("secretfile_changed") is not None:
                    # Lockfile exists and secretfile was tracked
                    lock.save(lockfile_path)
                    console.print(
                        f"\n[dim]Lockfile updated (secretfile tracking only): {lockfile_path}[/dim]"
                    )
                else:
                    console.print(
                        "\n[yellow]⚠[/yellow]  Lockfile not saved (no secrets stored successfully)"
                    )

        if dry_run:
            console.print(
                "\n[yellow]This was a dry run. Use 'secretzero sync' to apply changes.[/yellow]"
            )

    except RuntimeError as e:
        # RuntimeError from validation or sync has detailed error message
        console.print(f"\n[red]{e}[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"\n[red]Error during sync:[/red] {e}")
        raise click.Abort()


def _show_all_secrets(engine: SyncEngine, config) -> None:
    """Display a beautiful list of all secrets in the manifest.

    Args:
        engine: SyncEngine instance
        config: Loaded Secretfile configuration
    """
    if not config.secrets:
        console.print("[dim]No secrets configured in Secretfile[/dim]")
        return

    console.print("[bold]Secrets in Secretfile[/bold]\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Name", style="green")
    table.add_column("Kind")
    table.add_column("Generated", justify="center")
    table.add_column("One-time", justify="center")
    table.add_column("Rotation", style="yellow")
    table.add_column("Targets")

    for secret in config.secrets:
        info = engine.get_secret_info(secret.name)

        # Generate status
        generated = "[green]✓[/green]" if info and info["exists_in_lockfile"] else "[dim]—[/dim]"

        # One-time status
        one_time = "[yellow]Yes[/yellow]" if secret.one_time else "[dim]No[/dim]"

        # Rotation period
        rotation = secret.rotation_period if secret.rotation_period else "[dim]—[/dim]"

        # Targets summary
        targets_summary = ""
        if info and info["targets"]:
            targets_summary = ", ".join(f"{t['provider']}/{t['kind']}" for t in info["targets"])
        else:
            targets_summary = "[dim]No targets[/dim]"

        table.add_row(secret.name, secret.kind, generated, one_time, rotation, targets_summary)

    console.print(table)
    console.print(f"\n[dim]Total: {len(config.secrets)} secret(s)[/dim]")
    console.print("[dim]Use 'secretzero show <secret-name>' for detailed information[/dim]")


def _show_all_secrets_detailed(engine: SyncEngine, config) -> None:
    """Display detailed information for all secrets in the manifest.

    Args:
        engine: SyncEngine instance
        config: Loaded Secretfile configuration
    """
    if not config.secrets:
        console.print("[dim]No secrets configured in Secretfile[/dim]")
        return

    console.print("[bold]Detailed Secrets in Secretfile[/bold]\n")

    for i, secret in enumerate(config.secrets):
        info = engine.get_secret_info(secret.name)
        _show_secret_detailed(secret, info, config)

        # Add separator between secrets
        if i < len(config.secrets) - 1:
            console.print("\n" + "─" * 80 + "\n")

    console.print(f"\n[dim]Total: {len(config.secrets)} secret(s)[/dim]")


def _show_secret_brief(info: dict) -> None:
    """Display brief information about a secret.

    Args:
        info: Secret information dictionary from SyncEngine
    """
    console.print(f"[bold]Secret: {info['name']}[/bold]\n")

    table = Table(show_header=False, box=None)
    table.add_column("Property", style="cyan")
    table.add_column("Value")

    table.add_row("Kind", info["kind"])
    table.add_row("One-time", "Yes" if info["one_time"] else "No")

    if info.get("rotation_period"):
        table.add_row("Rotation Period", info["rotation_period"])

    table.add_row("Generated", "Yes" if info["exists_in_lockfile"] else "No")

    if info["exists_in_lockfile"]:
        table.add_row("Created", info["created_at"])
        table.add_row("Updated", info["updated_at"])
        table.add_row("Hash", info["hash"][:16] + "...")

    console.print(table)

    # Show targets
    if info["targets"]:
        console.print("\n[bold]Targets:[/bold]")
        for target in info["targets"]:
            console.print(f"  • {target['provider']} / {target['kind']}")


def _show_secret_detailed(secret, info: dict, config) -> None:
    """Display detailed information about a secret with full configuration.

    Args:
        secret: Secret model instance
        info: Secret information dictionary from SyncEngine
        config: Loaded Secretfile configuration
    """
    console.print(f"[bold cyan]Secret: {secret.name}[/bold cyan]\n")

    # Basic properties table
    console.print("[bold]Properties[/bold]")
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Property", style="cyan")
    table.add_column("Value")

    table.add_row("Kind", secret.kind)
    table.add_row("One-time", "Yes" if secret.one_time else "No")

    if secret.rotation_period:
        table.add_row("Rotation Period", secret.rotation_period)

    if info:
        table.add_row("Generated", "Yes" if info.get("exists_in_lockfile") else "No")
        if info.get("exists_in_lockfile"):
            table.add_row("Created", info.get("created_at", "N/A"))
            table.add_row("Updated", info.get("updated_at", "N/A"))
            hash_val = info.get("hash", "")
            if hash_val:
                table.add_row("Hash", hash_val[:16] + "...")

    console.print(table)

    # Variables
    if secret.vars:
        console.print("\n[bold]Variables[/bold]")
        vars_table = Table(show_header=True, header_style="bold cyan", box=None)
        vars_table.add_column("Key", style="green")
        vars_table.add_column("Value")
        for key, value in secret.vars.items():
            vars_table.add_row(key, str(value))
        console.print(vars_table)

    # Configuration
    if secret.config:
        console.print("\n[bold]Configuration[/bold]")
        _print_nested_dict(secret.config, indent=0)

    # Check if it's a template secret
    if secret.kind.startswith("templates."):
        template_name = secret.kind.split(".", 1)[1]
        if template_name in config.templates:
            template = config.templates[template_name]
            console.print(f"\n[bold]Template: {template_name}[/bold]")
            if template.description:
                console.print(f"[dim]{template.description}[/dim]")

            # Show template fields
            if template.fields:
                console.print("\n[bold]Template Fields[/bold]")
                for field_name, field in template.fields.items():
                    console.print(f"\n  [yellow]{field_name}[/yellow]")
                    console.print(f"  [dim]{field.description}[/dim]")

                    # Field generator
                    if field.generator:
                        generator_kind = (
                            field.generator.kind.value
                            if hasattr(field.generator.kind, "value")
                            else str(field.generator.kind)
                        )
                        console.print(f"  [cyan]Generator:[/cyan] {generator_kind}")
                        if field.generator.config:
                            for key, value in field.generator.config.items():
                                console.print(f"    • {key}: {value}")

                    # Field targets
                    if field.targets:
                        console.print("  [cyan]Targets:[/cyan]")
                        for target in field.targets:
                            console.print(f"    • {target.provider}/{target.kind}")
                            if target.config:
                                for key, value in target.config.items():
                                    console.print(f"      - {key}: {value}")

    # Targets
    if secret.targets:
        console.print("\n[bold]Targets[/bold]")
        for target in secret.targets:
            console.print(f"\n  [yellow]{target.provider}/{target.kind}[/yellow]")
            if target.config:
                for key, value in target.config.items():
                    console.print(f"    • {key}: {value}")


def _print_nested_dict(d: dict, indent: int = 0, max_depth: int = 3) -> None:
    """Pretty print a nested dictionary with indentation.

    Args:
        d: Dictionary to print
        indent: Current indentation level
        max_depth: Maximum depth to print
    """
    if indent >= max_depth or not d:
        return

    for key, value in d.items():
        if isinstance(value, dict):
            console.print(f"{'  ' * indent}[green]{key}:[/green]")
            _print_nested_dict(value, indent + 1, max_depth)
        elif isinstance(value, (list, tuple)):
            console.print(f"{'  ' * indent}[green]{key}:[/green]")
            for item in value:
                if isinstance(item, dict):
                    _print_nested_dict({f"[{len(value)}]": item}, indent + 1, max_depth)
                else:
                    console.print(f"{'  ' * (indent + 1)}• {item}")
        else:
            console.print(f"{'  ' * indent}[green]{key}:[/green] {value}")


@main.command()
@click.argument("secret_name", required=False)
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
    "--detailed",
    "-d",
    is_flag=True,
    help="Show detailed configuration and sub-fields",
)
def show(secret_name: str | None, file: str, lockfile: str, detailed: bool) -> None:
    """Show information about secrets.

    If no secret name is provided, displays a list of all secrets in the
    manifest file. If a secret name is provided, displays detailed metadata
    about that specific secret, including its configuration, generation status,
    and target storage locations.

    Use --detailed to show complete configuration and sub-fields.
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

    # If no secret name, show all secrets (optionally detailed)
    if not secret_name:
        if detailed:
            _show_all_secrets_detailed(engine, config)
        else:
            _show_all_secrets(engine, config)
        return

    # Find the secret in config
    secret = None
    for s in config.secrets:
        if s.name == secret_name:
            secret = s
            break

    if not secret:
        console.print(f"[red]Error:[/red] Secret '{secret_name}' not found in Secretfile")
        raise click.Abort()

    # Get secret info
    info = engine.get_secret_info(secret_name)

    # Display information
    if detailed:
        _show_secret_detailed(secret, info, config)
    else:
        _show_secret_brief(info)


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
@click.option(
    "--show-input",
    is_flag=True,
    help="Show secret input as plain text when prompting (default: masked)",
)
@click.argument("secret_name", required=False)
def rotate(
    file: str, lockfile: str, force: bool, dry_run: bool, show_input: bool, secret_name: str | None
) -> None:
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

    engine = SyncEngine(config, lock, hide_input=not show_input)

    # Filter secrets for rotation
    original_secrets = config.secrets
    config.secrets = secrets_to_rotate

    try:
        results = engine.sync(dry_run=False, force_rotation=True)

        console.print(f"[green]✓[/green] Rotated {results['secrets_generated']} secrets")

        if results["errors"]:
            console.print("\n[red]Errors:[/red]")
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
    console.print("[bold]Summary:[/bold]")
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
def drift(file: str, lockfile: str, secret_name: str | None) -> None:
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
        console.print(
            "\n[yellow]Drift detected. Run 'secretzero sync --force' to remediate.[/yellow]"
        )
    else:
        console.print("\n[green]No drift detected.[/green]")


@main.command()
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=True),
    default="Secretfile.yml",
    help="Path to Secretfile",
)
@click.option(
    "--type",
    "-t",
    "graph_type",
    type=click.Choice(["flow", "detailed", "architecture"]),
    default="flow",
    help="Type of graph to generate",
)
@click.option(
    "--format",
    "-o",
    "output_format",
    type=click.Choice(["mermaid", "terminal"]),
    default="mermaid",
    help="Output format",
)
@click.option(
    "--output",
    type=click.Path(),
    default=None,
    help="Output file path (prints to console if not specified)",
)
def graph(file: str, graph_type: str, output_format: str, output: str | None) -> None:
    """Generate visual graph of Secretfile relationships.

    This command creates visual representations of your secret flows,
    showing generators, secrets, and their target destinations.

    Graph Types:

    - flow: Simple flowchart showing generator → secret → target relationships
    - detailed: Detailed view with configuration parameters
    - architecture: High-level system architecture view

    Output Formats:

    - mermaid: Mermaid diagram markdown (can be rendered in GitHub, docs, etc.)
    - terminal: Text-based summary for console viewing

    Examples:

        # Generate simple flow diagram
        secretzero graph

        # Generate detailed diagram with configs
        secretzero graph --type detailed

        # Generate architecture overview
        secretzero graph --type architecture

        # Save to file
        secretzero graph --output secretflow.md

        # Terminal-friendly summary
        secretzero graph --format terminal
    """
    file_path = Path(file)

    if not file_path.exists():
        console.print(f"[red]Error:[/red] Secretfile not found: {file_path}")
        raise click.Abort()

    try:
        # Show appropriate message based on output format
        if output_format == "terminal":
            console.print("[bold]Generating configuration summary...[/bold]\n")
        else:
            console.print(f"[bold]Generating {graph_type} graph...[/bold]\n")

        # Generate the graph
        graph_output = generate_graph(
            secretfile_path=file_path,
            graph_type=graph_type,  # type: ignore
            output_format=output_format,  # type: ignore
        )

        # Output to file or console
        if output:
            output_path = Path(output)
            output_path.write_text(graph_output)
            console.print(f"[green]✓[/green] Graph saved to: {output_path}")
        else:
            # Print to console
            if output_format == "mermaid":
                console.print("[dim]Copy the following Mermaid diagram to render it:[/dim]\n")
            console.print(graph_output)

        # Show format-specific tips
        if output_format == "mermaid":
            console.print(
                "\n[dim]Tip: Mermaid diagrams can be rendered in GitHub README files, "
                "GitLab docs, or at https://mermaid.live[/dim]"
            )

    except Exception as e:
        console.print(f"[red]Error generating graph:[/red] {e}")
        raise click.Abort()


# Register provider CLI group
main.add_command(providers_group)


if __name__ == "__main__":
    main()
