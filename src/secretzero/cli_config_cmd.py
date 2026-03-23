"""CLI commands for application config: show effective config and idempotent updates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click
import yaml
from rich.console import Console

from secretzero.cli_config import (
    DEFAULT_CONFIG_YML_PATH,
    AppConfig,
    get_effective_config,
)

console = Console()


def _set_nested(d: dict[str, Any], key_path: str, value: Any) -> None:
    """Set a nested key in d using dot-separated path. Creates parent dicts as needed."""
    parts = key_path.strip().split(".")
    if not parts or not parts[0]:
        raise ValueError(f"Invalid config key path: {key_path!r}")
    current: dict[str, Any] = d
    for i, part in enumerate(parts[:-1]):
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def _coerce_value(value: str) -> Any:
    """Coerce string to int, float, or bool when appropriate; otherwise return string."""
    v = value.strip()
    if v.lower() in ("true", "yes"):
        return True
    if v.lower() in ("false", "no"):
        return False
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    return value


@click.group("config", invoke_without_command=True)
@click.pass_context
@click.option(
    "--file",
    "-f",
    type=click.Path(),
    default="Secretfile.yml",
    help="Path to Secretfile (for show: merge project config; for update: target file)",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "yaml"]),
    default="text",
    help="Output format (show command)",
)
def config_group(
    ctx: click.Context,
    file: str,
    output_format: str,
) -> None:
    """Show or update application config (defaults ← config.yml ← Secretfile config).

    Resolves config from: built-in defaults, then ~/.config/secretzero/config.yml,
    then the optional ``config`` block in the given Secretfile.
    """
    ctx.ensure_object(dict)
    ctx.obj["config_file"] = file
    ctx.obj["output_format"] = output_format
    if ctx.invoked_subcommand is None:
        ctx.invoke(show, file=file, output_format=output_format)


@config_group.command("show")
@click.option(
    "--file",
    "-f",
    type=click.Path(),
    default="Secretfile.yml",
    help="Path to Secretfile (used to merge project config block if present)",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "yaml"]),
    default="text",
    help="Output format",
)
def show(file: str, output_format: str) -> None:
    """Show effective application config (default command).

    Resolves centralized config from: built-in defaults, then
    ~/.config/secretzero/config.yml if present, then the optional ``config``
    block in the given Secretfile.
    """
    path = Path(file)
    result = get_effective_config(secretfile_path=path if path.exists() else None)

    if output_format == "json":
        click.echo(
            json.dumps(
                {"config": result.config.model_dump(), "sources": result.sources},
                indent=2,
            )
        )
        return

    if output_format == "yaml":
        click.echo(
            yaml.dump(
                {"config": result.config.model_dump(), "sources": result.sources},
                sort_keys=False,
            )
        )
        return

    # text
    console.print("[bold]Effective application config[/bold]\n")
    console.print(f"  Sources : [cyan]{', '.join(result.sources)}[/cyan]")
    console.print(f"  LLM    : provider=[cyan]{result.config.llm.default_provider}[/cyan]")
    if result.config.llm.default_provider == "ollama":
        p = result.config.llm.providers.ollama
        console.print(f"          base_url=[cyan]{p.base_url}[/cyan] model=[cyan]{p.model}[/cyan]")
    elif result.config.llm.default_provider == "openai":
        console.print(f"          model=[cyan]{result.config.llm.providers.openai.model}[/cyan]")
    elif result.config.llm.default_provider == "anthropic":
        console.print(f"          model=[cyan]{result.config.llm.providers.anthropic.model}[/cyan]")
    console.print(
        f"  Discovery : threshold=[cyan]{result.config.discovery.confidence_threshold}[/cyan]"
    )


@config_group.command("update")
@click.argument("key_path", required=True)
@click.argument("value", required=True)
@click.option(
    "--file",
    "-f",
    type=click.Path(),
    default=None,
    help="Secretfile path to update (default: Secretfile.yml). Use --user for user config.",
)
@click.option(
    "--user",
    is_flag=True,
    default=False,
    help="Update user config (~/.config/secretzero/config.yml) instead of Secretfile",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Print what would be written without changing files",
)
def update(
    key_path: str,
    value: str,
    file: str | None,
    user: bool,
    dry_run: bool,
) -> None:
    """Set a config key idempotently (e.g. llm.default_provider, llm.providers.ollama.model).

    Updates either the project Secretfile ``config`` block or the user config file.
    Key path is dot-separated (e.g. llm.model, llm.providers.ollama.base_url).
    Value is written as-is; numbers and booleans are coerced when possible.
    """
    if user:
        target_path = DEFAULT_CONFIG_YML_PATH
        target_name = "user config"
    else:
        target_path = Path(file or "Secretfile.yml")
        target_name = str(target_path)

    coerced = _coerce_value(value)

    if user:
        if not target_path.parent.exists():
            if dry_run:
                console.print(f"[dim]Would create {target_path.parent} and write config[/dim]")
            else:
                target_path.parent.mkdir(parents=True, exist_ok=True)
        current: dict[str, Any] = {}
        if target_path.exists():
            try:
                raw = yaml.safe_load(target_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    current = raw
            except Exception:
                pass
        _set_nested(current, key_path, coerced)
        if dry_run:
            console.print(f"[dim]Would write to [bold]{target_path}[/bold]:[/dim]")
            console.print(yaml.dump(current, sort_keys=False, default_flow_style=False))
            return
        try:
            AppConfig(**current)
        except Exception as e:
            console.print(f"[red]Error:[/red] Config would be invalid: {e}")
            raise SystemExit(1)
        target_path.write_text(yaml.dump(current, sort_keys=False, default_flow_style=False))
        console.print(f"[green]✓[/green] Updated [cyan]{key_path}[/cyan] in {target_name}")
        return

    # Secretfile
    if not target_path.exists():
        console.print(f"[red]Error:[/red] Secretfile not found: {target_path}")
        raise SystemExit(1)
    raw = yaml.safe_load(target_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        console.print("[red]Error:[/red] Secretfile is not a valid YAML mapping.")
        raise SystemExit(1)
    if "config" not in raw or not isinstance(raw["config"], dict):
        raw["config"] = {}
    _set_nested(raw["config"], key_path, coerced)
    try:
        AppConfig(**raw["config"])
    except Exception as e:
        console.print(f"[red]Error:[/red] Config would be invalid: {e}")
        raise SystemExit(1)
    if dry_run:
        console.print(f"[dim]Would update [bold]config.{key_path}[/bold] in {target_path}[/dim]")
        console.print("[dim]config block:[/dim]")
        console.print(yaml.dump(raw["config"], sort_keys=False, default_flow_style=False))
        return
    # Re-serialize the full Secretfile (preserve structure and comments best we can)
    target_path.write_text(yaml.dump(raw, sort_keys=False, default_flow_style=False))
    console.print(f"[green]✓[/green] Updated [cyan]config.{key_path}[/cyan] in {target_name}")
