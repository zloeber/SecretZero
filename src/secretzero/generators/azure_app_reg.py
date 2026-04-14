"""Entra / Azure AD app registration-shaped secrets (static-compatible)."""

from __future__ import annotations

from secretzero.generators.static import StaticGenerator


class AzureAppRegGenerator(StaticGenerator):
    """Same behavior as :class:`~secretzero.generators.static.StaticGenerator`.

    Use ``kind: azure_app_reg`` in the manifest for Entra app registration
    credentials (e.g. ``tenant_id``, ``client_id``, ``client_secret``) so the
    Azure provider bundle can own the kind string while CLI, API, and web
    surfaces still apply static-style dict/scalar prompts and Vector 2 forms.
    """

    PROMPTS_LIKE_STATIC = True
