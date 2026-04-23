#!/usr/bin/env zsh

set -euo pipefail

changed_list_file=""
diff_range=""

usage() {
  cat <<'EOF'
Usage: ./scripts/check-schema-doc-parity.sh [--changed-file-list <path> | --diff-range <range>]

Options:
  --changed-file-list <path>  Path to newline-separated changed files
  --diff-range <range>        Git diff range (e.g. origin/main...HEAD)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --changed-file-list)
      [[ $# -lt 2 ]] && { echo "Error: --changed-file-list requires a value"; exit 1; }
      changed_list_file="$2"
      shift 2
      ;;
    --diff-range)
      [[ $# -lt 2 ]] && { echo "Error: --diff-range requires a value"; exit 1; }
      diff_range="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Error: unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ -n "${changed_list_file}" && -n "${diff_range}" ]]; then
  echo "Error: use either --changed-file-list or --diff-range, not both."
  exit 1
fi

tmp_changed="$(mktemp)"
trap 'rm -f "${tmp_changed}"' EXIT

if [[ -n "${changed_list_file}" ]]; then
  if [[ ! -f "${changed_list_file}" ]]; then
    echo "Error: changed file list not found: ${changed_list_file}"
    exit 1
  fi
  cp "${changed_list_file}" "${tmp_changed}"
elif [[ -n "${diff_range}" ]]; then
  git diff --name-only "${diff_range}" | sort -u > "${tmp_changed}"
else
  git diff --name-only HEAD | sort -u > "${tmp_changed}"
fi

# Activate parity gate when schema-surface files change.
if ! rg -q '^(src/secretzero/models.py|Secretfile.schema.json)$' "${tmp_changed}"; then
  echo "schema-doc-parity: skip (no schema-surface changes detected)"
  exit 0
fi

required_files=(
  "Secretfile.schema.json"
  "docs/schema.md"
  "docs/user-guide/configuration/index.md"
)

missing_required=0
for required in "${required_files[@]}"; do
  if ! rg -q "^${required}$" "${tmp_changed}"; then
    echo "schema-doc-parity: missing required update -> ${required}"
    missing_required=1
  fi
done

if ! rg -q '^examples/.+\.yml$' "${tmp_changed}" \
  && ! rg -q '^examples/.+/README.md$' "${tmp_changed}" \
  && ! rg -q '^Secretfile\.example\.yml$' "${tmp_changed}"; then
  echo "schema-doc-parity: no example manifest/docs update detected (examples/* or Secretfile.example.yml)"
  missing_required=1
fi

if [[ "${missing_required}" -ne 0 ]]; then
  cat <<'EOF'
schema-doc-parity: FAILED

When schema-facing files change (src/secretzero/models.py or Secretfile.schema.json),
you must update all parity surfaces:
  - Secretfile.schema.json
  - docs/schema.md
  - docs/user-guide/configuration/index.md
  - at least one examples/*.yml, examples/**/README.md, or Secretfile.example.yml
EOF
  exit 1
fi

echo "schema-doc-parity: passed"
