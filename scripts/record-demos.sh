#!/usr/bin/env bash
# Record SecretZero CLI demo with asciinema and convert to animated GIF
# Creates one consolidated demo showing all functionality with clear narration

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

# Directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEMO_DIR="${PROJECT_ROOT}/demos"
OUTPUT_DIR="${PROJECT_ROOT}/docs/inc/demos"

# Ensure directories exist
mkdir -p "${DEMO_DIR}"
mkdir -p "${OUTPUT_DIR}"

# Check dependencies
check_dependencies() {
    local missing=0
    
    if ! command -v asciinema &> /dev/null; then
        echo -e "${RED}✗ asciinema not found${NC}"
        echo "  Install with: brew install asciinema"
        missing=1
    fi
    
    if ! command -v agg &> /dev/null; then
        echo -e "${RED}✗ agg not found${NC}"
        echo "  Install with: brew install agg"
        missing=1
    fi
    
    if [ $missing -eq 1 ]; then
        exit 1
    fi
}

# Create demo script that will be recorded
create_demo_script() {
    local demo_script="${DEMO_DIR}/demo-all.sh"
    
    cat > "${demo_script}" << 'DEMOEOF'
#!/usr/bin/env bash
set +e

# Helper function to show a section
show_section() {
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  $1"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
    sleep 2
}

# Helper function to run a command with visible prompt
run_cmd() {
    echo "$ $1"
    echo
    eval "$1"
    echo
    sleep 3
}

# Demo sections
show_section "SecretZero - Secrets Orchestration Engine"

echo "Welcome to SecretZero! Let's explore its capabilities."
echo
read -r dummy

show_section "1. Help & Overview"
run_cmd "secretzero --help"

show_section "2. Configuration Validation"
echo "Validate your Secretfile configuration..."
run_cmd "secretzero validate"

show_section "3. Current Status"
echo "Check the status of secrets and sync state..."
run_cmd "secretzero status"

show_section "4. Available Providers"
echo "See which secret providers are supported..."
run_cmd "secretzero providers list"

show_section "5. Generator Types"
echo "View available secret generation methods..."
run_cmd "secretzero secret-types"

show_section "6. Testing Configuration"
echo "Dry-run to preview what would happen..."
run_cmd "secretzero test"

show_section "7. Dependency Graph Visualization via Mermaid"
echo "Visualize secret relationships..."
run_cmd "secretzero graph"


show_section "Demo Complete!"
echo "SecretZero is ready to orchestrate your secrets!"
echo
echo "For more information, visit: https://secret0.com"
echo
DEMOEOF

    chmod +x "${demo_script}"
    echo "${demo_script}"
}

# Main
cd "${PROJECT_ROOT}"

echo -e "${GREEN}=== SecretZero Consolidated Demo Recording ===${NC}"
check_dependencies

echo ""
echo -e "${YELLOW}Creating demo script...${NC}"
demo_script=$(create_demo_script)
echo -e "${GREEN}✓ Demo script created${NC}"

echo ""
echo -e "${YELLOW}Recording with asciinema...${NC}"
echo "⏺ Press Control-D when demo is complete"
echo ""

cast_file="${DEMO_DIR}/demo-all.cast"
gif_file="${OUTPUT_DIR}/demo-all.gif"

# Record with asciinema
asciinema rec \
    --command "${demo_script}" \
    --idle-time-limit 1.0 \
    --overwrite \
    "${cast_file}"

if [ ! -f "${cast_file}" ]; then
    echo -e "${RED}✗ Failed to record demo${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✓ Recording saved${NC}"

# Convert to GIF with agg
echo -e "${YELLOW}Converting to animated GIF...${NC}"
agg \
    "${cast_file}" \
    "${gif_file}"

if [ ! -f "${gif_file}" ]; then
    echo -e "${RED}✗ Failed to convert to GIF${NC}"
    exit 1
fi

echo -e "${GREEN}✓ GIF created${NC}"

echo ""
echo -e "${GREEN}=== Complete ===${NC}"
echo ""
echo "Files created:"
echo "  Cast (asciinema): ${cast_file}"
echo "  Animated GIF:     ${gif_file}"
echo ""
echo "Use the GIF in documentation or share it to show SecretZero features!"
ls -1 "${OUTPUT_DIR}"/demo-*.gif 2>/dev/null | while read -r f; do echo "    - $(basename "$f")"; done
