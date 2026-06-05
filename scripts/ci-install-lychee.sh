#!/usr/bin/env bash
# Install lychee for GitHub Actions ubuntu runners (linux-gnu tarballs only).
# v0.24+ release tarballs nest the binary under lychee-<arch>-unknown-linux-gnu/;
# older releases place `lychee` at the archive root. Local macOS dev: use `mise install`.
set -euo pipefail

LYCHEE_TAG="${LYCHEE_TAG:-lychee-v0.24.2}"
ARCH="$(uname -m)"
ARCHIVE="lychee-${ARCH}-unknown-linux-gnu.tar.gz"
TEMP_DIR="${RUNNER_TEMP:-/tmp}/lychee-download"

mkdir -p "${TEMP_DIR}"
cd "${TEMP_DIR}"

curl -fsSLO "https://github.com/lycheeverse/lychee/releases/download/${LYCHEE_TAG}/${ARCHIVE}"
tar xzf "${ARCHIVE}"

if [[ -f lychee ]]; then
  BIN=lychee
elif [[ -f "lychee-${ARCH}-unknown-linux-gnu/lychee" ]]; then
  BIN="lychee-${ARCH}-unknown-linux-gnu/lychee"
else
  BIN="$(find . -maxdepth 2 -type f -name lychee | head -1)"
fi

if [[ -z "${BIN}" || ! -f "${BIN}" ]]; then
  echo "Error: could not locate lychee binary after extracting ${ARCHIVE}"
  find . -maxdepth 3 -type f
  exit 1
fi

mkdir -p "${HOME}/.local/bin"
install -m 755 "${BIN}" "${HOME}/.local/bin/lychee"
if [[ -n "${GITHUB_PATH:-}" ]]; then
  echo "${HOME}/.local/bin" >> "${GITHUB_PATH}"
fi
lychee --version

