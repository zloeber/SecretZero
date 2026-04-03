"""Base generator class for secret generation."""

import os
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from secretzero.models import AgentInstructions


class BaseGenerator(ABC):
    """Abstract base class for secret generators."""

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
    def generate(self) -> str:
        """Generate a secret value.

        Returns:
            Generated secret value as a string
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

        Formats and prints the instructions so the user understands exactly
        how to obtain the secret value manually.

        Args:
            instructions: Instructions to display.
        """
        separator = "=" * 60
        print()
        print(separator)
        print("MANUAL RETRIEVAL INSTRUCTIONS")
        print(separator)
        print(instructions.summary)

        if instructions.prerequisites:
            print()
            print("Prerequisites:")
            for prereq in instructions.prerequisites:
                print(f"  • {prereq}")

        if instructions.required_tools:
            print()
            print("Required tools:")
            for tool in instructions.required_tools:
                print(f"  • {tool}")

        if instructions.steps:
            print()
            print("Steps:")
            for i, step in enumerate(instructions.steps, 1):
                print(f"  {i}. {step.description}")
                if step.action:
                    print(f"     → {step.action}")

        if instructions.estimated_time:
            print()
            print(f"Estimated time: {instructions.estimated_time}")

        if instructions.documentation_url:
            print()
            print(f"Documentation: {instructions.documentation_url}")

        if instructions.fallback:
            print()
            print(f"Fallback: {instructions.fallback}")

        print(separator)
        print()

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
