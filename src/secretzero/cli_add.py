"""Interactive and non-interactive ``secretzero add`` / ``secretzero new``."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from secretzero.secret_author import (
    ApplyResult,
    SecretAuthorError,
    SecretDraft,
    SourceDraft,
    TargetDraft,
    apply_secret_draft,
    default_generator_config,
    known_generator_kinds,
    parse_kv_pairs,
    parse_target_spec,
    prompt_fields_for_target,
    provider_kind_for_target,
    targets_in_category,
)

console = Console()

_SOURCE_KINDS = ("skip", "file", "env", "secret_ref", "provider_read")
_CATEGORIES = ("local", "cloud", "encrypted")


def _echo_result(result: ApplyResult, output_format: str) -> None:
    if output_format == "json":
        click.echo(json.dumps(result.as_dict(), indent=2))
        return
    verb = (
        "Would write" if result.dry_run else "Updated" if result.action == "updated" else "Created"
    )
    console.print(
        f"[green]✓[/green] {verb} secret [cyan]{result.name}[/cyan] "
        f"({result.generator_kind}) in [cyan]{result.path}[/cyan]"
    )
    if result.source_kind:
        console.print(f"  Source: [cyan]{result.source_kind}[/cyan]")
    for target in result.targets:
        console.print(f"  Target: [cyan]{target['provider']}/{target['kind']}[/cyan]")
    if result.providers_added:
        console.print(
            "  Added provider stub(s): "
            + ", ".join(f"[cyan]{name}[/cyan]" for name in result.providers_added)
        )
    if result.dry_run and result.yaml_preview:
        console.print("\n[dim]Dry run — file not written.[/dim]")
    else:
        console.print("\nNext steps:")
        console.print(f"  secretzero validate -f {result.path}")
        console.print(f"  secretzero sync --dry-run -f {result.path}")


def _choose(prompt: str, options: list[str], *, default: str | None = None) -> str:
    for index, option in enumerate(options, start=1):
        marker = " [dim](current)[/dim]" if default and option == default else ""
        console.print(f"  [cyan]{index}[/cyan]. {option}{marker}")
    raw = click.prompt(prompt, default=default or "", show_default=bool(default))
    text = str(raw).strip()
    if text.isdigit():
        number = int(text)
        if 1 <= number <= len(options):
            return options[number - 1]
    if text in options:
        return text
    raise click.ClickException(f"Choose one of: {', '.join(options)}")


def _inventory(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    import yaml

    with path.open(encoding="utf-8") as handle:
        doc = yaml.safe_load(handle) or {}
    rows = []
    for secret in doc.get("secrets") or []:
        if not isinstance(secret, dict):
            continue
        targets = []
        for target in secret.get("targets") or []:
            if isinstance(target, dict):
                targets.append(
                    {
                        "provider": str(target.get("provider") or ""),
                        "kind": str(target.get("kind") or ""),
                        "config": dict(target.get("config") or {}),
                    }
                )
        source = secret.get("source") or {}
        rows.append(
            {
                "name": str(secret.get("name")),
                "kind": str(secret.get("kind")),
                "source": source.get("kind") if isinstance(source, dict) else None,
                "targets": targets,
            }
        )
    return rows


def _print_inventory(rows: list[dict[str, Any]]) -> None:
    if not rows:
        console.print("[dim]No secrets in this Secretfile yet.[/dim]")
        return
    table = Table(title="Current secrets", show_header=True, header_style="bold cyan")
    table.add_column("Secret")
    table.add_column("Generator")
    table.add_column("Source")
    table.add_column("Targets")
    for row in rows:
        table.add_row(
            row["name"],
            row["kind"],
            row["source"] or "—",
            ", ".join(f"{item['provider']}/{item['kind']}" for item in row["targets"]) or "—",
        )
    console.print(table)


def _prompt_generator_config(kind: str) -> dict[str, Any]:
    config = default_generator_config(kind)
    if kind == "random_password":
        config["length"] = int(click.prompt("Password length", default=32))
        config["special"] = click.confirm("Include special characters?", default=True)
        return config
    if kind == "random_string":
        config["length"] = int(click.prompt("String length", default=32))
        return config
    if kind == "script":
        config["command"] = click.prompt("Command to run (no secret values)")
        return config
    if "value" in config:
        console.print(
            "[dim]Static values stay as null. Enter the secret later with "
            "secretzero web or secretzero sync.[/dim]"
        )
        return config
    return config


def _prompt_source() -> SourceDraft | None:
    choice = _choose("Value source", list(_SOURCE_KINDS), default="skip")
    if choice == "skip":
        return None
    if choice == "file":
        path = click.prompt("Source file path")
        fmt = click.prompt("Format", default="dotenv")
        key = click.prompt("Key in the file (blank to use the secret name)", default="")
        config: dict[str, Any] = {"path": path, "format": fmt}
        if str(key).strip():
            config["key"] = str(key).strip()
        return SourceDraft(kind="file", config=config)
    if choice == "env":
        return SourceDraft(kind="env", config={"name": click.prompt("Environment variable name")})
    if choice == "secret_ref":
        config = {"secret": click.prompt("Referenced secret name")}
        field_name = click.prompt("Field (blank for the whole value)", default="")
        if str(field_name).strip():
            config["field"] = str(field_name).strip()
        return SourceDraft(kind="secret_ref", config=config)
    provider = click.prompt("Provider alias")
    kind = click.prompt("Provider read kind")
    read_raw = click.prompt("Read config as JSON object", default="{}")
    read_cfg = json.loads(str(read_raw))
    if not isinstance(read_cfg, dict):
        raise click.ClickException("Read config must be a JSON object.")
    return SourceDraft(
        kind="provider_read",
        config={"provider": provider, "kind": kind, "read": read_cfg},
    )


def _prompt_target() -> TargetDraft:
    category = _choose(
        "Target category [local/cloud/encrypted]",
        list(_CATEGORIES),
        default="local",
    )
    rows = targets_in_category(category)
    if not rows:
        raise click.ClickException(f"No targets registered for category '{category}'.")
    kinds = [str(row["kind"]) for row in rows]
    kind = _choose("Target kind", kinds)
    config: dict[str, Any] = {}
    for field_name, default in prompt_fields_for_target(kind):
        if default is None:
            config[field_name] = click.prompt(field_name)
        else:
            config[field_name] = click.prompt(field_name, default=default)
    suggested = provider_kind_for_target(kind)
    provider = click.prompt("Provider alias", default=suggested)
    return TargetDraft(provider=str(provider).strip(), kind=kind, config=config)


def _interactive_draft(
    path: Path,
    *,
    name: str | None,
    kind: str | None,
    generator_config: dict[str, Any],
    targets: list[TargetDraft],
    source: SourceDraft | None,
    source_set: bool,
    mode: str,
) -> tuple[SecretDraft, str, bool]:
    rows = _inventory(path)
    _print_inventory(rows)
    resolved_mode = mode
    if resolved_mode == "upsert":
        action = _choose(
            "Add a new secret or edit an existing one?", ["add", "edit"], default="add"
        )
        resolved_mode = "create" if action == "add" else "edit"
    if not name:
        if resolved_mode == "edit":
            if not rows:
                raise click.ClickException("Nothing to edit — this Secretfile has no secrets.")
            name = _choose("Secret to edit", [row["name"] for row in rows])
        else:
            name = click.prompt("Secret name")
    current = next((row for row in rows if row["name"] == name), None)
    if not kind:
        kind = _choose(
            "Generator kind",
            known_generator_kinds(),
            default=current["kind"] if current else None,
        )
    if not generator_config:
        generator_config = _prompt_generator_config(kind)
    if not source_set:
        source = _prompt_source()
    replace_targets = False
    if not targets:
        if current and current["targets"] and resolved_mode == "edit":
            replace_targets = click.confirm("Replace existing targets?", default=False)
        while click.confirm("Add a target?", default=True):
            targets.append(_prompt_target())
            if not click.confirm("Add another target?", default=False):
                break
    if not targets:
        if resolved_mode == "edit" and current and not replace_targets:
            for item in current["targets"]:
                targets.append(
                    TargetDraft(
                        provider=item["provider"],
                        kind=item["kind"],
                        config=dict(item.get("config") or {}),
                    )
                )
        if not targets:
            raise click.ClickException("Add at least one target.")
    return (
        SecretDraft(
            name=str(name),
            kind=str(kind),
            config=generator_config,
            targets=targets,
            source=source,
        ),
        resolved_mode if resolved_mode in {"create", "edit"} else "upsert",
        replace_targets,
    )


def run_add(
    *,
    file: str,
    name: str | None,
    kind: str | None,
    generator_config_items: tuple[str, ...],
    target_specs: tuple[str, ...],
    source_kind: str | None,
    source_config_items: tuple[str, ...],
    source_required: bool,
    edit: bool,
    create: bool,
    replace_targets: bool,
    dry_run: bool,
    yes: bool,
    interactive: bool,
    output_format: str,
) -> None:
    """Create or edit one secret definition."""
    path = Path(file)
    try:
        generator_config = parse_kv_pairs(generator_config_items)
        targets = [parse_target_spec(spec) for spec in target_specs]
        source: SourceDraft | None = None
        source_set = source_kind is not None
        if source_kind and source_kind != "none":
            source = SourceDraft(
                kind=source_kind,
                required=source_required,
                config=parse_kv_pairs(source_config_items),
            )
        elif source_kind == "none":
            source = None
            source_set = True

        if edit and create:
            raise click.ClickException("Pass only one of --edit or --create.")
        mode = "edit" if edit else "create" if create else "upsert"
        use_prompts = interactive or (sys.stdin.isatty() and (not name or not kind or not targets))
        resolved_mode = mode
        if use_prompts and not yes:
            draft, resolved_mode, prompted_replace = _interactive_draft(
                path,
                name=name,
                kind=kind,
                generator_config=generator_config,
                targets=targets,
                source=source,
                source_set=source_set,
                mode=mode,
            )
            replace_targets = replace_targets or prompted_replace
            if not click.confirm(f"Write '{draft.name}' to {path}?", default=True):
                console.print("[dim]Aborted. Secretfile unchanged.[/dim]")
                return
        else:
            if not name or not kind or not targets:
                raise click.ClickException(
                    "Non-interactive add needs a name, --kind, and at least one --target. "
                    "Pass --interactive to walk through the prompts."
                )
            if not generator_config:
                generator_config = default_generator_config(kind)
            draft = SecretDraft(
                name=name,
                kind=kind,
                config=generator_config,
                targets=targets,
                source=source,
            )
            if mode == "upsert":
                resolved_mode = "edit" if _name_exists(path, name) else "create"

        result = apply_secret_draft(
            path,
            draft,
            mode=resolved_mode,  # type: ignore[arg-type]
            replace_targets=replace_targets,
            update_source=source_set,
            dry_run=dry_run,
        )
    except SecretAuthorError as exc:
        raise click.ClickException(str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"Invalid JSON: {exc}") from exc

    _echo_result(result, output_format)


def _name_exists(path: Path, name: str) -> bool:
    return any(row["name"] == name for row in _inventory(path))


def _shared_options(func):  # type: ignore[no-untyped-def]
    func = click.argument("name", required=False)(func)
    func = click.option(
        "--file", "-f", default="Secretfile.yml", show_default=True, help="Secretfile path"
    )(func)
    func = click.option(
        "--kind", "-k", help="Generator kind (random_password, static, script, ...)"
    )(func)
    func = click.option(
        "--generator-config",
        "-G",
        "generator_config_items",
        multiple=True,
        help="Generator config KEY=VALUE. Repeatable. Static value/default must be null or ${VAR}.",
    )(func)
    func = click.option(
        "--target",
        "-t",
        "target_specs",
        multiple=True,
        help="Target as provider=<alias>,kind=<kind>,<config key>=<value>. Repeatable.",
    )(func)
    func = click.option(
        "--source-kind",
        type=click.Choice(["none", "file", "env", "secret_ref", "provider_read"]),
        help="Optional value source. 'none' clears it when editing.",
    )(func)
    func = click.option(
        "--source-config",
        "source_config_items",
        multiple=True,
        help="Source config KEY=VALUE. Repeatable. Use JSON for nested read={...}.",
    )(func)
    func = click.option(
        "--source-optional",
        "source_required",
        is_flag=True,
        default=True,
        flag_value=False,
        help="Mark the value source as optional (generator runs if it cannot resolve).",
    )(func)
    func = click.option(
        "--edit", is_flag=True, help="Edit an existing secret. Fails if the name is missing."
    )(func)
    func = click.option(
        "--create", is_flag=True, help="Create a new secret. Fails if the name already exists."
    )(func)
    func = click.option(
        "--replace-targets",
        is_flag=True,
        help="When editing, replace targets instead of appending new ones.",
    )(func)
    func = click.option(
        "--dry-run", is_flag=True, help="Validate and print the result without writing."
    )(func)
    func = click.option("--yes", "-y", is_flag=True, help="Skip the interactive confirmation.")(
        func
    )
    func = click.option(
        "--interactive", is_flag=True, help="Walk through prompts even when stdin is not a TTY."
    )(func)
    func = click.option(
        "--format",
        "output_format",
        type=click.Choice(["text", "json"]),
        default="text",
        show_default=True,
        help="Output format. JSON omits generator config so secret material stays out of stdout.",
    )(func)
    return func


def _command_callback(
    name: str | None,
    file: str,
    kind: str | None,
    generator_config_items: tuple[str, ...],
    target_specs: tuple[str, ...],
    source_kind: str | None,
    source_config_items: tuple[str, ...],
    source_required: bool,
    edit: bool,
    create: bool,
    replace_targets: bool,
    dry_run: bool,
    yes: bool,
    interactive: bool,
    output_format: str,
) -> None:
    run_add(
        file=file,
        name=name,
        kind=kind,
        generator_config_items=generator_config_items,
        target_specs=target_specs,
        source_kind=source_kind,
        source_config_items=source_config_items,
        source_required=source_required,
        edit=edit,
        create=create,
        replace_targets=replace_targets,
        dry_run=dry_run,
        yes=yes,
        interactive=interactive,
        output_format=output_format,
    )


@click.command("add")
@_shared_options
def add_command(
    name: str | None,
    file: str,
    kind: str | None,
    generator_config_items: tuple[str, ...],
    target_specs: tuple[str, ...],
    source_kind: str | None,
    source_config_items: tuple[str, ...],
    source_required: bool,
    edit: bool,
    create: bool,
    replace_targets: bool,
    dry_run: bool,
    yes: bool,
    interactive: bool,
    output_format: str,
) -> None:
    """Add or edit one secret's generator, optional value source, and targets.

    With a name, ``--kind``, and ``--target``, this writes the Secretfile directly.
    Without those flags on a terminal, it walks through the same choices.
    Static secret values are not accepted here — use ``secretzero web`` or
    ``secretzero sync`` to enter them.

    ``secretzero new`` is an alias of this command.
    """
    _command_callback(
        name,
        file,
        kind,
        generator_config_items,
        target_specs,
        source_kind,
        source_config_items,
        source_required,
        edit,
        create,
        replace_targets,
        dry_run,
        yes,
        interactive,
        output_format,
    )


@click.command("new")
@_shared_options
def new_command(
    name: str | None,
    file: str,
    kind: str | None,
    generator_config_items: tuple[str, ...],
    target_specs: tuple[str, ...],
    source_kind: str | None,
    source_config_items: tuple[str, ...],
    source_required: bool,
    edit: bool,
    create: bool,
    replace_targets: bool,
    dry_run: bool,
    yes: bool,
    interactive: bool,
    output_format: str,
) -> None:
    """Alias of ``secretzero add``."""
    _command_callback(
        name,
        file,
        kind,
        generator_config_items,
        target_specs,
        source_kind,
        source_config_items,
        source_required,
        edit,
        create,
        replace_targets,
        dry_run,
        yes,
        interactive,
        output_format,
    )
