"""Provider capability introspection CLI commands."""

from typing import Any

import click
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table

from secretzero.providers.capabilities import CapabilityType
from secretzero.providers.registry import GLOBAL_PROVIDER_REGISTRY

console = Console()


@click.group("providers")
def providers_group() -> None:
    """Manage and introspect providers.

    Providers are external systems (Vault, AWS, Azure, etc.) that store
    or help manage secrets. These commands let you discover available
    providers and their capabilities.
    """
    pass


@providers_group.command("list")
def list_providers() -> None:
    """List all registered providers.

    Shows all provider types available in SecretZero.
    """
    provider_types = GLOBAL_PROVIDER_REGISTRY.list_provider_types()

    if not provider_types:
        console.print("[yellow]No providers registered.[/yellow]")
        return

    table = Table(title="Registered Providers")
    table.add_column("Provider", style="cyan", no_wrap=True)
    table.add_column("Type", style="magenta")
    table.add_column("Description")

    for provider_type in sorted(provider_types):
        provider_class = GLOBAL_PROVIDER_REGISTRY.get_provider_class(provider_type)
        if provider_class is not None:
            name = provider_class.display_name or provider_type.title()
            description = provider_class.description or ""
        else:
            name = provider_type.title()
            description = ""
        table.add_row(provider_type, name, description)

    # Add "local" provider even if not in registry (it's a special case)
    if "local" not in provider_types:
        table.add_row("local", "Local Filesystem", "Local file and template targets")

    console.print(table)


