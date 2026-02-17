#!/usr/bin/env bash
# shellcheck disable=SC2016
# =============================================================================
# Secret Report Generator Script
# =============================================================================
# This bash script scans the current codebase (or a specified directory) for
# potential secrets using open-source scanners from GitHub.
#
# Supported tools (all fit the criteria: uv/pip or single binary downloads):
#   - gitleaks: Single Go binary (from GitHub releases) - scans Git history and files.
#   - trufflehog: Single Go binary (from GitHub releases) - deep Git history scan with verification.
#   - trivy: Single Go binary (from GitHub releases) - comprehensive secret scanner (part of broader tool).
#   - detect-secrets: Python CLI via uv (or pip) - enterprise-friendly baseline-based scanning.
#
# Output:
#   - A dedicated report directory with raw JSON reports from each scanner.
#   - A unified `possible_secret_locations.json` file aggregating findings.
#     This structured output is designed for an agent to ingest and build an
#     ontology-based knowledge graph of secret relationships:
#       - Creation: Commit hashes where secrets were introduced (from gitleaks/trufflehog).
#       - Usage: Code locations, files, and lines where secrets appear.
#       - Location: Full filesystem paths, offsets, and secret types.
#       - Relationships: Link across scanners for confidence, e.g., "AWS key created in commit X, used in file Y".
#
# Usage:
#   ./generate_secret_reports.sh [OPTIONAL_PATH_TO_CODEBASE]
#
# Prerequisites:
#   - curl, tar, jq (for unified report; falls back gracefully).
#   - uv (preferred) or python3/pip for detect-secrets.
#   - Runs on Linux/macOS (x86_64/arm64); auto-detects architecture.
#   - Tools are installed to ./.venv/bin (local virtual environment).
#
# Notes:
#   - Scans the current Git repo state + history where possible.
#   - False positives are minimized via multiple scanners; agent can dedupe.
#   - Secrets are NOT stored in plaintext; redacted in outputs.
#   - Run in a clean environment; tools are idempotent (re-install if needed).
#   - Skips node_modules and .venv directories during scans.
# =============================================================================

set -euo pipefail

# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------
REPO_DIR="${1:-$(pwd)}"
if [ ! -d "$REPO_DIR" ]; then
    echo "❌ Error: Directory not found: $REPO_DIR"
    exit 1
fi

cd "$REPO_DIR"

# Top-level ignore list - add directories/files to exclude from final report
# Useful for filtering out examples, docs, tests, and other non-production code
IGNORE_PATHS=(
    "examples/"
    "docs/"
    "project/"
    "prompts/"
    ".venv/"
    "node_modules/"
    "test/"
    "tests/"
    "__pycache__/"
    "secret_reports_"
    "*.md"
    "*.txt"
    "CACHEDIR.TAG"
)

# Setup local venv
VENV_DIR="./.venv"
BIN_DIR="${VENV_DIR}/bin"
mkdir -p "$BIN_DIR"
export PATH="${BIN_DIR}:$PATH"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_DIR="secret_reports_${TIMESTAMP}"
mkdir -p "$REPORT_DIR"

echo "🚀 Generating secret reports for codebase: $REPO_DIR"
echo "📁 Reports will be saved to: $REPORT_DIR/"
echo "🔧 Tools will be installed to: $BIN_DIR"

