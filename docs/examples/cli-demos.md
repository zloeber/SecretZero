# CLI Command Reference - Animated Examples

This page demonstrates SecretZero CLI commands with live terminal recordings.

## Getting Help

View all available commands:

![SecretZero Help](inc/demo-help.svg)

## Validation

### Validate Secretfile Configuration

Ensure your `Secretfile.yml` is correctly formatted and valid:

![Validate Secretfile](inc/demo-validate.svg)

The validate command checks:
- YAML syntax
- Schema compliance  
- Provider configurations
- Target definitions
- Variable references

## Status Checking

### View Secret Status

Check the current state of your secrets:

![Check Status](inc/demo-status.svg)

Status information includes:
- Secret names and types
- Last rotation dates
- Target destinations
- Sync status

## Discovery

### List Available Providers

See which secret providers SecretZero supports:

![List Providers](inc/demo-providers.svg)

### List Secret Generator Types

View all supported secret generator types:

![List Secret Types](inc/demo-secret-types.svg)

## Testing

### Test Provider Connections

Verify connectivity to configured providers:

![Test Providers](inc/demo-test.svg)

## Visualization

### Generate Dependency Graph

Visualize the relationships between secrets, providers, and targets:

![Dependency Graph](inc/demo-graph.svg)

## Initialization

### Initialize Secrets (Dry Run)

Preview what would be created without making changes:

![Initialize Dry Run](inc/demo-init.svg)

---

**Note**: These are animated SVG recordings. If they don't play automatically in your browser, try refreshing the page.

## Command Quick Reference

| Command | Description |
|---------|-------------|
| `secretzero --help` | Show all available commands |
| `secretzero validate` | Validate Secretfile configuration |
| `secretzero status` | Show secret status and metadata |
| `secretzero providers` | List available providers |
| `secretzero secret-types` | List secret generator types |
| `secretzero test` | Test provider connections |
| `secretzero graph` | Generate dependency graph |
| `secretzero init` | Initialize and sync secrets |
| `secretzero rotate` | Rotate secrets based on policies |

For detailed documentation on each command, see the [CLI Reference](/reference/cli/).
