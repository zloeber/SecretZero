"""CLI command for validating and formatting Secretfile.yml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click
from rich.console import Console

try:  # Optional dependency: installed in dev, may be missing in older envs
    from ruamel.yaml import YAML
except ImportError:  # pragma: no cover - exercised in user environments without ruamel.yaml
    YAML = None  # type: ignore[assignment]

from secretzero.config import ConfigLoader

console = Console()


@click.command("format")
@click.option(
    "--file",
    "-f",
    "file_path",
    type=click.Path(),
    default="Secretfile.yml",
    help="Path to Secretfile.yml to validate and format",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Validate and print formatted YAML to stdout without modifying the file",
)
@click.option(
    "--add-missing",
    is_flag=True,
    help="Also add missing default values inside the config block (creating it if missing)",
)
def format_command(file_path: str, dry_run: bool, add_missing: bool) -> None:
    """Validate and reformat a Secretfile.yml without losing comments."""
    path = Path(file_path)

    loader = ConfigLoader()
    is_valid, message = loader.validate_file(path)
    if not is_valid:
        console.print(f"[red]Error:[/red] {message}")
        raise SystemExit(1)

    if YAML is None:
        console.print(
            "[red]Error:[/red] Optional dependency [cyan]ruamel.yaml[/cyan] is required for "
            "`secretzero format`. Install it with "
            "[cyan]pip install 'ruamel.yaml>=0.18.0'[/cyan] or upgrade/reinstall SecretZero."
        )
        raise SystemExit(1)

    # Use ruamel.yaml round-trip loader/dumper so comments and formatting are preserved.
    yaml_rt = YAML(typ="rt")
    yaml_rt.preserve_quotes = True
    yaml_rt.width = 120  # wrap long lines / strings nicely

    try:
        with path.open("r", encoding="utf-8") as f:
            data: Any = yaml_rt.load(f)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Error:[/red] Failed to parse YAML from {path}: {exc}")
        raise SystemExit(1)

    if data is None:
        console.print(f"[red]Error:[/red] Secretfile {path} is empty.")
        raise SystemExit(1)

    # Optionally, add missing default values under the ``config`` block.
    if add_missing:
        try:
            secretfile_model = loader.load_file(path)
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]Error:[/red] Failed to load Secretfile for defaults {path}: {exc}")
            raise SystemExit(1)

        model_data = secretfile_model.model_dump(mode="json", exclude_none=True)

        def _merge_missing(src: Any, dest: Any) -> None:
            if not isinstance(src, dict) or not isinstance(dest, dict):
                return
            for key, value in src.items():
                if key not in dest:
                    dest[key] = value
                else:
                    _merge_missing(value, dest[key])

        if isinstance(model_data, dict) and isinstance(data, dict):
            # Only proceed if the model has a config block.
            if "config" in model_data and isinstance(model_data["config"], dict):
                # If the YAML has no config block yet, create it wholesale from defaults.
                if "config" not in data or not isinstance(data["config"], dict):
                    data["config"] = model_data["config"]
                else:
                    _merge_missing(model_data["config"], data["config"])

    if dry_run:
        # Print the round-tripped YAML (with optional merged defaults) to stdout.
        import io

        buf = io.StringIO()
        yaml_rt.dump(data, buf)
        click.echo(buf.getvalue())
        return

    with path.open("w", encoding="utf-8") as f:
        yaml_rt.dump(data, f)

    console.print(f"[green]✓[/green] Secretfile validated and formatted: [cyan]{path}[/cyan]")
