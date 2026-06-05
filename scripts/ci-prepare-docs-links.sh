#!/usr/bin/env bash
# Materialize gitignored MkDocs artifacts (optional for lychee; root Secretfile.schema.json is committed).
set -euo pipefail

uv sync --frozen
uv run secretzero schema export --output docs/Secretfile.schema.json
test -f docs/Secretfile.schema.json
