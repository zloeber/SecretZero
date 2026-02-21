"""Provider capability introspection CLI commands."""

import json
from typing import Any

import click
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table

from secretzero.providers.base import BaseProvider
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

    provider_info = {
        "local": ("Local Filesystem", "Local file and template targets"),
        "vault": ("Hashicorp Vault", "Secret storage and management"),
        "aws": ("Amazon Web Services", "AWS Secrets Manager and other services"),
        "azure": ("Microsoft Azure", "Azure Key Vault and services"),
        "github": ("GitHub", "GitHub repository secrets"),
        "gitlab": ("GitLab", "GitLab project secrets"),
        "jenkins": ("Jenkins", "Jenkins credentials"),
        "kubernetes": ("Kubernetes", "Kubernetes secrets"),
    }

    for provider_type in sorted(provider_types):
        name, description = provider_info.get(provider_type, (provider_type.title(), ""))
        table.add_row(provider_type, name, description)

    # Add "local" provider even if not in registry (it's a special case)
    if "local" not in provider_types:
        name, description = provider_info["local"]
        table.add_row("local", name, description)

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
@click.option(
    "--provider",
    "-p",
    type=click.Choice(["github"]),
    default="github",
    help="Provider to check token permissions for",
)
@click.option(
    "--token",
    "-t",
    help="Token to check (uses GITHUB_TOKEN env var if not provided)",
)
def show_token_info(provider: str, token: str | None) -> None:
    """Show authentication token permissions and scopes.

    Currently supports GitHub tokens. Displays OAuth scopes,
    user information, and token capabilities.

    Examples:

        # Check GITHUB_TOKEN environment variable
        secretzero providers token-info

        # Check specific token
        secretzero providers token-info --token ghp_xxxxx

        # Explicitly specify provider
        secretzero providers token-info --provider github
    """
    if provider == "github":
        import os

        from secretzero.providers.github import GitHubAuth, GitHubProvider

        # Prepare auth config
        auth_config = {}
        if token:
            auth_config["token"] = token
        elif "GITHUB_TOKEN" in os.environ:
            auth_config["token"] = os.environ["GITHUB_TOKEN"]
        else:
            console.print(
                "[red]Error:[/red] No GitHub token found. "
                "Set GITHUB_TOKEN environment variable or use --token"
            )
            raise click.Abort()

        try:
            # Create auth instance and provider
            auth = GitHubAuth(auth_config)
            provider_instance = GitHubProvider("github", auth=auth)

            # Get token info (uses requests directly, no PyGithub needed)
            console.print("\n[bold]GitHub Token Information[/bold]\n")

            token_info = provider_instance.get_token_permissions()

            # Display user info
            console.print(f"[cyan]User:[/cyan] {token_info.get('user', 'unknown')}")
            if token_info.get("name"):
                console.print(f"[cyan]Name:[/cyan] {token_info['name']}")
            if token_info.get("email"):
                console.print(f"[cyan]Email:[/cyan] {token_info['email']}")

            # Display scopes
            scopes = token_info.get("scopes", [])
            if scopes:
                console.print(f"\n[cyan]Token Scopes ({len(scopes)}):[/cyan]")
                for scope in sorted(scopes):
                    scope_info = _get_scope_description(scope)
                    console.print(f"  ✓ [green]{scope}[/green] - {scope_info}")
            else:
                console.print("\n[yellow]No OAuth scopes found (may be a classic PAT)[/yellow]")

            # Show common operations
            console.print("\n[bold]Common Operations:[/bold]")
            can_read_repo = "repo" in scopes or not scopes
            can_write_secrets = "repo" in scopes or not scopes
            can_write_actions = "workflow" in scopes or not scopes

            if can_read_repo:
                console.print("  ✓ Read repository data")
            else:
                console.print("  ✗ Cannot read repository data (needs 'repo' scope)")

            if can_write_secrets:
                console.print("  ✓ Create/update repository secrets")
            else:
                console.print("  ✗ Cannot write secrets (needs 'repo' scope)")

            if can_write_actions:
                console.print("  ✓ Update GitHub Actions workflows")
            else:
                console.print("  ✗ Cannot update workflows (needs 'workflow' scope)")

            console.print("\n[dim]For more info on GitHub scopes: https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps[/dim]")

        except RuntimeError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise click.Abort()
        except Exception as e:
            console.print(f"[red]Error:[/red] Failed to get token information: {e}")
            raise click.Abort()
    else:
        console.print(f"[yellow]Token info not yet implemented for {provider}[/yellow]")


def _get_scope_description(scope: str) -> str:
    """Get description for a GitHub OAuth scope.

    Args:
        scope: OAuth scope name

    Returns:
        Human-readable description
    """
    scope_descriptions = {
        "repo": "Full control of private repositories",
        "repo:status": "Access commit status",
        "repo_deployment": "Access deployment status",
        "public_repo": "Access public repositories",
        "repo:invite": "Access repository invitations",
        "security_events": "Read and write security events",
        "admin:repo_hook": "Full control of repository hooks",
        "write:repo_hook": "Write repository hooks",
        "read:repo_hook": "Read repository hooks",
        "admin:org": "Full control of orgs and teams",
        "write:org": "Read and write org and team membership",
        "read:org": "Read org and team membership",
        "admin:public_key": "Full control of user public keys",
        "write:public_key": "Write user public keys",
        "read:public_key": "Read user public keys",
        "admin:org_hook": "Full control of organization hooks",
        "gist": "Create gists",
        "notifications": "Access notifications",
        "user": "Update all user data",
        "read:user": "Read all user profile data",
        "user:email": "Access user email addresses",
        "user:follow": "Follow and unfollow users",
        "delete_repo": "Delete repositories",
        "write:discussion": "Read and write team discussions",
        "read:discussion": "Read team discussions",
        "write:packages": "Upload packages",
        "read:packages": "Download packages",
        "delete:packages": "Delete packages",
        "admin:gpg_key": "Full control of user GPG keys",
        "write:gpg_key": "Write user GPG keys",
        "read:gpg_key": "Read user GPG keys",
        "workflow": "Update GitHub Action workflows",
        "admin:enterprise": "Full control of enterprises",
        "manage_runners:enterprise": "Manage enterprise runners and runner groups",
        "manage_billing:enterprise": "Read and write enterprise billing data",
        "read:enterprise": "Read enterprise profile data",
        "codespace": "Full control of codespaces",
        "copilot": "Full control of GitHub Copilot settings",
    }
    return scope_descriptions.get(scope, "Permission granted")