@providers_group.command("capabilities")
@click.argument("provider_type")
def show_capabilities(provider_type: str) -> None:
    """Show capabilities of a specific provider.

    Lists all operations (methods) that a provider supports.

    Example: secretzero providers capabilities vault
    """
    # Handle "local" provider specially (it's not a real provider class)
    if provider_type == "local":
        console.print("\n[bold]LOCAL Provider[/bold]\n")
        console.print(
            "[cyan]The 'local' provider is a special built-in provider for local filesystem operations.[/cyan]\n"
        )
        console.print("[bold]Supported Target Types:[/bold]")
        console.print(
            "  • [green]file[/green] - Store secrets in local files (dotenv, json, yaml, toml)"
        )
        console.print("  • [green]template[/green] - Render Jinja2 templates with secret values")
        console.print(
            "\n[dim]Note: The local provider does not have capability methods since it doesn't"
        )
        console.print(
            "connect to external systems. It operates directly on the local filesystem.[/dim]"
        )
        return

    try:
        provider_class = GLOBAL_PROVIDER_REGISTRY.get_provider_class(provider_type)
    except (ValueError, KeyError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise click.Abort()

    if provider_class is None:
        console.print(f"[red]Error:[/red] Provider '{provider_type}' not found")
        raise click.Abort()

    # Get capabilities from the class
    try:
        capabilities = provider_class.get_capabilities()
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to get capabilities: {e}")
        raise click.Abort()

    if not capabilities.capabilities:
        console.print(f"[yellow]{provider_type} provider has no capability methods.[/yellow]")
        console.print(
            "\nNote: Capability methods are prefixed with: generate_, retrieve_, "
            "store_, rotate_, or delete_"
        )
        return

    console.print(f"\n[bold]{provider_type.upper()} Provider Capabilities[/bold]\n")

    # Group by type
    by_type: dict[CapabilityType, list[str]] = {}
    for cap in capabilities.capabilities:
        cap_type = cap.capability_type
        if cap_type not in by_type:
            by_type[cap_type] = []
        by_type[cap_type].append(cap.method.name)

    # Display by type
    for cap_type in sorted(by_type.keys(), key=lambda x: x.value):
        methods = sorted(by_type[cap_type])
        console.print(f"[cyan]{cap_type.value.upper()}[/cyan] Operations:")
        for method in methods:
            console.print(f"  • {method}")
        console.print()


@providers_group.command("methods")
@click.argument("provider_type")
@click.option(
    "--type",
    "-t",
    "cap_type",
    type=click.Choice(["generate", "retrieve", "store", "rotate", "delete", "all"]),
    default="all",
    help="Filter by capability type",
)
def list_methods(provider_type: str, cap_type: str) -> None:
    """List methods for a provider, optionally filtered by type.

    Examples:
      secretzero providers methods vault
      secretzero providers methods vault --type generate
      secretzero providers methods aws -t retrieve
    """
    try:
        provider_class = GLOBAL_PROVIDER_REGISTRY.get_provider_class(provider_type)
    except (ValueError, KeyError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise click.Abort()

    if provider_class is None:
        console.print(f"[red]Error:[/red] Provider '{provider_type}' not found")
        raise click.Abort()

    # Get capabilities
    try:
        capabilities = provider_class.get_capabilities()
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to get capabilities: {e}")
        raise click.Abort()

    # Filter by type if specified
    filtered_caps = capabilities.capabilities
    if cap_type != "all":
        filtered_type = CapabilityType(cap_type)
        filtered_caps = [c for c in capabilities.capabilities if c.capability_type == filtered_type]

    if not filtered_caps:
        console.print(f"[yellow]No capabilities found for '{provider_type}'[/yellow]")
        if cap_type != "all":
            console.print(f"Filtered by type: {cap_type}")
        return

    table = Table(title=f"{provider_type.upper()} Methods")
    table.add_column("Method", style="cyan", no_wrap=True)
    table.add_column("Type", style="magenta")
    table.add_column("Requires Auth", style="yellow")
    table.add_column("Description")

    for cap in sorted(filtered_caps, key=lambda c: c.method.name):
        auth_required = "Yes" if cap.requires_auth else "No"
        description = (cap.method.description or "")[:50] + (
            "..." if len(cap.method.description or "") > 50 else ""
        )
        table.add_row(cap.method.name, cap.capability_type.value, auth_required, description)

    console.print(table)


@providers_group.command("schema")
@click.argument("provider_type")
@click.argument("method_name")
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output as JSON instead of formatted text",
)
def show_schema(provider_type: str, method_name: str, output_json: bool) -> None:
    """Show schema/signature for a specific provider method.

    Displays the parameters and return type for a method.

    Example: secretzero providers schema vault generate_password
    """
    try:
        provider_class = GLOBAL_PROVIDER_REGISTRY.get_provider_class(provider_type)
    except (ValueError, KeyError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise click.Abort()

    if provider_class is None:
        console.print(f"[red]Error:[/red] Provider '{provider_type}' not found")
        raise click.Abort()

    # Get capabilities
    try:
        capabilities = provider_class.get_capabilities()
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to get capabilities: {e}")
        raise click.Abort()

    # Find the method
    capability = capabilities.get_capability(method_name)
    if capability is None:
        console.print(
            f"[red]Error:[/red] Method '{method_name}' not found in '{provider_type}' provider"
        )
        console.print("\nAvailable methods:")
        for method in sorted(capabilities.list_methods_by_type(CapabilityType.GENERATE)):
            console.print(f"  • {method}")
        raise click.Abort()

    method_sig = capability.method

    if output_json:
        # Convert to JSON-serializable format
        schema_dict = {
            "method": method_sig.name,
            "description": method_sig.description,
            "return_type": method_sig.return_type,
            "parameters": {
                name: {
                    "type": param.type,
                    "required": param.required,
                    "default": param.default,
                    "description": param.description,
                }
                for name, param in method_sig.parameters.items()
            },
        }
        console.print_json(data=schema_dict)
    else:
        # Pretty text format
        console.print(f"\n[bold]{provider_type}.{method_name}[/bold]\n")

        console.print("[cyan]Description:[/cyan]")
        console.print(f"  {method_sig.description}\n")

        console.print("[cyan]Return Type:[/cyan]")
        console.print(f"  {method_sig.return_type}\n")

        if method_sig.parameters:
            console.print("[cyan]Parameters:[/cyan]")
            for param_name, param_schema in sorted(method_sig.parameters.items()):
                required_marker = "[red]*[/red]" if param_schema.required else ""
                console.print(f"  {param_name}: {param_schema.type} {required_marker}")
                if param_schema.description:
                    console.print(f"    └─ {param_schema.description}")
                if param_schema.default is not None:
                    console.print(f"    └─ default: {param_schema.default}")
            console.print()

        # Show example usage
        console.print("[cyan]Example Usage:[/cyan]")
        example_config = {
            "generator": "provider_backed",
            "generator_config": {
                "provider": f"{provider_type}_instance",
                "method": method_name,
                "method_args": (
                    {param: "value" for param in method_sig.parameters.keys()}
                    if method_sig.parameters
                    else {}
                ),
            },
        }
        yaml_example = _dict_to_yaml(example_config, indent=2)
        syntax = Syntax(yaml_example, "yaml", theme="monokai", line_numbers=False)
        console.print(syntax)


def _dict_to_yaml(d: dict, indent: int = 0) -> str:
    """Convert a dict to YAML-like string format."""
    lines = []
    indent_str = " " * indent

    for key, value in d.items():
        if isinstance(value, dict):
            lines.append(f"{indent_str}{key}:")
            lines.append(_dict_to_yaml(value, indent + 2))
        elif isinstance(value, list):
            lines.append(f"{indent_str}{key}:")
            for item in value:
                if isinstance(item, dict):
                    for k, v in item.items():
                        lines.append(f"{indent_str}  - {k}: {v}")
                else:
                    lines.append(f"{indent_str}  - {item}")
        elif isinstance(value, str):
            lines.append(f"{indent_str}{key}: {value}")
        else:
            lines.append(f"{indent_str}{key}: {value}")

    return "\n".join(lines)


@providers_group.command("token-info")
@click.argument("provider_type", default="github")
@click.option(
    "--token",
    "-t",
    help="Token to check (falls back to provider-specific env var, e.g. GITHUB_TOKEN)",
)
def show_token_info(provider_type: str, token: str | None) -> None:
    """Show authentication token permissions and scopes.

    Queries the provider's auth layer for token details such as user
    identity, granted scopes, and common operations.  Any provider whose
    auth class implements ``get_token_info`` is supported.

    PROVIDER_TYPE defaults to "github" when omitted.

    Examples:

    \b
        # Check GITHUB_TOKEN environment variable
        secretzero providers token-info

        # Check a specific token
        secretzero providers token-info github --token ghp_xxxxx

        # Use a different provider (if it supports token introspection)
        secretzero providers token-info vault --token s.xxxxxxx
    """
    import os

    from secretzero.providers.base import BaseProvider as _BaseProvider

    # --- resolve provider class from the registry -------------------------
    provider_class = GLOBAL_PROVIDER_REGISTRY.get_provider_class(provider_type)
    if provider_class is None:
        console.print(
            f"[red]Error:[/red] Provider '{provider_type}' is not registered. "
            "Run [cyan]secretzero providers list[/cyan] to see available providers."
        )
        raise click.Abort()

    # --- build an auth config from the explicit token or environment ------
    auth_config: dict[str, Any] = {}
    if token:
        auth_config["token"] = token
    else:
        # Resolve env-var name from the provider's auth class metadata
        env_var = getattr(provider_class.auth_class, "ENV_TOKEN", "") or ""
        if env_var and env_var in os.environ:
            auth_config["token"] = os.environ[env_var]
        elif env_var:
            console.print(
                f"[red]Error:[/red] No token found. "
                f"Set {env_var} environment variable or use --token"
            )
            raise click.Abort()
        else:
            console.print(
                f"[red]Error:[/red] No token provided and no known environment "
                f"variable for provider '{provider_type}'. Use --token."
            )
            raise click.Abort()

    # --- instantiate provider and retrieve token info ---------------------
    try:
        # Each provider's __init__ accepts (name, config, auth).
        # Providers that define a custom Auth class typically accept token via
        # config dict with a "token" key.
        provider_instance: _BaseProvider = provider_class(
            name=provider_type, config={"auth": auth_config, **auth_config}
        )

        console.print(f"\n[bold]{provider_type.upper()} Token Information[/bold]\n")

        token_info = provider_instance.get_token_info()

        # Display user info
        console.print(f"[cyan]User:[/cyan] {token_info.get('user', 'unknown')}")
        if token_info.get("name"):
            console.print(f"[cyan]Name:[/cyan] {token_info['name']}")
        if token_info.get("email"):
            console.print(f"[cyan]Email:[/cyan] {token_info['email']}")

        # Display scopes using provider-supplied descriptions
        scope_descriptions = provider_class.get_scope_descriptions()
        scopes: list[str] = token_info.get("scopes", [])
        if scopes:
            console.print(f"\n[cyan]Token Scopes ({len(scopes)}):[/cyan]")
            for scope in sorted(scopes):
                desc = scope_descriptions.get(scope, "Permission granted")
                console.print(f"  ✓ [green]{scope}[/green] - {desc}")
        else:
            console.print("\n[yellow]No scopes found (token may use implicit permissions)[/yellow]")

        # Display any extra keys the provider returned
        extra_keys = set(token_info.keys()) - {"user", "name", "email", "scopes", "token_type"}
        if extra_keys:
            console.print("\n[bold]Additional Details:[/bold]")
            for key in sorted(extra_keys):
                console.print(f"  [cyan]{key}:[/cyan] {token_info[key]}")

    except NotImplementedError:
        console.print(
            f"[yellow]Provider '{provider_type}' does not support token introspection.[/yellow]"
        )
        raise click.Abort()
    except RuntimeError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise click.Abort()
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to get token information: {e}")
        raise click.Abort()
