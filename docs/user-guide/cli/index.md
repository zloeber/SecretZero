# CLI Reference

Complete reference for all SecretZero command-line interface commands.

## Overview

SecretZero provides a comprehensive CLI for managing secrets throughout their lifecycle. All commands follow a consistent pattern and support common flags.

```bash
secretzero [OPTIONS] COMMAND [ARGS]...
```

## Global Options

These options work with all commands:

| Option | Description |
|--------|-------------|
| `--version` | Show version and exit |
| `--help` | Show help message and exit |

## Available Commands

### Discovery & Setup

| Command | Description |
|---------|-------------|
| [`discover`](discover.md) | Discover secrets in your project using AI analysis (local-first) |
| [`create`](create.md) | Create a new Secretfile from a template |
| [`init`](init.md) | Initialize project by checking and installing provider dependencies |
| [`validate`](validate.md) | Validate Secretfile configuration |
| [`test`](test.md) | Test provider connectivity and authentication |

### Secret Management

| Command | Description |
|---------|-------------|
| [`sync`](sync.md) | Generate and synchronize secrets to targets |
| [`show`](show.md) | Display information about a specific secret |
| [`rotate`](rotate.md) | Rotate secrets based on rotation policies |

### Compliance & Monitoring

| Command | Description |
|---------|-------------|
| [`policy`](policy.md) | Check secrets against policy rules |
| [`drift`](drift.md) | Detect drift between lockfile and actual targets |

### Utilities

| Command | Description |
|---------|-------------|
| `secret-types` | List supported secret types and generators |
| [`terraform`](terraform.md) | Generate Terraform manifests from a Secretfile |

## Command Quick Reference

### Discover Secrets in Your Project

```bash
# Discover with local AI analysis (Ollama required)
secretzero discover

# Preview without saving output
secretzero discover --dry-run

# Ensure only local models (no external APIs)
secretzero discover --local-only

# Use JSON output for parsing
secretzero discover --format json

# Control confidence threshold (0.0-1.0)
secretzero discover --confidence-threshold 0.8
```

!!! info "Local-First Processing"
    The `discover` command keeps all analysis local by default. No project data is sent to external services when using the default Ollama configuration.

[Learn more →](discover.md)

### Create New Project

```bash
# Create basic Secretfile
secretzero create

# Create from specific template
secretzero create --template-type aws

# Custom output location
secretzero create --output my-secrets.yml
```

[Learn more →](create.md)

### Initialize Dependencies

```bash
# Check provider dependencies
secretzero init

# Auto-install missing dependencies
secretzero init --install

# Preview without installing
secretzero init --dry-run
```

[Learn more →](init.md)

### Validate Configuration

```bash
# Validate default Secretfile.yml
secretzero validate

# Validate specific file
secretzero validate --file Secretfile.prod.yml
```

[Learn more →](validate.md)

### Test Provider Connectivity

```bash
# Test all providers
secretzero test

# Test specific file
secretzero test --file Secretfile.yml
```

[Learn more →](test.md)

### Generate and Sync Secrets

```bash
# Preview changes (dry run)
secretzero sync --dry-run

# Actually sync secrets
secretzero sync

# Use specific files
secretzero sync --file Secretfile.yml --lockfile .secrets.lock
```

[Learn more →](sync.md)

### Show Secret Information

```bash
# Show secret details
secretzero show database_password

# Use specific files
secretzero show api_key --file Secretfile.yml
```

[Learn more →](show.md)

### Rotate Secrets

```bash
# Preview rotation (dry run)
secretzero rotate --dry-run

# Rotate all due secrets
secretzero rotate

# Force rotate specific secret
secretzero rotate --force database_password

# Rotate specific secret
secretzero rotate api_key
```

[Learn more →](rotate.md)

### Check Policy Compliance

```bash
# Check policies
secretzero policy

# Fail on warnings
secretzero policy --fail-on-warning

# Use specific file
secretzero policy --file Secretfile.prod.yml
```

[Learn more →](policy.md)

### Detect Configuration Drift

