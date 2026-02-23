"""Server entry point for the SecretZero API."""

import os
import sys
from pathlib import Path

try:
    import uvicorn
except ImportError:
    print("Error: FastAPI and uvicorn are required to run the API server.")
    print("Install with: pip install secretzero[api]")
    sys.exit(1)

from secretzero.api.app import create_app


def run() -> None:
    """Run the SecretZero API server."""
    # Get configuration from environment
    host = os.environ.get("SECRETZERO_HOST", "127.0.0.1")
    port = int(os.environ.get("SECRETZERO_PORT", "8000"))
    secretfile_path = os.environ.get("SECRETZERO_CONFIG", "Secretfile.yml")
    reload = os.environ.get("SECRETZERO_RELOAD", "false").lower() == "true"

    # Check if Secretfile exists
    config_path = Path(secretfile_path)
    if not config_path.exists():
        print(f"Warning: Secretfile not found at {secretfile_path}")
        print("Some API endpoints may not work correctly.")

    # Create app
    app = create_app(secretfile_path=secretfile_path)

    # Print startup info
    print("\n🔐 SecretZero API Server")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"Host:        {host}")
    print(f"Port:        {port}")
    print(f"Config:      {secretfile_path}")
    print(f"Docs:        http://{host}:{port}/docs")
    print(f"ReDoc:       http://{host}:{port}/redoc")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    # Check for API key
    if "SECRETZERO_API_KEY" in os.environ:
        print("🔑 API Key authentication enabled")
    else:
        print("⚠️  WARNING: Running in insecure mode (no API key required)")
        print("   Set SECRETZERO_API_KEY environment variable to enable authentication")

    print()

    # Run server
    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    run()
