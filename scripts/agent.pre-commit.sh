#!/usr/bin/env zsh

set -euo pipefail

MODE="fast"
QUIET=0

usage() {
  cat <<'EOF'
Usage: ./scripts/agent.pre-commit.sh [--mode fast|full] [--quiet]

Modes:
  fast (default): run core gates, skip heavy checks unless relevant files changed
  full          : run complete gate suite (includes e2e + all validations)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      [[ $# -lt 2 ]] && { echo "Error: --mode requires a value"; exit 1; }
      MODE="$2"
      shift 2
      ;;
    --quiet)
      QUIET=1
      shift
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

if [[ "${MODE}" != "fast" && "${MODE}" != "full" ]]; then
  echo "Error: --mode must be 'fast' or 'full'"
  exit 1
fi

log() {
  [[ "${QUIET}" -eq 1 ]] || echo "$@"
}

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${repo_root}" ]]; then
  echo "Error: not inside a git repository."
  exit 1
fi
cd "${repo_root}"

tmp_before="$(mktemp)"
tmp_after="$(mktemp)"
tmp_new="$(mktemp)"
tmp_changed="$(mktemp)"
trap 'rm -f "${tmp_before}" "${tmp_after}" "${tmp_new}" "${tmp_changed}"' EXIT

git status --porcelain | awk '{print substr($0,4)}' | sort -u > "${tmp_before}"

if git rev-parse --verify HEAD >/dev/null 2>&1; then
  git diff --name-only HEAD | sort -u > "${tmp_changed}"
else
  git ls-files | sort -u > "${tmp_changed}"
fi

log "==> Running schema/docs parity gate"
./scripts/check-schema-doc-parity.sh --changed-file-list "${tmp_changed}"

requires_e2e=0
requires_all_validations=0

if [[ "${MODE}" == "full" ]]; then
  requires_e2e=1
  requires_all_validations=1
else
  if rg -q '^(src/secretzero/api/|tests/e2e/|src/secretzero/(network_webui|agent_webui|network_web_dashboard|api/))' "${tmp_changed}"; then
    requires_e2e=1
  fi
  if ! rg -q '^examples/.+\.yml$' "${tmp_changed}"; then
    requires_all_validations=1
  fi
fi

log "==> Mode: ${MODE}"
log "==> Bootstrapping dependencies once"
uv sync --frozen --all-extras >/dev/null

log "==> Running quality + schema gate"
task lint:fix && task format && task schema:update

log "==> Running core tests"
uv run pytest --maxfail=1 --disable-warnings -v tests --ignore=tests/e2e

if [[ "${requires_e2e}" -eq 1 ]]; then
  log "==> Running e2e tests"
  uv run pytest --maxfail=1 --disable-warnings -v tests/e2e
else
  log "==> Skipping e2e tests (no relevant changes in fast mode)"
fi

log "==> Running security scan + validations"
task security:scan &
pid_security=$!

if [[ "${requires_all_validations}" -eq 1 ]]; then
  (
    for file in examples/*.yml; do
      [[ -f "${file}" ]] || continue
      uv run secretzero validate -f "${file}"
    done
  ) &
  pid_valid=$!
else
  (
    while IFS= read -r file; do
      [[ -n "${file}" ]] || continue
      uv run secretzero validate -f "${file}"
    done < <(rg '^examples/.+\.yml$' "${tmp_changed}")
  ) &
  pid_valid=$!
fi

wait "${pid_security}"
wait "${pid_valid}"

log "==> Checking README and docs hyperlinks (lychee)"
task docs:links

git status --porcelain | awk '{print substr($0,4)}' | sort -u > "${tmp_after}"
comm -13 "${tmp_before}" "${tmp_after}" > "${tmp_new}"

if [[ -s "${tmp_new}" ]]; then
  echo
  echo "Pre-commit checks introduced new file changes:"
  sed 's/^/  - /' "${tmp_new}"
  echo
  echo "Next required steps before push:"
  echo "  1) Commit these generated/fixed changes"
  echo "  2) Re-run at least:"
  echo "       task test"
  echo "       task security:scan"
  echo "       task docs:links"
  exit 2
fi

echo
echo "All pre-push checks completed with no new generated changes."