```bash
# Check all secrets
secretzero drift

# Check specific secret
secretzero drift database_password

# Use specific files
secretzero drift --file Secretfile.yml --lockfile .secrets.lock
```

[Learn more →](drift.md)

## Common Workflows

### Initial Setup Workflow

```bash
# 1. Create Secretfile
secretzero create

# 2. Edit Secretfile.yml to add your secrets
vim Secretfile.yml

# 3. Validate configuration
secretzero validate

# 4. Test provider connectivity
secretzero test

# 5. Preview what would be generated
secretzero sync --dry-run

# 6. Generate and sync secrets
secretzero sync
```

### Daily Development Workflow

```bash
# Check current state
secretzero show my_secret

# Make changes to Secretfile.yml
vim Secretfile.yml

# Validate changes
secretzero validate

# Preview changes
secretzero sync --dry-run

# Apply changes
secretzero sync

# Verify changes
secretzero show my_secret
```

### Rotation Workflow

```bash
# Check which secrets need rotation
secretzero rotate --dry-run

# Review rotation policy compliance
secretzero policy

# Rotate due secrets
secretzero rotate

# Or force rotate specific secret
secretzero rotate --force api_key
```

### Production Deployment Workflow

```bash
# Validate production configuration
secretzero validate --file Secretfile.prod.yml

# Check policy compliance
secretzero policy --file Secretfile.prod.yml --fail-on-warning

# Test provider connectivity
secretzero test --file Secretfile.prod.yml

# Dry run in production
secretzero sync --file Secretfile.prod.yml --dry-run

# Deploy to production
secretzero sync --file Secretfile.prod.yml

# Verify no drift
secretzero drift --file Secretfile.prod.yml
```

### Monitoring Workflow

```bash
# Check for drift
secretzero drift

# Check policy compliance
secretzero policy

# Show rotation status
secretzero rotate --dry-run

# Review specific secrets
secretzero show database_password
secretzero show api_key
```

## Common Options

### File Selection

Most commands support these file options:

```bash
# Use default Secretfile.yml
secretzero sync

# Use specific Secretfile
secretzero sync --file Secretfile.prod.yml
secretzero sync -f Secretfile.prod.yml

# Use specific lockfile
secretzero sync --lockfile .production.lock
secretzero sync -l .production.lock

# Use both
secretzero sync -f Secretfile.prod.yml -l .production.lock
```

### Dry Run Mode

Preview changes without making them:

```bash
secretzero sync --dry-run
secretzero rotate --dry-run
```

Dry run shows what would happen without actually:

- Generating new secret values
- Storing secrets in targets
- Updating the lockfile

### Force Operations

Override safety checks:

```bash
# Force rotate even if not due
secretzero rotate --force database_password

# Force sync even if unchanged
secretzero sync --force
```

## Environment Variables

### Configuration

```bash
# Override default Secretfile location
export SECRETZERO_FILE=/path/to/Secretfile.yml

# Override default lockfile location
export SECRETZERO_LOCKFILE=/path/to/.secrets.lock

# Enable debug mode
export SECRETZERO_DEBUG=1
```

### Provider Authentication

```bash
# AWS
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_REGION=us-east-1
export AWS_PROFILE=production

# Vault
export VAULT_ADDR=https://vault.example.com
export VAULT_TOKEN=your_token
export VAULT_NAMESPACE=production

# Kubernetes
export KUBECONFIG=/path/to/kubeconfig
export KUBE_CONTEXT=production

# GitHub
export GITHUB_TOKEN=your_token

# GitLab
export GITLAB_TOKEN=your_token

# Azure
export AZURE_CLIENT_ID=your_client_id
export AZURE_CLIENT_SECRET=your_secret
export AZURE_TENANT_ID=your_tenant
```

## Exit Codes

SecretZero uses standard exit codes:

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | General error |
| `2` | Command line usage error |
| `3` | Validation error |
| `4` | Provider connection error |
| `5` | Policy violation |

**Usage in scripts:**

```bash
#!/bin/bash

secretzero validate
if [ $? -ne 0 ]; then
  echo "Validation failed"
  exit 1
fi

secretzero sync
if [ $? -ne 0 ]; then
  echo "Sync failed"
  exit 1
fi

echo "Success!"
```

