"""CLI interface for SecretZero."""

import json
import sys
from pathlib import Path
from typing import Any

import click
import yaml
from rich import box
from rich.console import Console
from rich.table import Table

from secretzero import __version__
from secretzero.api.audit import AuditLogger
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

# Standardized exit codes for automation / AI agent consumption
EXIT_SUCCESS = 0
EXIT_VALIDATION_ERROR = 1
EXIT_MISSING_DEPENDENCY = 2
EXIT_AUTH_FAILURE = 3
EXIT_DRIFT_DETECTED = 4
EXIT_CONFIG_ERROR = 5
EXIT_UNKNOWN_ERROR = 127


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
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
@click.option(
    "--var-file",
    "-v",
    "var_files",
    type=click.Path(exists=True),
    multiple=True,
    help="Path to .szvar variable file(s) to validate with (can be specified multiple times)",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (text or json)",
)
def validate(file: str, var_files: tuple[str, ...], output_format: str) -> None:
    """Validate Secretfile configuration.

    This command checks the syntax and structure of your Secretfile.yml,
    ensuring all required fields are present and properly formatted.

    Variable files (.szvar) can be specified for validation to ensure the
    final merged configuration is valid.
    """
    file_path = Path(file)
    var_file_paths = [Path(vf) for vf in var_files] if var_files else None
    loader = ConfigLoader()

    is_valid, message = loader.validate_file(file_path, var_files=var_file_paths)

    if output_format == "json":
        result: dict = {"valid": is_valid, "message": message, "file": str(file_path)}
        if is_valid:
            try:
                config = loader.load_file(file_path, var_files=var_file_paths)
                result["config"] = {
                    "version": config.version,
                    "variables_count": len(config.variables),
                    "providers_count": len(config.providers),
                    "secrets_count": len(config.secrets),
                    "templates_count": len(config.templates),
                }
            except (ValueError, KeyError, AttributeError):
                pass
        click.echo(json.dumps(result, indent=2))
        if not is_valid:
            sys.exit(EXIT_VALIDATION_ERROR)
        return

    console.print(f"Validating: {file_path}")
    if var_file_paths:
        console.print(f"With variable file(s): {', '.join(str(vf) for vf in var_file_paths)}")

    if is_valid:
        console.print(f"[green]✓[/green] {message}")

        # Show summary of configuration
        config = loader.load_file(file_path, var_files=var_file_paths)
        console.print("\n[bold]Configuration Summary:[/bold]")
        console.print(f"  Version: {config.version}")
        console.print(f"  Variables: {len(config.variables)}")
        console.print(f"  Providers: {len(config.providers)}")
        console.print(f"  Secrets: {len(config.secrets)}")
        console.print(f"  Templates: {len(config.templates)}")
    else:
        console.print(f"[red]✗[/red] {message}")
        sys.exit(EXIT_VALIDATION_ERROR)


@main.command()
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=True),
    default="Secretfile.yml",
    help="Path to Secretfile",
)
@click.option(
    "--var-file",
    "-v",
    "var_files",
    type=click.Path(exists=True),
    multiple=True,
    help="Path to .szvar variable file(s) to merge (can be specified multiple times)",
)
@click.option(
    "--format",
    type=click.Choice(["yaml", "json"]),
    default="yaml",
    help="Output format (yaml or json)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Write output to file instead of stdout",
)
def render(file: str, var_files: tuple[str, ...], format: str, output: str | None) -> None:
    """Render the final Secretfile configuration with variables interpolated.

    This command displays or saves the complete Secretfile configuration after
    merging variable files and applying variable interpolation. This is useful
    for debugging variable issues or understanding the final configuration.

    Variable files (.szvar) are merged in order with later files taking precedence.

    Examples:

        # Render to stdout
        secretzero render

        # Render with variable file
        secretzero render --var-file dev.szvar

        # Render with multiple variable files
        secretzero render --var-file base.szvar --var-file dev.szvar

        # Render to file in JSON format
        secretzero render --var-file dev.szvar --format json --output rendered.json
    """
    file_path = Path(file)
    var_file_paths = [Path(vf) for vf in var_files] if var_files else None
    loader = ConfigLoader()

    # Load configuration with optional variable files
    try:
        config = loader.load_file(file_path, var_files=var_file_paths)
    except Exception as e:
        console.print(f"[red]Error loading Secretfile:[/red] {e}")
        raise click.Abort()

    # Convert to dictionary for output
    config_dict = config.model_dump(mode="python", exclude_none=True)

    # Format output
    if format == "json":
        output_content = json.dumps(config_dict, indent=2)
    else:  # yaml
        output_content = yaml.dump(config_dict, default_flow_style=False, sort_keys=False)

    # Write to file or stdout
    if output:
        output_path = Path(output)
        output_path.write_text(output_content)
        console.print(f"[green]✓[/green] Rendered configuration written to: {output}")
    else:
        console.print(output_content)


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
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (text or json)",
)
def status(file: str, lockfile: str, verbose: bool, output_format: str) -> None:
    """Show synchronization status of secrets and targets.

    This command displays which secrets have been generated and synced to their
    configured targets, along with timestamps and rotation information.
    """
    file_path = Path(file)
    lockfile_path = Path(lockfile)
    secretfile_content = file_path.read_text()

    loader = ConfigLoader()

    try:
        config = loader.load_file(file_path)
    except Exception as e:
        if output_format == "json":
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error loading Secretfile:[/red] {e}")
        sys.exit(EXIT_CONFIG_ERROR)

    # Load lockfile
    lock = Lockfile.load(lockfile_path)
    tracked_secretfile = lock.get_secretfile_info()
    current_secretfile_hash = Lockfile._hash_value(secretfile_content)
    secretfile_changed = None
    if tracked_secretfile:
        tracked_hash = tracked_secretfile.get("hash")
        tracked_filename = tracked_secretfile.get("filename")
        secretfile_changed = (
            tracked_filename != file_path.name or tracked_hash != current_secretfile_hash
        )

    if output_format == "json":
        secrets_data = []
        for secret in config.secrets:
            entry = lock.get_secret_info(secret.name)
            secret_info: dict = {
                "name": secret.name,
                "kind": secret.kind,
                "one_time": secret.one_time,
                "rotation_period": secret.rotation_period,
                "status": "synced" if entry else "not_synced",
                "targets": [{"provider": t.provider, "kind": t.kind} for t in secret.targets],
            }
            if entry:
                secret_info["created_at"] = str(entry.created_at)
                secret_info["updated_at"] = str(entry.updated_at)
                if entry.last_rotated:
                    secret_info["last_rotated"] = str(entry.last_rotated)
                    secret_info["rotation_count"] = entry.rotation_count
            secrets_data.append(secret_info)
        result = {
            "secrets": secrets_data,
            "total": len(config.secrets),
            "synced": sum(1 for s in secrets_data if s["status"] == "synced"),
            "lockfile": str(lockfile_path),
            "lockfile_exists": lockfile_path.exists(),
            "secretfile": {
                "path": str(file_path),
                "current_hash": current_secretfile_hash,
                "tracked_hash": tracked_secretfile.get("hash") if tracked_secretfile else None,
                "tracked_filename": (
                    tracked_secretfile.get("filename") if tracked_secretfile else None
                ),
                "tracked_synced_at": (
                    tracked_secretfile.get("synced_at") if tracked_secretfile else None
                ),
                "changed": secretfile_changed,
            },
        }
        click.echo(json.dumps(result, indent=2))
        return

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
        _show_secretfile_tracking_status(
            file_path,
            current_secretfile_hash,
            tracked_secretfile,
            secretfile_changed,
            verbose,
        )
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


def _show_secretfile_tracking_status(
    file_path: Path,
    current_hash: str,
    tracked_secretfile: dict[str, str | None],
    secretfile_changed: bool | None,
    verbose: bool,
) -> None:
    """Show Secretfile hash status vs the lockfile."""
    if not tracked_secretfile:
        console.print("[yellow]⚠[/yellow] Secretfile hash not tracked in lockfile")
        console.print("[dim]Run 'secretzero sync' to record the Secretfile hash[/dim]")
        return

    if secretfile_changed:
        console.print("[yellow]⚠[/yellow] Secretfile hash does not match lockfile")
        console.print(
            "[dim]Next: run 'secretzero sync' to refresh the lockfile, or "
            "'secretzero sync --dry-run' to review changes[/dim]"
        )
    else:
        console.print("[green]✓[/green] Secretfile hash matches lockfile")

    if verbose:
        tracked_hash = tracked_secretfile.get("hash")
        tracked_filename = tracked_secretfile.get("filename")
        synced_at = tracked_secretfile.get("synced_at")
        console.print(f"[dim]Secretfile: {file_path.name}[/dim]")
        if tracked_filename and tracked_filename != file_path.name:
            console.print(f"[dim]Tracked Secretfile: {tracked_filename}[/dim]")
        if tracked_hash:
            console.print(f"[dim]Current hash: {current_hash[:16]}...[/dim]")
            console.print(f"[dim]Tracked hash: {tracked_hash[:16]}...[/dim]")
        if synced_at:
            console.print(f"[dim]Last synced: {synced_at}[/dim]")


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

    # Format target display with provider and kind
    target_display = f"[bold]{target.provider}[/bold] → {target.kind}"

    console.print(f"{indent}{target_icon} {target_display}")

    # Show target configuration details
    _show_target_config_details(target, indent, verbose, target_hash)


