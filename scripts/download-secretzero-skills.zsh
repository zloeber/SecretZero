#!/usr/bin/env bash
# Portable installer (bash): works on GitHub Actions and other images without zsh.
# Filename remains .zsh for stable raw-URL links in docs; run with bash or zsh.

set -euo pipefail

readonly DEFAULT_REPO="zloeber/SecretZero"
readonly DEFAULT_REF="main"
readonly SKILLS=("secretzero-agent" "secretzero-author" "secretzero-handle")

repo="${DEFAULT_REPO}"
ref="${DEFAULT_REF}"
target_dir=""
source_root="${SECRETZERO_SKILLS_SOURCE_ROOT:-}"

usage() {
  cat <<'EOF'
Usage: download-secretzero-skills.zsh TARGET_DIR [--ref REF] [--repo OWNER/REPO]

Download the SecretZero skill folders into TARGET_DIR.

Examples:
  ./scripts/download-secretzero-skills.zsh ~/.agents/skills
  ./scripts/download-secretzero-skills.zsh ./skills --ref main
  curl -fsSL \
    https://raw.githubusercontent.com/zloeber/SecretZero/main/scripts/download-secretzero-skills.zsh \
    | bash -s -- ~/.agents/skills
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ref)
      [[ $# -lt 2 ]] && { echo "Error: --ref requires a value."; exit 1; }
      ref="$2"
      shift 2
      ;;
    --repo)
      [[ $# -lt 2 ]] && { echo "Error: --repo requires a value."; exit 1; }
      repo="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      echo "Error: unknown argument: $1"
      usage
      exit 1
      ;;
    *)
      if [[ -n "${target_dir}" ]]; then
        echo "Error: target directory already set to ${target_dir}"
        usage
        exit 1
      fi
      target_dir="$1"
      shift
      ;;
  esac
done

if [[ -z "${target_dir}" ]]; then
  echo "Error: TARGET_DIR is required."
  usage
  exit 1
fi

mkdir -p "${target_dir}"

if [[ -z "${source_root}" ]]; then
  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "${tmp_dir}"' EXIT

  archive_path="${tmp_dir}/secretzero-skills.tar.gz"
  archive_url="https://codeload.github.com/${repo}/tar.gz/${ref}"

  echo "Downloading SecretZero skills from ${archive_url}"
  curl -fsSL "${archive_url}" -o "${archive_path}"
  tar -xzf "${archive_path}" -C "${tmp_dir}"

  extracted_dir=""
  shopt -s nullglob
  for d in "${tmp_dir}"/*; do
    if [[ -d "${d}" ]]; then
      extracted_dir="${d}"
      break
    fi
  done
  shopt -u nullglob

  if [[ -z "${extracted_dir}" ]]; then
    echo "Error: could not locate extracted GitHub archive contents."
    exit 1
  fi

  source_root="${extracted_dir}/skills"
fi

if [[ ! -d "${source_root}" ]]; then
  echo "Error: skills source root not found: ${source_root}"
  exit 1
fi

for skill_name in "${SKILLS[@]}"; do
  skill_source="${source_root}/${skill_name}"

  if [[ ! -d "${skill_source}" ]]; then
    echo "Error: missing skill directory: ${skill_source}"
    exit 1
  fi
done

for skill_name in "${SKILLS[@]}"; do
  skill_source="${source_root}/${skill_name}"
  skill_target="${target_dir}/${skill_name}"

  rm -rf "${skill_target}"
  cp -R "${skill_source}" "${skill_target}"
  echo "Installed ${skill_name} -> ${skill_target}"
done

echo "SecretZero skills installed into ${target_dir}"
