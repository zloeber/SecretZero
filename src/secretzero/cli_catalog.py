"""CLI for the machine-complete SecretZero capability catalog."""

from __future__ import annotations

import json

import click
import yaml
from rich.console import Console
from rich.table import Table

from secretzero.bundle_catalog import build_bundle_catalog, find_catalog_entry

console = Console()


def _render_text_catalog(catalog: dict) -> None:
    console.print("[bold]SecretZero capability catalog[/bold]\n")

    if catalog.get("generators"):
        table = Table(show_header=True, header_style="bold cyan", title="Generators")
        table.add_column("Kind", style="green")
        table.add_column("Bundle")
        table.add_column("Description")
        for entry in catalog["generators"]:
            table.add_row(
                entry.get("kind", ""),
                entry.get("bundle") or "—",
                entry.get("description") or "—",
            )
        console.print(table)
        console.print()

    if catalog.get("targets"):
        table = Table(show_header=True, header_style="bold cyan", title="Targets")
        table.add_column("Kind", style="green")
        table.add_column("Bundle")
        table.add_column("Provider")
        table.add_column("Description")
        for entry in catalog["targets"]:
            table.add_row(
                entry.get("kind", ""),
                entry.get("bundle") or "—",
                entry.get("provider_kind") or "—",
                entry.get("description") or "—",
            )
        console.print(table)
        console.print()

    if catalog.get("bundles"):
        table = Table(show_header=True, header_style="bold cyan", title="Bundles")
        table.add_column("Bundle", style="green")
        table.add_column("Provider")
        table.add_column("Targets")
        table.add_column("Generators")
        for bundle in catalog["bundles"]:
            table.add_row(
                bundle.get("name", ""),
                bundle.get("provider_kind") or "—",
                ", ".join(bundle.get("target_kinds") or []) or "—",
                ", ".join(bundle.get("generator_kinds") or []) or "—",
            )
        console.print(table)


def _render_kind_details(catalog: dict, kind: str) -> None:
    entry = find_catalog_entry(catalog, kind)
    if entry is None:
        console.print(f"[red]Unknown kind:[/red] {kind}")
        console.print("Run [bold]secretzero catalog --format json[/bold] for the full catalog.")
        return

    console.print(f"[bold]{entry['type'].title()}:[/bold] [green]{kind}[/green]\n")
    if entry.get("description"):
        console.print(f"[cyan]Description:[/cyan] {entry['description']}")
    if entry.get("bundle"):
        console.print(f"[cyan]Bundle:[/cyan] {entry['bundle']}")
    if entry.get("provider_kind"):
        console.print(f"[cyan]Provider kind:[/cyan] {entry['provider_kind']}")
    if entry.get("class_path"):
        console.print(f"[cyan]Class:[/cyan] {entry['class_path']}")
    if entry.get("typical_generators"):
        console.print(f"[cyan]Typical generators:[/cyan] {', '.join(entry['typical_generators'])}")
    if entry.get("provider_config_key"):
        console.print(f"[cyan]Provider config key:[/cyan] {entry['provider_config_key']}")
    config = entry.get("config")
    if config:
        console.print("\n[cyan]Configuration options:[/cyan]")
        for option, desc in config.items():
            console.print(f"  • {option}: {desc}")
    example = entry.get("example")
    if example:
        console.print("\n[cyan]Example:[/cyan]")
        console.print(f"[dim]{example}[/dim]")


@click.command("catalog")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "yaml"]),
    default="text",
    show_default=True,
    help="Output format",
)
@click.option("--bundle", help="Filter to a bundle name (e.g. gitlab, core, local)")
@click.option("--provider", "provider_kind", help="Filter to a provider/bundle kind (e.g. gitlab)")
@click.option("--kind", "-k", help="Filter to a generator or target kind")
@click.option(
    "--kind-type",
    type=click.Choice(["generator", "target"]),
    help="When using --kind, restrict to generator or target",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="With --kind, show detailed configuration for that kind",
)
def catalog_command(
    output_format: str,
    bundle: str | None,
    provider_kind: str | None,
    kind: str | None,
    kind_type: str | None,
    verbose: bool,
) -> None:
    """List all generator kinds, target kinds, and provider bundles.

    Machine-complete catalog backed by the live BundleRegistry. Prefer
    ``--format json`` for agent workflows.
    """
    catalog = build_bundle_catalog(
        bundle=bundle,
        provider_kind=provider_kind,
        kind=kind,
        kind_type=kind_type,
    )

    if output_format == "json":
        click.echo(json.dumps(catalog, indent=2))
        return

    if output_format == "yaml":
        click.echo(yaml.safe_dump(catalog, sort_keys=False))
        return

    if kind and verbose:
        _render_kind_details(catalog, kind)
        return

    _render_text_catalog(catalog)
    console.print(
        "[dim]Use --format json for machine-readable output; "
        "--kind <kind> --verbose for one entry.[/dim]"
    )