def _show_target_config_details(
    target, indent: str, verbose: bool, target_hash: str | None
) -> None:
    """Show detailed configuration for a target.

    Args:
        target: Target configuration
        indent: Base indentation for display
        verbose: Whether to show detailed information
        target_hash: Target hash if synced
    """
    config = target.config
    config_indent = indent + "   "

    # Show primary storage location based on target kind
    if target.kind == "file":
        path = config.get("path", "")
        fmt = config.get("format", "raw")
        path_display = f"[cyan]{path}[/cyan]" if path else "[yellow]Not configured[/yellow]"
        console.print(f"{config_indent}📄 Path: {path_display}")
        if fmt and fmt != "raw":
            console.print(f"{config_indent}   Format: {fmt}")
        if config.get("merge"):
            console.print(f"{config_indent}   Merge mode: enabled")
        _show_config_variables(config, config_indent, verbose)
        if verbose:
            _show_all_config_raw(config, config_indent)

    elif target.kind == "ssm_parameter":
        name = config.get("name", "")
        param_type = config.get("type", "String")
        name_display = f"[cyan]{name}[/cyan]" if name else "[yellow]Not configured[/yellow]"
        console.print(f"{config_indent}🔐 Parameter: {name_display}")
        console.print(f"{config_indent}   Type: {param_type}")
        if config.get("overwrite"):
            console.print(f"{config_indent}   Overwrite: enabled")
        if config.get("description"):
            console.print(f"{config_indent}   Description: {config.get('description')}")
        if config.get("tier"):
            console.print(f"{config_indent}   Tier: {config.get('tier')}")
        _show_config_variables(config, config_indent, verbose)
        if verbose:
            _show_all_config_raw(config, config_indent)

    elif target.kind == "secrets_manager":
        name = config.get("name", "")
        name_display = f"[cyan]{name}[/cyan]" if name else "[yellow]Not configured[/yellow]"
        console.print(f"{config_indent}🔐 Secret: {name_display}")
        if config.get("region"):
            console.print(f"{config_indent}   Region: {config.get('region')}")
        if config.get("description"):
            console.print(f"{config_indent}   Description: {config.get('description')}")
        if config.get("kms_key_id"):
            console.print(f"{config_indent}   KMS Key: {config.get('kms_key_id')}")
        _show_config_variables(config, config_indent, verbose)
        if verbose:
            _show_all_config_raw(config, config_indent)

    elif target.kind == "key_vault":
        vault_name = config.get("vault_name", "")
        secret_name = config.get("name", "")
        vault_display = (
            f"[cyan]{vault_name}[/cyan]" if vault_name else "[yellow]Not configured[/yellow]"
        )
        secret_display = (
            f"[cyan]{secret_name}[/cyan]" if secret_name else "[yellow]Not configured[/yellow]"
        )
        console.print(f"{config_indent}🔒 Vault: {vault_display}")
        console.print(f"{config_indent}   Secret Name: {secret_display}")
        _show_config_variables(config, config_indent, verbose)
        if verbose:
            _show_all_config_raw(config, config_indent)

    elif target.kind == "kubernetes":
        namespace = config.get("namespace", "default")
        secret_name = config.get("name", "")
        secret_display = (
            f"[cyan]{secret_name}[/cyan]" if secret_name else "[yellow]Not configured[/yellow]"
        )
        console.print(f"{config_indent}☸️  Namespace: [cyan]{namespace}[/cyan]")
        console.print(f"{config_indent}   Secret Name: {secret_display}")
        if config.get("secret_type"):
            console.print(f"{config_indent}   Type: {config.get('secret_type')}")
        if config.get("create_if_missing"):
            console.print(f"{config_indent}   Auto-create: enabled")
        _show_config_variables(config, config_indent, verbose)
        if verbose:
            _show_all_config_raw(config, config_indent)

    elif target.kind == "vault":
        path = config.get("path", "")
        engine = config.get("engine", "secret")
        path_display = f"[cyan]{path}[/cyan]" if path else "[yellow]Not configured[/yellow]"
        console.print(f"{config_indent}🏦 Engine: [cyan]{engine}[/cyan]")
        console.print(f"{config_indent}   Path: {path_display}")
        if config.get("mount_point"):
            console.print(f"{config_indent}   Mount Point: {config.get('mount_point')}")
        _show_config_variables(config, config_indent, verbose)
        if verbose:
            _show_all_config_raw(config, config_indent)

    elif target.kind == "github_secret":
        repo = config.get("repository", "")
        visibility = config.get("visibility", "private")
        repo_display = f"[cyan]{repo}[/cyan]" if repo else "[yellow]Not configured[/yellow]"
        console.print(f"{config_indent}🐙 Repository: {repo_display}")
        console.print(f"{config_indent}   Visibility: {visibility}")
        if config.get("secret_name"):
            console.print(f"{config_indent}   Secret Name: {config.get('secret_name')}")
        _show_config_variables(config, config_indent, verbose)
        if verbose:
            _show_all_config_raw(config, config_indent)

    elif target.kind == "gitlab_secret":
        project = config.get("project_id", "")
        project_display = (
            f"[cyan]{project}[/cyan]" if project else "[yellow]Not configured[/yellow]"
        )
        console.print(f"{config_indent}🦊 Project: {project_display}")
        if config.get("variable_name"):
            console.print(f"{config_indent}   Variable Name: {config.get('variable_name')}")
        if config.get("protected"):
            console.print(f"{config_indent}   Protected: {config.get('protected')}")
        if config.get("masked"):
            console.print(f"{config_indent}   Masked: {config.get('masked')}")
        _show_config_variables(config, config_indent, verbose)
        if verbose:
            _show_all_config_raw(config, config_indent)

    elif target.kind == "jenkins_credential":
        credential_id = config.get("credential_id", "")
        credential_type = config.get("credential_type", "secret_text")
        cred_display = (
            f"[cyan]{credential_id}[/cyan]" if credential_id else "[yellow]Not configured[/yellow]"
        )
        console.print(f"{config_indent}🔨 Credential ID: {cred_display}")
        console.print(f"{config_indent}   Type: {credential_type}")
        if config.get("folder"):
            console.print(f"{config_indent}   Folder: {config.get('folder')}")
        _show_config_variables(config, config_indent, verbose)
        if verbose:
            _show_all_config_raw(config, config_indent)

    else:
        # Generic target - show all config
        console.print(f"{config_indent}Configuration:")
        for key, value in config.items():
            if isinstance(value, dict):
                console.print(f"{config_indent}   {key}:")
                for k, v in value.items():
                    console.print(f"{config_indent}      {k}: {v}")
            else:
                console.print(f"{config_indent}   {key}: {value}")

    # Show hash if verbose
    if verbose and target_hash:
        console.print(f"{config_indent}[dim]Hash: {target_hash[:16]}...[/dim]")


def _show_config_variables(config: dict, indent: str, verbose: bool) -> None:
    """Show any variable references in configuration.

    Args:
        config: Configuration dictionary
        indent: Indentation for display
        verbose: Whether to show detailed information
    """
    import re

    # Find all variable references like {{var.name}} or ${VAR_NAME}
    variable_pattern = re.compile(r"\{\{var\.(\w+)\}\}|\$\{(\w+)\}")
    found_vars = set()

    for value in config.values():
        if isinstance(value, str):
            matches = variable_pattern.findall(value)
            for match in matches:
                var_name = match[0] or match[1]
                found_vars.add(var_name)

    if found_vars and verbose:
        console.print(f"{indent}Variables used:")
        for var_name in sorted(found_vars):
            console.print(f"{indent}   • [yellow]{var_name}[/yellow]")


