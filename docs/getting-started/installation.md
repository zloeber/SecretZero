# Installation

This guide covers all the ways to install SecretZero and its optional dependencies.

## System Requirements

- **Python**: 3.9, 3.10, 3.11, or 3.12
- **Operating System**: Linux, macOS, or Windows
- **pip**: Latest version recommended

## Basic Installation

The simplest way to install SecretZero:

```bash
pip install secretzero
```

This installs the core functionality including:

- CLI commands
- Configuration parsing and validation
- Local file storage support
- Basic secret generators

## Optional Dependencies

SecretZero uses optional dependencies for cloud providers and additional features. Install only what you need:

### Cloud Providers

=== "AWS"
    ```bash
    pip install secretzero[aws]
    ```
    
    Includes:
    
    - AWS Secrets Manager support
    - SSM Parameter Store support
    - IAM role authentication
    - boto3 SDK

=== "Azure"
    ```bash
    pip install secretzero[azure]
    ```
    
    Includes:
    
    - Azure Key Vault support
    - Managed Identity authentication
    - Azure SDK

=== "HashiCorp Vault"
    ```bash
    pip install secretzero[vault]
    ```
    
    Includes:
    
    - Vault KV v2 support
    - Token and AppRole authentication
    - hvac client library

=== "All Cloud Providers"
    ```bash
    pip install secretzero[aws,azure,vault]
    ```

### CI/CD Platforms

=== "GitHub"
    ```bash
    pip install secretzero[github]
    ```
    
    Includes:
    
    - GitHub Actions secrets
    - Repository, environment, and organization secrets
    - PyGithub library

=== "GitLab"
    ```bash
    pip install secretzero[gitlab]
    ```
    
    Includes:
    
    - GitLab CI/CD variables
    - Project and group variables
    - python-gitlab library

=== "Jenkins"
    ```bash
    pip install secretzero[jenkins]
    ```
    
    Includes:
    
    - Jenkins credentials
    - String and username/password credentials
    - python-jenkins library

=== "All CI/CD"
    ```bash
    pip install secretzero[cicd]
    ```

### Container Platforms

```bash
pip install secretzero[kubernetes]
```

Includes:

- Kubernetes Secret support
- External Secrets Operator integration
- All secret types (TLS, Docker, SSH, etc.)
- Official Kubernetes Python client

### API Server

```bash
pip install secretzero[api]
```

Includes:

- FastAPI web framework
- Uvicorn ASGI server
- OpenAPI documentation
- REST API endpoints

### Documentation Tools

```bash
pip install secretzero[docs]
```

Includes:

- MkDocs with Material theme
- Documentation generation tools
- API documentation plugins

### Everything

Install all optional dependencies:

```bash
pip install secretzero[all]
```

This includes all cloud providers, CI/CD platforms, Kubernetes support, API server, and documentation tools.

## Development Installation

For contributing to SecretZero:

### 1. Clone the Repository

```bash
git clone https://github.com/zloeber/SecretZero.git
cd SecretZero
```

### 2. Create a Virtual Environment

=== "Linux/macOS"
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

=== "Windows"
    ```bash
    python -m venv venv
    venv\Scripts\activate
    ```

### 3. Install in Development Mode

```bash
pip install -e ".[all,dev]"
```

This installs:

- All optional dependencies
- Development tools (pytest, black, ruff, mypy)
- The package in editable mode

### 4. Verify Installation

```bash
secretzero --version
pytest
```

## Alternative Installation Methods

### Using pipx

[pipx](https://pipx.pypa.io/) installs Python applications in isolated environments:

```bash
pipx install secretzero
pipx inject secretzero boto3 azure-identity  # Add optional dependencies
```

### Using Poetry

If you use [Poetry](https://python-poetry.org/) for dependency management:

```bash
poetry add secretzero
poetry add secretzero[aws,azure,vault]
```

### Using Docker

You can run SecretZero in a Docker container:

```dockerfile
FROM python:3.11-slim

# Install SecretZero
RUN pip install secretzero[all]

# Copy your Secretfile
COPY Secretfile.yml /app/Secretfile.yml
WORKDIR /app

# Run SecretZero
CMD ["secretzero", "sync"]
```

Build and run:

```bash
docker build -t secretzero .
docker run -v $(pwd):/app secretzero
```

## Verifying Installation

After installation, verify everything is working:

### 1. Check Version

```bash
secretzero --version
```

Expected output:
```
SecretZero version 0.1.0
```

### 2. Check Available Commands

```bash
secretzero --help
```

You should see all available commands:
- `create` - Create new Secretfile
- `validate` - Validate configuration
- `sync` - Generate and sync secrets
- `show` - Show secret status
- `rotate` - Rotate secrets
- `policy` - Check policies
- `drift` - Detect drift
- `test` - Test connectivity

### 3. Test Installation

Create a test Secretfile:

```bash
secretzero create
```

This creates a `Secretfile.yml` with example configuration.

Validate it:

```bash
secretzero validate
```

If you see ✅ messages, everything is installed correctly!

## Upgrading

To upgrade to the latest version:

```bash
pip install --upgrade secretzero
```

To upgrade with all dependencies:

```bash
pip install --upgrade secretzero[all]
```

## Uninstalling

To remove SecretZero:

```bash
pip uninstall secretzero
```

This removes the package but leaves your configuration files intact.

## Troubleshooting

### Python Version Issues

If you get a Python version error:

```bash
# Check your Python version
python --version

# Use a specific Python version
python3.11 -m pip install secretzero
```

### Permission Errors

If you get permission errors on Linux/macOS:

```bash
# Install for current user only
pip install --user secretzero
```

Or use a virtual environment (recommended):

```bash
python -m venv venv
source venv/bin/activate
pip install secretzero
```

### Import Errors

If you get import errors after installation:

```bash
# Ensure you're using the correct Python/pip
which python
which pip

# Reinstall with verbose output
pip install -v secretzero
```

### Cloud Provider Dependencies

If cloud provider commands fail:

```bash
# Check if optional dependencies are installed
pip show boto3          # AWS
pip show azure-identity # Azure
pip show hvac           # Vault

# Install missing dependencies
pip install secretzero[aws,azure,vault]
```

## Platform-Specific Notes

### macOS

On macOS with Apple Silicon (M1/M2):

```bash
# Install Xcode Command Line Tools if needed
xcode-select --install

# Then install SecretZero
pip install secretzero
```

### Windows

On Windows, you may need to install Visual C++ Build Tools for some dependencies:

1. Download [Visual C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
2. Install with C++ development tools
3. Then install SecretZero

### Linux

On minimal Linux distributions, install Python development headers:

=== "Ubuntu/Debian"
    ```bash
    sudo apt-get update
    sudo apt-get install python3-dev python3-pip
    pip install secretzero
    ```

=== "CentOS/RHEL"
    ```bash
    sudo yum install python3-devel python3-pip
    pip install secretzero
    ```

=== "Alpine"
    ```bash
    apk add python3-dev py3-pip gcc musl-dev
    pip install secretzero
    ```

## Next Steps

Now that SecretZero is installed:

1. **[Quick Start →](quickstart.md)** - Create your first secret in 5 minutes
2. **[First Project →](first-project.md)** - Build a complete project
3. **[Basic Concepts →](concepts.md)** - Understand the architecture

## Getting Help

If you encounter installation issues:

- Check the [Troubleshooting Guide](../reference/troubleshooting.md)
- Search [GitHub Issues](https://github.com/zloeber/SecretZero/issues)
- Ask in [GitHub Discussions](https://github.com/zloeber/SecretZero/discussions)