## Shell Completion

### Bash

```bash
# Generate completion script
_SECRETZERO_COMPLETE=bash_source secretzero > ~/.secretzero-complete.bash

# Add to ~/.bashrc
echo 'source ~/.secretzero-complete.bash' >> ~/.bashrc
source ~/.bashrc
```

### Zsh

```bash
# Generate completion script
_SECRETZERO_COMPLETE=zsh_source secretzero > ~/.secretzero-complete.zsh

# Add to ~/.zshrc
echo 'source ~/.secretzero-complete.zsh' >> ~/.zshrc
source ~/.zshrc
```

### Fish

```bash
# Generate completion script
_SECRETZERO_COMPLETE=fish_source secretzero > ~/.config/fish/completions/secretzero.fish
```

## Output Formats

### Standard Output

Most commands output human-readable text:

```bash
secretzero sync
```

```
Synchronizing secrets...

✓ Processed 3 secrets
  • Generated: 2
  • Skipped: 1
  • Stored: 2
```

### Verbose Output

Enable detailed output:

```bash
secretzero sync --verbose
```

### Quiet Mode

Suppress output (show only errors):

```bash
secretzero sync --quiet
```

### JSON Output

Output structured JSON (where supported):

```bash
secretzero show my_secret --format json
```

## Best Practices

### 1. Always Validate First

```bash
secretzero validate && secretzero sync
```

### 2. Use Dry Run Before Production

```bash
# Preview in production environment
secretzero sync -f Secretfile.prod.yml --dry-run

# If looks good, apply
secretzero sync -f Secretfile.prod.yml
```

### 3. Check Policy Compliance

```bash
# Fail on warnings in CI/CD
secretzero policy --fail-on-warning
```

### 4. Monitor for Drift

```bash
# Regular drift detection
secretzero drift
```

### 5. Automate with Scripts

```bash
#!/bin/bash
# deploy-secrets.sh

set -e

echo "Validating configuration..."
secretzero validate --file Secretfile.prod.yml

echo "Checking policy compliance..."
secretzero policy --file Secretfile.prod.yml --fail-on-warning

echo "Testing provider connectivity..."
secretzero test --file Secretfile.prod.yml

echo "Syncing secrets..."
secretzero sync --file Secretfile.prod.yml

echo "Verifying no drift..."
secretzero drift --file Secretfile.prod.yml

echo "Done!"
```

## Troubleshooting

### Command Not Found

```bash
# Ensure SecretZero is installed
pip install secretzero

# Or install in virtual environment
python -m venv venv
source venv/bin/activate
pip install secretzero
```

### Permission Denied

```bash
# Check file permissions
ls -l Secretfile.yml

# Ensure readable
chmod 644 Secretfile.yml
```

### Provider Connection Failed

```bash
# Test specific provider
secretzero test

# Check credentials
echo $AWS_ACCESS_KEY_ID
echo $VAULT_TOKEN
```

### Command Hanging

Some commands may take time:

- `sync` - Generating and storing secrets
- `rotate` - Rotating multiple secrets
- `drift` - Checking all targets

Use `--verbose` to see progress:

```bash
secretzero sync --verbose
```

## Getting Help

### Command Help

```bash
# General help
secretzero --help

# Command-specific help
secretzero sync --help
secretzero rotate --help
```

### Version Information

```bash
secretzero --version
```

### Debug Information

```bash
# Enable debug mode
export SECRETZERO_DEBUG=1
secretzero sync
```

## Next Steps

<div class="grid cards" markdown>

-   :material-rocket-launch: **init Command**

    ---

    Create new Secretfile from templates
    
    [init Reference →](init.md)

-   :material-sync: **sync Command**

    ---

    Generate and sync secrets
    
    [sync Reference →](sync.md)

-   :material-rotate-3d: **rotate Command**

    ---

    Rotate secrets automatically
    
    [rotate Reference →](rotate.md)

-   :material-shield-check: **policy Command**

    ---

    Check compliance
    
    [policy Reference →](policy.md)

</div>
