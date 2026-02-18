"""Random password generator."""

import secrets
import string
from typing import Any

from secretzero.generators.base import BaseGenerator


class RandomPasswordGenerator(BaseGenerator):
    """Generate cryptographically secure random passwords."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize password generator.

        Args:
            config: Configuration with options:
                - length: Password length (default: 32)
                - upper: Include uppercase letters (default: True)
                - lower: Include lowercase letters (default: True)
                - number: Include numbers (default: True)
                - special: Include special characters (default: True)
                - exclude_characters: Characters to exclude (default: "")
        """
        super().__init__(config)
        self.length = config.get("length", 32)
        self.use_upper = config.get("upper", True)
        self.use_lower = config.get("lower", True)
        self.use_number = config.get("number", True)
        self.use_special = config.get("special", True)
        self.exclude_characters = config.get("exclude_characters", "")

    def generate(self) -> str:
        """Generate a random password.

        Returns:
            Generated password string

        Raises:
            ValueError: If no character types are enabled
        """
        # Build character set based on configuration
        charset = ""

        if self.use_upper:
            charset += string.ascii_uppercase
        if self.use_lower:
            charset += string.ascii_lowercase
        if self.use_number:
            charset += string.digits
        if self.use_special:
            charset += string.punctuation

        if not charset:
            raise ValueError("At least one character type must be enabled")

        # Remove excluded characters
        if self.exclude_characters:
            charset = "".join(c for c in charset if c not in self.exclude_characters)

        if not charset:
            raise ValueError("Character set is empty after applying exclusions")

        # Generate password using cryptographically secure random
        password = "".join(secrets.choice(charset) for _ in range(self.length))

        return password
