"""Script-based generator."""

import subprocess
from typing import Any

from secretzero.generators.base import BaseGenerator


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
                cmd = self.command
            else:
                cmd = [self.command] + self.args

            # Execute script
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                shell=self.use_shell,
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
