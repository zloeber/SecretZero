"""CLI commands for bundled SecretZero skill management."""

from __future__ import annotations

import click
from rich.console import Console

from secretzero.skills import (
    SUPPORTED_TARGETS,
    install_skills_for_targets,
    list_bundled_skills,
    resolve_skill_names,
    resolve_targets,
    skill_markdown,
)

console = Console()


@click.group("skills", invoke_without_command=True)
@click.pass_context
def skills_group(ctx: click.Context) -> None:
    """Install and inspect bundled SecretZero agent skills."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@skills_group.command("list")
def skills_list() -> None:
    """List bundled skills available for install."""
    bundled = list_bundled_skills()
    if not bundled:
        console.print("[yellow]No bundled skills found in package data.[/yellow]")
        return
    console.print("[bold]Bundled skills:[/bold]")
    for skill_name in bundled:
        console.print(f"- {skill_name}")


@skills_group.command("show")
@click.argument("skill_name", required=False)
def skills_show(skill_name: str | None) -> None:
    """Show a bundled skill document."""
    if not skill_name:
        skill_names = list_bundled_skills()
        if not skill_names:
            console.print("[yellow]No bundled skills found in package data.[/yellow]")
            return
        console.print("[bold]Available skills:[/bold]")
        for item in skill_names:
            console.print(f"- {item}")
        console.print("[dim]Use `secretzero skills show <name>` to print SKILL.md content.[/dim]")
        return
    content = skill_markdown(skill_name)
    if not content:
        console.print(f"[red]Skill '{skill_name}' not found.[/red]")
        raise click.Abort()
    console.print(content)


@skills_group.command("install")
@click.option(
    "--scope",
    type=click.Choice(["project", "user"]),
    default="user",
    show_default=True,
    help="Install to local project config or user-global location.",
)
@click.option(
    "--target",
    "targets",
    multiple=True,
    type=click.Choice(SUPPORTED_TARGETS),
    help="Explicit target to install (repeatable). If omitted, auto-detect targets.",
)
@click.option(
    "--disable-target",
    "disable_targets",
    multiple=True,
    type=click.Choice(SUPPORTED_TARGETS),
    help="Disable one or more auto-detected targets.",
)
@click.option(
    "--skill",
    "skills",
    multiple=True,
    help="Install only this bundled skill (repeatable). Omit to install all.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would be installed without writing files.",
)
def skills_install(
    scope: str,
    targets: tuple[str, ...],
    disable_targets: tuple[str, ...],
    skills: tuple[str, ...],
    dry_run: bool,
) -> None:
    """Install bundled skills into supported agent targets."""
    selected_targets = resolve_targets(
        mode="skills",
        scope=scope,  # type: ignore[arg-type]
        enable_targets=list(targets),
        disable_targets=list(disable_targets),
    )
    if not selected_targets:
        console.print(
            "[yellow]No targets selected. Use --target to choose targets explicitly.[/yellow]"
        )
        return
    try:
        selected_skills = resolve_skill_names(list(skills) if skills else None)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise click.Abort() from exc
    results = install_skills_for_targets(
        targets=selected_targets,
        scope=scope,  # type: ignore[arg-type]
        skill_names=selected_skills if skills else None,
        dry_run=dry_run,
    )
    for result in results:
        line = f"[{result.target}] {result.details} -> {result.path}"
        if result.dry_run:
            console.print(f"[dim](dry run)[/dim] {line}")
        elif result.applied:
            console.print(f"[green]{line}[/green]")
        else:
            console.print(f"[yellow]{line}[/yellow]")
