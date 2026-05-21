"""Shared HCL literal formatting for Terraform-related output."""

from __future__ import annotations

import json


def format_hcl_string(value: str) -> str:
    """Render a Python string as an HCL double-quoted literal."""
    return json.dumps(value)


def format_hcl_assignment(key: str, value: str) -> str:
    """Render a single top-level tfvars assignment."""
    return f"{key} = {format_hcl_string(value)}"
