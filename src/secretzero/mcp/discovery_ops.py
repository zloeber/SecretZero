"""Metadata-only secret discovery helpers for MCP backends."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from secretzero.cli_config import get_effective_config
from secretzero.discovery import DiscoveryAgent
from secretzero.mcp.config import McpConfig


def resolve_scan_directory(cfg: McpConfig, directory: str | None = None) -> Path:
    """Resolve and jail a scan directory under the configured workspace root."""
    raw = directory or str(cfg.workspace_root)
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    else:
        path = path.resolve()
    root = cfg.workspace_root.resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"Directory {path} is outside workspace root {root}")
    return path


def run_detect_scan(
    directory: Path,
    *,
    all_keys: bool = False,
) -> dict[str, Any]:
    """Scan for dotenv-style secret key names without reading values into output."""
    secret_suffixes = r"(PASSWORD|SECRET|KEY|TOKEN|CREDENTIAL|CERT|PRIVATE)"
    secret_prefixes = r"(PWD|PASS|AUTH|API)"
    secret_patterns = [
        (re.compile(rf"^([A-Z_][A-Z0-9_]*{secret_suffixes}[A-Z0-9_]*)=", re.M), "dotenv"),
        (re.compile(rf"^([A-Z_][A-Z0-9_]*_{secret_prefixes})\s*=", re.M), "dotenv"),
    ]
    if all_keys:
        secret_patterns = [(re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=", re.M), "dotenv")]

    ignored_dir_parts = {
        ".git",
        "__pycache__",
        "venv",
        ".venv",
        "node_modules",
        ".terraform",
        "dist",
        "build",
    }

    def _should_ignore(path: Path) -> bool:
        try:
            parts = path.relative_to(directory).parts
        except ValueError:
            parts = path.parts
        return any(part in ignored_dir_parts for part in parts)

    found: dict[str, dict[str, Any]] = {}

    for path in directory.rglob("*"):
        if not path.is_file() or _should_ignore(path):
            continue
        name_lower = path.name.lower()
        is_env_file = name_lower.startswith(".env") or name_lower.endswith(".env")
        is_secret_file = name_lower.startswith(("secrets", "credentials"))
        if not (is_env_file or is_secret_file):
            continue
        try:
            content = path.read_text(errors="ignore")
            for pattern, file_type in secret_patterns:
                for match in pattern.finditer(content):
                    var_name = match.group(1).lower()
                    if var_name not in found:
                        found[var_name] = {
                            "name": var_name,
                            "env_var": match.group(1),
                            "file": str(path.relative_to(directory)),
                            "file_type": file_type,
                        }
        except (OSError, UnicodeDecodeError):
            continue

    suggestions = []
    for var_name, info in sorted(found.items()):
        suggestions.append(
            {
                "name": var_name,
                "env_var": info["env_var"],
                "source_file": info["file"],
                "suggested_config": {
                    "name": var_name,
                    "kind": "static",
                    "config": {"default": f"${{{info['env_var']}}}"},
                    "targets": [
                        {
                            "provider": "local",
                            "kind": "file",
                            "config": {"path": ".env", "format": "dotenv"},
                        }
                    ],
                },
            }
        )

    return {
        "detected": suggestions,
        "total": len(suggestions),
        "all_keys": all_keys,
        "directory": str(directory),
    }


def run_discover_bindings(
    directory: Path,
    *,
    local_only: bool = True,
) -> dict[str, Any]:
    """Run pattern-based discovery (no LLM) and return metadata-only bindings."""
    secretfile_path = directory / "Secretfile.yml"
    effective = get_effective_config(
        secretfile_path=secretfile_path if secretfile_path.exists() else None
    )
    agent = DiscoveryAgent(config=effective.config)
    result = agent.discover(
        project_root=directory,
        dry_run=True,
        use_llm=False,
        local_only=local_only,
        verbose=False,
    )
    return {
        "files_scanned": result.files_scanned,
        "total_secrets": result.total_secrets,
        "dry_run": True,
        "directory": str(directory),
        "llm_used": False,
        "secrets": [
            {
                "name": candidate.name,
                "description": candidate.description,
                "confidence": candidate.confidence,
                "generator": candidate.suggested_generator,
                "source_file": candidate.source_file,
                "line": candidate.line_number,
                "tags": candidate.tags,
                "containing_symbol": candidate.containing_symbol,
                "symbol_fqn": candidate.symbol_fqn,
                "symbol_id": candidate.symbol_id,
            }
            for candidate in result.candidates
        ],
    }
