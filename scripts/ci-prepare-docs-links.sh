#!/usr/bin/env bash
# Materialize generated doc artifacts required by lychee (not committed; see .gitignore).
set -euo pipefail

uv sync --frozen
uv run secretzero schema export --output docs/Secretfile.schema.json
