# secretzero init

Initialize project dependencies by checking and installing required provider libraries.

## Synopsis

```bash
secretzero init [OPTIONS]
```

## Description

The `init` command reads your Secretfile, identifies configured providers, checks if required libraries are installed, and can optionally install missing dependencies automatically. This is useful when setting up a project for the first time or ensuring all team members have the necessary dependencies installed.

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--file`, `-f` | path | `Secretfile.yml` | Path to Secretfile |
| `--install` | flag | `False` | Automatically install missing dependencies |
| `--dry-run` | flag | `False` | Show what would be installed without installing |
| `--help` | flag | - | Show help message |

## Provider Dependencies

SecretZero maps provider kinds to their required Python packages:

| Provider | Required Package | Install Command |
|----------|-----------------|-----------------|
| `aws` | `boto3` | `pip install secretzero[aws]` |
| `azure` | `azure.identity` | `pip install secretzero[azure]` |
| `vault` | `hvac` | `pip install secretzero[vault]` |
| `kubernetes` | `kubernetes` | `pip install secretzero[kubernetes]` |
| `github` | `github` (PyGithub) | `pip install secretzero[github]` |
| `gitlab` | `gitlab` (python-gitlab) | `pip install secretzero[gitlab]` |
| `jenkins` | `jenkins` (python-jenkins) | `pip install secretzero[jenkins]` |

## Examples

### Check Dependencies

Check which provider dependencies are installed:

```bash
secretzero init
```

**Output:**

```
Checking provider dependencies...

✓ local (local): dependency installed
✗ aws (aws): missing dependency
✗ kubernetes (kubernetes): missing dependency

✓ 1 provider(s) have required dependencies

⚠ 2 provider(s) missing dependencies:
  • aws (aws): pip install secretzero[aws]
  • kubernetes (kubernetes): pip install secretzero[kubernetes]

Run with --install to automatically install missing dependencies
```

### Dry Run

Preview what would be installed without making changes:

```bash
secretzero init --dry-run
```

**Output:**

```
Checking provider dependencies...

✗ aws (aws): missing dependency
✗ kubernetes (kubernetes): missing dependency

⚠ 2 provider(s) missing dependencies:
  • aws (aws): pip install secretzero[aws]
  • kubernetes (kubernetes): pip install secretzero[kubernetes]

Dry run mode - no packages will be installed
```

### Auto-Install Dependencies

Automatically install all missing dependencies:

```bash
secretzero init --install
```

**Output:**

```
Checking provider dependencies...

✗ aws (aws): missing dependency
✗ kubernetes (kubernetes): missing dependency

⚠ 2 provider(s) missing dependencies:
  • aws (aws): pip install secretzero[aws]
  • kubernetes (kubernetes): pip install secretzero[kubernetes]

Installing missing dependencies...

Installing secretzero[aws]...
✓ Installed secretzero[aws]

Installing secretzero[kubernetes]...
✓ Installed secretzero[kubernetes]

✓ Dependency installation complete!
```

### Check Specific Secretfile

Check dependencies for a specific Secretfile:

```bash
secretzero init --file Secretfile.prod.yml
```

## Complete Workflow

Typical project initialization workflow:

```bash
# 1. Create a new Secretfile from template
secretzero create --template-type aws

# 2. Edit the Secretfile to add your secrets
vim Secretfile.yml

# 3. Check and install provider dependencies
secretzero init --install

# 4. Validate configuration
secretzero validate

# 5. Test provider connectivity
secretzero test

# 6. Preview secret generation
secretzero sync --dry-run

# 7. Generate and sync secrets
secretzero sync
```

## Repository Setup

For team collaboration, add to your repository setup instructions:

```bash
# Clone repository
git clone https://github.com/myorg/myproject.git
cd myproject

# Install SecretZero
pip install secretzero

# Install provider dependencies
secretzero init --install

# Configure secrets
secretzero sync
```

## CI/CD Integration

Use in CI/CD pipelines to ensure dependencies are available:

```yaml
# .github/workflows/setup.yml
name: Setup Secrets

on: [push]

jobs:
  setup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Install SecretZero
        run: pip install secretzero
      
      - name: Install provider dependencies
        run: secretzero init --install
      
      - name: Validate configuration
        run: secretzero validate
      
      - name: Sync secrets
        run: secretzero sync
```

## Error Handling

### Secretfile Not Found

**Error:**

```
Error: Secretfile not found: Secretfile.yml

Create one first with: secretzero create
```

**Solution:**

Create a Secretfile first:

```bash
secretzero create
```

### Installation Failed

**Error:**

```
✗ Failed to install secretzero[aws]: subprocess exited with code 1
```

**Common causes and solutions:**

1. **Permission denied**: Use a virtual environment or `--user` flag
   ```bash
   python -m venv venv
   source venv/bin/activate
   secretzero init --install
   ```

2. **Network issues**: Check internet connectivity and PyPI access

3. **Incompatible Python version**: Ensure Python 3.12+ is installed
   ```bash
   python --version
   ```

### No Providers Configured

If no providers requiring external dependencies are configured:

```
Checking provider dependencies...

✓ local (local): dependency installed

All provider dependencies are installed!
```

This is normal for projects using only the built-in `local` provider.

## Best Practices

### 1. Run After Cloning

Always run `init --install` after cloning a repository:

```bash
git clone https://github.com/myorg/myproject.git
cd myproject
pip install secretzero
secretzero init --install
```

### 2. Use in Setup Scripts

Include in project setup scripts:

```bash
#!/bin/bash
# setup.sh

# Install SecretZero
pip install secretzero

# Install provider dependencies
secretzero init --install

# Validate and sync
secretzero validate
secretzero sync --dry-run
```

### 3. Document Required Providers

In your README.md:

```markdown
## Setup

This project uses the following secret providers:
- AWS (SSM Parameter Store, Secrets Manager)
- Kubernetes (Secrets)
- HashiCorp Vault

Install all dependencies with:
```bash
secretzero init --install
```
```

### 4. Check Before Syncing

Always verify dependencies before syncing secrets:

```bash
secretzero init       # Check dependencies
secretzero validate   # Validate configuration
secretzero sync       # Sync secrets
```

## Related Commands

- [`create`](create.md) - Create a new Secretfile from template
- [`validate`](validate.md) - Validate Secretfile configuration
- [`test`](test.md) - Test provider connectivity
- [`sync`](sync.md) - Generate and sync secrets

## See Also

- [Installation Guide](../../getting-started/installation.md) - Installing SecretZero and extras
- [Providers Overview](../providers/index.md) - Available provider types
- [Getting Started](../../getting-started/quickstart.md) - Complete tutorial
- [Configuration Guide](../configuration/index.md) - Secretfile structure

## Next Steps

After initializing dependencies:

1. **[Validate configuration](validate.md)** - Check for errors
2. **[Test providers](test.md)** - Verify connectivity
3. **[Sync secrets](sync.md)** - Generate and store secrets