def _show_all_config_raw(config: dict, indent: str) -> None:
    """Show all raw configuration values for debugging.

    Args:
        config: Configuration dictionary
        indent: Indentation for display
    """
    console.print(f"{indent}[dim]Raw Configuration:[/dim]")
    for key, value in config.items():
        if value == "":
            value_display = "[yellow]<empty>[/yellow]"
        elif isinstance(value, bool):
            value_display = "[green]true[/green]" if value else "[red]false[/red]"
        elif isinstance(value, dict):
            value_display = "{...}"
        else:
            value_display = str(value)
        console.print(f"{indent}   {key}: {value_display}")


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

    # Check generators
    for name in dir(generators):
        if name.endswith("Generator") and not name.startswith("_"):
            obj = getattr(generators, name)
            if inspect.isclass(obj):
                # Convert class name to snake_case
                converted_name = _class_name_to_snake_case(name, "Generator")
                if converted_name == type_name:
                    target_class = obj
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
    console.print("[dim]Example configuration would go here[/dim]")


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
    "--var-file",
    "-v",
    "var_files",
    type=click.Path(exists=True),
    multiple=True,
    help="Path to .szvar variable file(s) to merge (can be specified multiple times)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be done without making changes",
)
@click.option(
    "--plan",
    is_flag=True,
    help="Show detailed execution plan (created/updated/unchanged/skipped) without applying",
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
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (text or json)",
)
@click.option(
    "--clean",
    is_flag=True,
    help="Remove lockfile entries that have no corresponding secret in the Secretfile",
)
def sync(
    file: str,
    lockfile: str,
    var_files: tuple[str, ...],
    dry_run: bool,
    plan: bool,
    show_input: bool,
    no_prompt: bool,
    secrets: tuple[str, ...],
    output_format: str,
    clean: bool,
) -> None:
    """Generate and synchronize secrets to targets.

    This command generates secret values according to your Secretfile
    configuration and stores them in the specified targets (local files,
    cloud providers, etc.).

    By default, syncs all secrets. Use --secret to sync specific secrets only.

    Variable files (.szvar) can be used to override variables defined in the
    Secretfile. Multiple variable files can be specified, and they are merged
    in order with later files taking precedence.

    Examples:

        # Sync all secrets
        secretzero sync

        # Sync with variable file override
        secretzero sync --var-file dev.szvar

        # Sync with multiple variable files
        secretzero sync --var-file base.szvar --var-file dev.szvar

        # Sync only specific secrets
        secretzero sync --secret db_password --secret api_key

        # Short form
        secretzero sync -s db_password -s api_key

        # Preview plan before applying
        secretzero sync --plan

        # Machine-readable plan output
        secretzero sync --plan --format json
    """
    # --plan implies --dry-run
    if plan:
        dry_run = True
    file_path = Path(file)

    # Generate default lockfile name from secretfile if not explicitly provided
    if lockfile == ".gitsecrets.lock":
        # Only use default if Secretfile.yml; otherwise derive from secretfile name
        if file != "Secretfile.yml":
            # Replace .yml with .lock
            lockfile_name = file_path.stem + ".lock"
            lockfile = lockfile_name

    lockfile_path = Path(lockfile)

    # Convert var_files to Path objects
    var_file_paths = [Path(vf) for vf in var_files] if var_files else None

    loader = ConfigLoader()

    # Load configuration with optional variable files
    try:
        config = loader.load_file(file_path, var_files=var_file_paths)
    except Exception as e:
        if output_format == "json":
            click.echo(json.dumps({"error": str(e), "exit_code": EXIT_CONFIG_ERROR}))
        else:
            console.print(f"[red]Error loading Secretfile:[/red] {e}")
        sys.exit(EXIT_CONFIG_ERROR)

    # Read secretfile content for change detection
    secretfile_content = file_path.read_text()

    # Load lockfile
    lock = Lockfile.load(lockfile_path)

    # Check for orphaned lockfile entries and warn if found
    orphaned_entries = _find_lockfile_orphans(config, lock)
    if orphaned_entries and output_format == "text":
        console.print(
            f"[yellow]⚠ Warning:[/yellow] {len(orphaned_entries)} orphaned entr{'y' if len(orphaned_entries) == 1 else 'ies'} in lockfile (not in Secretfile)"
        )
        if len(orphaned_entries) <= 10:
            for entry in orphaned_entries:
                console.print(f"  - {entry}")
        else:
            for entry in orphaned_entries[:10]:
                console.print(f"  - {entry}")
            console.print(f"  ... and {len(orphaned_entries) - 10} more")
        console.print("  Use [cyan]secretzero sync --clean[/cyan] to remove orphaned entries\n")

    # Clean orphaned lockfile entries if requested
    cleaned_entries = []
    if clean:
        cleaned_entries = _clean_lockfile_orphans(config, lock, dry_run)

    # Create sync engine and run with secretfile tracking
    engine = SyncEngine(
        config,
        lock,
        secretfile_path=file_path,
        secretfile_content=secretfile_content,
        hide_input=not show_input,
        prompt_on_empty=not no_prompt,
    )

    if dry_run and output_format == "text":
        if plan:
            console.print("[cyan]PLAN:[/cyan] Showing execution plan without applying changes\n")
        else:
            console.print("[yellow]DRY RUN:[/yellow] No changes will be made\n")

    # Prepare secret name filter
    secret_names = list(secrets) if secrets else None
    if secret_names and output_format == "text":
        console.print(
            f"[bold]Synchronizing {len(secret_names)} secret(s):[/bold] {', '.join(secret_names)}\n"
        )
    elif output_format == "text" and not plan:
        console.print("[bold]Synchronizing secrets...[/bold]\n")

    try:
        results = engine.sync(dry_run=dry_run, secret_names=secret_names)

        if output_format == "json":
            # Build plan data when --plan flag used
            plan_details = None
            if plan:
                plan_details = []
                for detail in results.get("details", []):
                    is_stored = detail.get("stored")
                    is_skipped = detail.get("skipped")
                    exists = lock.get_secret_info(detail["name"]) is not None
                    if is_stored and not exists:
                        action = "create"
                    elif is_stored:
                        action = "update"
                    elif is_skipped:
                        action = "skip"
                    else:
                        action = "unchanged"
                    plan_details.append(
                        {
                            "name": detail["name"],
                            "kind": detail["kind"],
                            "action": action,
                            "reason": detail.get("reason", ""),
                            "targets": detail.get("targets", []),
                        }
                    )
            json_result: dict = {
                "dry_run": dry_run,
                "plan": plan,
                "secrets_stored": results["secrets_stored"],
                "secrets_skipped": results["secrets_skipped"],
                "errors": results.get("errors", []),
                "details": results.get("details", []),
            }
            if plan_details is not None:
                json_result["plan_details"] = plan_details
            if clean:
                json_result["cleaned"] = cleaned_entries
            click.echo(json.dumps(json_result, indent=2, default=str))
            if results.get("errors"):
                sys.exit(EXIT_UNKNOWN_ERROR)
            return

        # Display summary with improved visual formatting
        success_count = results["secrets_stored"]
        failed_count = len([d for d in results["details"] if d.get("errors")])
        skipped_count = results["secrets_skipped"]

        if plan:
            console.print("\n[bold cyan]Execution Plan[/bold cyan]")
            plan_table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
            plan_table.add_column("Action", justify="center", width=10)
            plan_table.add_column("Secret Name", style="bold")
            plan_table.add_column("Type", style="dim")
            plan_table.add_column("Targets")

            for detail in results["details"]:
                secret_name = detail["name"]
                secret_kind = detail["kind"]
                is_skipped = detail.get("skipped")
                is_stored = detail.get("stored")
                existing = lock.get_secret_info(secret_name)

                if is_skipped:
                    action = "[yellow]skip[/yellow]"
                elif is_stored and not existing:
                    action = "[green]create[/green]"
                elif is_stored:
                    action = "[blue]update[/blue]"
                else:
                    action = "[dim]unchanged[/dim]"

                targets_str = (
                    ", ".join(f"{t['provider']}/{t['kind']}" for t in detail.get("targets", []))
                    or "[dim]none[/dim]"
                )
                plan_table.add_row(action, secret_name, secret_kind, targets_str)

            console.print(plan_table)
            console.print(
                f"\n[dim]Plan summary: {success_count} create/update, {skipped_count} skip[/dim]"
            )
            console.print("\n[cyan]Run 'secretzero sync' to apply this plan.[/cyan]")
            return

        console.print("\n[bold]Summary[/bold]")
        console.print(f"[green]✓ Success:[/green] {success_count} secret(s) stored")
        if failed_count > 0:
            console.print(f"[red]✗ Failed:[/red] {failed_count} secret(s) had errors")
        if skipped_count > 0:
            console.print(f"[yellow]⊙ Skipped:[/yellow] {skipped_count} secret(s) skipped")
        if cleaned_entries:
            console.print(
                f"[cyan]🗑 Cleaned:[/cyan] {len(cleaned_entries)} orphaned lockfile entr{'y' if len(cleaned_entries) == 1 else 'ies'}"
            )

        # Show if secretfile changed
        if results.get("secretfile_changed"):
            console.print("\n[yellow]⚠ Secretfile has changed since last sync[/yellow]")

        # Show cleaned entries
        if cleaned_entries:
            console.print(
                f"\n[bold cyan]Cleaned Lockfile Entries[/bold cyan] ({len(cleaned_entries)} orphaned)"
            )
            cleaned_table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
            cleaned_table.add_column("Status", justify="center", width=8)
            cleaned_table.add_column("Secret Name", style="yellow")
            cleaned_table.add_column("Result", style="dim")

            for entry_name in cleaned_entries:
                status_icon = "[cyan]🗑[/cyan]" if not dry_run else "[dim]•[/dim]"
                result_text = (
                    "[cyan]Removed[/cyan]" if not dry_run else "[dim]Would remove (dry run)[/dim]"
                )
                cleaned_table.add_row(status_icon, entry_name, result_text)

            console.print(cleaned_table)

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
            if results["secrets_stored"] > 0 or cleaned_entries:
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
        if output_format == "json":
            click.echo(json.dumps({"error": str(e), "exit_code": EXIT_VALIDATION_ERROR}))
        else:
            console.print(f"\n[red]{e}[/red]")
        sys.exit(EXIT_VALIDATION_ERROR)
    except Exception as e:
        if output_format == "json":
            click.echo(json.dumps({"error": str(e), "exit_code": EXIT_UNKNOWN_ERROR}))
        else:
            console.print(f"\n[red]Error during sync:[/red] {e}")
        sys.exit(EXIT_UNKNOWN_ERROR)


