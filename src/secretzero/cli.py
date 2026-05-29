"""CLI interface for SecretZero."""

import json
import os
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import click
import yaml
from rich import box
from rich.console import Console
from rich.table import Table

from secretzero import __version__
from secretzero.agent_adopt_cli import (
    render_agent_list_json,
    render_agent_list_text,
    run_agent_adopt_command,
)
from secretzero.agent_context import env_sz_agent_mode, spill_guard_active
from secretzero.api.audit import AuditLogger
from secretzero.backup import (
    BACKUP_FORMAT_VERSION,
    collect_backup_entries,
    decrypt_backup_document,
    encrypt_backup_document,
    load_plain_backup_document,
    resolve_backup_age_recipients,
    restore_backup_entries,
)
from secretzero.bundles import get_bundle_registry
from secretzero.cli_config_cmd import config_group
from secretzero.cli_format import format_command
from secretzero.cli_providers import providers_group
from secretzero.config import ConfigLoader
from secretzero.drift import DriftDetector
from secretzero.environment_resolution import (
    ResolvedEnvironmentContext,
    apply_target_profile,
    resolve_environment_context,
)
from secretzero.gitnexus_intel import (
    emit_gitnexus_sidecars,
    format_blast_radius_cli,
    print_impact_suggestion,
    run_gitnexus_analyze_skills,
    run_gitnexus_blast_radius,
)
from secretzero.graph import generate_graph
from secretzero.ingest_preseed import describe_ingest_source_match, secret_names_for_ingest_source
from secretzero.lockfile import Lockfile
from secretzero.lockfile_import import run_lockfile_import
from secretzero.lockfile_state import sync_state_for_secret_target
from secretzero.manifest_plaintext import list_manifest_plaintext_violations
from secretzero.models import SECRETFILE_MANIFEST_SPEC_VERSION, AgentMode, Secretfile
from secretzero.policy import PolicyEngine
from secretzero.provider_identity import collect_provider_identity_rows
from secretzero.rotation import should_rotate_secret
from secretzero.sync import SyncEngine
from secretzero.terraform_export import (
    TerraformGeneratorOptions,
    TerraformOutputFormat,
    generate_terraform,
)

console = Console()

# Standardized exit codes for automation / AI agent consumption
EXIT_SUCCESS = 0
EXIT_VALIDATION_ERROR = 1
EXIT_MISSING_DEPENDENCY = 2
EXIT_AUTH_FAILURE = 3
EXIT_DRIFT_DETECTED = 4
EXIT_CONFIG_ERROR = 5
EXIT_UNKNOWN_ERROR = 127


_environment_option = click.option(
    "--environment",
    "-e",
    type=str,
    default=None,
    help="Named environment profile from Secretfile.environments.profiles",
)


def _should_emit_gitnexus_sidecar(
    dry_run: bool,
    results: dict[str, Any],
    cleaned_entries: list[str],
) -> bool:
    """Mirror lockfile persist conditions for GitNexus sidecar emission."""
    if dry_run:
        return False
    if results.get("secrets_stored", 0) > 0 or cleaned_entries:
        return True
    if results.get("secretfile_changed") is not None:
        return True
    return False


def _try_emit_gitnexus_sidecar(
    file_path: Path, config: Secretfile, *, echo: bool = False
) -> dict[str, Any] | None:
    try:
        summary = emit_gitnexus_sidecars(secretfile_path=file_path, secretfile=config)
        if echo and not summary.get("skipped") and summary.get("secrets_overlay"):
            console.print(f"[dim]GitNexus overlay:[/dim] {summary['secrets_overlay']}")
        return summary
    except Exception as exc:  # noqa: BLE001 — never block primary command
        if echo:
            console.print(f"[dim]GitNexus overlay skipped:[/dim] {exc}")
        return {"error": str(exc)}


def _print_provider_identity_panel(
    secretfile: Secretfile, rows: list[dict[str, Any]] | None = None
) -> None:
    """Rich table: configured providers and resolved authenticated identity."""
    rows = rows or collect_provider_identity_rows(secretfile)
    if not rows:
        return
    table = Table(title="Provider identity", box=box.ROUNDED)
    table.add_column("Provider", style="cyan", no_wrap=True)
    table.add_column("Kind", style="dim")
    table.add_column("Status", justify="center", width=10)
    table.add_column("Identity")
    for r in rows:
        st = r["status"]
        if st == "ok":
            st_txt = "[green]ok[/green]"
        elif st == "local":
            st_txt = "[dim]local[/dim]"
        elif st == "unauthenticated":
            st_txt = "[yellow]no auth[/yellow]"
        else:
            st_txt = "[red]issue[/red]"
        ident = str(r.get("primary") or "—")
        if r.get("secondary"):
            ident = f"{ident}\n[dim]{r['secondary']}[/dim]"
        table.add_row(r["alias"], r["kind"], st_txt, ident)
    console.print(table)
    console.print()


def _print_sync_readiness_panel(readiness: dict[str, Any]) -> None:
    """Print policy / target-access gates that would block a full ``sync``."""
    blocked = bool(readiness.get("sync_blocked"))
    headline = str(readiness.get("headline") or "")
    if blocked:
        console.print("[bold red]Full sync would be blocked[/bold red]")
        console.print(f"[red]{headline}[/red]\n")
    else:
        console.print("[bold green]Full sync readiness[/bold green]")
        console.print(f"[dim]{headline}[/dim]\n")

    identity = readiness.get("provider_identity") or {}
    rows = identity.get("rows") or []
    if identity.get("has_policies"):
        pol_table = Table(title="Provider identity policies (sync gate)", box=box.ROUNDED)
        pol_table.add_column("Policy", style="cyan", no_wrap=True)
        pol_table.add_column("Provider", style="dim", no_wrap=True)
        pol_table.add_column("Status", justify="center", width=14)
        pol_table.add_column("Detail")
        for r in rows:
            st = r.get("status", "")
            if st == "ok":
                st_txt = "[green]ok[/green]"
            else:
                st_txt = f"[red]{st}[/red]"
            detail = str(r.get("detail") or "—")
            pol_table.add_row(
                str(r.get("policy_name") or "—"),
                str(r.get("provider_alias") or "—"),
                st_txt,
                detail,
            )
        console.print(pol_table)
        console.print()
    elif identity.get("has_policies") is False:
        console.print(f"[dim]{identity.get('headline', '')}[/dim]\n")

    access = readiness.get("target_access") or {}
    results = access.get("results") or []
    if access.get("total_count", 0) > 0:
        acc_table = Table(title="Target provider connectivity (sync gate)", box=box.ROUNDED)
        acc_table.add_column("Provider", style="cyan", no_wrap=True)
        acc_table.add_column("OK", justify="center", width=8)
        acc_table.add_column("Detail")
        for item in results:
            ok = item.get("ok")
            ok_txt = "[green]yes[/green]" if ok else "[red]no[/red]"
            err = item.get("error")
            detail = str(err) if err else ("—" if ok else "connection failed")
            acc_table.add_row(str(item.get("provider") or "—"), ok_txt, detail)
        console.print(acc_table)
        console.print()


@click.group(context_settings={"help_option_names": ["-h", "--help"]}, invoke_without_command=True)
@click.version_option(version=__version__)
@click.option(
    "--non-interactive",
    "-n",
    is_flag=True,
    default=False,
    help="Disable all interactive prompts; error when human input would be required.",
)
@_environment_option
@click.pass_context
def main(ctx: click.Context, non_interactive: bool, environment: str | None) -> None:
    """SecretZero: Secrets orchestration, lifecycle, and bootstrap engine.

    SecretZero helps automate the creation, seeding, and lifecycle management
    of project secrets through a declarative, schema-driven workflow.
    """
    ctx.ensure_object(dict)
    ctx.obj["non_interactive"] = non_interactive
    ctx.obj["environment"] = environment
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit(EXIT_SUCCESS)


def _is_non_interactive() -> bool:
    """Return True when ``--non-interactive`` was passed on the CLI.

    Safe to call from any depth — returns *False* if there is no Click
    context (e.g. during unit tests).
    """
    ctx = click.get_current_context(silent=True)
    if ctx is None:
        return False
    obj = ctx.find_root().obj
    if obj is None:
        return False
    return bool(obj.get("non_interactive", False))


def _env_flag(name: str) -> bool:
    """Return True when environment variable is a truthy flag."""
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _redact_target_config_for_spill_guard(cfg: dict[str, Any]) -> dict[str, Any]:
    """Strip target config down to non-sensitive structural fields for agent-safe JSON."""
    if not cfg:
        return {}
    allow = {"path", "format", "merge", "key", "environment", "output_path", "namespace"}
    out: dict[str, Any] = {k: cfg[k] for k in allow if k in cfg}
    extra = sorted(set(cfg) - set(out))
    if extra:
        out["_redacted_config_keys"] = extra
    return out


def _root_environment() -> str | None:
    """Return the root CLI environment selection, if any."""
    ctx = click.get_current_context(silent=True)
    if ctx is None:
        return None
    root = ctx.find_root()
    obj = root.obj if root is not None else None
    if not obj:
        return None
    value = obj.get("environment")
    return str(value) if value else None


def _effective_environment(environment: str | None) -> str | None:
    """Prefer command-local environment, then fall back to the root CLI flag."""
    return environment if environment is not None else _root_environment()


def _load_secretfile_for_cli(
    file: str,
    *,
    var_files: tuple[str, ...] = (),
    environment: str | None = None,
    lockfile: str | None = None,
) -> tuple[Path, Secretfile, ResolvedEnvironmentContext]:
    """Load a Secretfile with environment-aware var-file and target-profile resolution."""
    file_path = Path(file)
    runtime_var_file_paths = [Path(vf) for vf in var_files] if var_files else None
    runtime_lockfile = None
    if lockfile is not None:
        runtime_lockfile = _runtime_lockfile_override(file, lockfile)

    loader = ConfigLoader()
    base_secretfile = loader.load_file(file_path)
    env_ctx = resolve_environment_context(
        secretfile=base_secretfile,
        secretfile_path=file_path,
        environment=_effective_environment(environment),
        runtime_var_files=runtime_var_file_paths,
        runtime_lockfile=runtime_lockfile,
    )
    secretfile = loader.load_file(file_path, var_files=env_ctx.resolved_var_files or None)
    secretfile = apply_target_profile(secretfile, env_ctx.resolved_target_profile)
    return file_path, secretfile, env_ctx


def _runtime_lockfile_override(file: str, lockfile: str) -> str | None:
    """Normalize lockfile CLI input to optional explicit override."""
    if lockfile == ".gitsecrets.lock":
        return None
    return lockfile


def _backup_target_environments(
    secretfile: Secretfile, environment: str | None
) -> list[str | None]:
    """Return environments targeted by backup commands."""
    selected = _effective_environment(environment)
    if selected is not None:
        return [selected]
    env_cfg = secretfile.environments
    if env_cfg and env_cfg.profiles:
        return sorted(env_cfg.profiles.keys())
    return [None]


def _build_backup_engine(
    *,
    file: str,
    lockfile: str,
    var_files: tuple[str, ...],
    environment: str | None,
) -> tuple[Path, Secretfile, ResolvedEnvironmentContext, Lockfile, SyncEngine, str]:
    """Load the environment-aware manifest and engine used by backup workflows."""
    file_path, config, env_ctx = _load_secretfile_for_cli(
        file,
        var_files=var_files,
        environment=environment,
        lockfile=lockfile,
    )
    lock = Lockfile.load(env_ctx.resolved_lockfile)
    secretfile_content = file_path.read_text()
    engine = SyncEngine(
        config,
        lock,
        secretfile_path=file_path,
        secretfile_content=secretfile_content,
        hide_input=True,
        prompt_on_empty=False,
        sync_client="cli",
    )
    return file_path, config, env_ctx, lock, engine, secretfile_content


def _backup_entry_environment(entry: dict[str, Any], payload: dict[str, Any]) -> str | None:
    """Resolve the environment label for a backup entry, including legacy payloads."""
    value = entry.get("environment")
    if value is not None:
        return str(value) if value else None
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    meta_environment = meta.get("environment")
    if meta_environment:
        return str(meta_environment)
    environments = meta.get("environments")
    if isinstance(environments, list) and len(environments) == 1:
        only = environments[0]
        if isinstance(only, dict) and only.get("name"):
            return str(only["name"])
    return None


def _enforce_get_sandbox_policy() -> None:
    """Block ``get`` in sandbox mode unless explicitly overridden."""
    if not _env_flag("SZ_SANDBOX"):
        return
    if _env_flag("SZ_ALLOW_GET_IN_SANDBOX"):
        return
    raise click.ClickException(
        "secretzero get is blocked in sandbox mode (SZ_SANDBOX=true). "
        "Set SZ_ALLOW_GET_IN_SANDBOX=true to override intentionally."
    )


def _parse_get_args(raw_args: tuple[str, ...]) -> dict[str, Any]:
    """Parse repeatable KEY=VALUE args for ``secretzero get``."""
    parsed: dict[str, Any] = {}
    for item in raw_args:
        if "=" not in item:
            raise click.ClickException(f"Invalid --arg '{item}'. Expected KEY=VALUE format.")
        key, raw_value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise click.ClickException(f"Invalid --arg '{item}'. KEY cannot be empty.")
        raw_value = raw_value.strip()
        try:
            parsed[key] = json.loads(raw_value)
        except json.JSONDecodeError:
            parsed[key] = raw_value
    return parsed


