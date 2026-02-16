"""Secret storage targets for SecretZero."""

from secretzero.targets.base import BaseTarget
from secretzero.targets.file import FileTarget

__all__ = [
    "BaseTarget",
    "FileTarget",
]
