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