@main.command()
@click.option(
    "--detailed",
    is_flag=True,
    help="Include runtime and environment details.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "yaml"]),
    default="text",
    show_default=True,
    help="Output format.",
)
def version(detailed: bool, output_format: str) -> None:
    """Show installed SecretZero version information."""
    payload: dict[str, Any] = {
        "name": "secretzero",
        "version": __version__,
        "website": "https://secret0.com",
    }
    if detailed:
        payload.update(
            {
                "python_version": platform.python_version(),
                "platform": platform.platform(),
                "executable": sys.executable,
                "manifest_spec_version": SECRETFILE_MANIFEST_SPEC_VERSION,
            }
        )

    if output_format == "json":
        click.echo(json.dumps(payload, indent=2))
        return
    if output_format == "yaml":
        click.echo(yaml.safe_dump(payload, sort_keys=False).strip())
        return

    if detailed:
        table = Table(title="SecretZero Version", box=box.ROUNDED)
        table.add_column("Field", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")
        for key, value in payload.items():
            table.add_row(key, str(value))
        console.print(table)
    else:
        console.print(
            f"SecretZero version [green]{__version__}[/green] ([link={payload['website']}]{payload['website']}[/link])"
        )


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
    template = """# yaml-language-server: $schema=https://github.com/zloeber/SecretZero/raw/refs/heads/main/Secretfile.schema.json
# Secretfile.yml
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
@_environment_option
def init(file: str, install: bool, dry_run: bool, environment: str | None) -> None:
    """Initialize project by checking and installing provider dependencies.

    This command reads your Secretfile, identifies configured providers,
    and checks if the required libraries are installed. It can optionally
    install missing dependencies automatically.
    """
    import subprocess
    import sys

    try:
        file_path, config, _ = _load_secretfile_for_cli(file, environment=environment)
    except Exception as e:
        console.print(f"[red]Error loading Secretfile:[/red] {e}")
        raise click.Abort()

    # Look up required packages from provider registry
    from secretzero.providers.registry import GLOBAL_PROVIDER_REGISTRY

    console.print("[bold]Checking provider dependencies...[/bold]\n")

    missing = []
    installed = []

    for provider_name, provider_config in config.providers.items():
        # When ``kind:`` is omitted, use the provider alias (e.g. providers.aws → aws).
        provider_kind = provider_config.kind or provider_name

        provider_class = GLOBAL_PROVIDER_REGISTRY.get_provider_class(provider_kind)
        if provider_class is not None and provider_class.required_package is not None:
            import_name, install_name = provider_class.required_package

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
@click.option(
    "--strict-manifest-plaintext",
    is_flag=True,
    help=(
        "Fail if static-like secrets embed literal value/default material in the manifest "
        "(agent-safe authoring)."
    ),
)
@_environment_option
def validate(
    file: str,
    var_files: tuple[str, ...],
    output_format: str,
    strict_manifest_plaintext: bool,
    environment: str | None,
) -> None:
    """Validate Secretfile configuration.

    This command checks the syntax and structure of your Secretfile.yml,
    ensuring all required fields are present and properly formatted.

    Variable files (.szvar) can be specified for validation to ensure the
    final merged configuration is valid.
    """
    file_path = Path(file)
    config: Secretfile | None = None
    env_ctx: ResolvedEnvironmentContext | None = None
    plaintext_violations: list[str] = []
    try:
        file_path, config, env_ctx = _load_secretfile_for_cli(
            file,
            var_files=var_files,
            environment=environment,
        )
        is_valid = True
        message = "Secretfile is valid"
        if config is not None and (strict_manifest_plaintext or env_sz_agent_mode()):
            plaintext_violations = list_manifest_plaintext_violations(config)
            if plaintext_violations:
                is_valid = False
                message = "Manifest contains plaintext static-like payloads"
    except Exception as exc:
        is_valid = False
        message = str(exc)

    if output_format == "json":
        result: dict = {"valid": is_valid, "message": message, "file": str(file_path)}
        if plaintext_violations:
            result["plaintext_violations"] = plaintext_violations
        if is_valid and config is not None:
            result["config"] = {
                "manifest_spec_version": SECRETFILE_MANIFEST_SPEC_VERSION,
                "variables_count": len(config.variables),
                "providers_count": len(config.providers),
                "secrets_count": len(config.secrets),
                "templates_count": len(config.templates),
            }
        click.echo(json.dumps(result, indent=2))
        if not is_valid:
            sys.exit(EXIT_VALIDATION_ERROR)
        return

    console.print(f"Validating: {file_path}")
    if env_ctx and env_ctx.resolved_var_files:
        console.print(
            "With variable file(s): " + ", ".join(str(vf) for vf in env_ctx.resolved_var_files)
        )

    if plaintext_violations:
        console.print(f"[red]✗[/red] {message}")
        for row in plaintext_violations:
            console.print(f"  • {row}")
        sys.exit(EXIT_VALIDATION_ERROR)

    if is_valid and config is not None:
        console.print(f"[green]✓[/green] {message}")

        # Show summary of configuration
        console.print("\n[bold]Configuration Summary:[/bold]")
        console.print(f"  Manifest spec version: {SECRETFILE_MANIFEST_SPEC_VERSION}")
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
@_environment_option
def render(
    file: str,
    var_files: tuple[str, ...],
    format: str,
    output: str | None,
    environment: str | None,
) -> None:
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
    if spill_guard_active():
        msg = (
            "secretzero render is blocked while SZ_AGENT_MODE or SZ_AGENT is enabled "
            "(full interpolated manifest may contain secret material). "
            "Unset those variables, or use metadata-only commands such as "
            "'secretzero validate' and 'secretzero list secrets'."
        )
        console.print(f"[red]Error:[/red] {msg}")
        raise click.Abort()
    try:
        file_path, config, _ = _load_secretfile_for_cli(
            file,
            var_files=var_files,
            environment=environment,
        )
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
    "--detailed",
    is_flag=True,
    help="Show full status report (previous default text output).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (text or json)",
)
@_environment_option
def status(
    file: str,
    lockfile: str,
    verbose: bool,
    detailed: bool,
    output_format: str,
    environment: str | None,
) -> None:
    """Show synchronization status of secrets and targets.

    This command displays which secrets have been generated and synced to their
    configured targets, along with timestamps and rotation information.
    """
    try:
        file_path, config, env_ctx = _load_secretfile_for_cli(
            file,
            environment=environment,
            lockfile=lockfile,
        )
    except Exception as e:
        if output_format == "json":
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error loading Secretfile:[/red] {e}")
        sys.exit(EXIT_CONFIG_ERROR)

    lockfile_path = env_ctx.resolved_lockfile
    secretfile_content = file_path.read_text()

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

    sync_engine = SyncEngine(config, lock)
    sync_readiness = sync_engine.preflight_sync_readiness()

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
            "provider_identity": collect_provider_identity_rows(config),
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
            "sync_readiness": sync_readiness,
        }
        click.echo(json.dumps(result, indent=2, default=str))
        return

    if verbose and not detailed:
        detailed = True

    if detailed:
        console.print("[bold]Secret Synchronization Status:[/bold]\n")
        _print_provider_identity_panel(config)
        _print_sync_readiness_panel(sync_readiness)

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
            console.print(
                "[dim]Run 'secretzero sync' to generate secrets and create lockfile[/dim]"
            )
        return

    _show_status_compact(
        config=config, lock=lock, lockfile_path=lockfile_path, sync_readiness=sync_readiness
    )


def _show_status_compact(
    config, lock: Lockfile, lockfile_path: Path, sync_readiness: dict[str, Any]
) -> None:
    """Show compact, relation-focused status mapping for secrets and targets."""
    console.print("[bold]Secret -> Target Status[/bold]")
    console.print(
        "[dim]Legend: [green]→ synced[/green], [red]→ pending/drift[/red], [yellow]→ unknown[/yellow][/dim]\n"
    )

    if not config.secrets:
        console.print("[dim]No secrets configured[/dim]")
        return

    provider_status = {
        row.get("alias", ""): row.get("status", "unknown")
        for row in sync_readiness.get("provider_identity", {}).get("rows", [])
    }
    provider_access = {
        str(item.get("provider") or ""): bool(item.get("ok"))
        for item in sync_readiness.get("target_access", {}).get("results", [])
    }

    for secret in config.secrets:
        secret_label = _compact_secret_label(secret)
        console.print(f"[bold cyan]{secret_label}[/bold cyan]")
        if not secret.targets:
            console.print("  [dim]└─ no targets configured[/dim]")
            console.print("  [dim]synced:0 pending:0 unknown:0[/dim]\n")
            continue

        state_counts = {"synced": 0, "pending": 0, "unknown": 0}
        for idx, target in enumerate(secret.targets):
            target_state = sync_state_for_secret_target(lock, secret.name, target)
            provider_state = provider_status.get(target.provider)
            arrow = _status_arrow_for_target(
                target_state, provider_state, provider_access.get(target.provider)
            )
            target_label = _compact_target_label(target)
            connector = "└─" if idx == len(secret.targets) - 1 else "├─"
            if target_state == "synced":
                state_counts["synced"] += 1
            elif provider_access.get(target.provider) is True or provider_state in {"ok", "local"}:
                state_counts["pending"] += 1
            else:
                state_counts["unknown"] += 1
            console.print(f"  {connector} {arrow} {target_label}")
        console.print(
            f"  [dim]synced:{state_counts['synced']} pending:{state_counts['pending']} unknown:{state_counts['unknown']}[/dim]\n"
        )
    console.print(
        f"\n[dim]Secrets: {len(config.secrets)} | Tracked lock entries: {len(lock.secrets)} | Lockfile: {lockfile_path}[/dim]"
    )


def _status_arrow_for_target(
    target_state: str, provider_identity_status: str | None, provider_access_ok: bool | None
) -> str:
    """Return color-coded arrow for compact status output."""
    if target_state == "synced":
        return "[green]→[/green]"
    if provider_access_ok is True:
        return "[red]→[/red]"
    if provider_identity_status in {"ok", "local"}:
        return "[red]→[/red]"
    return "[yellow]→[/yellow]"


def _compact_secret_label(secret) -> str:
    """Return compact secret label: <name> (<optional provider>/<type>)."""
    secret_provider = getattr(secret, "provider", None)
    if secret_provider:
        return f"{secret.name} ({secret_provider}/{secret.kind})"
    return f"{secret.name} ({secret.kind})"


def _compact_target_label(target) -> str:
    """Return compact target label: <provider>/<type> - <path>."""
    location_keys = (
        "path",
        "name",
        "secret_name",
        "variable_name",
        "credential_id",
        "repository",
        "project_id",
        "vault_name",
        "namespace",
    )
    location = next(
        (str(target.config.get(k)) for k in location_keys if target.config.get(k)), "unconfigured"
    )
    annotations: list[str] = []
    if target.kind == "file":
        if target.config.get("key"):
            annotations.append(f"key={target.config.get('key')}")
        template_var = target.config.get("template_variable") or target.config.get("template_var")
        if template_var:
            annotations.append(f"template={template_var}")
    suffix = f" ({', '.join(annotations)})" if annotations else ""
    return f"{target.provider}/{target.kind} - {location}{suffix}"


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
    from secretzero.policy import ProviderIdentityPolicy

    schema_json = Secretfile.model_json_schema()
    pi_json = ProviderIdentityPolicy.model_json_schema()
    defs = schema_json.setdefault("$defs", {})
    for key, val in pi_json.get("$defs", {}).items():
        defs[key] = val
    defs["ProviderIdentityPolicy"] = {k: v for k, v in pi_json.items() if k != "$defs"}
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
    from secretzero.providers.registry import GLOBAL_PROVIDER_REGISTRY

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

            # Create provider instance with the profile via registry
            provider = None
            try:
                provider_class = GLOBAL_PROVIDER_REGISTRY.get_provider_class(provider_kind)
                if provider_class is None:
                    console.print(f"[yellow]Unknown provider type: {provider_kind}[/yellow]")
                    continue
                config_dict = provider_config.model_dump()
                config_dict["auth"]["selected_profile"] = profile_name
                provider = provider_class(name=provider_name, config=config_dict)
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
@_environment_option
def test(file: str, include_profiles: bool, verbose: bool, environment: str | None) -> None:
    """Test provider connectivity and authentication.

    This command validates that all configured providers can be authenticated
    and accessed successfully. Use --include-profiles to also test each
    defined authentication profile for providers that support them.
    Use --verbose to see detailed error information when tests fail.
    """
    try:
        _file_path, config, _ = _load_secretfile_for_cli(file, environment=environment)
    except Exception as e:
        console.print(f"[red]Error loading Secretfile:[/red] {e}")
        raise click.Abort()

    console.print("[bold]Testing Provider Connectivity:[/bold]\n")

    if not config.providers:
        console.print("[dim]No providers configured[/dim]")
        return

    from secretzero.providers.registry import GLOBAL_PROVIDER_REGISTRY

    all_passed = True
    for provider_name, provider_config in config.providers.items():
        console.print(f"  • {provider_name}: ", end="")

        # Determine provider type - provider_config is a Provider model
        provider_kind = provider_config.kind if provider_config.kind else provider_name

        # Handle special "local" provider
        if provider_kind == "local":
            console.print("[green]✓ Local provider (always available)[/green]")
            continue

        # Look up the provider class from the registry
        provider_class = GLOBAL_PROVIDER_REGISTRY.get_provider_class(provider_kind)
        if provider_class is None:
            console.print(f"[yellow]Unknown provider type: {provider_kind}[/yellow]")
            all_passed = False
            continue

        # Create provider instance
        provider = None
        try:
            config_dict = provider_config.model_dump()
            provider = provider_class(name=provider_name, config=config_dict)
        except ImportError:
            pkg_info = provider_class.required_package
            pkg_label = pkg_info[0] if pkg_info else provider_kind
            console.print(f"[yellow]{pkg_label} not installed[/yellow]")
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


# ---------------------------------------------------------------------------
# auth group – interactive authentication helpers
# ---------------------------------------------------------------------------


@main.group()
def auth() -> None:
    """Authenticate with providers interactively.

    Use ``auth login`` to start an interactive OAuth device flow for a
    supported provider, and ``auth status`` to inspect the current token.
    """
    pass


@auth.command("login")
@click.option(
    "--provider",
    "-p",
    required=True,
    help="Provider to authenticate with (e.g. github)",
)
@click.option(
    "--client-id",
    required=True,
    help="OAuth App client ID registered with the provider",
)
@click.option(
    "--scopes",
    "-s",
    default=None,
    help="Comma-separated OAuth scopes (default: provider-specific)",
)
@click.option(
    "--no-browser",
    is_flag=True,
    help="Don't open the browser automatically",
)
@click.option(
    "--save-to",
    type=click.Path(),
    default=None,
    help="Write the token to a file (e.g. .env). Format: KEY=VALUE",
)
@click.option(
    "--env-var",
    default=None,
    help="Environment variable name used when writing to --save-to (default: provider-specific)",
)
def auth_login(
    provider: str,
    client_id: str,
    scopes: str | None,
    no_browser: bool,
    save_to: str | None,
    env_var: str | None,
) -> None:
    """Log in to a provider using the OAuth device flow.

    Starts the OAuth 2.0 Device Authorization Grant.  You will be shown a
    one-time code and a URL to visit in your browser.  After authorizing,
    the CLI receives an access token.

    \b
    Examples:
      secretzero auth login --provider github --client-id Iv1.abc123
      secretzero auth login -p github --client-id Iv1.abc123 --scopes repo,workflow
      secretzero auth login -p github --client-id Iv1.abc123 --save-to .env
    """
    if _is_non_interactive():
        console.print(
            "[red]Error:[/red] 'auth login' requires interactive input "
            "and cannot be used with --non-interactive."
        )
        sys.exit(EXIT_AUTH_FAILURE)
    _auth_login_impl(provider, client_id, scopes, no_browser, save_to, env_var)


def _auth_login_impl(
    provider_name: str,
    client_id: str,
    scopes_csv: str | None,
    no_browser: bool,
    save_to: str | None,
    env_var: str | None,
) -> None:
    """Implementation for ``auth login`` (extracted for testability)."""
    from secretzero.providers.registry import GLOBAL_PROVIDER_REGISTRY

    # --- Resolve provider class -------------------------------------------
    provider_class = GLOBAL_PROVIDER_REGISTRY.get_provider_class(provider_name)
    if provider_class is None:
        console.print(f"[red]Unknown provider:[/red] {provider_name}")
        console.print("Run [bold]secretzero providers[/bold] to see available types.")
        raise click.Abort()

    # --- Ensure the provider supports device flow -------------------------
    auth_methods = provider_class.auth_methods or {}
    if "oauth_device" not in auth_methods:
        console.print(
            f"[red]Provider '{provider_name}' does not support interactive OAuth login.[/red]"
        )
        console.print(f"Supported auth methods: {', '.join(auth_methods.keys()) or 'none'}")
        raise click.Abort()

    # --- Parse scopes -----------------------------------------------------
    scope_list: list[str] | None = None
    if scopes_csv:
        scope_list = [s.strip() for s in scopes_csv.split(",") if s.strip()]

    # --- Create an auth instance and run the device flow ------------------
    auth_cls = provider_class.auth_class
    if auth_cls is None:
        console.print(f"[red]Provider '{provider_name}' has no auth class configured.[/red]")
        raise click.Abort()

    auth_instance = auth_cls({})

    console.print(
        f"\n[bold]Authenticating with {provider_class.display_name or provider_name}…[/bold]\n"
    )

    def _on_user_code(
        user_code: str,
        verification_uri: str,
        verification_uri_complete: str | None,
    ) -> None:
        console.print("  Open your browser and visit:")
        url = verification_uri_complete or verification_uri
        console.print(f"    [bold cyan]{url}[/bold cyan]\n")
        console.print(f"  Then enter the code: [bold yellow]{user_code}[/bold yellow]\n")
        console.print("[dim]  Waiting for authorization…[/dim]")

    try:
        result = auth_instance.authenticate_device_flow(
            client_id=client_id,
            scopes=scope_list,
            open_browser=not no_browser,
            on_user_code=_on_user_code,
        )
    except RuntimeError as exc:
        console.print(f"\n[red]Authentication failed:[/red] {exc}")
        sys.exit(EXIT_UNKNOWN_ERROR)

    # --- Success ----------------------------------------------------------
    token = result["access_token"]
    granted_scopes = result.get("scope", "")
    console.print("\n[green]✓ Authentication successful![/green]")
    if granted_scopes:
        console.print(f"  Scopes: {granted_scopes}")

    # Determine env-var name
    default_env_var = getattr(auth_cls, "ENV_TOKEN", "TOKEN")
    var_name = env_var or default_env_var

    # --- Optionally persist to file ---------------------------------------
    if save_to:
        _save_token_to_file(save_to, var_name, token)
    else:
        console.print(f"\n  Token (set as [bold]{var_name}[/bold]):")
        console.print(f"  [dim]{token[:8]}{'*' * 20}[/dim]")
        console.print(
            f"\n[dim]  Tip: use --save-to .env to persist, or export {var_name}=<token>[/dim]"
        )


def _save_token_to_file(path: str, var_name: str, token: str) -> None:
    """Append or overwrite a KEY=VALUE entry in a dotenv-style file."""
    from pathlib import Path as _Path

    target = _Path(path)
    lines: list[str] = []
    replaced = False

    if target.exists():
        for line in target.read_text().splitlines():
            if line.startswith(f"{var_name}="):
                lines.append(f"{var_name}={token}")
                replaced = True
            else:
                lines.append(line)

    if not replaced:
        lines.append(f"{var_name}={token}")

    target.write_text("\n".join(lines) + "\n")
    console.print(f"  Token written to [bold]{path}[/bold] as {var_name}")


@auth.command("status")
@click.option(
    "--provider",
    "-p",
    required=True,
    help="Provider to check token status for (e.g. github)",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
def auth_status(provider: str, output_format: str) -> None:
    """Show information about the current authentication token.

    Inspects the token found in the provider's expected environment variable
    (e.g. ``GITHUB_TOKEN``) and displays user, scopes, and token type.

    \b
    Examples:
      secretzero auth status --provider github
      secretzero auth status -p github --format json
    """
    _auth_status_impl(provider, output_format)


def _auth_status_impl(provider_name: str, output_format: str) -> None:
    """Implementation for ``auth status``."""
    from secretzero.providers.registry import GLOBAL_PROVIDER_REGISTRY

    provider_class = GLOBAL_PROVIDER_REGISTRY.get_provider_class(provider_name)
    if provider_class is None:
        console.print(f"[red]Unknown provider:[/red] {provider_name}")
        raise click.Abort()

    auth_cls = provider_class.auth_class
    if auth_cls is None:
        console.print(f"[red]Provider '{provider_name}' has no auth class.[/red]")
        raise click.Abort()

    auth_instance = auth_cls({})

    try:
        info = auth_instance.get_token_info()
    except RuntimeError as exc:
        console.print(f"[red]Could not retrieve token info:[/red] {exc}")
        sys.exit(EXIT_UNKNOWN_ERROR)

    if output_format == "json":
        click.echo(json.dumps(info, indent=2))
        return

    console.print(
        f"[bold]Token status for {provider_class.display_name or provider_name}:[/bold]\n"
    )
    for key, value in info.items():
        if isinstance(value, dict):
            console.print(f"  {key}:")
            for k, v in value.items():
                console.print(f"    {k}: {v}")
        elif isinstance(value, (tuple, set)) or type(value).__name__ == "list":
            console.print(f"  {key}: {', '.join(str(v) for v in value)}")
        else:
            console.print(f"  {key}: {value}")


# ---------------------------------------------------------------------------
# providers – list/inspect provider types
# ---------------------------------------------------------------------------


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
    from secretzero.providers.registry import GLOBAL_PROVIDER_REGISTRY

    console.print("[bold]Available Provider Types:[/bold]\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Provider", style="green")
    table.add_column("Description")
    table.add_column("Auth Methods")

    # Build info from the registry + class metadata
    for prov_type in sorted(GLOBAL_PROVIDER_REGISTRY.list_provider_types()):
        provider_class = GLOBAL_PROVIDER_REGISTRY.get_provider_class(prov_type)
        if provider_class is not None:
            desc = provider_class.display_name or provider_class.description or ""
            auth = (
                ", ".join(provider_class.auth_methods.keys()) if provider_class.auth_methods else ""
            )
        else:
            desc = prov_type.title()
            auth = ""
        table.add_row(prov_type, desc, auth)

    # Always include "local" even if not in registry
    if "local" not in [t for t in GLOBAL_PROVIDER_REGISTRY.list_provider_types()]:
        table.add_row("local", "Local filesystem", "none")

    console.print(table)

    if not verbose:
        console.print(
            "\nUse [bold]secretzero providers --provider <type> --verbose[/bold] for detailed configuration options"
        )


def _show_provider_details(provider_name: str, target_name: str | None, verbose: bool) -> None:
    """Show detailed information about a specific provider and optionally a target type."""
    from secretzero.providers.registry import GLOBAL_PROVIDER_REGISTRY

    provider_class = GLOBAL_PROVIDER_REGISTRY.get_provider_class(provider_name)

    # --- Local filesystem fallback (no provider class) ---
    local_fallback: dict[str, Any] = {
        "description": "Local filesystem",
        "auth_methods": {"none": "No authentication required"},
        "config_options": {"base_path": "Base directory for files (default: .)"},
        "config_example": "providers:\n  local:\n    kind: local\n    config: {}",
        "target_details": {
            "file": {
                "description": "Local File",
                "config": {
                    "path": "File path to store secret",
                    "format": "File format: dotenv, json, yaml, toml, or tfvars (default: dotenv; .tfvars paths infer tfvars)",
                    "merge": "Whether to merge with existing file content (default: true)",
                    "mode": "File permissions as octal (default: 0600)",
                },
                "example": (
                    "targets:\n"
                    "  - provider: local\n"
                    "    kind: file\n"
                    "    config:\n"
                    "      path: ./secrets.env\n"
                    "      format: dotenv\n"
                    "      mode: '0600'"
                ),
            }
        },
    }

    if provider_class is None and provider_name != "local":
        console.print(f"[red]Unknown provider:[/red] {provider_name}")
        console.print("\nRun 'secretzero providers' to see available providers")
        return

    # Resolve metadata from class or local fallback
    if provider_class is not None:
        td = provider_class.target_details or {}
        auth = provider_class.auth_methods or {}
        config_opts = provider_class.config_options or {}
        config_ex = provider_class.config_example or ""
        desc = provider_class.display_name or provider_class.description or provider_name.title()
    else:
        td = local_fallback["target_details"]
        auth = local_fallback["auth_methods"]
        config_opts = local_fallback["config_options"]
        config_ex = local_fallback["config_example"]
        desc = local_fallback["description"]

    if target_name:
        # Show details for a specific target type
        if target_name in td:
            target_info = td[target_name]
            console.print(f"[bold]Target Type: {target_name}[/bold]\n")
            console.print(f"[cyan]Provider:[/cyan] {provider_name}")
            console.print(f"[cyan]Description:[/cyan] {target_info.get('description', '')}\n")

            console.print("[cyan]Configuration Options:[/cyan]")
            for option, option_desc in target_info.get("config", {}).items():
                console.print(f"  • {option}: {option_desc}")

            console.print("\n[cyan]Example:[/cyan]")
            console.print(f"[dim]{target_info.get('example', '')}[/dim]")
        else:
            console.print(
                f"[red]Unknown target type:[/red] {target_name} for provider {provider_name}"
            )
            console.print(
                f"\nRun [bold]secretzero providers --provider {provider_name}[/bold] to see available targets"
            )
        return

    # Show provider overview
    console.print(f"[bold]Provider: {provider_name}[/bold]\n")
    console.print(f"[cyan]Description:[/cyan] {desc}\n")

    console.print("[cyan]Authentication Methods:[/cyan]")
    for auth_method, auth_desc in auth.items():
        console.print(f"  • [green]{auth_method}[/green]: {auth_desc}")

    console.print("\n[cyan]Configuration Options:[/cyan]")
    for option, option_desc in config_opts.items():
        console.print(f"  • {option}: {option_desc}")

    console.print("\n[cyan]Example:[/cyan]")
    console.print(f"[dim]{config_ex}[/dim]")

    if verbose:
        console.print("\n[cyan]Target Types for this Provider:[/cyan]")
        for target_type in td:
            console.print(
                f"  • [green]{target_type}[/green] - "
                f"[dim]use [bold]secretzero providers --provider {provider_name} --target {target_type}[/bold] for details[/dim]"
            )


def _cli_force_targets_map(
    config: Any,
    secret_names: tuple[str, ...],
    force_target_args: tuple[str, ...],
) -> dict[str, frozenset[str]] | None:
    """Build ``force_targets`` for :meth:`SyncEngine.sync`; validate target IDs."""
    if not force_target_args:
        return None
    from secretzero.sync import SyncEngine

    if len(secret_names) != 1:
        raise click.BadParameter(
            "--force-target requires exactly one --secret (use -s once)",
        )
    name = secret_names[0]
    sec = next((s for s in config.secrets if s.name == name), None)
    if sec is None:
        raise click.BadParameter(f"Secret {name!r} not found in Secretfile")
    allowed = {SyncEngine._build_target_id(t) for t in sec.targets}
    bad = [ft for ft in force_target_args if ft not in allowed]
    if bad:
        opts = ", ".join(sorted(allowed)) or "(none)"
        raise click.BadParameter(
            f"Unknown --force-target {bad[0]!r} for secret {name!r}. Valid: {opts}"
        )
    return {name: frozenset(force_target_args)}


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
    "--environment",
    "-e",
    type=str,
    default=None,
    help="Named environment profile from Secretfile.environments.profiles",
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
@click.option(
    "--refresh/--no-refresh",
    default=True,
    help=(
        "Refresh lockfile target validity right before sync "
        "(default: enabled; use --no-refresh to opt out)"
    ),
)
@click.option(
    "--force-target",
    "force_targets",
    multiple=True,
    help=(
        "Re-push the current secret value to these target IDs only (repeatable). "
        "Target IDs match the lockfile (e.g. local/file/.env, github/github_secret/…). "
        "Requires exactly one --secret. Use when multiple targets exist and at least one is already synced."
    ),
)
def sync(
    file: str,
    lockfile: str,
    var_files: tuple[str, ...],
    environment: str | None,
    dry_run: bool,
    plan: bool,
    show_input: bool,
    no_prompt: bool,
    secrets: tuple[str, ...],
    output_format: str,
    clean: bool,
    refresh: bool,
    force_targets: tuple[str, ...],
) -> None:
    """Generate and synchronize secrets to targets.

    When the global ``--non-interactive`` flag is set, interactive prompts are
    automatically disabled (equivalent to ``--no-prompt``).

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

        # Re-push to one target when several exist and others are already synced
        secretzero sync -s api_key --force-target local/file/.env.production

        # Preview plan before applying
        secretzero sync --plan

        # Machine-readable plan output
        secretzero sync --plan --format json

        # Opt out of automatic pre-sync refresh
        secretzero sync --no-refresh
    """
    # --plan implies --dry-run
    if plan:
        dry_run = True

    # --non-interactive forces prompts off
    if _is_non_interactive():
        no_prompt = True

    file_path = Path(file)

    runtime_lockfile = _runtime_lockfile_override(file, lockfile)
    runtime_var_file_paths = [Path(vf) for vf in var_files] if var_files else None

    loader = ConfigLoader()

    # Load base config first so environment profiles can be resolved safely.
    try:
        base_config = loader.load_file(file_path)
        env_ctx = resolve_environment_context(
            secretfile=base_config,
            secretfile_path=file_path,
            environment=_effective_environment(environment),
            runtime_var_files=runtime_var_file_paths,
            runtime_lockfile=runtime_lockfile,
        )
        config = loader.load_file(file_path, var_files=env_ctx.resolved_var_files or None)
        config = apply_target_profile(config, env_ctx.resolved_target_profile)
    except Exception as e:
        if output_format == "json":
            click.echo(json.dumps({"error": str(e), "exit_code": EXIT_CONFIG_ERROR}))
        else:
            console.print(f"[red]Error loading Secretfile:[/red] {e}")
        sys.exit(EXIT_CONFIG_ERROR)
    lockfile_path = env_ctx.resolved_lockfile

    # Read secretfile content for change detection
    secretfile_content = file_path.read_text()

    # Load lockfile
    lock = Lockfile.load(lockfile_path)

    # Determine active variable context
    active_var_files = env_ctx.resolved_var_files or []
    active_variables = dict(config.variables or {})

    # Detect variable context changes relative to lockfile
    variable_context_changed = False
    if active_var_files or active_variables:
        variable_context_changed = lock.variable_context_changed(active_var_files, active_variables)

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

    # Warn if the variable context changed compared to the last sync
    if variable_context_changed and output_format == "text":
        console.print(
            "[yellow]⚠ Variable context has changed since the last sync for this lockfile.[/yellow]"
        )

    if output_format == "text" and env_ctx.selected_environment:
        console.print(
            f"[dim]Environment:[/dim] {env_ctx.selected_environment}  "
            f"[dim]Lockfile:[/dim] {lockfile_path}"
        )
        if lock.secretfile and lock.secretfile.var_files:
            prev_files = ", ".join(lock.secretfile.var_files)
            current_files = ", ".join(vf.name for vf in active_var_files) or "[none]"
            console.print(f"  Previous var files: {prev_files}")
            console.print(f"  Current  var files: {current_files}")
        console.print(
            "  Existing lockfile entries from previous contexts will not block syncing new targets.\n"
            "  Consider using [cyan]--lockfile[/cyan] per environment or [cyan]secretzero sync --clean[/cyan] "
            "to remove unused entries."
        )

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

    provider_identity_rows = collect_provider_identity_rows(config)
    if output_format == "text":
        _print_provider_identity_panel(config, provider_identity_rows)

    if dry_run and output_format == "text":
        if plan:
            console.print("[cyan]PLAN:[/cyan] Showing execution plan without applying changes\n")
        else:
            console.print("[yellow]DRY RUN:[/yellow] No changes will be made\n")

    # Prepare secret name filter
    secret_names = list(secrets) if secrets else None
    force_targets_map: dict[str, frozenset[str]] | None = None
    if force_targets:
        force_targets_map = _cli_force_targets_map(config, secrets, force_targets)
    if force_targets_map is not None and not secret_names:
        raise click.BadParameter("--force-target requires --secret")

    if secret_names and output_format == "text":
        console.print(
            f"[bold]Synchronizing {len(secret_names)} secret(s):[/bold] {', '.join(secret_names)}\n"
        )
    elif output_format == "text" and not plan:
        console.print("[bold]Synchronizing secrets...[/bold]\n")

    try:
        results = engine.sync(
            dry_run=dry_run,
            secret_names=secret_names,
            ignore_foreign_context_targets=variable_context_changed,
            force_targets=force_targets_map,
            refresh=refresh,
        )

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
                "variable_context_changed": variable_context_changed,
                "provider_identity": provider_identity_rows,
                "selected_environment": env_ctx.selected_environment,
                "resolved_var_files": [str(p) for p in env_ctx.resolved_var_files],
                "resolved_lockfile": str(lockfile_path),
                "resolved_target_profile": env_ctx.resolved_target_profile,
            }
            if plan_details is not None:
                json_result["plan_details"] = plan_details
            if clean:
                json_result["cleaned"] = cleaned_entries
            if refresh:
                json_result["refresh"] = results.get("refresh")
            if _should_emit_gitnexus_sidecar(dry_run, results, cleaned_entries):
                gn = _try_emit_gitnexus_sidecar(file_path, config, echo=False)
                if gn is not None:
                    json_result["gitnexus"] = gn
            click.echo(json.dumps(json_result, indent=2, default=str))
            # Mirror text mode: persist lockfile after sync (JSON path used to return here without saving).
            if not dry_run:
                if results["secrets_stored"] > 0 or cleaned_entries:
                    lock.track_variable_context(active_var_files, dict(config.variables or {}))
                    lock.save(lockfile_path)
                elif results.get("secretfile_changed") is not None:
                    lock.track_variable_context(active_var_files, dict(config.variables or {}))
                    lock.save(lockfile_path)
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
        refresh_result = results.get("refresh") if refresh else None
        if refresh_result and refresh_result.get("mismatch_targets", 0) > 0:
            action_word = "would prune" if dry_run else "pruned"
            console.print(
                "[yellow]⚠ Refreshed lockfile targets:[/yellow] "
                f"{action_word} {refresh_result['mismatch_targets']} stale target entr"
                f"{'y' if refresh_result['mismatch_targets'] == 1 else 'ies'} "
                f"across {refresh_result['mismatch_secrets']} secret"
                f"{'' if refresh_result['mismatch_secrets'] == 1 else 's'}"
            )

        # Show if secretfile changed
        if results.get("secretfile_changed"):
            console.print("\n[yellow]⚠ Secretfile has changed since last sync[/yellow]")
        # Show variable context change (text mode) if not already warned above
        if variable_context_changed and output_format == "text":
            console.print(
                "[yellow]⚠ Variable context for this Secretfile has changed since last sync.[/yellow]"
            )

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
                lock.track_variable_context(active_var_files, dict(config.variables or {}))
                lock.save(lockfile_path)
                console.print(f"\n[green]✓[/green] Lockfile saved: {lockfile_path}")
            else:
                # Check if lockfile was modified (secretfile tracking)
                if results.get("secretfile_changed") is not None:
                    # Lockfile exists and secretfile was tracked
                    lock.track_variable_context(active_var_files, dict(config.variables or {}))
                    lock.save(lockfile_path)
                    console.print(
                        f"\n[dim]Lockfile updated (secretfile tracking only): {lockfile_path}[/dim]"
                    )
                else:
                    console.print(
                        "\n[yellow]⚠[/yellow]  Lockfile not saved (no secrets stored successfully)"
                    )

            if _should_emit_gitnexus_sidecar(dry_run, results, cleaned_entries):
                _try_emit_gitnexus_sidecar(file_path, config, echo=True)

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
    help="Show orphaned lockfile entries without removing them.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (text or json)",
)
@_environment_option
def clean(
    file: str,
    lockfile: str,
    dry_run: bool,
    output_format: str,
    environment: str | None,
) -> None:
    """Remove orphaned lockfile entries without running sync."""
    try:
        _file_path, config, env_ctx = _load_secretfile_for_cli(
            file,
            environment=environment,
            lockfile=lockfile,
        )
    except Exception as e:
        if output_format == "json":
            click.echo(json.dumps({"error": str(e), "exit_code": EXIT_CONFIG_ERROR}))
        else:
            console.print(f"[red]Error loading Secretfile:[/red] {e}")
        sys.exit(EXIT_CONFIG_ERROR)

    lockfile_path = env_ctx.resolved_lockfile
    lock = Lockfile.load(lockfile_path)
    orphaned_entries = _clean_lockfile_orphans(config, lock, dry_run=dry_run)

    if not dry_run and orphaned_entries:
        lock.save(lockfile_path)

    if output_format == "json":
        click.echo(
            json.dumps(
                {
                    "cleaned": len(orphaned_entries),
                    "orphaned_entries": orphaned_entries,
                    "dry_run": dry_run,
                    "lockfile": str(lockfile_path),
                },
                indent=2,
            )
        )
        return

    if orphaned_entries:
        action = "Would remove" if dry_run else "Removed"
        console.print(
            f"[cyan]🗑 {action}[/cyan] {len(orphaned_entries)} orphaned lockfile entr"
            f"{'y' if len(orphaned_entries) == 1 else 'ies'}"
        )
        for secret_name in orphaned_entries:
            console.print(f"  • {secret_name}")
    else:
        console.print("[green]✓[/green] No orphaned lockfile entries found.")

    if dry_run:
        console.print("[yellow]Dry run only; no changes written.[/yellow]")


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
@_environment_option
def show(
    secret_name: str | None,
    file: str,
    lockfile: str,
    detailed: bool,
    environment: str | None,
) -> None:
    """Show information about secrets.

    If no secret name is provided, displays a list of all secrets in the
    manifest file. If a secret name is provided, displays detailed metadata
    about that specific secret, including its configuration, generation status,
    and target storage locations.

    Use --detailed to show complete configuration and sub-fields.
    """
    try:
        file_path, config, env_ctx = _load_secretfile_for_cli(
            file,
            environment=environment,
            lockfile=lockfile,
        )
    except Exception as e:
        console.print(f"[red]Error loading Secretfile:[/red] {e}")
        raise click.Abort()

    # Load lockfile
    lockfile_path = env_ctx.resolved_lockfile
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
@click.option("--provider", required=True, help="Configured provider alias from Secretfile")
@click.option("--secret-id", required=True, help="Provider secret identifier/path")
@click.option(
    "--method",
    help="Provider retrieval method (default: retrieve_secret, fallback: get_secret)",
)
@click.option(
    "--arg",
    "method_args",
    multiple=True,
    help="Method argument in KEY=VALUE form (repeatable). VALUE may be JSON.",
)
@click.option(
    "--reveal",
    is_flag=True,
    help="Include secret value in output when provider supports plaintext retrieval.",
)
@click.option(
    "--policy-check/--no-policy-check",
    default=True,
    help="Validate policy violations before retrieval.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (text or json)",
)
@_environment_option
def get(
    file: str,
    lockfile: str,
    provider: str,
    secret_id: str,
    method: str | None,
    method_args: tuple[str, ...],
    reveal: bool,
    policy_check: bool,
    output_format: str,
    environment: str | None,
) -> None:
    """Retrieve a secret value through provider bundle methods.

    This command is sandbox-protected:
    - ``SZ_SANDBOX=true`` blocks retrieval.
    - ``SZ_ALLOW_GET_IN_SANDBOX=true`` explicitly overrides the block.

    By default, output is metadata-only. Pass ``--reveal`` to include plaintext
    when the provider API returns a revealable value.

    ``--reveal`` is blocked when ``SZ_AGENT`` or ``SZ_AGENT_MODE`` is enabled.
    """
    if reveal and spill_guard_active():
        msg = (
            "secretzero get --reveal is blocked while SZ_AGENT or SZ_AGENT_MODE is enabled "
            "(prevents plaintext from entering agent logs)."
        )
        if output_format == "json":
            click.echo(json.dumps({"error": msg, "exit_code": EXIT_CONFIG_ERROR}))
        else:
            console.print(f"[red]Error:[/red] {msg}")
        sys.exit(EXIT_CONFIG_ERROR)
    try:
        _enforce_get_sandbox_policy()
        file_path, config, env_ctx = _load_secretfile_for_cli(
            file,
            environment=environment,
            lockfile=lockfile,
        )
    except click.ClickException as e:
        if output_format == "json":
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error:[/red] {e}")
        sys.exit(EXIT_VALIDATION_ERROR)
    except Exception as e:
        if output_format == "json":
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error loading Secretfile:[/red] {e}")
        sys.exit(EXIT_CONFIG_ERROR)

    lockfile_path = env_ctx.resolved_lockfile
    lock = Lockfile.load(lockfile_path) if lockfile_path.exists() else Lockfile()

    if policy_check:
        policy_engine = PolicyEngine(config)
        violations = policy_engine.validate_all(lock)
        blocking = [v for v in violations if v.severity == "error"]
        if blocking:
            payload = {
                "error": "Policy blocked get command execution",
                "violations": [
                    {
                        "policy": v.policy_name,
                        "secret": v.secret_name,
                        "severity": v.severity,
                        "message": v.message,
                        "suggestion": v.suggestion,
                    }
                    for v in blocking
                ],
            }
            if output_format == "json":
                click.echo(json.dumps(payload, indent=2))
            else:
                console.print("[red]Error:[/red] Policy blocked get command execution")
                for item in payload["violations"]:
                    console.print(f"  • {item['secret']}: {item['message']}")
            sys.exit(EXIT_VALIDATION_ERROR)

    engine = SyncEngine(config, lock)
    parsed_args = _parse_get_args(method_args)

    try:
        result = engine.get_provider_secret(
            provider_name=provider,
            secret_id=secret_id,
            method_name=method,
            method_args=parsed_args,
        )
    except Exception as e:
        if output_format == "json":
            click.echo(json.dumps({"error": str(e)}, indent=2))
        else:
            console.print(f"[red]Error:[/red] {e}")
        sys.exit(EXIT_UNKNOWN_ERROR)

    response: dict[str, Any] = {
        "provider": result["provider"],
        "secret_id": secret_id,
        "method": result["method"],
        "retrieved": result["retrieved"],
        "revealable": result["revealable"],
        "notes": result.get("notes"),
        "revealed": bool(reveal and result["revealable"]),
    }
    if reveal and result["revealable"]:
        response["value"] = result["value"]

    gn_summary = _try_emit_gitnexus_sidecar(file_path, config, echo=False)
    if gn_summary is not None:
        response["gitnexus"] = gn_summary

    if output_format == "json":
        click.echo(json.dumps(response, indent=2))
        return

    if gn_summary and not gn_summary.get("skipped"):
        p = gn_summary.get("secrets_overlay")
        if p:
            console.print(f"[dim]GitNexus overlay:[/dim] {p}")

    console.print("[bold]Secret Retrieval[/bold]")
    console.print(f"  Provider: [cyan]{response['provider']}[/cyan]")
    console.print(f"  Method: [cyan]{response['method']}[/cyan]")
    console.print(f"  Secret ID: [cyan]{secret_id}[/cyan]")
    console.print(f"  Revealable: [cyan]{response['revealable']}[/cyan]")
    if response.get("notes"):
        console.print(f"  Notes: [yellow]{response['notes']}[/yellow]")
    if reveal and result["revealable"]:
        console.print("\n[bold]Value[/bold]")
        console.print(result["value"])
    elif not reveal:
        console.print(
            "\n[dim]Value not shown. Use --reveal to print plaintext when provider allows it.[/dim]"
        )
    else:
        console.print(
            "\n[yellow]Provider does not return plaintext for this secret; showing metadata only.[/yellow]"
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
@click.option(
    "--secret",
    "-s",
    "secrets",
    multiple=True,
    help="Rotate only this secret by name (repeat for multiple secrets)",
)
@click.option(
    "--trigger-reindex",
    is_flag=True,
    help=(
        "After a successful rotation, run `gitnexus analyze --skills` in the Secretfile directory "
        "(requires GitNexus CLI on PATH)."
    ),
)
@click.argument("secret_name", required=False)
@_environment_option
def rotate(
    file: str,
    lockfile: str,
    force: bool,
    dry_run: bool,
    show_input: bool,
    output_format: str,
    secrets: tuple[str, ...],
    trigger_reindex: bool,
    secret_name: str | None,
    environment: str | None,
) -> None:
    """Rotate secrets based on rotation policies.

    This command checks which secrets need rotation and regenerates them.
    Respects rotation_period settings and one_time flags.

    Limit to specific secrets with ``--secret`` / ``-s`` (repeatable) or a single
    optional ``SECRET_NAME`` positional argument — not both.
    """
    try:
        file_path, config, env_ctx = _load_secretfile_for_cli(
            file,
            environment=environment,
            lockfile=lockfile,
        )
    except Exception as e:
        if output_format == "json":
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error loading Secretfile:[/red] {e}")
        sys.exit(EXIT_CONFIG_ERROR)

    # Load lockfile
    lockfile_path = env_ctx.resolved_lockfile
    lock = Lockfile.load(lockfile_path)

    if output_format == "text":
        console.print("[bold]Checking secrets for rotation...[/bold]\n")

    if secrets and secret_name:
        msg = "Use either --secret/-s or SECRET_NAME positional argument, not both."
        if output_format == "json":
            click.echo(json.dumps({"error": msg}))
        else:
            console.print(f"[red]Error:[/red] {msg}")
        sys.exit(EXIT_VALIDATION_ERROR)

    # Filter secrets (--secret/-s, optional positional, or all)
    names_filter: list[str] | None = None
    if secrets:
        names_filter = list(dict.fromkeys(secrets))
    elif secret_name:
        names_filter = [secret_name]

    secrets_to_check = config.secrets
    if names_filter is not None:
        known = {s.name for s in config.secrets}
        missing = [n for n in names_filter if n not in known]
        if missing:
            miss = ", ".join(repr(n) for n in missing)
            if output_format == "json":
                click.echo(json.dumps({"error": f"Secret(s) not found in Secretfile: {miss}"}))
            else:
                console.print(f"[red]Error:[/red] Secret(s) not found in Secretfile: {miss}")
            sys.exit(EXIT_VALIDATION_ERROR)
        order = {n: i for i, n in enumerate(names_filter)}
        secrets_to_check = sorted(
            [s for s in config.secrets if s.name in order],
            key=lambda s: order[s.name],
        )

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

    secretfile_content = file_path.read_text()
    engine = SyncEngine(
        config,
        lock,
        secretfile_path=file_path,
        secretfile_content=secretfile_content,
        hide_input=not show_input,
    )

    # Filter secrets for rotation
    original_secrets = config.secrets
    config.secrets = secrets_to_rotate

    try:
        results = engine.sync(dry_run=False, force_rotation=True)

        if output_format == "json":
            payload: dict[str, Any] = {
                "dry_run": False,
                "secrets_rotated": results.get("secrets_generated", 0),
                "details": rotation_details,
                "errors": results.get("errors", []),
            }
            if (
                trigger_reindex
                and results.get("secrets_generated", 0) > 0
                and not results.get("errors")
            ):
                proc = run_gitnexus_analyze_skills(file_path.parent)
                payload["gitnexus_reindex"] = {
                    "returncode": proc.returncode,
                    "stdout": proc.stdout[-8000:] if proc.stdout else "",
                    "stderr": proc.stderr[-8000:] if proc.stderr else "",
                }
            click.echo(json.dumps(payload, indent=2))
        else:
            console.print(f"[green]✓[/green] Rotated {results['secrets_generated']} secrets")

            if results["errors"]:
                console.print("\n[red]Errors:[/red]")
                for error in results["errors"]:
                    console.print(f"  • {error}")

            if (
                trigger_reindex
                and results.get("secrets_generated", 0) > 0
                and not results.get("errors")
            ):
                proc = run_gitnexus_analyze_skills(file_path.parent)
                if proc.returncode == 0:
                    console.print(
                        "[dim]GitNexus re-index:[/dim] gitnexus analyze --skills completed"
                    )
                else:
                    console.print(
                        f"[yellow]GitNexus re-index exited {proc.returncode}[/yellow]"
                        + (f": {proc.stderr.strip()}" if proc.stderr else "")
                    )

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
@_environment_option
def policy(
    file: str,
    lockfile: str,
    fail_on_warning: bool,
    output_format: str,
    environment: str | None,
) -> None:
    """Check secrets against policy rules.

    This command validates secrets against rotation, compliance, and
    access control policies defined in the Secretfile.
    """
    try:
        _file_path, config, env_ctx = _load_secretfile_for_cli(
            file,
            environment=environment,
            lockfile=lockfile,
        )
    except Exception as e:
        if output_format == "json":
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error loading Secretfile:[/red] {e}")
        sys.exit(EXIT_CONFIG_ERROR)

    # Load lockfile
    lock = None
    lockfile_path = env_ctx.resolved_lockfile
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
@_environment_option
def drift(
    file: str,
    lockfile: str,
    output_format: str,
    secret_name: str | None,
    environment: str | None,
) -> None:
    """Detect drift between lockfile and actual targets.

    This command checks if secrets have been modified outside of
    SecretZero's control.
    """
    file_path = Path(file)
    effective_environment = _effective_environment(environment)
    try:
        file_path, _config, env_ctx = _load_secretfile_for_cli(
            file,
            environment=environment,
            lockfile=lockfile,
        )
    except Exception as e:
        if output_format == "json":
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error loading Secretfile:[/red] {e}")
        sys.exit(EXIT_CONFIG_ERROR)

    lockfile_path = env_ctx.resolved_lockfile

    if not lockfile_path.exists():
        if output_format == "json":
            click.echo(json.dumps({"error": f"Lockfile not found: {lockfile_path}"}))
        else:
            console.print(f"[red]Error:[/red] Lockfile not found: {lockfile_path}")
            console.print("Run 'secretzero sync' first to generate secrets")
        sys.exit(EXIT_CONFIG_ERROR)

    detector = DriftDetector(file_path, lockfile_path, environment=effective_environment)
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


@main.command("import")
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
    help="Path to .szvar variable file(s) to merge (repeatable)",
)
@click.option(
    "--environment",
    "-e",
    type=str,
    default=None,
    help="Named environment profile from Secretfile.environments.profiles",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be imported without updating the lockfile",
)
@click.option(
    "--check",
    is_flag=True,
    help="Report drift between lockfile and live targets only (no import)",
)
@click.option(
    "--fail-on-drift",
    is_flag=True,
    help="With --check, exit with a non-zero status when drift is detected",
)
@click.option(
    "--secret",
    "-s",
    "secrets",
    multiple=True,
    help="Import only these secrets (repeatable)",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (text or json)",
)
def lockfile_import_cmd(
    file: str,
    lockfile: str,
    var_files: tuple[str, ...],
    environment: str | None,
    dry_run: bool,
    check: bool,
    fail_on_drift: bool,
    secrets: tuple[str, ...],
    output_format: str,
) -> None:
    """Import pre-seeded values from targets into the lockfile (read-only on targets).

    Refreshes stale lockfile target IDs, then reads each secret from configured targets and
    updates lockfile hashes when values are consistent across targets. Use ``--check`` for a
    drift-only report (add ``--fail-on-drift`` for CI-style gating).
    """
    file_path = Path(file)
    runtime_lockfile = _runtime_lockfile_override(file, lockfile)
    runtime_var_file_paths = [Path(vf) for vf in var_files] if var_files else None
    loader = ConfigLoader()

    try:
        base_config = loader.load_file(file_path)
        env_ctx = resolve_environment_context(
            secretfile=base_config,
            secretfile_path=file_path,
            environment=_effective_environment(environment),
            runtime_var_files=runtime_var_file_paths,
            runtime_lockfile=runtime_lockfile,
        )
    except Exception as e:
        if output_format == "json":
            click.echo(json.dumps({"error": str(e), "exit_code": EXIT_CONFIG_ERROR}))
        else:
            console.print(f"[red]Error loading Secretfile:[/red] {e}")
        sys.exit(EXIT_CONFIG_ERROR)

    lockfile_path = env_ctx.resolved_lockfile

    if check:
        if not lockfile_path.exists():
            if output_format == "json":
                click.echo(json.dumps({"error": f"Lockfile not found: {lockfile_path}"}))
            else:
                console.print(f"[red]Error:[/red] Lockfile not found: {lockfile_path}")
            sys.exit(EXIT_CONFIG_ERROR)
        detector = DriftDetector(
            file_path,
            lockfile_path,
            environment=_effective_environment(environment),
            runtime_var_files=runtime_var_file_paths,
        )
        secret_name = secrets[0] if len(secrets) == 1 else None
        if len(secrets) > 1:
            if output_format == "json":
                click.echo(
                    json.dumps(
                        {
                            "error": "Only one --secret may be used with --check",
                            "exit_code": EXIT_VALIDATION_ERROR,
                        }
                    )
                )
            else:
                console.print("[red]Error:[/red] Only one --secret may be used with --check")
            sys.exit(EXIT_VALIDATION_ERROR)
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
            if fail_on_drift and drift_found:
                sys.exit(EXIT_DRIFT_DETECTED)
            return
        console.print("[bold]Drift check (import --check)[/bold]\n")
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
                "\n[yellow]Drift detected.[/yellow] "
                "Run [cyan]secretzero import[/cyan] to refresh the lockfile from targets, "
                "or [cyan]secretzero sync[/cyan] to remediate."
            )
            if fail_on_drift:
                sys.exit(EXIT_DRIFT_DETECTED)
        else:
            console.print("\n[green]No drift detected.[/green]")
        return

    try:
        config = loader.load_file(file_path, var_files=env_ctx.resolved_var_files or None)
        config = apply_target_profile(config, env_ctx.resolved_target_profile)
    except Exception as e:
        if output_format == "json":
            click.echo(json.dumps({"error": str(e), "exit_code": EXIT_CONFIG_ERROR}))
        else:
            console.print(f"[red]Error loading Secretfile:[/red] {e}")
        sys.exit(EXIT_CONFIG_ERROR)

    secretfile_content = file_path.read_text()
    lock = Lockfile.load(lockfile_path)
    active_var_files = env_ctx.resolved_var_files or []

    engine = SyncEngine(
        config,
        lock,
        secretfile_path=file_path,
        secretfile_content=secretfile_content,
        hide_input=True,
        prompt_on_empty=False,
        sync_client="cli",
    )
    secret_list = list(secrets) if secrets else None

    try:
        summary = run_lockfile_import(
            engine,
            secretfile=config,
            secretfile_path=file_path,
            secretfile_content=secretfile_content,
            secret_names=secret_list,
            active_var_files=active_var_files,
            dry_run=dry_run,
        )
    except Exception as e:
        if output_format == "json":
            click.echo(json.dumps({"error": str(e), "exit_code": EXIT_UNKNOWN_ERROR}))
        else:
            console.print(f"[red]Import failed:[/red] {e}")
        sys.exit(EXIT_UNKNOWN_ERROR)

    if not dry_run and lockfile_path:
        lock.save(lockfile_path)

    err_count = int(summary.get("errors") or 0)
    if output_format == "json":
        click.echo(json.dumps(summary, indent=2))
        if err_count:
            sys.exit(EXIT_VALIDATION_ERROR)
        return

    console.print("[bold]Lockfile import[/bold]\n")
    ref = summary.get("refresh") or {}
    console.print(
        f"  Refresh: checked_secrets={ref.get('checked_secrets', 0)}, "
        f"stale_secrets={ref.get('mismatch_secrets', 0)}, "
        f"stale_targets={ref.get('mismatch_targets', 0)}"
    )
    console.print(
        f"  Imported: {summary.get('imported', 0)}, updated: {summary.get('updated', 0)}, "
        f"unchanged: {summary.get('unchanged', 0)}, skipped: {summary.get('skipped', 0)}, "
        f"errors: {err_count}"
    )
    if summary.get("would_apply"):
        console.print(f"  [dim]Would apply (dry-run): {summary['would_apply']}[/dim]")
    for row in summary.get("details") or []:
        if not isinstance(row, dict):
            continue
        st = row.get("status")
        nm = row.get("secret")
        console.print(f"  - {nm}: {st}" + (f" ({row.get('detail')})" if row.get("detail") else ""))
        for f in row.get("fields") or []:
            if isinstance(f, dict):
                console.print(
                    f"      · {f.get('field')}: {f.get('status')}"
                    + (f" ({f.get('detail')})" if f.get("detail") else "")
                )
    if err_count:
        console.print(f"\n[red]Import finished with {err_count} error(s).[/red]")
        sys.exit(EXIT_VALIDATION_ERROR)
    console.print("\n[green]Import complete.[/green]")


@main.group("ingest")
def ingest_group() -> None:
    """Pre-seed lockfile hashes from on-disk secrets files (dotenv / json / yaml) without emitting values."""


@ingest_group.command("preseed")
@click.option(
    "--source",
    "-s",
    "source",
    required=True,
    type=click.Path(exists=True),
    help="Path to the secrets file on disk (must match a local file target path in the manifest)",
)
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
    help="Path to .szvar variable file(s) to merge (repeatable)",
)
@click.option(
    "--environment",
    "-e",
    type=str,
    default=None,
    help="Named environment profile from Secretfile.environments.profiles",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be imported without updating the lockfile",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format (text or json)",
)
def ingest_preseed_cmd(
    source: str,
    file: str,
    lockfile: str,
    var_files: tuple[str, ...],
    environment: str | None,
    dry_run: bool,
    output_format: str,
) -> None:
    """Import hashes for secrets whose local ``file`` target points at ``--source``.

    This is a focused alias for operators and agents: it resolves the manifest,
    finds every secret whose ``local/file`` target path matches the given file,
    then runs the same lockfile import engine used by ``secretzero import``.
    Secret values never appear on stdout (only status metadata / counts).
    """
    file_path = Path(file)
    source_path = Path(source).resolve()
    runtime_lockfile = _runtime_lockfile_override(file, lockfile)
    runtime_var_file_paths = [Path(vf) for vf in var_files] if var_files else None
    loader = ConfigLoader()

    try:
        base_config = loader.load_file(file_path)
        env_ctx = resolve_environment_context(
            secretfile=base_config,
            secretfile_path=file_path,
            environment=_effective_environment(environment),
            runtime_var_files=runtime_var_file_paths,
            runtime_lockfile=runtime_lockfile,
        )
        config = loader.load_file(file_path, var_files=env_ctx.resolved_var_files or None)
        config = apply_target_profile(config, env_ctx.resolved_target_profile)
    except Exception as e:
        if output_format == "json":
            click.echo(json.dumps({"error": str(e), "exit_code": EXIT_CONFIG_ERROR}))
        else:
            console.print(f"[red]Error loading Secretfile:[/red] {e}")
        sys.exit(EXIT_CONFIG_ERROR)

    lockfile_path = env_ctx.resolved_lockfile
    secretfile_content = file_path.read_text()
    lock = Lockfile.load(lockfile_path)
    active_var_files = env_ctx.resolved_var_files or []

    matched = secret_names_for_ingest_source(
        config, source=source_path, secretfile_dir=file_path.parent
    )
    match_meta = describe_ingest_source_match(
        config, source=source_path, secretfile_dir=file_path.parent
    )

    if not matched:
        msg = (
            f"No secrets reference local file target path {source_path} "
            f"(resolved from {source!r}). Add a local/file target whose config.path matches this file."
        )
        if output_format == "json":
            click.echo(
                json.dumps(
                    {"error": msg, "exit_code": EXIT_VALIDATION_ERROR, "ingest": match_meta},
                    indent=2,
                )
            )
        else:
            console.print(f"[red]Error:[/red] {msg}")
        sys.exit(EXIT_VALIDATION_ERROR)

    engine = SyncEngine(
        config,
        lock,
        secretfile_path=file_path,
        secretfile_content=secretfile_content,
        hide_input=True,
        prompt_on_empty=False,
        sync_client="cli",
    )

    try:
        summary = run_lockfile_import(
            engine,
            secretfile=config,
            secretfile_path=file_path,
            secretfile_content=secretfile_content,
            secret_names=matched,
            active_var_files=active_var_files,
            dry_run=dry_run,
        )
    except Exception as e:
        if output_format == "json":
            click.echo(json.dumps({"error": str(e), "exit_code": EXIT_UNKNOWN_ERROR}))
        else:
            console.print(f"[red]Ingest failed:[/red] {e}")
        sys.exit(EXIT_UNKNOWN_ERROR)

    if not dry_run and lockfile_path:
        lock.save(lockfile_path)

    err_count = int(summary.get("errors") or 0)
    if output_format == "json":
        out = dict(summary)
        out["ingest"] = match_meta
        click.echo(json.dumps(out, indent=2))
        if err_count:
            sys.exit(EXIT_VALIDATION_ERROR)
        return

    console.print("[bold]Ingest preseed[/bold]")
    console.print(f"  Source: [cyan]{source_path}[/cyan]")
    console.print(f"  Matched secrets: {', '.join(matched)}")
    ref = summary.get("refresh") or {}
    console.print(
        f"  Refresh: checked_secrets={ref.get('checked_secrets', 0)}, "
        f"stale_secrets={ref.get('mismatch_secrets', 0)}, "
        f"stale_targets={ref.get('mismatch_targets', 0)}"
    )
    console.print(
        f"  Imported: {summary.get('imported', 0)}, updated: {summary.get('updated', 0)}, "
        f"unchanged: {summary.get('unchanged', 0)}, skipped: {summary.get('skipped', 0)}, "
        f"errors: {err_count}"
    )
    if err_count:
        console.print(f"\n[red]Ingest finished with {err_count} error(s).[/red]")
        sys.exit(EXIT_VALIDATION_ERROR)
    console.print("\n[green]Ingest complete.[/green]")


@main.group("backup")
def backup_group() -> None:
    """Encrypted backup and restore for synced target values."""


@backup_group.command("create")
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=True),
    default="Secretfile.yml",
    help="Path to Secretfile",
)
@click.option(
    "--lockfile", "-l", type=click.Path(), default=".gitsecrets.lock", help="Path to lockfile"
)
@click.option(
    "--var-file",
    "-v",
    "var_files",
    type=click.Path(exists=True),
    multiple=True,
    help="Path to .szvar variable file(s) to merge (repeatable)",
)
@click.option(
    "--environment",
    "-e",
    type=str,
    default=None,
    help="Named environment profile from Secretfile.environments.profiles",
)
@click.option(
    "--secret", "-s", "secrets", multiple=True, help="Backup only these secrets (repeatable)"
)
@click.option(
    "--output",
    "-o",
    "output_file",
    type=click.Path(),
    default=None,
    help="Write backup payload to this file (default: stdout for plain, default file for encrypted)",
)
@click.option(
    "--encrypted",
    is_flag=True,
    help="Encrypt the backup payload with SOPS/AGE before writing it",
)
@click.option(
    "--age-recipient",
    "age_recipients",
    multiple=True,
    help="AGE recipient (repeatable). Overrides env/auto recipient resolution.",
)
@click.option(
    "--age-key-file",
    type=click.Path(exists=True),
    default=None,
    help="AGE private key file (used to derive recipient when --age-recipient is omitted)",
)
@click.option("--dry-run", is_flag=True, help="Show what would be backed up without writing files")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text")
def backup_create_cmd(
    file: str,
    lockfile: str,
    var_files: tuple[str, ...],
    environment: str | None,
    secrets: tuple[str, ...],
    output_file: str | None,
    encrypted: bool,
    age_recipients: tuple[str, ...],
    age_key_file: str | None,
    dry_run: bool,
    output_format: str,
) -> None:
    """Extract retrievable values from synced targets into a local backup payload."""
    if not encrypted and (age_recipients or age_key_file):
        msg = "--age-recipient and --age-key-file require --encrypted"
        if output_format == "json":
            click.echo(json.dumps({"error": msg, "exit_code": EXIT_CONFIG_ERROR}))
        else:
            console.print(f"[red]Error:[/red] {msg}")
        sys.exit(EXIT_CONFIG_ERROR)
    if not encrypted and spill_guard_active():
        msg = "Plain backup output is blocked while SZ_AGENT or SZ_AGENT_MODE is enabled; rerun with --encrypted."
        if output_format == "json":
            click.echo(json.dumps({"error": msg, "exit_code": EXIT_CONFIG_ERROR}))
        else:
            console.print(f"[red]Error:[/red] {msg}")
        sys.exit(EXIT_CONFIG_ERROR)

    file_path = Path(file)
    loader = ConfigLoader()
    try:
        base_config = loader.load_file(file_path)
        target_environments = _backup_target_environments(base_config, environment)
    except Exception as exc:
        if output_format == "json":
            click.echo(json.dumps({"error": str(exc), "exit_code": EXIT_CONFIG_ERROR}))
        else:
            console.print(f"[red]Error loading Secretfile:[/red] {exc}")
        sys.exit(EXIT_CONFIG_ERROR)

    backup_doc: dict[str, Any] = {
        "version": BACKUP_FORMAT_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "entries": [],
        "warnings": [],
        "secret_count": 0,
    }
    environment_meta: list[dict[str, Any]] = []
    try:
        for env_name in target_environments:
            _, config, env_ctx, _lock, engine, _secretfile_content = _build_backup_engine(
                file=file,
                lockfile=lockfile,
                var_files=var_files,
                environment=env_name,
            )
            env_doc = collect_backup_entries(
                engine=engine,
                secretfile=config,
                secret_names=list(secrets) if secrets else None,
            )
            env_label = env_ctx.selected_environment
            for entry in env_doc.get("entries") or []:
                entry["environment"] = env_label
            backup_doc["entries"].extend(env_doc.get("entries") or [])
            backup_doc["warnings"].extend(env_doc.get("warnings") or [])
            backup_doc["secret_count"] += int(env_doc.get("secret_count") or 0)
            environment_meta.append(
                {
                    "name": env_label,
                    "lockfile": str(env_ctx.resolved_lockfile),
                    "target_profile": env_ctx.resolved_target_profile,
                    "var_files": [str(path) for path in env_ctx.resolved_var_files or []],
                    "entry_count": len(env_doc.get("entries") or []),
                    "secret_count": int(env_doc.get("secret_count") or 0),
                }
            )
    except Exception as exc:
        if output_format == "json":
            click.echo(json.dumps({"error": str(exc), "exit_code": EXIT_CONFIG_ERROR}))
        else:
            console.print(f"[red]Backup create failed:[/red] {exc}")
        sys.exit(EXIT_CONFIG_ERROR)

    for idx, entry in enumerate(backup_doc.get("entries") or [], start=1):
        entry["entry_id"] = f"e{idx}"
    resolved_output_file = output_file
    if encrypted and not resolved_output_file:
        resolved_output_file = "secretzero.backup.enc.json"

    backup_doc["meta"] = {
        "format_version": BACKUP_FORMAT_VERSION,
        "secretfile": str(file_path),
        "environment": environment_meta[0]["name"] if len(environment_meta) == 1 else None,
        "environments": environment_meta,
        "entry_count": len(backup_doc.get("entries") or []),
        "encrypted": encrypted,
    }

    recipients: list[str] = []
    generated_key_file: Path | None = None
    if encrypted:
        try:
            recipients, generated_key_file = resolve_backup_age_recipients(
                output_file=Path(resolved_output_file),
                explicit_recipients=age_recipients,
                age_key_file=Path(age_key_file) if age_key_file else None,
            )
        except Exception as exc:
            if output_format == "json":
                click.echo(json.dumps({"error": str(exc), "exit_code": EXIT_CONFIG_ERROR}))
            else:
                console.print(f"[red]Backup recipient resolution failed:[/red] {exc}")
            sys.exit(EXIT_CONFIG_ERROR)
        backup_doc["meta"]["generated_age_key_file"] = (
            str(generated_key_file) if generated_key_file else None
        )
    else:
        backup_doc["meta"]["generated_age_key_file"] = None

    if not dry_run:
        if encrypted:
            try:
                encrypt_backup_document(
                    backup_doc=backup_doc,
                    output_file=Path(resolved_output_file),
                    recipients=recipients,
                    age_key_file=Path(age_key_file) if age_key_file else generated_key_file,
                )
            except Exception as exc:
                if output_format == "json":
                    click.echo(json.dumps({"error": str(exc), "exit_code": EXIT_UNKNOWN_ERROR}))
                else:
                    console.print(f"[red]Backup encryption failed:[/red] {exc}")
                sys.exit(EXIT_UNKNOWN_ERROR)
        else:
            plain_payload = json.dumps(backup_doc, indent=2)
            if resolved_output_file:
                Path(resolved_output_file).write_text(plain_payload, encoding="utf-8")
            else:
                click.echo(plain_payload)
                return

    summary = {
        "dry_run": dry_run,
        "encrypted": encrypted,
        "output_file": resolved_output_file,
        "entries": len(backup_doc.get("entries") or []),
        "warnings": backup_doc.get("warnings") or [],
        "generated_age_key_file": str(generated_key_file) if generated_key_file else None,
        "environments": [item["name"] for item in environment_meta],
    }
    if output_format == "json":
        click.echo(json.dumps(summary, indent=2))
        return
    console.print("[bold]Backup create[/bold]")
    console.print(f"  Entries: {summary['entries']}")
    if summary["output_file"]:
        console.print(
            f"  Output: {summary['output_file']}{' [dim](dry-run)[/dim]' if dry_run else ''}"
        )
    else:
        console.print("  Output: stdout")
    if generated_key_file:
        console.print(f"  [yellow]Generated age key:[/yellow] {generated_key_file}")
    for warning in summary["warnings"]:
        console.print(f"  [dim]- {warning}[/dim]")


@backup_group.command("restore")
@click.option(
    "--file",
    "-f",
    type=click.Path(),
    default="Secretfile.yml",
    help="Path to Secretfile (ignored when using --print)",
)
@click.option(
    "--lockfile",
    "-l",
    type=click.Path(),
    default=".gitsecrets.lock",
    help="Path to lockfile (ignored when using --print)",
)
@click.option(
    "--var-file",
    "-v",
    "var_files",
    type=click.Path(exists=True),
    multiple=True,
    help="Path to .szvar variable file(s) to merge (repeatable)",
)
@click.option(
    "--environment",
    "-e",
    type=str,
    default=None,
    help="Named environment profile from Secretfile.environments.profiles",
)
@click.option("--backup-file", type=click.Path(exists=True), required=True, help="Backup file path")
@click.option(
    "--encrypted",
    is_flag=True,
    help="Decrypt the backup file with SOPS/AGE before restoring",
)
@click.option(
    "--age-key-file",
    type=click.Path(exists=True),
    default=None,
    help="AGE private key file used for decryption (optional if env is configured)",
)
@click.option(
    "--entry",
    "only_entries",
    multiple=True,
    help="Restore only these entry IDs (repeatable, e.g. e3)",
)
@click.option(
    "--skip-entry",
    "skip_entries",
    multiple=True,
    help="Skip these entry IDs (repeatable, e.g. e2)",
)
@click.option(
    "--import-only",
    "import_only",
    multiple=True,
    help="Do not write target; only update lockfile for selector secret or secret@target_id",
)
@click.option(
    "--print",
    "print_values",
    is_flag=True,
    help="Print selected backup entries to stdout; skip targets, Secretfile, and lockfile updates",
)
@click.option(
    "--yes", "assume_yes", is_flag=True, help="Non-interactive: accept per-target restore prompts"
)
@click.option("--dry-run", is_flag=True, help="Show what would be restored")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text")
def backup_restore_cmd(
    file: str,
    lockfile: str,
    var_files: tuple[str, ...],
    environment: str | None,
    backup_file: str,
    encrypted: bool,
    age_key_file: str | None,
    only_entries: tuple[str, ...],
    skip_entries: tuple[str, ...],
    import_only: tuple[str, ...],
    print_values: bool,
    assume_yes: bool,
    dry_run: bool,
    output_format: str,
) -> None:
    """Restore backup entries to captured targets and update lockfiles (or --print values only)."""
    if print_values and dry_run:
        msg = "--print and --dry-run cannot be used together"
        if output_format == "json":
            click.echo(json.dumps({"error": msg, "exit_code": EXIT_CONFIG_ERROR}))
        else:
            console.print(f"[red]Error:[/red] {msg}")
        sys.exit(EXIT_CONFIG_ERROR)
    if print_values and import_only:
        msg = "--print cannot be combined with --import-only"
        if output_format == "json":
            click.echo(json.dumps({"error": msg, "exit_code": EXIT_CONFIG_ERROR}))
        else:
            console.print(f"[red]Error:[/red] {msg}")
        sys.exit(EXIT_CONFIG_ERROR)
    if print_values and spill_guard_active():
        msg = "Printing backup values to stdout is blocked while SZ_AGENT or SZ_AGENT_MODE is enabled."
        if output_format == "json":
            click.echo(json.dumps({"error": msg, "exit_code": EXIT_CONFIG_ERROR}))
        else:
            console.print(f"[red]Error:[/red] {msg}")
        sys.exit(EXIT_CONFIG_ERROR)
    if not print_values and not Path(file).is_file():
        if output_format == "json":
            click.echo(
                json.dumps(
                    {"error": f"Secretfile not found: {file}", "exit_code": EXIT_CONFIG_ERROR}
                )
            )
        else:
            console.print(f"[red]Error:[/red] Secretfile not found: {file}")
        sys.exit(EXIT_CONFIG_ERROR)
    try:
        payload = (
            decrypt_backup_document(
                backup_file=Path(backup_file),
                age_key_file=Path(age_key_file) if age_key_file else None,
            )
            if encrypted
            else load_plain_backup_document(backup_file=Path(backup_file))
        )
    except Exception as exc:
        if output_format == "json":
            click.echo(json.dumps({"error": str(exc), "exit_code": EXIT_AUTH_FAILURE}))
        else:
            action = "decrypt" if encrypted else "load"
            console.print(f"[red]Backup {action} failed:[/red] {exc}")
        sys.exit(EXIT_AUTH_FAILURE)

    raw_entries = payload.get("entries") or []
    if not isinstance(raw_entries, list):
        if output_format == "json":
            click.echo(
                json.dumps(
                    {"error": "Backup entries payload is invalid", "exit_code": EXIT_CONFIG_ERROR}
                )
            )
        else:
            console.print("[red]Error:[/red] Backup entries payload is invalid")
        sys.exit(EXIT_CONFIG_ERROR)

    entries: list[dict[str, Any]] = [e for e in raw_entries if isinstance(e, dict)]
    entry_groups: dict[str | None, list[dict[str, Any]]] = {}
    for entry in entries:
        entry_groups.setdefault(_backup_entry_environment(entry, payload), []).append(entry)

    requested_environment = _effective_environment(environment)
    if requested_environment is not None:
        target_environments = [requested_environment]
    elif any(name is not None for name in entry_groups):
        target_environments = sorted(name for name in entry_groups if name is not None)
    else:
        target_environments = [None]

    selected_ids = set(only_entries)
    skipped_ids = set(skip_entries)
    per_environment_candidates: dict[str | None, list[dict[str, Any]]] = {}
    for env_name in target_environments:
        env_entries = entry_groups.get(env_name, [])
        candidates: list[dict[str, Any]] = []
        for entry in env_entries:
            entry_id = str(entry.get("entry_id") or "")
            if selected_ids and entry_id not in selected_ids:
                continue
            if entry_id in skipped_ids:
                continue
            if not assume_yes and not print_values:
                selector = f"{entry.get('secret_ref')}@{entry.get('target_id')}"
                if not click.confirm(f"Restore {entry_id or selector}?", default=True):
                    continue
            candidates.append(entry)
        per_environment_candidates[env_name] = candidates

    if requested_environment is not None and not per_environment_candidates.get(
        requested_environment
    ):
        if output_format == "json":
            click.echo(
                json.dumps(
                    {
                        "error": f"No backup entries found for environment '{requested_environment}'",
                        "exit_code": EXIT_CONFIG_ERROR,
                    }
                )
            )
        else:
            console.print(
                f"[red]Error:[/red] No backup entries found for environment '{requested_environment}'"
            )
        sys.exit(EXIT_CONFIG_ERROR)

    if print_values:
        printed_rows: list[dict[str, Any]] = []
        for env_name in target_environments:
            for entry in per_environment_candidates.get(env_name, []):
                row = dict(entry)
                resolved_env: str | None = env_name if env_name is not None else None
                if resolved_env is None and row.get("environment") is not None:
                    resolved_env = str(row["environment"])
                row["environment"] = resolved_env
                printed_rows.append(row)
        if output_format == "json":
            click.echo(
                json.dumps(
                    {"printed": len(printed_rows), "entries": printed_rows},
                    indent=2,
                    default=str,
                )
            )
            return
        click.echo(
            click.style("Printing secret values from the backup to this terminal.", fg="yellow"),
            err=True,
        )
        table = Table(
            title="Backup entries",
            show_header=True,
            header_style="bold cyan",
            box=box.ROUNDED,
        )
        table.add_column("Entry")
        table.add_column("Environment")
        table.add_column("Secret")
        table.add_column("Target ID")
        table.add_column("Value")
        for row in printed_rows:
            raw_val = row.get("value")
            if isinstance(raw_val, (dict, list)):
                val_str = json.dumps(raw_val, default=str)
            else:
                val_str = "" if raw_val is None else str(raw_val)
            table.add_row(
                str(row.get("entry_id") or ""),
                str(row.get("environment") or ""),
                str(row.get("secret_ref") or ""),
                str(row.get("target_id") or ""),
                val_str,
            )
        console.print(table)
        return

    if dry_run:
        summary = {
            "dry_run": True,
            "selected": sum(len(items) for items in per_environment_candidates.values()),
            "available_entries": len(entries),
            "import_only_selectors": list(import_only),
            "environments": {
                (name or "default"): len(items)
                for name, items in per_environment_candidates.items()
            },
        }
        if output_format == "json":
            click.echo(json.dumps(summary, indent=2))
        else:
            console.print("[bold]Backup restore (dry-run)[/bold]")
            console.print(
                f"  Selected entries: {summary['selected']} / {summary['available_entries']}"
            )
        return

    totals = {
        "restored": 0,
        "imported_only": 0,
        "skipped": 0,
        "errors": [],
        "selected_entries": 0,
        "environments": [],
    }
    try:
        for env_name in target_environments:
            candidates = per_environment_candidates.get(env_name, [])
            if not candidates:
                continue
            (
                file_path,
                config,
                env_ctx,
                lock,
                engine,
                secretfile_content,
            ) = _build_backup_engine(
                file=file,
                lockfile=lockfile,
                var_files=var_files,
                environment=env_name,
            )
            result = restore_backup_entries(
                engine=engine,
                entries=candidates,
                import_only_selectors=set(import_only),
            )
            lock.track_secretfile(file_path, secretfile_content)
            lock.track_variable_context(
                env_ctx.resolved_var_files or [], dict(config.variables or {})
            )
            lock.save(env_ctx.resolved_lockfile)
            totals["restored"] += result["restored"]
            totals["imported_only"] += result["imported_only"]
            totals["skipped"] += result["skipped"]
            totals["errors"].extend(result["errors"])
            totals["selected_entries"] += len(candidates)
            totals["environments"].append(
                {
                    "name": env_ctx.selected_environment,
                    "lockfile": str(env_ctx.resolved_lockfile),
                    "selected_entries": len(candidates),
                }
            )
    except Exception as exc:
        if output_format == "json":
            click.echo(json.dumps({"error": str(exc), "exit_code": EXIT_UNKNOWN_ERROR}))
        else:
            console.print(f"[red]Backup restore failed:[/red] {exc}")
        sys.exit(EXIT_UNKNOWN_ERROR)

    summary = {
        "restored": totals["restored"],
        "imported_only": totals["imported_only"],
        "skipped": totals["skipped"],
        "errors": totals["errors"],
        "selected_entries": totals["selected_entries"],
        "environments": totals["environments"],
    }
    if output_format == "json":
        click.echo(json.dumps(summary, indent=2))
        if totals["errors"]:
            sys.exit(EXIT_VALIDATION_ERROR)
        return
    console.print("[bold]Backup restore[/bold]")
    console.print(
        f"  Restored: {summary['restored']}, import-only: {summary['imported_only']}, "
        f"skipped: {summary['skipped']}"
    )
    for err in summary["errors"]:
        console.print(f"  [red]- {err}[/red]")
    if summary["errors"]:
        sys.exit(EXIT_VALIDATION_ERROR)
    console.print("[green]Restore complete.[/green]")


main.add_command(backup_group, name="export")


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
    type=click.Choice(["flow", "detailed", "architecture", "destination"]),
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
@_environment_option
def graph(
    file: str,
    graph_type: str,
    output_format: str,
    output: str | None,
    environment: str | None,
) -> None:
    """Generate visual graph of Secretfile relationships.

    This command creates visual representations of your secret flows,
    showing generators, secrets, and their target destinations.

    Graph Types:

    - flow: Simple flowchart showing generator → secret → target relationships
    - detailed: Detailed view with configuration parameters
    - architecture: High-level system architecture view
    - destination: Destination-centric view grouped by target destinations and keys

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

        # Generate destination-centric overview
        secretzero graph --type destination

        # Save to file
        secretzero graph --output secretflow.md

        # Terminal-friendly summary
        secretzero graph --format terminal

        # Machine-readable JSON graph
        secretzero graph --format json
    """
    try:
        file_path, config, _ = _load_secretfile_for_cli(file, environment=environment)
        if output_format == "json":
            # Build machine-readable graph
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
            secretfile=config,
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


@main.group("list")
def list_group() -> None:
    """List secrets, providers, targets, or variables from a Secretfile.

    Named ``list_group`` so the built-in ``list`` remains available in this module
    (a function named ``list`` would shadow it and break ``list(...)`` calls below).
    """
    pass


@list_group.command("secrets")
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
@_environment_option
def list_secrets(
    file: str,
    output_format: str,
    name_filter: str | None,
    environment: str | None,
) -> None:
    """List all secrets defined in the Secretfile."""
    try:
        _file_path, config, _ = _load_secretfile_for_cli(file, environment=environment)
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


@list_group.command("providers")
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
@_environment_option
def list_providers(file: str, output_format: str, environment: str | None) -> None:
    """List all providers configured in the Secretfile."""
    try:
        _file_path, config, _ = _load_secretfile_for_cli(file, environment=environment)
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


@list_group.command("targets")
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
@_environment_option
def list_targets(file: str, output_format: str, environment: str | None) -> None:
    """List all target destinations across all secrets in the Secretfile."""
    try:
        _file_path, config, _ = _load_secretfile_for_cli(file, environment=environment)
    except Exception as e:
        if output_format == "json":
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error loading Secretfile:[/red] {e}")
        sys.exit(EXIT_CONFIG_ERROR)

    all_targets = []
    for secret in config.secrets:
        for t in secret.targets:
            cfg = t.config
            if spill_guard_active():
                cfg = _redact_target_config_for_spill_guard(dict(cfg))
            all_targets.append(
                {
                    "secret": secret.name,
                    "provider": t.provider,
                    "kind": t.kind,
                    "config": cfg,
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
        cfg = t["config"]
        if spill_guard_active():
            cfg_str = ", ".join(f"{k}={v}" for k, v in cfg.items() if not str(k).startswith("_"))
        else:
            cfg_str = ", ".join(f"{k}={v}" for k, v in cfg.items()) if cfg else "[dim]—[/dim]"
        if not cfg_str:
            cfg_str = "[dim]—[/dim]"
        table.add_row(t["secret"], t["provider"], t["kind"], cfg_str)

    console.print(table)
    console.print(f"\n[dim]Total: {len(all_targets)} target(s)[/dim]")


@list_group.command("variables")
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
@_environment_option
def list_variables(
    file: str,
    output_format: str,
    name_filter: str | None,
    environment: str | None,
) -> None:
    """List all variables defined in the Secretfile."""
    try:
        _file_path, config, _ = _load_secretfile_for_cli(file, environment=environment)
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
        if spill_guard_active():
            click.echo(
                json.dumps(
                    {
                        "variable_names": sorted(variables.keys()),
                        "total": len(variables),
                        "values_redacted": True,
                        "note": "Values omitted under SZ_AGENT or SZ_AGENT_MODE",
                    },
                    indent=2,
                )
            )
        else:
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
        if spill_guard_active():
            table.add_row(name, "[dim]omitted (SZ_AGENT or SZ_AGENT_MODE)[/dim]")
        else:
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
@click.option(
    "--all-keys",
    is_flag=True,
    help=(
        "For .env-style files, list every exported variable name (KEY=…), not only "
        "names matching secret-related keyword heuristics."
    ),
)
def detect(directory: str, output_format: str, output: str | None, all_keys: bool) -> None:
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
    if all_keys:
        secret_patterns = [
            (re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=", re.M), "dotenv"),
        ]

    # Directories that should be ignored when recursively scanning for env-style files.
    ignored_dir_parts = {
        ".git",
        "__pycache__",
        "venv",
        ".venv",
        "node_modules",
        ".terraform",
        "dist",
        "build",
    }

    def _should_ignore(path: Path) -> bool:
        """Return True if the path is inside an ignored directory."""
        try:
            parts = path.relative_to(dir_path).parts
        except ValueError:
            parts = path.parts
        return any(part in ignored_dir_parts for part in parts)

    found: dict[str, dict] = {}

    # Recursively scan for env-style files and secret-related config files.
    for path in dir_path.rglob("*"):
        if not path.is_file() or _should_ignore(path):
            continue

        name_lower = path.name.lower()
        is_env_file = name_lower.startswith(".env") or name_lower.endswith(".env")
        is_secret_file = name_lower.startswith(("secrets", "credentials"))

        if not (is_env_file or is_secret_file):
            continue

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
            continue

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
        payload: dict[str, Any] = {
            "detected": suggestions,
            "total": len(suggestions),
            "all_keys": all_keys,
        }
        click.echo(json.dumps(payload, indent=2))
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


@main.group("gitnexus")
def gitnexus_group() -> None:
    """GitNexus knowledge-graph bridge commands (optional GitNexus CLI on PATH)."""


@gitnexus_group.command("blast-radius")
@click.option(
    "--symbol",
    "-s",
    "symbol_fqn",
    required=True,
    help="Fully qualified symbol name to pass to GitNexus impact analysis",
)
@click.option(
    "--cwd",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    default=None,
    help="Repository root (default: current working directory)",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Print raw subprocess result as JSON",
)
def gitnexus_blast_radius_cmd(symbol_fqn: str, cwd: str | None, as_json: bool) -> None:
    """Run GitNexus impact analysis for blast-radius / security review."""
    root = Path(cwd).resolve() if cwd else Path.cwd()
    proc = run_gitnexus_blast_radius(symbol_fqn, cwd=root)
    if as_json:
        click.echo(
            json.dumps(
                {
                    "returncode": proc.returncode,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                    "hint_cli": format_blast_radius_cli(symbol_fqn, cwd=root),
                },
                indent=2,
            )
        )
        if proc.returncode == 127:
            sys.exit(EXIT_MISSING_DEPENDENCY)
        sys.exit(EXIT_SUCCESS if proc.returncode == 0 else EXIT_UNKNOWN_ERROR)
    if proc.returncode == 127:
        print_impact_suggestion(symbol_fqn)
        sys.exit(EXIT_MISSING_DEPENDENCY)
    out = (proc.stdout or "").strip() or (proc.stderr or "").strip()
    if out:
        console.print(out)
    else:
        console.print("[dim](no output from gitnexus)[/dim]")
    sys.exit(EXIT_SUCCESS if proc.returncode == 0 else EXIT_UNKNOWN_ERROR)


# Register config, format, and provider CLI groups/commands
main.add_command(config_group)
main.add_command(format_command)
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
# Network web UI (manual secret seeding)
# ---------------------------------------------------------------------------


@main.command("web")
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
    "--environment",
    "-e",
    type=str,
    default=None,
    help="Named environment profile from Secretfile.environments.profiles",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview only; does not open the network web UI",
)
@click.option(
    "--host",
    default="0.0.0.0",  # nosec B104
    show_default=True,
    help="Address to bind (use 127.0.0.1 for local-only)",
)
@click.option(
    "--port",
    type=int,
    default=None,
    help="TCP port (default: random in agent web_port_min–web_port_max from Secretfile)",
)
@click.option(
    "--token",
    default=None,
    help="Bootstrap access token (default: generate randomly)",
)
@click.option(
    "--token-file",
    type=click.Path(exists=True),
    default=None,
    help="Read bootstrap token from file (whitespace trimmed); overrides --token",
)
@click.option(
    "--tls-cert",
    type=click.Path(exists=True),
    default=None,
    help="PEM TLS certificate for HTTPS",
)
@click.option(
    "--tls-key",
    type=click.Path(exists=True),
    default=None,
    help="PEM TLS private key for HTTPS",
)
@click.option(
    "--tls-self-signed",
    is_flag=True,
    help="Generate a short-lived self-signed certificate (requires cryptography)",
)
@click.option(
    "--tls-san",
    multiple=True,
    default=(),
    help="Extra Subject Alternative Name (hostname or IP); repeat for multiple (with --tls-self-signed)",
)
@click.option(
    "--timeout",
    type=float,
    default=3600.0,
    show_default=True,
    help="Seconds to wait before timing out if the UI is not shut down",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Show a structured sync debug log at the bottom of the dashboard (no secret values).",
)
def web_command(
    file: str,
    lockfile: str,
    var_files: tuple[str, ...],
    environment: str | None,
    dry_run: bool,
    host: str,
    port: int | None,
    token: str | None,
    token_file: str | None,
    tls_cert: str | None,
    tls_key: str | None,
    tls_self_signed: bool,
    tls_san: tuple[str, ...],
    timeout: float,
    debug: bool,
) -> None:
    """Serve an HTTPS-capable web UI to inspect the manifest, sync, and update secrets.

    Binds to all interfaces by default. Share the printed URL and bootstrap token
    out of band. For trusted transport use --tls-self-signed, your own --tls-cert
    / --tls-key, an SSH tunnel, or a reverse proxy with a real certificate.

    Use **Shut down** in the UI to stop the server; the CLI also saves the lockfile when the session ends.
    """
    import secrets as std_secrets

    from secretzero.agent import AgentSecretSynchronizer
    from secretzero.network_webui import run_network_blocking_web_session

    file_path = Path(file)
    runtime_lockfile = _runtime_lockfile_override(file, lockfile)
    runtime_var_file_paths = [Path(vf) for vf in var_files] if var_files else None
    loader = ConfigLoader()

    if tls_self_signed and (tls_cert or tls_key):
        console.print(
            "[red]Error:[/red] use either --tls-self-signed or --tls-cert/--tls-key, not both."
        )
        raise click.Abort()
    if (tls_cert or tls_key) and not (tls_cert and tls_key):
        console.print("[red]Error:[/red] --tls-cert and --tls-key must be provided together.")
        raise click.Abort()

    try:
        base_secretfile = loader.load_file(file_path)
        env_ctx = resolve_environment_context(
            secretfile=base_secretfile,
            secretfile_path=file_path,
            environment=_effective_environment(environment),
            runtime_var_files=runtime_var_file_paths,
            runtime_lockfile=runtime_lockfile,
        )
        secretfile = loader.load_file(file_path, var_files=env_ctx.resolved_var_files or None)
        secretfile = apply_target_profile(secretfile, env_ctx.resolved_target_profile)
    except Exception as exc:
        console.print(f"[red]Error loading Secretfile:[/red] {exc}")
        raise click.ClickException(str(exc)) from exc

    lockfile_path = env_ctx.resolved_lockfile
    secretfile_content = file_path.read_text()
    lock = Lockfile.load(lockfile_path)
    agent_cfg = secretfile.effective_agent_config()

    synchronizer = AgentSecretSynchronizer(
        secretfile,
        lock,
        dry_run=dry_run,
        secretfile_path=file_path,
        secretfile_content=secretfile_content,
    )

    try:
        synchronizer.sync(sz_agent=False)
    except Exception as exc:
        console.print(f"[red]Agent sync failed:[/red] {exc}")
        raise click.ClickException(str(exc)) from exc

    if dry_run:
        console.print(
            "[yellow]Skipping network web UI in --dry-run "
            "(remove --dry-run to start the server).[/yellow]"
        )
        return

    bootstrap = None
    if token_file:
        bootstrap = Path(token_file).read_text().strip()
    elif token:
        bootstrap = token.strip()
    if not bootstrap:
        bootstrap = std_secrets.token_urlsafe(32)

    tls_cert_path = Path(tls_cert) if tls_cert else None
    tls_key_path = Path(tls_key) if tls_key else None
    http_mode = not (tls_cert_path and tls_key_path) and not tls_self_signed

    console.print("[bold cyan]SecretZero network web[/bold cyan]")
    if env_ctx.selected_environment:
        console.print(
            f"[dim]Environment:[/dim] {env_ctx.selected_environment}  "
            f"[dim]Lockfile:[/dim] {lockfile_path}"
        )
    if http_mode:
        console.print(
            "[bold yellow]Warning:[/bold yellow] running in HTTP mode (no TLS). "
            "Use only on trusted networks or with an external TLS tunnel/proxy."
        )
    console.print(
        "[dim]Share the URL and bootstrap token while the server is running. "
        "The token works once; self-signed TLS shows a browser warning—verify the "
        "SPKI fingerprint if prompted.[/dim]\n"
    )

    def _on_ready(base_url: str, used_port: int, spki_fp: str | None) -> None:
        join = "&" if "?" in base_url else "?"
        access_url = f"{base_url.rstrip('/')}{join}access_token={quote(bootstrap, safe='')}"
        console.print(
            f"[bold]Listen[/bold]  {host}:{used_port}  (link uses 127.0.0.1 when host is 0.0.0.0)"
        )
        console.print(f"[bold]Bootstrap token[/bold]  {bootstrap}")
        console.print(f"[bold]Open[/bold]           {access_url}")
        if spki_fp:
            console.print(f"[bold]TLS SPKI SHA-256[/bold]  {spki_fp}")
        if debug:
            console.print(
                "[dim]Debug log panel is ON (structured sync summaries at the bottom of the dashboard).[/dim]"
            )

    try:
        _base_url, _used_port, _fp = run_network_blocking_web_session(
            secretfile=secretfile,
            lockfile=lock,
            lockfile_path=lockfile_path,
            secretfile_path=file_path,
            secretfile_content=secretfile_content,
            var_file_paths=env_ctx.resolved_var_files,
            runtime_var_file_paths=runtime_var_file_paths,
            runtime_lockfile=runtime_lockfile,
            environment=env_ctx.selected_environment,
            dry_run=dry_run,
            debug=debug,
            host=host,
            port=port,
            port_min=agent_cfg.web_port_min,
            port_max=agent_cfg.web_port_max,
            bootstrap_token=bootstrap,
            tls_certfile=tls_cert_path,
            tls_keyfile=tls_key_path,
            tls_self_signed=tls_self_signed,
            tls_extra_sans=[*tls_san],
            timeout=timeout,
            on_ready=_on_ready,
        )
    except TimeoutError as exc:
        raise click.ClickException(str(exc)) from exc

    console.print("[green]Web session ended.[/green]")

    if not dry_run:
        lock.save(lockfile_path)


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
    "--environment",
    "-e",
    type=str,
    default=None,
    help="Named environment profile from Secretfile.environments.profiles",
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
    help="Prompt for manual secrets interactively (CLI prompts; not used with --web)",
)
@click.option(
    "--web",
    is_flag=True,
    help="Collect manual secret values via a temporary localhost web form (Vector 2)",
)
@click.option(
    "--web-host",
    default="127.0.0.1",
    show_default=True,
    help="DEPRECATED: agent web mode always binds to 127.0.0.1 for safety",
)
@click.option(
    "--verbose",
    "-V",
    is_flag=True,
    help="Verbose logging for agent sync",
)
@click.option(
    "--refresh/--no-refresh",
    default=True,
    help=(
        "Refresh lockfile target validity right before sync "
        "(default: enabled; use --no-refresh to opt out)"
    ),
)
def agent_sync(
    file: str,
    lockfile: str,
    var_files: tuple[str, ...],
    environment: str | None,
    dry_run: bool,
    output_json: bool,
    interactive: bool,
    web: bool,
    web_host: str,
    verbose: bool,
    refresh: bool,
) -> None:
    """Agent-aware secret synchronisation with guided instructions.

    The ``--interactive`` flag is rejected when ``--non-interactive`` is set.

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

        # Secure local web form for manual values (never echoed to the agent)
        secretzero agent sync --web

        # Sync with variable file override
        secretzero agent sync --var-file dev.szvar

        # Opt out of automatic pre-sync refresh
        secretzero agent sync --no-refresh
    """
    import json as _json
    import logging

    from secretzero.agent import (
        AgentSecretSynchronizer,
        build_agent_sync_json_payload,
        env_sz_agent,
        resolve_resolved_mode_label,
    )
    from secretzero.agent_webui import run_blocking_web_agent_form

    if verbose:
        logging.basicConfig(level=logging.DEBUG)
        logging.getLogger("secretzero").setLevel(logging.DEBUG)

    # --non-interactive conflicts with --interactive
    if interactive and _is_non_interactive():
        console.print("[red]Error:[/red] --interactive cannot be used with --non-interactive.")
        sys.exit(EXIT_CONFIG_ERROR)

    file_path = Path(file)

    runtime_lockfile = _runtime_lockfile_override(file, lockfile)
    runtime_var_file_paths = [Path(vf) for vf in var_files] if var_files else None
    loader = ConfigLoader()

    try:
        base_secretfile = loader.load_file(file_path)
        env_ctx = resolve_environment_context(
            secretfile=base_secretfile,
            secretfile_path=file_path,
            environment=_effective_environment(environment),
            runtime_var_files=runtime_var_file_paths,
            runtime_lockfile=runtime_lockfile,
        )
        secretfile = loader.load_file(file_path, var_files=env_ctx.resolved_var_files or None)
        secretfile = apply_target_profile(secretfile, env_ctx.resolved_target_profile)
    except Exception as exc:
        console.print(f"[red]Error loading Secretfile:[/red] {exc}")
        raise click.ClickException(str(exc)) from exc

    lockfile_path = env_ctx.resolved_lockfile
    # Read secretfile content for change detection
    secretfile_content = file_path.read_text()

    # Load lockfile
    lock = Lockfile.load(lockfile_path)

    sz_agent = env_sz_agent()
    agent_cfg = secretfile.effective_agent_config()
    use_web = (web or agent_cfg.mode == AgentMode.WEB) and not sz_agent
    if sz_agent and web:
        console.print(
            "[yellow]Note:[/yellow] SZ_AGENT is set; --web is ignored (automation-only mode)."
        )
    if web and interactive:
        console.print(
            "[dim]Note: --web takes precedence over --interactive for collecting values.[/dim]"
        )
    if web and web_host != "127.0.0.1":
        console.print(
            "[yellow]Note:[/yellow] --web-host is deprecated for `agent sync`; "
            "Vector 2 now always binds to 127.0.0.1."
        )

    synchronizer = AgentSecretSynchronizer(
        secretfile,
        lock,
        dry_run=dry_run,
        secretfile_path=file_path,
        secretfile_content=secretfile_content,
    )

    try:
        result = synchronizer.sync(sz_agent=sz_agent, refresh=refresh)
    except Exception as exc:
        console.print(f"[red]Agent sync failed:[/red] {exc}")
        raise click.ClickException(str(exc)) from exc

    if use_web and result.pending_secrets and not dry_run:
        try:

            def _agent_web_on_ready(url: str) -> None:
                console.print(f"[cyan]Open the local web form to continue:[/cyan] {url}")
                console.print(
                    "[dim]Copy this exact URL to the operator (including scheme, host, port, and "
                    "path). Do not paste secret values into chat. After they submit the form once, "
                    "this helper stops the localhost server; if they abandon the flow, interrupt "
                    "this command or wait for it to time out.[/dim]"
                )

            result = run_blocking_web_agent_form(
                pending_secret_names=list(result.pending_secrets.keys()),
                secretfile=secretfile,
                lockfile=lock,
                lockfile_path=lockfile_path,
                secretfile_path=file_path,
                secretfile_content=secretfile_content,
                dry_run=dry_run,
                port_min=agent_cfg.web_port_min,
                port_max=agent_cfg.web_port_max,
                host="127.0.0.1",
                open_browser=not _is_non_interactive(),
                on_ready=_agent_web_on_ready,
            )
        except Exception as exc:
            console.print(f"[yellow]Web UI failed ({exc}); showing instructions instead.[/yellow]")
    elif use_web and result.pending_secrets and dry_run and not output_json:
        console.print("[dim]Skipping localhost web UI because --dry-run is set.[/dim]")

    # Save lockfile if not dry run
    if not dry_run:
        lock.save(lockfile_path)

    resolved = resolve_resolved_mode_label(secretfile, cli_web=web, sz_agent=sz_agent)

    if output_json:
        payload = build_agent_sync_json_payload(
            result,
            dry_run=dry_run,
            sz_agent=sz_agent,
            resolved_mode=resolved,
        )
        payload["selected_environment"] = env_ctx.selected_environment
        payload["resolved_var_files"] = [str(p) for p in env_ctx.resolved_var_files]
        payload["resolved_lockfile"] = str(lockfile_path)
        payload["resolved_target_profile"] = env_ctx.resolved_target_profile
        click.echo(_json.dumps(payload, indent=2, default=str))
        return

    _display_agent_sync_results(
        result,
        lock,
        interactive=interactive and not web,
        dry_run=dry_run,
    )


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
    from secretzero.agent_instructions_report import (
        instruction_entries_from_mapping,
        render_instruction_entries,
    )

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

    # Pending secrets with instructions (shared renderer with `agent instructions`)
    if result.pending_secrets:
        pending_entries = instruction_entries_from_mapping(result.pending_secrets)
        render_instruction_entries(
            pending_entries,
            console,
            detailed=False,
            header=(
                f"\n[bold yellow]\u23f3 {len(pending_entries)} secret(s) require manual "
                "intervention:[/bold yellow]"
            ),
        )

        if interactive:
            for entry in pending_entries:
                secret_name = entry.secret_name
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
    refresh_info = sync_results.get("refresh") if isinstance(sync_results, dict) else None
    if refresh_info and refresh_info.get("mismatch_targets", 0) > 0:
        action_word = "would prune" if dry_run else "pruned"
        console.print(
            "\n[yellow]⚠ Refreshed lockfile targets:[/yellow] "
            f"{action_word} {refresh_info['mismatch_targets']} stale target entr"
            f"{'y' if refresh_info['mismatch_targets'] == 1 else 'ies'} "
            f"across {refresh_info['mismatch_secrets']} secret"
            f"{'' if refresh_info['mismatch_secrets'] == 1 else 's'}"
        )
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


@agent.command("instructions")
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
    "--environment",
    "-e",
    type=str,
    default=None,
    help="Named environment profile from Secretfile.environments.profiles",
)
@click.option(
    "--secret",
    "-s",
    "secret_names",
    multiple=True,
    help="Limit output to specific secret name(s)",
)
@click.option(
    "--all",
    "show_all",
    is_flag=True,
    help="Show all secrets with agent_instructions (default: pending manual only)",
)
@click.option(
    "--detailed",
    is_flag=True,
    help="Include optional instruction metadata (prerequisites, tools, timing, docs)",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
def agent_instructions(
    file: str,
    lockfile: str,
    var_files: tuple[str, ...],
    environment: str | None,
    secret_names: tuple[str, ...],
    show_all: bool,
    detailed: bool,
    output_format: str,
) -> None:
    """Print concise agent instructions for manual secret acquisition.

    By default shows only secrets that still require manual input (not in the
    lockfile and not auto-syncable). Use ``--all`` to list every secret that
    defines ``agent_instructions`` in the manifest.

    Examples:

        secretzero agent instructions

        secretzero agent instructions --all --detailed

        secretzero agent instructions -s stripe_key --format json
    """
    import json as _json

    from secretzero.agent_instructions_report import (
        InstructionScope,
        build_instructions_json_payload,
        collect_instruction_entries,
        render_instructions_console,
    )

    try:
        _file_path, secretfile, env_ctx = _load_secretfile_for_cli(
            file,
            var_files=var_files,
            environment=environment,
            lockfile=lockfile,
        )
    except Exception as exc:
        if output_format == "json":
            click.echo(_json.dumps({"error": str(exc)}))
        else:
            console.print(f"[red]Error loading Secretfile:[/red] {exc}")
        sys.exit(EXIT_CONFIG_ERROR)

    lock = Lockfile.load(env_ctx.resolved_lockfile)
    scope = InstructionScope.ALL if show_all else InstructionScope.PENDING
    name_filter = frozenset(secret_names) if secret_names else None
    entries = collect_instruction_entries(
        secretfile,
        lock,
        scope=scope,
        secret_names=name_filter,
    )

    if output_format == "json":
        payload = build_instructions_json_payload(entries, scope=scope, detailed=detailed)
        click.echo(_json.dumps(payload, indent=2))
        return

    render_instructions_console(
        entries,
        console,
        detailed=detailed,
        scope=scope,
    )


def _agent_adopt_options(func: Any) -> Any:
    """Shared Click options for ``agent adopt`` and ``agent backup``."""
    func = click.option(
        "--target",
        type=click.Choice(["hermes", "openclaw"], case_sensitive=False),
        default=None,
        help="Agent runtime target (default: autodetect Hermes, then OpenClaw)",
    )(func)
    func = click.option(
        "--source-dir",
        type=click.Path(exists=True, file_okay=False, dir_okay=True),
        default=None,
        help="Agent install root to scan (default: autodetect for target)",
    )(func)
    func = click.option(
        "--output-dir",
        type=click.Path(file_okay=False, dir_okay=True),
        default=None,
        help="Write SecretZero env here (default: resolved source-dir)",
    )(func)
    func = click.option(
        "--template",
        is_flag=True,
        help="Write agent.env.template with discovered key names only",
    )(func)
    func = click.option(
        "--preseed-lockfile",
        is_flag=True,
        help="Hash present credentials into .gitsecrets.lock (no values emitted)",
    )(func)
    func = click.option("--dry-run", is_flag=True, help="Plan without writing files")(func)
    func = click.option(
        "--force",
        is_flag=True,
        help="Replace existing Secretfile instead of merging new secrets",
    )(func)
    func = click.option(
        "--format",
        "output_format",
        type=click.Choice(["text", "json"]),
        default="text",
        help="Output format",
    )(func)
    return func


@agent.command("list")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
def agent_list_cmd(output_format: str) -> None:
    """List detected agent installs and existing SecretZero environments.

    Read-only discovery for Hermes, OpenClaw, and future agent targets.
    Never reads or prints secret values.

    Examples:

        secretzero agent list

        secretzero agent list --format json
    """
    if output_format == "json":
        render_agent_list_json()
    else:
        render_agent_list_text(console)


@agent.command("adopt")
@_agent_adopt_options
def agent_adopt_cmd(
    target: str | None,
    source_dir: str | None,
    output_dir: str | None,
    template: bool,
    preseed_lockfile: bool,
    dry_run: bool,
    force: bool,
    output_format: str,
) -> None:
    """Bootstrap a SecretZero environment from a local agent install.

    Scans the agent home for **present** credentials (catalog-driven, metadata-only
    output), writes ``Secretfile.yml`` into ``--output-dir`` (default: agent home),
    and optionally preseeds the lockfile or emits safe templates.

    This is **not** ``secretzero backup create`` (encrypted value export). Use
    ``secretzero backup create --encrypted`` after adopt/sync for DR payloads.

    Examples:

        secretzero agent adopt

        secretzero agent adopt --target hermes --source-dir ~/.hermes

        secretzero agent adopt --output-dir ./agents/hermes --template --preseed-lockfile

        secretzero agent adopt --dry-run --format json
    """
    run_agent_adopt_command(
        target=target,
        source_dir=source_dir,
        output_dir=output_dir,
        template=template,
        preseed_lockfile=preseed_lockfile,
        dry_run=dry_run,
        force=force,
        output_format=output_format,
        console=console,
    )


@agent.command("backup")
@_agent_adopt_options
def agent_backup_cmd(
    target: str | None,
    source_dir: str | None,
    output_dir: str | None,
    template: bool,
    preseed_lockfile: bool,
    dry_run: bool,
    force: bool,
    output_format: str,
) -> None:
    """Alias for ``agent adopt`` (bootstrap SecretZero env from agent install).

    Prefer ``secretzero agent adopt`` in new automation. This alias exists for
    operator wording ("back up agent config into SecretZero").
    """
    run_agent_adopt_command(
        target=target,
        source_dir=source_dir,
        output_dir=output_dir,
        template=template,
        preseed_lockfile=preseed_lockfile,
        dry_run=dry_run,
        force=force,
        output_format=output_format,
        console=console,
    )


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
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed LLM prompts and responses (text/json output only)",
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
    verbose: bool,
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
    from secretzero.cli_config import get_effective_config
    from secretzero.discovery import DiscoveryAgent

    # Resolve effective config: defaults ← config.yml ← Secretfile config block
    secretfile_path = Path(path) / "Secretfile.yml"
    try:
        effective = get_effective_config(secretfile_path=secretfile_path)
        cli_cfg = effective.config
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
        effective_model: str | None = model
        if effective_model is None:
            llm_cfg = cli_cfg.llm.providers
            if effective_provider == "ollama":
                effective_model = llm_cfg.ollama.model
            elif effective_provider == "openai":
                effective_model = llm_cfg.openai.model
            elif effective_provider == "anthropic":
                effective_model = llm_cfg.anthropic.model
            elif effective_provider == "azure_openai":
                effective_model = llm_cfg.azure_openai.deployment or None

        if no_llm:
            console.print("  LLM analysis : [yellow]disabled (--no-llm)[/yellow]")
        else:
            if local_only:
                console.print(f"  LLM provider : [cyan]{effective_provider}[/cyan] (local-only)")
            else:
                console.print(f"  LLM provider : [cyan]{effective_provider}[/cyan]")
            if effective_model:
                console.print(f"  LLM model    : [cyan]{effective_model}[/cyan]")

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
            verbose=verbose,
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
            "llm_used": result.llm_provider is not None and not no_llm,
            "llm_provider": result.llm_provider,
            "llm_model": result.llm_model,
            "secrets": [
                {
                    "name": c.name,
                    "description": c.description,
                    "confidence": c.confidence,
                    "generator": c.suggested_generator,
                    "source_file": c.source_file,
                    "line": c.line_number,
                    "tags": c.tags,
                    "containing_symbol": c.containing_symbol,
                    "symbol_fqn": c.symbol_fqn,
                    "symbol_id": c.symbol_id,
                }
                for c in result.candidates
            ],
        }
        if verbose and result.llm_interactions:
            data["llm_interactions"] = result.llm_interactions
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


# ---------------------------------------------------------------------------
# scaffold-bundle – generate a provider bundle from a template
# ---------------------------------------------------------------------------


@main.command("scaffold-bundle")
@click.argument("name")
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default=".",
    help="Parent directory for the generated package (default: current directory)",
)
@click.option(
    "--with-target",
    "target_kinds",
    multiple=True,
    help="Target kind to include (can be repeated, e.g. --with-target my_secret)",
)
@click.option(
    "--with-generator",
    "generator_kinds",
    multiple=True,
    help="Generator kind to include (can be repeated, e.g. --with-generator my_token)",
)
@click.option(
    "--description",
    "provider_description",
    default=None,
    help="Short description for the provider",
)
def scaffold_bundle(
    name: str,
    output_dir: str,
    target_kinds: tuple[str, ...],
    generator_kinds: tuple[str, ...],
    provider_description: str | None,
) -> None:
    """Scaffold a new SecretZero provider bundle package.

    NAME is the provider identifier (e.g. "mycloud"). The command creates a
    pip-installable package with all the boilerplate needed for a provider,
    optional targets and generators, a bundle manifest, pyproject.toml, and
    starter tests.

    \b
    Examples:
      secretzero scaffold-bundle mycloud
      secretzero scaffold-bundle mycloud --with-target mycloud_secret --with-generator mycloud_token
      secretzero scaffold-bundle mycloud -o ~/projects
    """  # noqa: D301
    _scaffold_bundle_impl(name, output_dir, target_kinds, generator_kinds, provider_description)


def _scaffold_bundle_impl(
    name: str,
    output_dir: str,
    target_kinds: tuple[str, ...],
    generator_kinds: tuple[str, ...],
    provider_description: str | None,
) -> None:
    """Implementation of the scaffold-bundle command."""
    import re
    import textwrap

    # Validate name
    if not re.match(r"^[a-z][a-z0-9_]*$", name):
        console.print(
            f"[red]Error:[/red] Bundle name must be lowercase alphanumeric with "
            f"underscores (got '{name}')"
        )
        raise SystemExit(1)

    pkg_name = f"secretzero_{name}"
    class_prefix = name.replace("_", " ").title().replace(" ", "")
    provider_class_name = f"{class_prefix}Provider"
    auth_class_name = f"{class_prefix}Auth"
    desc = provider_description or f"{class_prefix} provider for SecretZero"

    base_dir = Path(output_dir) / pkg_name
    src_dir = base_dir / "src" / pkg_name
    tests_dir = base_dir / "tests"

    if base_dir.exists():
        console.print(f"[red]Error:[/red] Directory already exists: {base_dir}")
        raise SystemExit(1)

    # Collect file definitions
    files: dict[str, str] = {}

    # ---- pyproject.toml ----
    entry_generators = ""
    entry_targets = ""
    for gk in generator_kinds:
        entry_generators += f'  # "{gk}" generator available via bundle manifest\n'
    for tk in target_kinds:
        entry_targets += f'  # "{tk}" target available via bundle manifest\n'

    files[str(base_dir / "pyproject.toml")] = textwrap.dedent(f"""\
        [build-system]
        requires = ["setuptools>=68.0", "setuptools-scm>=8.0"]
        build-backend = "setuptools.backends._legacy:_Backend"

        [project]
        name = "{pkg_name}"
        version = "0.1.0"
        description = "{desc}"
        requires-python = ">=3.12"
        dependencies = [
            "secretzero>=0.2",
        ]

        [project.entry-points."secretzero.providers"]
        {name} = "{pkg_name}:BUNDLE_MANIFEST"
    """)

    # ---- src/<pkg>/__init__.py (bundle manifest) ----
    def _fmt_dict(items: dict[str, str], indent: int = 8) -> str:
        """Format a dict literal with one entry per line."""
        if not items:
            return "{}"
        pad = " " * indent
        lines = ["{"]
        for k, v in items.items():
            lines.append(f'{pad}"{k}": "{v}",')
        lines.append(" " * (indent - 4) + "}")
        return "\n".join(lines)

    def _fmt_list(items: tuple[str, ...], indent: int = 8) -> str:
        """Format a list literal."""
        if not items:
            return "[]"
        pad = " " * indent
        lines = ["["]
        for item in items:
            lines.append(f'{pad}"{item}",')
        lines.append(" " * (indent - 4) + "]")
        return "\n".join(lines)

    gen_map: dict[str, str] = {}
    for gk in generator_kinds:
        gc_name = gk.replace("_", " ").title().replace(" ", "") + "Generator"
        gen_map[gk] = f"{pkg_name}.generators:{gc_name}"
    target_map: dict[str, str] = {}
    for tk in target_kinds:
        tc_name = tk.replace("_", " ").title().replace(" ", "") + "Target"
        target_map[tk] = f"{pkg_name}.targets:{tc_name}"

    init_lines = [
        f'"""{desc}."""',
        "",
        "from secretzero.bundles.registry import BundleManifest",
        "",
        "BUNDLE_MANIFEST = BundleManifest(",
        f'    name="{name}",',
        '    version="0.1.0",',
        f'    provider_class="{pkg_name}.provider:{provider_class_name}",',
        f"    generators={_fmt_dict(gen_map)},",
        f"    targets={_fmt_dict(target_map)},",
        f"    generator_kinds={_fmt_list(generator_kinds)},",
        f"    target_kinds={_fmt_list(target_kinds)},",
        ")",
        "",
    ]
    files[str(src_dir / "__init__.py")] = "\n".join(init_lines)

    # ---- src/<pkg>/provider.py ----
    files[str(src_dir / "provider.py")] = textwrap.dedent(f'''\
        """{class_prefix} provider implementation."""

        from typing import Any

        from secretzero.providers.base import BaseProvider, ProviderAuth


        class {auth_class_name}(ProviderAuth):
            """Authentication handler for {class_prefix}."""

            ENV_TOKEN: str = "{name.upper()}_TOKEN"

            def authenticate(self) -> bool:
                """Authenticate with {class_prefix}."""
                token = self.config.get("token") or __import__("os").environ.get(self.ENV_TOKEN)
                if not token:
                    return False
                self._token = token
                return True

            def is_authenticated(self) -> bool:
                """Check if authenticated."""
                return hasattr(self, "_token") and self._token is not None

            def get_client(self) -> Any:
                """Return an authenticated API client."""
                if not self.is_authenticated():
                    self.authenticate()
                # TODO: return your SDK client here
                return None


        class {provider_class_name}(BaseProvider):
            """{class_prefix} provider for SecretZero."""

            display_name = "{desc}"
            description = "{desc}"
            required_package: tuple[str, str] | None = None  # e.g. ("my_sdk", "{pkg_name}")
            auth_class = {auth_class_name}

            auth_methods: dict[str, str] = {{
                "token": "Use a {class_prefix} API token",
            }}
            config_options: dict[str, str] = {{
                "url": "{class_prefix} API URL (optional)",
            }}
            config_example: str = (
                "providers:\\n"
                "  {name}:\\n"
                "    kind: {name}\\n"
                "    auth:\\n"
                "      kind: token\\n"
                "      config:\\n"
                "        token: ${{{name.upper()}_TOKEN}}"
            )
            target_details: dict[str, dict[str, Any]] = {{}}

            def __init__(
                self,
                name: str = "{name}",
                config: dict[str, Any] | None = None,
                auth: ProviderAuth | None = None,
            ) -> None:
                super().__init__(name=name, config=config or {{}}, auth=auth)

            @property
            def provider_kind(self) -> str:
                return "{name}"

            def test_connection(self) -> tuple[bool, str | None]:
                """Test connectivity to {class_prefix}."""
                # TODO: implement real connectivity test
                if self.auth and self.auth.is_authenticated():
                    return True, None
                return False, "Not authenticated"

            def get_supported_targets(self) -> list[str]:
                return {[*target_kinds] if target_kinds else []}
    ''')

    # ---- src/<pkg>/targets.py (if targets requested) ----
    if target_kinds:
        target_classes = ""
        for tk in target_kinds:
            tc_name = tk.replace("_", " ").title().replace(" ", "") + "Target"
            target_classes += textwrap.dedent(f'''\

                class {tc_name}(BaseTarget):
                    """{class_prefix} target: {tk}."""

                    def store(self, secret_name: str, secret_value: str) -> bool:
                        """Store a secret in {class_prefix}."""
                        # TODO: implement store
                        raise NotImplementedError

                    def retrieve(self, secret_name: str) -> str | None:
                        """Retrieve a secret from {class_prefix}."""
                        # TODO: implement retrieve
                        raise NotImplementedError

            ''')
        files[str(src_dir / "targets.py")] = textwrap.dedent(f'''\
            """{class_prefix} target implementations."""

            from secretzero.targets.base import BaseTarget
            {target_classes}
        ''')

    # ---- src/<pkg>/generators.py (if generators requested) ----
    if generator_kinds:
        gen_classes = ""
        for gk in generator_kinds:
            gc_name = gk.replace("_", " ").title().replace(" ", "") + "Generator"
            gen_classes += textwrap.dedent(f'''\

                class {gc_name}(BaseGenerator):
                    """{class_prefix} generator: {gk}."""

                    def generate(self) -> str:
                        """Generate a secret value."""
                        # TODO: implement generation logic
                        raise NotImplementedError

            ''')
        files[str(src_dir / "generators.py")] = textwrap.dedent(f'''\
            """{class_prefix} generator implementations."""

            from secretzero.generators.base import BaseGenerator
            {gen_classes}
        ''')

    # ---- tests/__init__.py ----
    files[str(tests_dir / "__init__.py")] = ""

    # ---- tests/test_provider.py ----
    files[str(tests_dir / "test_provider.py")] = textwrap.dedent(f'''\
        """Tests for {class_prefix} provider."""

        from {pkg_name}.provider import {auth_class_name}, {provider_class_name}


        def test_provider_kind():
            """Provider reports correct kind."""
            provider = {provider_class_name}()
            assert provider.provider_kind == "{name}"


        def test_auth_env_token():
            """{auth_class_name} declares expected ENV_TOKEN."""
            assert {auth_class_name}.ENV_TOKEN == "{name.upper()}_TOKEN"


        def test_provider_display_name():
            """Provider has a display_name set."""
            assert {provider_class_name}.display_name != ""
    ''')

    # ---- tests/test_bundle.py ----
    files[str(tests_dir / "test_bundle.py")] = textwrap.dedent(f'''\
        """Tests for {class_prefix} bundle manifest."""

        from secretzero.bundles.registry import BundleManifest

        from {pkg_name} import BUNDLE_MANIFEST


        def test_manifest_is_bundle_manifest():
            """BUNDLE_MANIFEST is a valid BundleManifest."""
            assert isinstance(BUNDLE_MANIFEST, BundleManifest)


        def test_manifest_name():
            """Bundle name matches provider name."""
            assert BUNDLE_MANIFEST.name == "{name}"


        def test_manifest_provider_class():
            """Provider class path is set."""
            assert BUNDLE_MANIFEST.provider_class is not None
    ''')

    # ---- README.md ----
    target_section = ""
    if target_kinds:
        kinds_list = ", ".join(f"`{tk}`" for tk in target_kinds)
        target_section = f"\n**Targets:** {kinds_list}\n"
    gen_section = ""
    if generator_kinds:
        kinds_list = ", ".join(f"`{gk}`" for gk in generator_kinds)
        gen_section = f"\n**Generators:** {kinds_list}\n"

    files[str(base_dir / "README.md")] = textwrap.dedent(f"""\
        # {pkg_name}

        {desc}

        ## Installation

        ```bash
        pip install {pkg_name}
        ```

        SecretZero discovers the bundle automatically via `entry_points`.
        {target_section}{gen_section}
        ## Development

        ```bash
        pip install -e ".[dev]"
        pytest
        ```

        ## Usage

        ```yaml
        providers:
          {name}:
            kind: {name}
            auth:
              kind: token
              config:
                token: ${{{name.upper()}_TOKEN}}
        ```
    """)

    # Write all files
    for file_path, content in files.items():
        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)

    console.print(f"[green]✓[/green] Scaffolded bundle [bold]{pkg_name}[/bold] at {base_dir}\n")
    console.print("Generated files:")
    for file_path in sorted(files.keys()):
        rel = Path(file_path).relative_to(base_dir)
        console.print(f"  [cyan]{rel}[/cyan]")

    console.print("\nNext steps:")
    console.print(f"  1. cd {base_dir}")
    console.print(f"  2. Implement the TODO stubs in [cyan]src/{pkg_name}/provider.py[/cyan]")
    if target_kinds:
        console.print(f"  3. Implement target methods in [cyan]src/{pkg_name}/targets.py[/cyan]")
    if generator_kinds:
        console.print(
            f"  {'4' if target_kinds else '3'}. Implement generator in "
            f"[cyan]src/{pkg_name}/generators.py[/cyan]"
        )
    console.print("  • Run [bold]pytest[/bold] to test")
    console.print(f"  • Run [bold]secretzero validate-bundle src/{pkg_name}[/bold] to validate")
    console.print("  • Run [bold]pip install -e .[/bold] to register with SecretZero")


@main.command("terraform")
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
    help="Path to .szvar variable file(s) (can be specified multiple times)",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default="terraform-out",
    help="Directory to write generated Terraform files",
)
@click.option(
    "--format",
    "tf_format",
    type=click.Choice(["hcl", "json"]),
    default="hcl",
    help="Terraform output format (hcl or json)",
)
@click.option(
    "--include-static-secrets/--no-include-static-secrets",
    default=False,
    help="Include default values for static-secret Terraform variables (may embed secrets in code).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show a summary of what would be generated without writing files",
)
@_environment_option
def terraform(
    file: str,
    var_files: tuple[str, ...],
    output_dir: str,
    tf_format: str,
    include_static_secrets: bool,
    dry_run: bool,
    environment: str | None,
) -> None:
    """Generate Terraform manifests from a Secretfile.

    This command translates your Secretfile configuration into Terraform
    resources, using bundle-provided Terraform provider metadata where
    available. Generated configuration can be emitted as HCL (``.tf``)
    or Terraform JSON (``.tf.json``).
    """
    output_path = Path(output_dir)

    try:
        _file_path, secretfile, _ = _load_secretfile_for_cli(
            file,
            var_files=var_files,
            environment=environment,
        )
    except Exception as e:
        console.print(f"[red]Error loading Secretfile:[/red] {e}")
        sys.exit(EXIT_CONFIG_ERROR)

    if include_static_secrets and spill_guard_active():
        console.print(
            "[red]Error:[/red] --include-static-secrets is blocked while SZ_AGENT or "
            "SZ_AGENT_MODE is enabled (generated Terraform may embed secret defaults)."
        )
        sys.exit(EXIT_CONFIG_ERROR)

    registry = get_bundle_registry()

    options = TerraformGeneratorOptions(
        output_dir=output_path,
        format=TerraformOutputFormat(tf_format),
        include_static_secrets=include_static_secrets,
    )

    project = generate_terraform(secretfile, options, registry=registry)

    if dry_run:
        console.print("[bold]Terraform generation plan (dry run)[/bold]\n")
        console.print(f"  Secrets: {len(secretfile.secrets)}")
        console.print(f"  Providers: {len(project.required_providers)}")
        console.print(f"  Resources: {len(project.resources)}")
        if project.required_providers:
            console.print("\n[bold]Required providers:[/bold]")
            for rp in project.required_providers.values():
                src = f" (source: {rp.source})" if rp.source else ""
                ver = f" (version: {rp.version})" if rp.version else ""
                console.print(f"  • {rp.name}{src}{ver}")
        console.print(
            "\n[dim]Use --format hcl|json and remove --dry-run to write Terraform files.[/dim]"
        )
        return

    written_paths = project.write_files(options.output_dir, options.format)

    console.print("[green]✓[/green] Generated Terraform configuration\n")
    console.print("[bold]Files written:[/bold]")
    for p in written_paths:
        console.print(f"  [cyan]{p}[/cyan]")

    console.print("\nNext steps:")
    console.print(f"  1. cd {output_path}")
    console.print("  2. terraform init")
    console.print("  3. terraform plan")
    console.print("  4. terraform apply")


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
        click.echo(_json.dumps(result, indent=2))
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
