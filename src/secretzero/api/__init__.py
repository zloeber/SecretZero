"""REST API integration for SecretZero.

This package provides the FastAPI application used for the optional
SecretZero API server. To avoid forcing API dependencies (FastAPI,
uvicorn, etc.) on users who only need the CLI, we intentionally avoid
importing the FastAPI app at module import time.

Use :func:`create_app` to construct the FastAPI application when the
API extras are installed and you actually want to run the server.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - used only for type checking
    # This import is only evaluated by type checkers and does not
    # pull in FastAPI at runtime unless the function is called.
    from secretzero.api.app import create_app as _create_app

__all__ = ["create_app"]


def create_app(*args: Any, **kwargs: Any):
    """Lazily import and construct the FastAPI application.

    This indirection ensures that importing :mod:`secretzero.api`
    does not require the optional API dependencies to be installed.
    FastAPI (and its transitive dependencies) are only imported when
    this function is actually called.
    """

    from secretzero.api.app import create_app as _create_app

    return _create_app(*args, **kwargs)
