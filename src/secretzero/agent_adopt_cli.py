"""CLI rendering for agent adopt/list commands."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import click
from rich.table import Table

from secretzero.integrations.adopt import run_agent_adopt, run_agent_list
from secretzero.integrations.registry import list_agent_targets


def render_agent_list_text(console: Any) -> None:
    result = run_agent_list()
    targets = list_agent_targets()
    console.print("[bold]Registered agent targets:[/bold] " + ", ".join(targets))
    detections = result.detections
    if not detections:
        console.print("\n[yellow]No agent installs detected on this host.[/yellow]")
        console.print(
            "[dim]Try: secretzero agent adopt --target hermes --source-dir ~/.hermes[/dim]"
        )
        return
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Target")
    table.add_column("Install path")
    table.add_column("SecretZero env")
    table.add_column("Signals")
    for row in detections:
        table.add_row(
            str(row.get("target")),
            str(row.get("source_dir")),
            "yes" if row.get("has_secretzero_env") else "no",
            ", ".join(row.get("signals") or []),
        )
    console.print(table)


def render_agent_list_json() -> None:
    result = run_agent_list()
    payload = asdict(result)
    payload["registered_targets"] = list_agent_targets()
    click.echo(json.dumps(payload, indent=2))


def render_agent_adopt_text(console: Any, result: Any) -> None:
    if not result.generated and result.reason:
        console.print(f"[yellow]{result.reason}[/yellow]")
    if result.target:
        console.print(f"[bold]Target:[/bold] {result.target}")
        console.print(f"[bold]Source:[/bold] {result.source_dir}")
        console.print(f"[bold]Output:[/bold] {result.output_dir}")
    if result.discovered:
        console.print(f"\n[green]Present credentials:[/green] {len(result.discovered)}")
        for item in result.discovered:
            console.print(
                f"  • {item['secret_name']} ({item['env_key']}) "
                f"[dim]via {item['source_file']}[/dim]"
            )
    if result.generated:
        console.print("\n[green]✓ SecretZero environment written[/green]")
        for path in result.artifacts:
            console.print(f"  • {path}")
    elif result.dry_run and result.discovered:
        console.print("\n[cyan]Dry run — planned artifacts:[/cyan]")
        for path in result.artifacts:
            console.print(f"  • {path}")
    if result.preseed:
        console.print(
            f"\n[bold]Lockfile preseed:[/bold] imported={result.preseed.get('imported', 0)}, "
            f"updated={result.preseed.get('updated', 0)}"
        )
    if result.next_steps:
        console.print("\n[bold]Next steps:[/bold]")
        for step in result.next_steps:
            console.print(f"  {step}")


def render_agent_adopt_json(result: Any) -> None:
    click.echo(json.dumps(asdict(result), indent=2))


def run_agent_adopt_command(
    *,
    target: str | None,
    source_dir: str | None,
    output_dir: str | None,
    template: bool,
    preseed_lockfile: bool,
    dry_run: bool,
    force: bool,
    output_format: str,
    console: Any,
) -> None:
    result = run_agent_adopt(
        target=target,
        source_dir=Path(source_dir) if source_dir else None,
        output_dir=Path(output_dir) if output_dir else None,
        template=template,
        preseed_lockfile=preseed_lockfile,
        dry_run=dry_run,
        force=force,
    )
    if output_format == "json":
        render_agent_adopt_json(result)
    else:
        render_agent_adopt_text(console, result)
