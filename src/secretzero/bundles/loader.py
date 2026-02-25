"""Dynamic class loader for SecretZero provider bundles.

Provides utilities for loading Python classes from dotted path strings,
enabling the bundle registry to dynamically import provider, generator,
and target classes from third-party packages.
"""

import importlib
from typing import Any


def load_class(dotted_path: str) -> type:
    """Load a class from a dotted path string.

    The path format is ``'module.submodule:ClassName'``, where the colon
    separates the importable module path from the attribute name.

    Args:
        dotted_path: Dotted path in ``'module.path:ClassName'`` format.

    Returns:
        The class referenced by the path.

    Raises:
        ValueError: If the path format is invalid (no colon separator).
        ImportError: If the module cannot be imported.
        AttributeError: If the class cannot be found in the module.

    Example:
        >>> cls = load_class("secretzero.generators.static:StaticGenerator")
        >>> cls.__name__
        'StaticGenerator'
    """
    if ":" not in dotted_path:
        raise ValueError(
            f"Invalid dotted path '{dotted_path}': expected 'module.path:ClassName' format"
        )

    module_path, class_name = dotted_path.rsplit(":", 1)
    module = importlib.import_module(module_path)
    cls: type = getattr(module, class_name)
    return cls


def load_class_safe(dotted_path: str) -> type[Any] | None:
    """Load a class from a dotted path string, returning None on failure.

    Convenience wrapper around :func:`load_class` that catches all errors
    and returns ``None`` instead of raising, enabling graceful degradation.

    Args:
        dotted_path: Dotted path in ``'module.path:ClassName'`` format.

    Returns:
        The class if loading succeeded, or ``None`` on any error.
    """
    try:
        return load_class(dotted_path)
    except (ImportError, AttributeError, ValueError, Exception):
        return None
