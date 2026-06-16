"""MCP server entry point for SecretZero."""

from __future__ import annotations

import sys


def main() -> None:
    """Run the SecretZero MCP server over stdio."""
    from secretzero.mcp.app import create_mcp_app
    from secretzero.mcp.backend.factory import build_backend
    from secretzero.mcp.config import load_mcp_config
    from secretzero.mcp.guards import apply_startup_env

    try:
        cfg = load_mcp_config(argv=sys.argv[1:])
    except ValueError as exc:
        print(f"secretzero-mcp: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    apply_startup_env(cfg)

    try:
        backend = build_backend(cfg)
    except ValueError as exc:
        print(f"secretzero-mcp: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    app = create_mcp_app(cfg, backend)
    app.run(transport="stdio")


if __name__ == "__main__":
    main()
