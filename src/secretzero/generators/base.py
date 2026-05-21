"""Base generator class for secret generation."""

import os
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from secretzero.models import AgentInstructions


class BaseGenerator(ABC):
    """Abstract base class for secret generators."""

    #: When True, this kind uses the same manifest shape and prompting rules as
    #: :class:`~secretzero.generators.static.StaticGenerator` (scalar or dict
    #: ``value`` / ``default``). Bundle-registered generators can set this so
    #: agent sync, CLI, and web UIs treat the secret like ``kind: static``.
    PROMPTS_LIKE_STATIC: ClassVar[bool] = False

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize generator with configuration.

        Args:
            config: Generator configuration dictionary
        """
        self.config = config
        self.field_description = None
        self.hide_input = False
        self.manual_instructions: AgentInstructions | None = None

    @abstractmethod
    def generate(self) -> Any:
        """Generate a secret value.

        Returns:
            Generated secret value (typically a string; static may return a dict)
        """
        pass

    def get_manual_instructions(self) -> "AgentInstructions | None":
        """Return step-by-step manual instructions for obtaining this secret.

        Called when automatic generation fails or interactive input is required
        so that the user is shown clear directions for retrieving the secret by
        hand.

        Subclasses should override this to provide generator- or provider-
        specific guidance.  When ``manual_instructions`` has been set on the
        instance (e.g. from a Secretfile ``agent_instructions`` block) that
        value is returned directly as the user-defined instructions take
        precedence over built-in defaults.

        Returns:
            AgentInstructions with step-by-step manual retrieval directions,
            or ``None`` if no instructions are available.
        """
        return self.manual_instructions

    @staticmethod
    def _display_manual_instructions(instructions: "AgentInstructions") -> None:
        """Print manual retrieval instructions to the console.

        Uses the shared Rich renderer (detailed mode) so sync-time prompts match
        ``secretzero agent instructions --detailed`` formatting.

        Args:
            instructions: Instructions to display.
        """
        from rich.console import Console

        from secretzero.agent_instructions_report import (
            InstructionEntry,
            render_instruction_entries,
        )

        entry = InstructionEntry(secret_name="Manual retrieval", instructions=instructions)
        render_instruction_entries(
            [entry],
            Console(),
            detailed=True,
            header="\n[bold]Manual retrieval instructions[/bold]",
        )

    def generate_with_fallback(
        self, env_var_name: str | None = None, field_description: str | None = None
    ) -> str:
        """Generate a secret value with environment variable fallback.

        First checks for an environment variable, then falls back to generation.

        Args:
            env_var_name: Optional environment variable name to check first
            field_description: Optional field description for context in prompts

        Returns:
            Secret value from environment or generated
        """
        if field_description:
            self.field_description = field_description

        if env_var_name:
            env_value = os.environ.get(env_var_name)
            if env_value:
                return env_value

        return self.generate()
