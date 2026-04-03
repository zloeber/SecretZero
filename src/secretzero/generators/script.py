"""Script-based generator."""

import os
import subprocess
from typing import Any

from secretzero.generators.base import BaseGenerator
from secretzero.models import AgentInstructions, AgentInstructionStep


class ScriptGenerator(BaseGenerator):
    """Execute external scripts to generate secret values."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize script generator.

        Args:
            config: Configuration with options:
                - command: Command/script to execute
                - args: Optional list of arguments
                - shell: Whether to use shell execution (default: False)
                - timeout: Execution timeout in seconds (default: 30)
        """
        super().__init__(config)
        self.command = config.get("command", "")
        self.args = config.get("args", [])
        self.use_shell = config.get("shell", False)
        self.timeout = config.get("timeout", 30)

    def generate(self) -> str:
        """Execute script and return output as secret value.

        Returns:
            Script output as secret value

        Raises:
            ValueError: If command is not specified
            RuntimeError: If script execution fails
        """
        if not self.command:
            raise ValueError("Script command is required")

        try:
            # Build command list
            if self.use_shell:
                if os.name == "nt":
                    cmd = ["cmd", "/c", self.command]
                else:
                    cmd = ["/bin/sh", "-c", self.command]
            else:
                cmd = [self.command] + self.args

            # Execute script
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                shell=False,
                timeout=self.timeout,
                check=True,
            )

            # Return stripped output
            return result.stdout.strip()

        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"Script execution timed out after {self.timeout}s") from e
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Script execution failed with exit code {e.returncode}: {e.stderr}"
            ) from e
        except Exception as e:
            raise RuntimeError(f"Script execution error: {e}") from e

    def get_manual_instructions(self) -> AgentInstructions:
        """Return step-by-step instructions for manually running the script.

        These instructions are displayed when the script fails or cannot be
        executed in the current environment.

        Returns:
            AgentInstructions describing how to run the script manually.
        """
        if self.manual_instructions is not None:
            return self.manual_instructions

        command = self.command
        args_str = " ".join(str(a) for a in self.args) if self.args else ""
        full_command = f"{command} {args_str}".strip() if args_str else command

        steps = [
            AgentInstructionStep(
                action=f"Run the command: {full_command}",
                description="Execute the script in a terminal with appropriate permissions",
            ),
            AgentInstructionStep(
                action="Capture the standard output of the command",
                description="The secret value is the trimmed stdout of the script",
            ),
            AgentInstructionStep(
                action="Copy the output value",
                description="Paste the script output as the secret value when prompted",
            ),
        ]

        prerequisites = []
        if self.use_shell:
            prerequisites.append("A POSIX-compatible shell (/bin/sh) or cmd.exe on Windows")
        else:
            prerequisites.append(f"The executable '{command}' available in PATH")

        return AgentInstructions(
            summary=(
                f"Script-based secret generation failed (command: '{full_command}'). "
                "Follow these steps to run the script manually and obtain the secret value."
            ),
            steps=steps,
            prerequisites=prerequisites,
            estimated_time="1–5 minutes",
            automation_hint=(
                f"Secret generation can be automated by ensuring '{command}' is executable "
                "and returns the expected output on stdout."
            ),
            fallback=(
                "If the script cannot be run, contact the person who configured this secret "
                "to obtain the value or an alternative."
            ),
        )
