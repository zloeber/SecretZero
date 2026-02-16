"""Random string generator."""

import secrets
import string
from typing import Any

from secretzero.generators.base import BaseGenerator


class RandomStringGenerator(BaseGenerator):
    """Generate random alphanumeric strings."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize string generator.

        Args:
            config: Configuration with options:
                - length: String length (default: 32)
                - charset: Character set to use (default: alphanumeric)
                  Options: "alphanumeric", "alpha", "numeric", "hex"
        """
        super().__init__(config)
        self.length = config.get("length", 32)
        charset_type = config.get("charset", "alphanumeric")

        # Define character sets
        charsets = {
            "alphanumeric": string.ascii_letters + string.digits,
            "alpha": string.ascii_letters,
            "numeric": string.digits,
            "hex": string.hexdigits.lower(),
        }

        self.charset = charsets.get(charset_type, charsets["alphanumeric"])

    def generate(self) -> str:
        """Generate a random string.

        Returns:
            Generated random string
        """
        return "".join(secrets.choice(self.charset) for _ in range(self.length))
