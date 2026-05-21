"""Collect and render ``agent_instructions`` reports for CLI and tooling."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from rich.console import Console
from rich.rule import Rule

from secretzero.agent import secret_supports_automatic_generation
from secretzero.lockfile import Lockfile
from secretzero.models import AgentInstructions, Secret, Secretfile


class InstructionScope(str, Enum):
    """Which secrets to include in an instructions report."""

    PENDING = "pending"
    ALL = "all"


@dataclass(frozen=True)
class InstructionEntry:
    """One secret's rendered agent instructions."""

    secret_name: str
    instructions: AgentInstructions


def _secret_matches_filter(secret_name: str, secret_names: frozenset[str] | None) -> bool:
    if secret_names is None:
        return True
    return secret_name in secret_names


def _is_pending_manual_secret(secret: Secret, lockfile: Lockfile) -> bool:
    if lockfile.get_secret_info(secret.name) is not None:
        return False
    if secret_supports_automatic_generation(secret):
        return False
    return secret.agent_instructions is not None


def collect_instruction_entries(
    secretfile: Secretfile,
    lockfile: Lockfile,
    *,
    scope: InstructionScope = InstructionScope.PENDING,
    secret_names: frozenset[str] | None = None,
) -> list[InstructionEntry]:
    """Return rendered instruction entries for the requested scope."""
    entries: list[InstructionEntry] = []
    for secret in secretfile.secrets:
        if not _secret_matches_filter(secret.name, secret_names):
            continue
        if secret.agent_instructions is None:
            continue
        if scope == InstructionScope.PENDING and not _is_pending_manual_secret(secret, lockfile):
            continue
        rendered = secret.agent_instructions.render_for_secret(
            variables=secretfile.variables,
            secret_name=secret.name,
            secret=secret,
        )
        entries.append(InstructionEntry(secret_name=secret.name, instructions=rendered))
    return entries


def _instructions_to_dict(
    instructions: AgentInstructions,
    *,
    detailed: bool,
) -> dict[str, Any]:
    payload = instructions.model_dump(exclude_none=True)
    if detailed:
        return payload
    return {
        "summary": payload["summary"],
        "steps": payload.get("steps", []),
    }


def build_instructions_json_payload(
    entries: list[InstructionEntry],
    *,
    scope: InstructionScope,
    detailed: bool = False,
) -> dict[str, Any]:
    """Build machine-readable instructions report payload (no secret values)."""
    return {
        "scope": scope.value,
        "total": len(entries),
        "secrets": {
            entry.secret_name: _instructions_to_dict(entry.instructions, detailed=detailed)
            for entry in entries
        },
    }


def _render_optional_section(
    console: Console,
    *,
    title: str,
    lines: list[str] | None,
    bullet: bool = True,
) -> None:
    if not lines:
        return
    console.print(f"\n  [bold yellow]{title}:[/bold yellow]")
    for line in lines:
        prefix = "    • " if bullet else "    "
        console.print(f"{prefix}{line}")


def instruction_entries_from_mapping(
    pending_secrets: dict[str, AgentInstructions],
) -> list[InstructionEntry]:
    """Build report entries from a pending-secrets mapping (e.g. agent sync result)."""
    return [
        InstructionEntry(secret_name=secret_name, instructions=instructions)
        for secret_name, instructions in pending_secrets.items()
    ]


def render_instruction_entries(
    entries: list[InstructionEntry],
    console: Console,
    *,
    detailed: bool = False,
    header: str | None = None,
) -> None:
    """Print one or more instruction entries using the shared Rich layout."""
    if not entries:
        return
    if header:
        console.print(header)
    for entry in entries:
        _render_instruction_entry(console, entry, detailed=detailed)


def _render_instruction_entry(
    console: Console,
    entry: InstructionEntry,
    *,
    detailed: bool,
) -> None:
    instructions = entry.instructions
    console.print()
    console.print(Rule(f"[bold cyan]{entry.secret_name}[/bold cyan]", style="cyan"))
    console.print(f"  [bold]Summary:[/bold] {instructions.summary}")

    if detailed:
        _render_optional_section(
            console,
            title="Prerequisites",
            lines=instructions.prerequisites,
        )
        if instructions.required_tools:
            _render_optional_section(
                console,
                title="Required tools",
                lines=instructions.required_tools,
            )

    if instructions.steps:
        console.print("\n  [bold blue]Steps:[/bold blue]")
        for index, step in enumerate(instructions.steps, 1):
            console.print(f"    {index}. [bold]{step.action}[/bold]")
            if step.description:
                console.print(f"       [dim]{step.description}[/dim]")

    if not detailed:
        return

    if instructions.automation_hint:
        console.print(
            f"\n  [italic]Automation:[/italic] {instructions.automation_hint}",
        )
    if instructions.estimated_time:
        console.print(f"  [italic]Estimated time:[/italic] {instructions.estimated_time}")
    if instructions.fallback:
        console.print(f"  [italic]Fallback:[/italic] {instructions.fallback}")
    if instructions.documentation_url:
        console.print(f"  [blue]Docs:[/blue] {instructions.documentation_url}")


def render_instructions_console(
    entries: list[InstructionEntry],
    console: Console,
    *,
    detailed: bool = False,
    scope: InstructionScope = InstructionScope.PENDING,
) -> None:
    """Print a concise numbered Rich report for agent instructions."""
    if not entries:
        if scope == InstructionScope.PENDING:
            console.print("[dim]No pending secrets with agent instructions[/dim]")
        else:
            console.print("[dim]No secrets with agent instructions[/dim]")
        return

    scope_label = "pending manual" if scope == InstructionScope.PENDING else "all configured"
    header = (
        f"\n[bold]Agent instructions[/bold] "
        f"([cyan]{len(entries)}[/cyan] {scope_label} secret"
        f"{'' if len(entries) == 1 else 's'})"
    )
    render_instruction_entries(entries, console, detailed=detailed, header=header)
