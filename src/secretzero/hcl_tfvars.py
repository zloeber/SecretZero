"""Parse and format flat Terraform ``.tfvars`` assignment files."""

from __future__ import annotations

import re

from secretzero.hcl_values import format_hcl_assignment

_ASSIGNMENT_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*=\s*(.+)$")
_UNSUPPORTED_VALUE_RE = re.compile(r"(<<|\{|\[)")

_TFVARS_HEADER = "# Written by SecretZero — keep gitignored; do not commit secrets."


def parse_tfvars(content: str) -> dict[str, str]:
    """Parse flat top-level ``name = value`` assignments from tfvars text.

    Raises:
        ValueError: On unsupported constructs (nested types, heredocs) or bad syntax.
    """
    result: dict[str, str] = {}
    for line_no, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        match = _ASSIGNMENT_RE.match(line)
        if not match:
            raise ValueError(f"Invalid tfvars assignment at line {line_no}: {raw_line!r}")

        key, value_part = match.group(1), match.group(2).strip()
        if _UNSUPPORTED_VALUE_RE.search(value_part):
            raise ValueError(
                f"Unsupported tfvars value at line {line_no} (nested/heredoc not supported): "
                f"{raw_line!r}"
            )

        result[key] = _parse_value(value_part, line_no=line_no, raw_line=raw_line)

    return result


def format_tfvars(data: dict[str, str], *, include_header: bool = False) -> str:
    """Format assignments as tfvars text with stable key ordering."""
    lines: list[str] = []
    if include_header:
        lines.append(_TFVARS_HEADER)
    for key in sorted(data):
        lines.append(format_hcl_assignment(key, data[key]))
    return "\n".join(lines) + ("\n" if lines else "")


def _parse_value(value_part: str, *, line_no: int, raw_line: str) -> str:
    if value_part.startswith('"'):
        return _parse_double_quoted(value_part, line_no=line_no, raw_line=raw_line)

    lowered = value_part.lower()
    if lowered in ("true", "false"):
        return lowered

    if re.fullmatch(r"-?\d+(\.\d+)?", value_part):
        return value_part

    raise ValueError(
        f"Unsupported tfvars value at line {line_no} (expected quoted string): {raw_line!r}"
    )


def _parse_double_quoted(value_part: str, *, line_no: int, raw_line: str) -> str:
    if not value_part.endswith('"') or len(value_part) < 2:
        raise ValueError(f"Unterminated string at line {line_no}: {raw_line!r}")

    chars: list[str] = []
    i = 1
    while i < len(value_part) - 1:
        ch = value_part[i]
        if ch != "\\":
            chars.append(ch)
            i += 1
            continue

        i += 1
        if i >= len(value_part) - 1:
            raise ValueError(f"Unterminated escape at line {line_no}: {raw_line!r}")

        esc = value_part[i]
        if esc == "n":
            chars.append("\n")
        elif esc == "r":
            chars.append("\r")
        elif esc == "t":
            chars.append("\t")
        elif esc == '"':
            chars.append('"')
        elif esc == "\\":
            chars.append("\\")
        elif esc == "u" and i + 4 < len(value_part) - 1:
            hex_part = value_part[i + 1 : i + 5]
            if re.fullmatch(r"[0-9a-fA-F]{4}", hex_part):
                chars.append(chr(int(hex_part, 16)))
                i += 4
            else:
                chars.append(esc)
        else:
            chars.append(esc)
        i += 1

    return "".join(chars)