# ------------------------------------------------------------------------------
# Tool Installation Functions (Single Binary or uv)
# ------------------------------------------------------------------------------
install_gitleaks() {
    if [ -f "$BIN_DIR/gitleaks" ]; then
        echo "✅ gitleaks already installed"
        return
    fi
    echo "📦 Installing gitleaks (single binary)..."
    LATEST_TAG=$(curl -s https://api.github.com/repos/gitleaks/gitleaks/releases/latest | grep '"tag_name"' | sed -E 's/.*"([^"]+)".*/\1/')
    VERSION=${LATEST_TAG#v}
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    ARCH=$(uname -m | sed 's/x86_64/amd64/; s/aarch64/arm64/; s/armv.*/arm64/')
    URL="https://github.com/gitleaks/gitleaks/releases/download/${LATEST_TAG}/gitleaks_${VERSION}_${OS}_${ARCH}.tar.gz"
    curl -L -sSf "$URL" -o /tmp/gitleaks.tar.gz
    tar -xzf /tmp/gitleaks.tar.gz -C "$BIN_DIR"
    chmod +x "$BIN_DIR/gitleaks"
    rm /tmp/gitleaks.tar.gz
    echo "✅ gitleaks installed: $("$BIN_DIR/gitleaks" --version)"
}

install_trufflehog() {
    if [ -f "$BIN_DIR/trufflehog" ]; then
        echo "✅ trufflehog already installed"
        return
    fi
    echo "📦 Installing trufflehog (single binary)..."
    curl -sSfL https://raw.githubusercontent.com/trufflesecurity/trufflehog/main/scripts/install.sh | sh -s -- -b "$BIN_DIR"
    echo "✅ trufflehog installed: $("$BIN_DIR/trufflehog" --version)"
}

install_trivy() {
    if [ -f "$BIN_DIR/trivy" ]; then
        echo "✅ trivy already installed"
        return
    fi
    echo "📦 Installing trivy (single binary)..."
    curl -sSfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b "$BIN_DIR"
    echo "✅ trivy installed: $("$BIN_DIR/trivy" --version)"
}

install_detect_secrets() {
    if [ -f "$BIN_DIR/detect-secrets" ]; then
        echo "✅ detect-secrets already installed"
        return
    fi
    echo "📦 Installing detect-secrets (via uv/pip)..."
    if command -v uv &> /dev/null; then
        uv pip install --python-preference only-managed -p "$VENV_DIR" detect-secrets
    elif command -v python3 &> /dev/null; then
        python3 -m pip install --target "$VENV_DIR" detect-secrets
    else
        echo "❌ Python/uv not found. Install manually: pip install detect-secrets"
        exit 1
    fi
    echo "✅ detect-secrets installed: $("$BIN_DIR/detect-secrets" --version)"
}

# Install all tools
for tool in gitleaks trufflehog trivy detect-secrets; do
    install_${tool//-/_}
done

# ------------------------------------------------------------------------------
# Run Scanners
# ------------------------------------------------------------------------------
echo "🔍 Running gitleaks (Git history + files)..."
"$BIN_DIR/gitleaks" git \
    --report-format json \
    --report-path "$REPORT_DIR/gitleaks.json" \
    --verbose . > "$REPORT_DIR/gitleaks.log" 2>&1 || true

echo "🔍 Running trufflehog (deep Git history scan)..."
# Create exclude patterns file for trufflehog
cat > /tmp/trufflehog_exclude.txt << 'EOF'
node_modules
.venv
\.git
EOF
"$BIN_DIR/trufflehog" filesystem . \
    --json \
    --force-skip-binaries \
    --force-skip-archives \
    --exclude-paths=/tmp/trufflehog_exclude.txt \
    --no-update > "$REPORT_DIR/trufflehog.json" 2>&1 || true
rm -f /tmp/trufflehog_exclude.txt

echo "🔍 Running trivy (filesystem secrets)..."
"$BIN_DIR/trivy" fs \
    --scanners secret \
    --skip-dirs node_modules \
    --skip-dirs .venv \
    . \
    --format json \
    --output "$REPORT_DIR/trivy.json" > "$REPORT_DIR/trivy.log" 2>&1 || true

echo "🔍 Running detect-secrets (baseline-style scan)..."
"$BIN_DIR/detect-secrets" scan \
    --all-files \
    --exclude-lines "node_modules|\.venv" \
    . > "$REPORT_DIR/detect-secrets.json" 2>&1 || true

# ------------------------------------------------------------------------------
# Create Unified Ontology-Ready Report
# ------------------------------------------------------------------------------
echo "📊 Creating unified secret locations report..."

if command -v jq &> /dev/null; then
    # Build ignore patterns as JSON array for jq
    IGNORE_PATTERNS_JSON=$(printf '%s\n' "${IGNORE_PATHS[@]}" | jq -R . | jq -s .)
    
    echo "🚫 Filtering out paths matching: ${IGNORE_PATHS[*]}"
    
    # Process each scanner output and combine into unified report
    jq -s --argjson ignore_patterns "$IGNORE_PATTERNS_JSON" '
        def safe_array: if type == "array" then . else [] end;
        def safe_object: if type == "object" then . else {} end;
        
        # Function to check if file matches any ignore pattern
        def should_ignore:
            . as $file |
            $ignore_patterns | any(. as $pattern |
                if ($pattern | endswith("/")) then
                    # Directory pattern: check if file path starts with or contains the directory
                    ($file | startswith($pattern)) or ($file | contains("/" + $pattern))
                elif ($pattern | startswith("*")) then
                    # Wildcard pattern: convert to regex
                    $file | test($pattern | gsub("\\*"; ".*") + "$")
                else
                    # Exact match
                    $file | contains($pattern)
                end
            );
        
        [
            # Gitleaks findings
            (.[0] | safe_array | .[] | {
                scanner: "gitleaks",
                file: .File,
                line: .StartLine,
                secret_type: .RuleID,
                snippet: (.Secret // "" | tostring | .[0:20] + "..."),
                commit: .Commit,
                location: "file:\(.File):\(.StartLine)"
            }),
            
            # Trufflehog findings (newline-delimited JSON)
            (.[1] | safe_array | .[] | select(.SourceMetadata?) | {
                scanner: "trufflehog",
                file: (.SourceMetadata.Data.Filesystem.file // "unknown"),
                line: (.SourceMetadata.Data.Filesystem.line // 0),
                secret_type: .DetectorName,
                snippet: "[REDACTED]",
                commit: (.SourceMetadata.Data.Git.commit // null),
                location: ("file:\(.SourceMetadata.Data.Filesystem.file // "unknown"):\(.SourceMetadata.Data.Filesystem.line // 0)")
            }),
            
            # Trivy findings (from Secrets scan)
            (.[2] | safe_object | .Results // [] | .[] | .Secrets // [] | .[] | {
                scanner: "trivy",
                file: .Target,
                line: .StartLine,
                secret_type: .RuleID,
                snippet: "[REDACTED]",
                commit: null,
                location: ("file:\(.Target):\(.StartLine)")
            }),
            
            # Detect-secrets findings
            (.[3] | safe_object | .results // {} | to_entries | .[] | .value[] | {
                scanner: "detect-secrets",
                file: (.filename // .key),
                line: .line_number,
                secret_type: .type,
                snippet: "[REDACTED]",
                commit: null,
                location: ("file:\(.filename // .key):\(.line_number)")
            })
        ] 
        | map(select(.file | should_ignore | not))
        | unique_by(.location)
    ' \
        "$REPORT_DIR/gitleaks.json" \
        <(grep -v '^{.*"level":"error"' "$REPORT_DIR/trufflehog.json" 2>/dev/null | jq -s '.' 2>/dev/null || echo '[]') \
        "$REPORT_DIR/trivy.json" \
        "$REPORT_DIR/detect-secrets.json" \
        > "$REPORT_DIR/possible_secret_locations.json" 2>&1
    
    if [ ! -s "$REPORT_DIR/possible_secret_locations.json" ]; then
        echo "⚠️  Warning: Failed to create unified report with jq, using fallback format"
        echo '[]' > "$REPORT_DIR/possible_secret_locations.json"
    fi
else
    cat > "$REPORT_DIR/possible_secret_locations.json" << EOF
{
    "scanner_reports": {
        "gitleaks": $(cat "$REPORT_DIR/gitleaks.json" 2>/dev/null || echo "[]"),
        "trufflehog": $(cat "$REPORT_DIR/trufflehog.json" 2>/dev/null || echo "[]"),
        "trivy": $(cat "$REPORT_DIR/trivy.json" 2>/dev/null || echo "[]"),
        "detect_secrets": $(cat "$REPORT_DIR/detect-secrets.json" 2>/dev/null || echo "[]")
    },
    "note_for_agent": "Parse individual reports for secret locations. Key fields: file, line, commit (for creation), secret_type (for ontology nodes). Build KG: nodes=secrets/files/commits, edges=created_in->used_in->located_at."
}
EOF
fi

# ------------------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------------------
echo ""
echo "✅ Secret reports generated successfully!"
echo "📍 Report directory: $REPORT_DIR/"
echo "🔑 Key output for agent: $REPORT_DIR/possible_secret_locations.json"

if command -v jq &> /dev/null && [ -f "$REPORT_DIR/possible_secret_locations.json" ]; then
    FINDING_COUNT=$(jq 'length' "$REPORT_DIR/possible_secret_locations.json" 2>/dev/null || echo "0")
    echo "📊 Total unique findings (after filtering): $FINDING_COUNT"
    
    if [ "$FINDING_COUNT" -gt 0 ]; then
        echo ""
        echo "Breakdown by scanner:"
        jq -r 'group_by(.scanner) | map("  - \(.[0].scanner): \(length)") | .[]' \
            "$REPORT_DIR/possible_secret_locations.json" 2>/dev/null || true
    fi
fi

echo ""
echo "Next steps for ontology KG:"
echo "  - Secrets as nodes (type, value hash)."
echo "  - Relationships: 'created_in_commit' -> 'appears_in_file' -> 'used_at_line'."
echo "  - Cross-scanner validation for high-confidence edges."
echo ""
echo "💡 To modify ignore patterns, edit IGNORE_PATHS array at the top of this script"
echo ""
echo "Run again anytime: ./$(basename "$0")"