def _find_lockfile_orphans(config, lock: Lockfile) -> list[str]:
    """Find lockfile entries with no corresponding Secretfile definition.

    Args:
        config: Loaded Secretfile configuration
        lock: Lockfile instance

    Returns:
        List of secret names that are orphaned in the lockfile
    """
    # Collect all valid secret names from Secretfile
    valid_secret_names = set()

    # Add regular secrets
    for secret in config.secrets:
        valid_secret_names.add(secret.name)

        # If it's a template secret, also add all field names
        if secret.kind.startswith("templates."):
            template_name = secret.kind.replace("templates.", "")
            template = config.templates.get(template_name)
            if template and template.fields:
                for field_name in template.fields.keys():
                    field_secret_name = f"{secret.name}.{field_name}"
                    valid_secret_names.add(field_secret_name)

    # Find orphaned entries in lockfile
    orphaned_entries = []
    lockfile_secrets_dict = lock.secrets  # Get the dict directly
    for secret_name in lockfile_secrets_dict:  # Iterate without converting to list first
        if secret_name not in valid_secret_names:
            orphaned_entries.append(secret_name)

    return orphaned_entries


def _clean_lockfile_orphans(config, lock: Lockfile, dry_run: bool) -> list[str]:
    """Find and remove lockfile entries with no corresponding Secretfile definition.

    Args:
        config: Loaded Secretfile configuration
        lock: Lockfile instance
        dry_run: If True, only report what would be removed

    Returns:
        List of secret names that were (or would be) removed
    """
    # Find orphaned entries using the shared detection function
    orphaned_entries = _find_lockfile_orphans(config, lock)

    # Remove orphaned entries (unless dry run)
    if not dry_run and orphaned_entries:
        for secret_name in orphaned_entries:
            lock.remove_secret(secret_name)

    return orphaned_entries


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
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (text or json)",
)
@click.argument("secret_name", required=False)
def rotate(
    file: str,
    lockfile: str,
    force: bool,
    dry_run: bool,
    show_input: bool,
    output_format: str,
    secret_name: str | None,
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
        if output_format == "json":
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error loading Secretfile:[/red] {e}")
        sys.exit(EXIT_CONFIG_ERROR)

    # Load lockfile
    lock = Lockfile.load(lockfile_path)

    if output_format == "text":
        console.print("[bold]Checking secrets for rotation...[/bold]\n")

    # Filter secrets
    secrets_to_check = config.secrets
    if secret_name:
        secrets_to_check = [s for s in config.secrets if s.name == secret_name]
        if not secrets_to_check:
            if output_format == "json":
                click.echo(json.dumps({"error": f"Secret '{secret_name}' not found"}))
            else:
                console.print(f"[red]Error:[/red] Secret '{secret_name}' not found")
            sys.exit(EXIT_VALIDATION_ERROR)

    secrets_to_rotate = []
    rotation_details = []

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
            if output_format == "text":
                console.print(f"  ⚠️  {secret.name}: one_time secret (rotation disabled)")
            rotation_details.append(
                {"name": secret.name, "status": "skipped", "reason": "one_time secret"}
            )
            continue

        # Check if rotation needed
        should_rotate_flag, reason = should_rotate_secret(
            secret.rotation_period,
            entry.last_rotated,
            entry.created_at,
        )

        if should_rotate_flag or force:
            secrets_to_rotate.append(secret)
            rotation_details.append(
                {"name": secret.name, "status": "needs_rotation", "reason": reason}
            )
            if output_format == "text":
                status_icon = "⚠️" if should_rotate_flag else "ℹ️"
                console.print(f"  {status_icon}  {secret.name}: {reason}")
        else:
            rotation_details.append({"name": secret.name, "status": "ok", "reason": reason})
            if output_format == "text":
                console.print(f"  ✓  {secret.name}: {reason}")

    if not secrets_to_rotate:
        if output_format == "json":
            click.echo(
                json.dumps(
                    {
                        "dry_run": dry_run,
                        "secrets_rotated": 0,
                        "details": rotation_details,
                        "errors": [],
                    },
                    indent=2,
                )
            )
        else:
            console.print("\n[green]No secrets need rotation.[/green]")
        return

    if output_format == "text":
        console.print(f"\n[yellow]Found {len(secrets_to_rotate)} secret(s) to rotate[/yellow]")

    if dry_run:
        if output_format == "json":
            click.echo(
                json.dumps(
                    {
                        "dry_run": True,
                        "secrets_rotated": 0,
                        "would_rotate": [s.name for s in secrets_to_rotate],
                        "details": rotation_details,
                        "errors": [],
                    },
                    indent=2,
                )
            )
        else:
            console.print("\n[yellow]DRY RUN:[/yellow] No changes will be made")
            for secret in secrets_to_rotate:
                console.print(f"  Would rotate: {secret.name}")
        return

    # Perform rotation via sync with force flag
    if output_format == "text":
        console.print("\n[bold]Rotating secrets...[/bold]\n")

    engine = SyncEngine(config, lock, hide_input=not show_input)

    # Filter secrets for rotation
    original_secrets = config.secrets
    config.secrets = secrets_to_rotate

    try:
        results = engine.sync(dry_run=False, force_rotation=True)

        if output_format == "json":
            click.echo(
                json.dumps(
                    {
                        "dry_run": False,
                        "secrets_rotated": results.get("secrets_generated", 0),
                        "details": rotation_details,
                        "errors": results.get("errors", []),
                    },
                    indent=2,
                )
            )
        else:
            console.print(f"[green]✓[/green] Rotated {results['secrets_generated']} secrets")

            if results["errors"]:
                console.print("\n[red]Errors:[/red]")
                for error in results["errors"]:
                    console.print(f"  • {error}")

        # Save lockfile regardless of output format
        lock.save(lockfile_path)
        if output_format != "json":
            console.print(f"\n[green]✓[/green] Lockfile updated: {lockfile_path}")

    except Exception as e:
        if output_format == "json":
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"\n[red]Error during rotation:[/red] {e}")
        sys.exit(EXIT_UNKNOWN_ERROR)
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
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (text or json)",
)
def policy(file: str, lockfile: str, fail_on_warning: bool, output_format: str) -> None:
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
        if output_format == "json":
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error loading Secretfile:[/red] {e}")
        sys.exit(EXIT_CONFIG_ERROR)

    # Load lockfile
    lock = None
    if lockfile_path.exists():
        lock = Lockfile.load(lockfile_path)

    # Create policy engine
    engine = PolicyEngine(config)

    # Validate all secrets
    violations = engine.validate_all(lock)

    # Group violations by severity
    errors = [v for v in violations if v.severity == "error"]
    warnings = [v for v in violations if v.severity == "warning"]
    infos = [v for v in violations if v.severity == "info"]

    if output_format == "json":
        click.echo(
            json.dumps(
                {
                    "compliant": len(violations) == 0,
                    "violations": [
                        {
                            "secret": v.secret_name,
                            "severity": v.severity,
                            "message": v.message,
                            "suggestion": v.suggestion,
                        }
                        for v in violations
                    ],
                    "errors_count": len(errors),
                    "warnings_count": len(warnings),
                    "info_count": len(infos),
                },
                indent=2,
            )
        )
        if errors or (fail_on_warning and warnings):
            sys.exit(EXIT_VALIDATION_ERROR)
        return

    console.print("[bold]Checking policy compliance...[/bold]\n")

    if not violations:
        console.print("[green]✓ All secrets comply with policies[/green]")
        return

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
        sys.exit(EXIT_VALIDATION_ERROR)


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
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (text or json)",
)
@click.argument("secret_name", required=False)
def drift(file: str, lockfile: str, output_format: str, secret_name: str | None) -> None:
    """Detect drift between lockfile and actual targets.

    This command checks if secrets have been modified outside of
    SecretZero's control.
    """
    file_path = Path(file)
    lockfile_path = Path(lockfile)

    if not lockfile_path.exists():
        if output_format == "json":
            click.echo(json.dumps({"error": f"Lockfile not found: {lockfile_path}"}))
        else:
            console.print(f"[red]Error:[/red] Lockfile not found: {lockfile_path}")
            console.print("Run 'secretzero sync' first to generate secrets")
        sys.exit(EXIT_CONFIG_ERROR)

    detector = DriftDetector(file_path, lockfile_path)
    results = detector.check_drift(secret_name)

    drift_found = any(r.has_drift for r in results)

    if output_format == "json":
        click.echo(
            json.dumps(
                {
                    "drift_detected": drift_found,
                    "results": [
                        {
                            "secret_name": r.secret_name,
                            "has_drift": r.has_drift,
                            "message": r.message,
                            "details": r.details or {},
                        }
                        for r in results
                    ],
                },
                indent=2,
            )
        )
        if drift_found:
            sys.exit(EXIT_DRIFT_DETECTED)
        return

    console.print("[bold]Checking for drift...[/bold]\n")

    # Display results
    for result in results:
        if result.has_drift:
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
        sys.exit(EXIT_DRIFT_DETECTED)
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
    type=click.Choice(["mermaid", "terminal", "json"]),
    default="mermaid",
    help="Output format (mermaid, terminal, or json)",
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
    - json: Machine-readable nodes and edges

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

        # Machine-readable JSON graph
        secretzero graph --format json
    """
    file_path = Path(file)

    if not file_path.exists():
        console.print(f"[red]Error:[/red] Secretfile not found: {file_path}")
        sys.exit(EXIT_CONFIG_ERROR)

    try:
        if output_format == "json":
            # Build machine-readable graph
            loader = ConfigLoader()
            config = loader.load_file(file_path)
            nodes = []
            edges = []
            for secret in config.secrets:
                nodes.append(
                    {
                        "id": secret.name,
                        "type": "secret",
                        "kind": secret.kind,
                        "one_time": secret.one_time,
                        "rotation_period": secret.rotation_period,
                    }
                )
                # Generator → secret edge
                edges.append(
                    {
                        "from": secret.kind,
                        "to": secret.name,
                        "label": "generates",
                    }
                )
                # Secret → target edges
                for target in secret.targets:
                    target_id = f"{target.provider}/{target.kind}"
                    if not any(n["id"] == target_id for n in nodes):
                        nodes.append(
                            {
                                "id": target_id,
                                "type": "target",
                                "provider": target.provider,
                                "kind": target.kind,
                            }
                        )
                    edges.append({"from": secret.name, "to": target_id, "label": "stored_in"})
            json_graph = {"nodes": nodes, "edges": edges}
            graph_str = json.dumps(json_graph, indent=2)
            if output:
                Path(output).write_text(graph_str)
                console.print(f"[green]✓[/green] Graph saved to: {output}")
            else:
                click.echo(graph_str)
            return

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
        sys.exit(EXIT_UNKNOWN_ERROR)


@main.group()
def list() -> None:
    """List secrets, providers, targets, or variables from a Secretfile."""
    pass


@list.command("secrets")
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=True),
    default="Secretfile.yml",
    help="Path to Secretfile",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (text or json)",
)
@click.option(
    "--filter",
    "name_filter",
    default=None,
    help="Filter secrets by name substring",
)
def list_secrets(file: str, output_format: str, name_filter: str | None) -> None:
    """List all secrets defined in the Secretfile."""
    loader = ConfigLoader()
    try:
        config = loader.load_file(Path(file))
    except Exception as e:
        if output_format == "json":
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error loading Secretfile:[/red] {e}")
        sys.exit(EXIT_CONFIG_ERROR)

    secrets = config.secrets
    if name_filter:
        secrets = [s for s in secrets if name_filter.lower() in s.name.lower()]

    if output_format == "json":
        click.echo(
            json.dumps(
                {
                    "secrets": [
                        {
                            "name": s.name,
                            "kind": s.kind,
                            "one_time": s.one_time,
                            "rotation_period": s.rotation_period,
                            "targets_count": len(s.targets),
                            "targets": [
                                {"provider": t.provider, "kind": t.kind} for t in s.targets
                            ],
                        }
                        for s in secrets
                    ],
                    "total": len(secrets),
                },
                indent=2,
            )
        )
        return

    if not secrets:
        console.print("[dim]No secrets configured[/dim]")
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Name", style="green")
    table.add_column("Kind")
    table.add_column("One-time", justify="center")
    table.add_column("Rotation")
    table.add_column("Targets")

    for s in secrets:
        targets_str = ", ".join(f"{t.provider}/{t.kind}" for t in s.targets) or "[dim]—[/dim]"
        table.add_row(
            s.name,
            s.kind,
            "[yellow]Yes[/yellow]" if s.one_time else "[dim]No[/dim]",
            s.rotation_period or "[dim]—[/dim]",
            targets_str,
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(secrets)} secret(s)[/dim]")


@list.command("providers")
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=True),
    default="Secretfile.yml",
    help="Path to Secretfile",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (text or json)",
)
def list_providers(file: str, output_format: str) -> None:
    """List all providers configured in the Secretfile."""
    loader = ConfigLoader()
    try:
        config = loader.load_file(Path(file))
    except Exception as e:
        if output_format == "json":
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error loading Secretfile:[/red] {e}")
        sys.exit(EXIT_CONFIG_ERROR)

    if output_format == "json":
        click.echo(
            json.dumps(
                {
                    "providers": [
                        {
                            "name": name,
                            "kind": p.kind,
                            "auth_kind": p.auth.kind if p.auth else None,
                            "fallback_generator": p.fallback_generator,
                        }
                        for name, p in config.providers.items()
                    ],
                    "total": len(config.providers),
                },
                indent=2,
            )
        )
        return

    if not config.providers:
        console.print("[dim]No providers configured[/dim]")
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Name", style="green")
    table.add_column("Kind")
    table.add_column("Auth Method")
    table.add_column("Fallback Generator")

    for name, p in config.providers.items():
        auth_method = p.auth.kind if p.auth and p.auth.kind else "[dim]—[/dim]"
        fallback = p.fallback_generator or "[dim]—[/dim]"
        table.add_row(name, p.kind or "[dim]—[/dim]", str(auth_method), fallback)

    console.print(table)
    console.print(f"\n[dim]Total: {len(config.providers)} provider(s)[/dim]")


@list.command("targets")
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=True),
    default="Secretfile.yml",
    help="Path to Secretfile",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (text or json)",
)
def list_targets(file: str, output_format: str) -> None:
    """List all target destinations across all secrets in the Secretfile."""
    loader = ConfigLoader()
    try:
        config = loader.load_file(Path(file))
    except Exception as e:
        if output_format == "json":
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error loading Secretfile:[/red] {e}")
        sys.exit(EXIT_CONFIG_ERROR)

    all_targets = []
    for secret in config.secrets:
        for t in secret.targets:
            all_targets.append(
                {
                    "secret": secret.name,
                    "provider": t.provider,
                    "kind": t.kind,
                    "config": t.config,
                }
            )

    if output_format == "json":
        click.echo(json.dumps({"targets": all_targets, "total": len(all_targets)}, indent=2))
        return

    if not all_targets:
        console.print("[dim]No targets configured[/dim]")
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Secret", style="green")
    table.add_column("Provider")
    table.add_column("Kind")
    table.add_column("Config")

    for t in all_targets:
        config_str = (
            ", ".join(f"{k}={v}" for k, v in t["config"].items()) if t["config"] else "[dim]—[/dim]"
        )
        table.add_row(t["secret"], t["provider"], t["kind"], config_str)

    console.print(table)
    console.print(f"\n[dim]Total: {len(all_targets)} target(s)[/dim]")


@list.command("variables")
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=True),
    default="Secretfile.yml",
    help="Path to Secretfile",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (text or json)",
)
@click.option(
    "--filter",
    "name_filter",
    default=None,
    help="Filter variables by name substring",
)
def list_variables(file: str, output_format: str, name_filter: str | None) -> None:
    """List all variables defined in the Secretfile."""
    loader = ConfigLoader()
    try:
        config = loader.load_file(Path(file))
    except Exception as e:
        if output_format == "json":
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error loading Secretfile:[/red] {e}")
        sys.exit(EXIT_CONFIG_ERROR)

    variables = dict(config.variables)
    if name_filter:
        variables = {k: v for k, v in variables.items() if name_filter.lower() in k.lower()}

    if output_format == "json":
        click.echo(
            json.dumps(
                {"variables": variables, "total": len(variables)},
                indent=2,
            )
        )
        return

    if not variables:
        console.print("[dim]No variables configured[/dim]")
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Name", style="green")
    table.add_column("Value")

    for name, value in variables.items():
        table.add_row(name, str(value))

    console.print(table)
    console.print(f"\n[dim]Total: {len(variables)} variable(s)[/dim]")


@main.command()
@click.argument("directory", default=".", type=click.Path(exists=True))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (text or json)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Write suggested Secretfile fragment to file instead of stdout",
)
def detect(directory: str, output_format: str, output: str | None) -> None:
    """Scan a directory for potential secrets and suggest Secretfile definitions.

    Looks for common secret patterns in files: .env files, config files,
    and environment variable references. Outputs a suggested Secretfile
    fragment that can be added to your Secretfile.yml.

    Examples:

        # Scan current directory
        secretzero detect

        # Scan specific directory
        secretzero detect ./src

        # Output suggested config as JSON
        secretzero detect --format json

        # Save suggestion to file
        secretzero detect -o suggested.yml
    """
    import re

    dir_path = Path(directory)

    # Patterns that suggest a potential secret value assignment in dotenv/shell files.
    # Group 1 captures the variable name (uppercase, with keyword suffix/prefix).
    secret_suffixes = r"(PASSWORD|SECRET|KEY|TOKEN|CREDENTIAL|CERT|PRIVATE)"
    secret_prefixes = r"(PWD|PASS|AUTH|API)"
    secret_patterns = [
        # VAR_NAME with a secret-related keyword anywhere in the suffix, e.g. DATABASE_PASSWORD=
        (re.compile(rf"^([A-Z_][A-Z0-9_]*{secret_suffixes}[A-Z0-9_]*)=", re.M), "dotenv"),
        # VAR_NAME ending with a short secret keyword, e.g. DB_PASS= or MY_API=
        (re.compile(rf"^([A-Z_][A-Z0-9_]*_{secret_prefixes})\s*=", re.M), "dotenv"),
    ]

    env_file_patterns = ["**/.env*", "**/secrets*", "**/credentials*", "**/*.env"]

    found: dict[str, dict] = {}

    # Scan env-style files
    for glob_pattern in env_file_patterns:
        for path in dir_path.glob(glob_pattern):
            if path.is_file() and not any(
                p in str(path) for p in [".git", "__pycache__", ".venv", "node_modules"]
            ):
                try:
                    content = path.read_text(errors="ignore")
                    for pattern, file_type in secret_patterns:
                        for m in pattern.finditer(content):
                            var_name = m.group(1).lower()
                            if var_name not in found:
                                found[var_name] = {
                                    "name": var_name,
                                    "env_var": m.group(1),
                                    "file": str(path.relative_to(dir_path)),
                                    "file_type": file_type,
                                }
                except (OSError, UnicodeDecodeError):
                    pass

    # Build suggestions
    suggestions = []
    for var_name, info in sorted(found.items()):
        suggestions.append(
            {
                "name": var_name,
                "env_var": info["env_var"],
                "source_file": info["file"],
                "suggested_config": {
                    "name": var_name,
                    "kind": "static",
                    "config": {"default": f"${{{info['env_var']}}}"},
                    "targets": [
                        {
                            "provider": "local",
                            "kind": "file",
                            "config": {"path": ".env", "format": "dotenv"},
                        }
                    ],
                },
            }
        )

    if output_format == "json":
        click.echo(json.dumps({"detected": suggestions, "total": len(suggestions)}, indent=2))
        return

    if not suggestions:
        console.print("[green]✓ No potential secrets detected in directory.[/green]")
        console.print(
            "\n[dim]Tip: Ensure your .env files and config files are in the scanned directory.[/dim]"
        )
        return

    console.print(f"[bold]Detected {len(suggestions)} potential secret(s):[/bold]\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Name", style="green")
    table.add_column("Env Variable")
    table.add_column("Source File")

    for s in suggestions:
        table.add_row(s["name"], s["env_var"], s["source_file"])

    console.print(table)

    # Generate suggested Secretfile fragment
    fragment_lines = ["# Suggested secret definitions (add to your Secretfile.yml)\nsecrets:"]
    for s in suggestions:
        cfg = s["suggested_config"]
        fragment_lines.append(f"  - name: {cfg['name']}")
        fragment_lines.append(f"    kind: {cfg['kind']}")
        fragment_lines.append("    config:")
        fragment_lines.append(f'      default: "{cfg["config"]["default"]}"')
        fragment_lines.append("    targets:")
        fragment_lines.append("      - provider: local")
        fragment_lines.append("        kind: file")
        fragment_lines.append("        config:")
        fragment_lines.append("          path: .env")
        fragment_lines.append("          format: dotenv")

    fragment = "\n".join(fragment_lines)

    if output:
        Path(output).write_text(fragment)
        console.print(f"\n[green]✓[/green] Suggested configuration written to: {output}")
    else:
        console.print("\n[bold]Suggested Secretfile fragment:[/bold]\n")
        console.print(f"[dim]{fragment}[/dim]")


# Register provider CLI group
main.add_command(providers_group)


@main.command()
@click.option(
    "--limit",
    "-n",
    default=50,
    help="Maximum number of log entries to return",
)
@click.option(
    "--offset",
    default=0,
    help="Number of entries to skip",
)
@click.option(
    "--action",
    "-a",
    default=None,
    help="Filter logs by action name",
)
@click.option(
    "--resource",
    "-r",
    default=None,
    help="Filter logs by resource name",
)
@click.option(
    "--log-file",
    type=click.Path(),
    default=".secretzero_audit.log",
    help="Path to audit log file",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (text or json)",
)
def audit(
    limit: int,
    offset: int,
    action: str | None,
    resource: str | None,
    log_file: str,
    output_format: str,
) -> None:
    """View API audit logs.

    Displays audit log entries recorded by the SecretZero API. Logs are written
    to a file when the API server is running.

    Examples:

        # Show recent audit logs
        secretzero audit

        # Filter by action
        secretzero audit --action sync

        # Filter by resource
        secretzero audit --resource secrets

        # Show in JSON format
        secretzero audit --format json

        # Show last 100 entries
        secretzero audit --limit 100
    """
    log_path = Path(log_file)
    logger = AuditLogger(log_file=log_path)

    logs = logger.get_logs(limit=limit, offset=offset, action=action, resource=resource)

    if output_format == "json":
        click.echo(
            json.dumps(
                {
                    "entries": [e.model_dump(mode="json") for e in logs],
                    "count": len(logs),
                },
                indent=2,
            )
        )
        return

    if not logs:
        console.print("[dim]No audit log entries found[/dim]")
        if not log_path.exists():
            console.print(
                f"[dim]Log file not found: {log_path}. "
                "The API server must be running to generate audit logs.[/dim]"
            )
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Timestamp", style="dim")
    table.add_column("Action", style="green")
    table.add_column("Resource")
    table.add_column("User")
    table.add_column("Success", justify="center")

    for entry in logs:
        success_str = "[green]✓[/green]" if entry.success else "[red]✗[/red]"
        timestamp_str = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S") if entry.timestamp else ""
        table.add_row(
            timestamp_str,
            entry.action,
            entry.resource,
            entry.user or "[dim]—[/dim]",
            success_str,
        )

    console.print(table)
    console.print(f"\n[dim]Showing {len(logs)} of available entries[/dim]")


# ---------------------------------------------------------------------------
# Agent command group
# ---------------------------------------------------------------------------


@main.group()
def agent() -> None:
    """Agent-specific commands for autonomous secret management.

    These commands are designed for use by AI agents and automation tools that
    need to manage secrets with minimal human intervention. They provide
    structured output and guided instructions for secrets that require manual
    acquisition.
    """
    pass


@agent.command("sync")
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
    "--var-file",
    "-v",
    "var_files",
    type=click.Path(exists=True),
    multiple=True,
    help="Path to .szvar variable file(s) to merge (can be specified multiple times)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview changes without applying them",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output results as JSON (machine-readable)",
)
@click.option(
    "--interactive",
    is_flag=True,
    help="Prompt for manual secrets interactively",
)
def agent_sync(
    file: str,
    lockfile: str,
    var_files: tuple[str, ...],
    dry_run: bool,
    output_json: bool,
    interactive: bool,
) -> None:
    """Agent-aware secret synchronisation with guided instructions.

    Automatically syncs secrets that can be generated without external input
    and provides structured step-by-step instructions for secrets that require
    manual acquisition (sign-ups, OAuth flows, admin approvals, etc.).

    Examples:

        # Run agent sync and view instructions for pending secrets
        secretzero agent sync

        # Output machine-readable JSON for further processing
        secretzero agent sync --json

        # Preview what would happen without making changes
        secretzero agent sync --dry-run

        # Interactively supply values for pending secrets
        secretzero agent sync --interactive

        # Sync with variable file override
        secretzero agent sync --var-file dev.szvar
    """
    from secretzero.agent import AgentSecretSynchronizer

    file_path = Path(file)

    # Generate default lockfile name from secretfile if not explicitly provided
    if lockfile == ".gitsecrets.lock":
        if file != "Secretfile.yml":
            lockfile_name = file_path.stem + ".lock"
            lockfile = lockfile_name

    lockfile_path = Path(lockfile)
    var_file_paths = [Path(vf) for vf in var_files] if var_files else None
    loader = ConfigLoader()

    try:
        secretfile = loader.load_file(file_path, var_files=var_file_paths)
    except Exception as exc:
        console.print(f"[red]Error loading Secretfile:[/red] {exc}")
        raise click.ClickException(str(exc)) from exc

    # Read secretfile content for change detection
    secretfile_content = file_path.read_text()

    # Load lockfile
    lock = Lockfile.load(lockfile_path)

    synchronizer = AgentSecretSynchronizer(
        secretfile,
        lock,
        dry_run=dry_run,
        secretfile_path=file_path,
        secretfile_content=secretfile_content,
    )

    try:
        result = synchronizer.sync()
    except Exception as exc:
        console.print(f"[red]Agent sync failed:[/red] {exc}")
        raise click.ClickException(str(exc)) from exc

    # Save lockfile if not dry run
    if not dry_run:
        lock.save(lockfile_path)

    if output_json:
        import json as _json

        output = {
            "synced_secrets": result.synced_secrets,
            "already_synced": result.already_synced,
            "pending_secrets": {
                k: v.model_dump(exclude_none=True) for k, v in result.pending_secrets.items()
            },
            "failed_secrets": result.failed_secrets,
            "automation_summary": result.automation_summary,
            "sync_results": result.sync_results,
            "dry_run": dry_run,
        }
        click.echo(_json.dumps(output, indent=2, default=str))
        return

    _display_agent_sync_results(result, lock, interactive=interactive, dry_run=dry_run)


def _display_agent_sync_results(
    result: Any, lock: Lockfile, *, interactive: bool = False, dry_run: bool = False
) -> None:
    """Display agent sync results in a human-readable format.

    Args:
        result: AgentSyncResult to display
        lock: Lockfile for validation information
        interactive: If True, prompt the user for pending secret values
        dry_run: If True, indicate preview mode
    """
    from rich.rule import Rule

    # Synced secrets
    if result.synced_secrets:
        console.print(
            f"\n[bold green]\u2705 Successfully synced {len(result.synced_secrets)} secret(s):[/bold green]"
        )
        for secret in result.synced_secrets:
            console.print(f"  • {secret}", style="green")

    # Already synced secrets (skipped)
    if result.already_synced:
        console.print(
            f"\n[bold blue]ℹ️  {len(result.already_synced)} secret(s) already in lockfile (skipped):[/bold blue]"
        )
        for secret in result.already_synced:
            console.print(f"  • {secret}", style="blue")

    # Pending secrets with instructions
    if result.pending_secrets:
        console.print(
            f"\n[bold yellow]\u23f3 {len(result.pending_secrets)} secret(s) require manual intervention:[/bold yellow]"
        )

        for secret_name, instructions in result.pending_secrets.items():
            console.print()
            console.print(Rule(f"[bold cyan]{secret_name}[/bold cyan]", style="cyan"))
            console.print(f"  [bold]Summary:[/bold] {instructions.summary}")

            if instructions.prerequisites:
                console.print("\n  [bold yellow]Prerequisites:[/bold yellow]")
                for prereq in instructions.prerequisites:
                    console.print(f"    • {prereq}")

            console.print("\n  [bold blue]Steps:[/bold blue]")
            for i, step in enumerate(instructions.steps, 1):
                console.print(f"    {i}. [bold]{step.action}[/bold]")
                console.print(f"       [dim]{step.description}[/dim]")
                if step.params:
                    console.print(f"       [italic]Params: {step.params}[/italic]")

            if instructions.automation_hint:
                console.print(
                    f"\n  \U0001f4a1 [italic]Automation: {instructions.automation_hint}[/italic]"
                )
            if instructions.estimated_time:
                console.print(
                    f"  \u23f1\ufe0f  [italic]Estimated time: {instructions.estimated_time}[/italic]"
                )
            if instructions.required_tools:
                console.print(
                    f"  \U0001f527 [italic]Required tools: {', '.join(instructions.required_tools)}[/italic]"
                )
            if instructions.fallback:
                console.print(f"  \U0001f504 [italic]Fallback: {instructions.fallback}[/italic]")
            if instructions.documentation_url:
                console.print(f"  \U0001f4da [blue]Docs: {instructions.documentation_url}[/blue]")

            if interactive:
                if click.confirm(f"\nHave you obtained the value for '{secret_name}'?"):
                    click.prompt(
                        f"Enter the secret value for {secret_name}",
                        hide_input=True,
                        confirmation_prompt=False,
                    )
                    console.print(
                        f"[green]\u2705 Value received for {secret_name}[/green] "
                        "(apply with 'secretzero sync' or store it manually)"
                    )

    # Failed secrets
    if result.failed_secrets:
        console.print(
            f"\n[bold red]\u274c {len(result.failed_secrets)} secret(s) failed:[/bold red]"
        )
        for secret, error in result.failed_secrets.items():
            console.print(f"  • [red]{secret}[/red]: {error}")

    # Show detailed sync results if available
    sync_results = result.sync_results
    if sync_results and sync_results.get("details"):
        console.print("\n[bold]Synced Secret Details[/bold]")

        details_table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
        details_table.add_column("Status", justify="center", width=8)
        details_table.add_column("Secret Name", style="bold")
        details_table.add_column("Type", style="dim")
        details_table.add_column("Result", justify="left")

        for detail in sync_results["details"]:
            secret_name = detail["name"]
            secret_kind = detail["kind"]
            is_stored = detail.get("stored")
            is_skipped = detail.get("skipped")
            has_errors = bool(detail.get("errors"))

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
                    # Check lockfile for validation
                    lockfile_info = lock.get_secret_info(secret_name)
                    if lockfile_info:
                        result_text = "[green]Stored & Validated[/green]"
                    else:
                        result_text = "[green]Stored[/green]"
            else:
                status_icon = "[dim]•[/dim]"
                result_text = "[dim]Processed[/dim]"

            details_table.add_row(status_icon, secret_name, secret_kind, result_text)

        console.print(details_table)

    # Summary
    console.print("\n[bold]\U0001f4ca Summary:[/bold]")
    if dry_run:
        console.print("[yellow]DRY RUN MODE - No changes applied[/yellow]")
    console.print(f"  Synced:   {result.automation_summary.get('fully_synced', 0)}")
    already_synced = result.automation_summary.get("already_synced", 0)
    if already_synced > 0:
        console.print(f"  Already synced: {already_synced}")
    console.print(f"  Pending:  {result.automation_summary.get('requires_intervention', 0)}")
    console.print(f"  Failed:   {result.automation_summary.get('failed', 0)}")

    # Show lockfile validation
    if not dry_run and result.synced_secrets:
        validated_count = sum(
            1 for name in result.synced_secrets if lock.get_secret_info(name) is not None
        )
        console.print(f"  Validated in lockfile: {validated_count}/{len(result.synced_secrets)}")


@main.command()
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    default=".",
    help="Project root directory to scan",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Output path for Secretfile.detect.yml (default: <path>/Secretfile.detect.yml)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Analyse without writing output files",
)
@click.option(
    "--provider",
    type=click.Choice(["ollama", "openai", "anthropic", "azure_openai"]),
    default=None,
    help="LLM provider to use for AI-enhanced analysis",
)
@click.option(
    "--model",
    default=None,
    help="LLM model name override",
)
@click.option(
    "--local-only",
    is_flag=True,
    help="Restrict to local LLM providers only (e.g. Ollama)",
)
@click.option(
    "--no-llm",
    is_flag=True,
    help="Disable LLM analysis; use pattern matching only",
)
@click.option(
    "--config",
    "-c",
    "config_file",
    type=click.Path(exists=True),
    default=None,
    help="Path to secretzero.yml configuration file",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["text", "json", "yaml"]),
    default="text",
    help="Output summary format",
)
@click.option(
    "--threshold",
    type=float,
    default=None,
    help="Confidence threshold (0.0\u20131.0) for including secrets (default from config)",
)
def discover(
    path: str,
    output: str | None,
    dry_run: bool,
    provider: str | None,
    model: str | None,
    local_only: bool,
    no_llm: bool,
    config_file: str | None,
    output_format: str,
    threshold: float | None,
) -> None:
    """AI-powered secret discovery.

    Scans a project directory for secrets, credentials, and sensitive
    configuration values.  Generates a ``Secretfile.detect.yml`` with
    recommended secret definitions that you can review and use as a
    starting point for your ``Secretfile.yml``.

    \b
    Examples:
      # Basic scan of current directory
      secretzero discover

      # Use OpenAI for deeper analysis
      secretzero discover --provider openai

      # Privacy-first local-only scan
      secretzero discover --local-only

      # Dry-run to preview without writing
      secretzero discover --dry-run
    """
    from secretzero.cli_config import CliConfigLoader
    from secretzero.discovery import DiscoveryAgent

    # Load CLI configuration
    loader = CliConfigLoader()
    try:
        cli_cfg = loader.load(config_path=config_file)
    except ValueError as exc:
        console.print(f"[red]Error loading config:[/red] {exc}")
        raise click.Abort()

    # Apply threshold override
    if threshold is not None:
        cli_cfg.discovery.confidence_threshold = threshold

    if output_format == "text":
        console.print("[bold]\U0001f50d Starting secret discovery...[/bold]\n")
        console.print(f"  Project root : [cyan]{Path(path).resolve()}[/cyan]")

        effective_provider = provider or cli_cfg.llm.default_provider
        if no_llm:
            console.print("  LLM analysis : [yellow]disabled (--no-llm)[/yellow]")
        elif local_only:
            console.print(f"  LLM provider : [cyan]{effective_provider}[/cyan] (local-only)")
        else:
            console.print(f"  LLM provider : [cyan]{effective_provider}[/cyan]")

        if dry_run:
            console.print("  Mode         : [yellow]dry-run (no files written)[/yellow]")

        console.print()

    agent = DiscoveryAgent(config=cli_cfg)

    try:
        result = agent.discover(
            project_root=path,
            output_path=output,
            dry_run=dry_run,
            use_llm=not no_llm,
            local_only=local_only,
            provider=provider,
            model=model,
        )
    except Exception as exc:
        console.print(f"[red]Discovery failed:[/red] {exc}")
        sys.exit(EXIT_UNKNOWN_ERROR)

    # Format output
    if output_format == "json":
        data = {
            "files_scanned": result.files_scanned,
            "total_secrets": result.total_secrets,
            "dry_run": result.dry_run,
            "output_path": str(result.output_path) if result.output_path else None,
            "secrets": [
                {
                    "name": c.name,
                    "description": c.description,
                    "confidence": c.confidence,
                    "generator": c.suggested_generator,
                    "source_file": c.source_file,
                    "line": c.line_number,
                    "tags": c.tags,
                }
                for c in result.candidates
            ],
        }
        click.echo(json.dumps(data, indent=2))
        return

    if output_format == "yaml":
        data = {
            "files_scanned": result.files_scanned,
            "total_secrets": result.total_secrets,
            "dry_run": result.dry_run,
            "output_path": str(result.output_path) if result.output_path else None,
            "secrets": [
                {
                    "name": c.name,
                    "description": c.description,
                    "confidence": round(c.confidence, 2),
                    "generator": c.suggested_generator,
                    "source_file": c.source_file,
                }
                for c in result.candidates
            ],
        }
        click.echo(yaml.dump(data, sort_keys=False, default_flow_style=False))
        return

    # Default: text output
    console.print(f"[green]\u2713[/green] Scanned [bold]{result.files_scanned}[/bold] file(s)")
    console.print(
        f"[green]\u2713[/green] Found [bold]{result.total_secrets}[/bold] secret candidate(s)"
    )

    if result.total_secrets > 0:
        console.print()
        from rich import box as _box
        from rich.table import Table as _Table

        table = _Table(show_header=True, header_style="bold cyan", box=_box.SIMPLE)
        table.add_column("Name", style="green")
        table.add_column("Generator", style="cyan")
        table.add_column("Confidence", justify="right")
        table.add_column("Source", style="dim")
        table.add_column("Tags", style="dim")

        for c in result.candidates:
            conf_color = (
                "green" if c.confidence >= 0.85 else "yellow" if c.confidence >= 0.65 else "red"
            )
            conf_str = f"[{conf_color}]{c.confidence:.0%}[/{conf_color}]"
            tags_str = ", ".join(c.tags[:3]) if c.tags else ""
            table.add_row(c.name, c.suggested_generator, conf_str, c.source_file, tags_str)

        console.print(table)

    if dry_run:
        console.print("\n[yellow]Dry-run mode:[/yellow] no files written.")
        console.print(
            f"[dim]Run without --dry-run to write:[/dim] [cyan]{result.output_path}[/cyan]"
        )
    elif result.total_secrets > 0 and result.output_path:
        console.print(f"\n[green]\u2713[/green] Written to: [cyan]{result.output_path}[/cyan]")
        console.print("\nNext steps:")
        console.print("  1. Review [cyan]Secretfile.detect.yml[/cyan] and remove false positives")
        console.print("  2. Rename/merge entries into your [cyan]Secretfile.yml[/cyan]")
        console.print("  3. Run [cyan]secretzero validate[/cyan] to check the configuration")
    else:
        console.print("\n[dim]No secrets found above the confidence threshold.[/dim]")




@main.command("validate-bundle")
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--output-format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
def validate_bundle(path: str, output_format: str) -> None:
    """Validate a SecretZero provider bundle.

    PATH can be a directory containing a Python package or a Python file
    that exports a ``BUNDLE_MANIFEST`` attribute.

    Checks performed:

    \b
    - BUNDLE_MANIFEST is a valid BundleManifest
    - All declared dotted class paths can be imported
    - Provider class inherits from BaseProvider
    - Generator classes inherit from BaseGenerator
    - Target classes inherit from BaseTarget
    """
    import importlib.util
    import sys

    from secretzero.bundles import BundleManifest
    from secretzero.bundles.registry import BundleRegistry

    bundle_path = Path(path).resolve()
    errors: list[str] = []
    manifest: BundleManifest | None = None

    # ------------------------------------------------------------------
    # 1. Locate and load the BUNDLE_MANIFEST
    # ------------------------------------------------------------------
    # Try loading as a Python file first, then as a package __init__.py
    candidate_files = []
    if bundle_path.is_file() and bundle_path.suffix == ".py":
        candidate_files = [bundle_path]
    elif bundle_path.is_dir():
        candidate_files = [
            bundle_path / "__init__.py",
            bundle_path / "bundle.py",
        ]

    for candidate in candidate_files:
        if not candidate.exists():
            continue
        spec = importlib.util.spec_from_file_location("_bundle_candidate", candidate)
        if spec is None or spec.loader is None:
            continue
        try:
            mod = importlib.util.module_from_spec(spec)
            sys.modules["_bundle_candidate"] = mod
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            if hasattr(mod, "BUNDLE_MANIFEST"):
                manifest = mod.BUNDLE_MANIFEST
                break
        except Exception as exc:
            errors.append(f"Failed to import {candidate}: {exc}")
        finally:
            sys.modules.pop("_bundle_candidate", None)

    if manifest is None and not errors:
        errors.append(
            f"No BUNDLE_MANIFEST found in '{bundle_path}'. "
            "Ensure your package exports a BUNDLE_MANIFEST attribute."
        )

    # ------------------------------------------------------------------
    # 2. Validate the manifest structure and class paths
    # ------------------------------------------------------------------
    if manifest is not None:
        if not isinstance(manifest, BundleManifest):
            errors.append(
                f"BUNDLE_MANIFEST is not a BundleManifest instance (got {type(manifest).__name__})"
            )
        else:
            registry = BundleRegistry()
            validation_errors = registry.validate_bundle_manifest(manifest)
            errors.extend(validation_errors)

    # ------------------------------------------------------------------
    # 3. Output results
    # ------------------------------------------------------------------
    if output_format == "json":
        import json as _json

        result = {
            "path": str(bundle_path),
            "valid": len(errors) == 0,
            "manifest": manifest.model_dump() if isinstance(manifest, BundleManifest) else None,
            "errors": errors,
        }
        console.print(_json.dumps(result, indent=2))
        sys.exit(EXIT_SUCCESS if len(errors) == 0 else EXIT_VALIDATION_ERROR)

    # Text output
    if isinstance(manifest, BundleManifest) and not errors:
        console.print(f"[green]✓[/green] Bundle [bold]{manifest.name}[/bold] v{manifest.version}")
        if manifest.provider_class:
            console.print(f"  Provider : [cyan]{manifest.provider_class}[/cyan]")
        if manifest.generators:
            console.print("  Generators:")
            for kind, path_str in manifest.generators.items():
                console.print(f"    • [cyan]{kind}[/cyan] → {path_str}")
        if manifest.targets:
            console.print("  Targets:")
            for kind, path_str in manifest.targets.items():
                console.print(f"    • [cyan]{kind}[/cyan] → {path_str}")
        console.print("\n[green]✓ Bundle is valid.[/green]")
        sys.exit(EXIT_SUCCESS)
    else:
        if isinstance(manifest, BundleManifest):
            console.print(
                f"[red]✗[/red] Bundle [bold]{manifest.name}[/bold] has {len(errors)} error(s):"
            )
        else:
            console.print(f"[red]✗[/red] Bundle validation failed with {len(errors)} error(s):")
        for err in errors:
            console.print(f"  [red]•[/red] {err}")
        sys.exit(EXIT_VALIDATION_ERROR)


if __name__ == "__main__":
    main()
