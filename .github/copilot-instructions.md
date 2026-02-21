# GitHub Copilot Instructions for SecretZero

## Project Overview

**SecretZero** is a secrets orchestration, lifecycle, and bootstrap engine for code repositories. It is **not a secret database** but rather a declarative tool that automates the creation, seeding, and lifecycle management of project secrets.

Think of it as:
- Terraform for secrets lifecycle
- Renovate for credentials  
- NPM/Yarn for secret dependencies
- A lockfile for compliance

**Key Capabilities:**
- Idempotent bootstrap of initial secrets across multiple environments
- Lockfile tracking with rotation history and timestamps
- Multi-provider support (AWS, Azure, Vault, GitHub, GitLab, Jenkins, Kubernetes)
- Type-safe validation with Pydantic models
- CLI and REST API interfaces
- Rotation policies and compliance checking
- Drift detection across secret stores

## Architecture & Module Structure

### Core Modules

```
src/secretzero/
├── models.py          # Pydantic models for enums and base configurations
├── config.py          # Configuration loading and validation
├── cli.py             # Click-based CLI commands
├── sync.py            # Secret synchronization logic
├── lockfile.py        # Lockfile management and tracking
├── rotation.py        # Secret rotation policies and execution
├── policy.py          # Policy validation and enforcement
├── drift.py           # Drift detection across targets
├── generators/        # Generator implementations (random, script, api, etc.)
├── providers/         # Provider implementations (AWS, Azure, Vault, etc.)
├── targets/           # Target implementations (files, k8s, cloud vaults, etc.)
└── api/               # FastAPI REST API server
```

### Key Concepts

- **Secretfile**: YAML configuration file defining secrets, their generation, and storage targets
- **Lockfile**: YAML lockfile tracking secret state, rotation history, and metadata
- **Provider**: Source for generating or retrieving secrets (Vault, cloud KMS, etc.)
- **Generator**: Algorithm for creating secret values (random_password, random_string, static, script, api)
- **Target**: Destination for storing/deploying secrets (files, K8s, cloud vaults, CI/CD systems)
- **Profile**: Environment-specific configuration for multi-environment deployments

## Development Setup

### Requirements
- Python 3.12+
- Optional extras via `pip install secretzero[aws,azure,vault,kubernetes,api,dev]`

### Common Development Commands

```bash
# Install in development mode with all dependencies
pip install -e ".[all,dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=secretzero --cov-report=term-missing

# Format code
black src/ tests/

# Lint code
ruff check --fix src/ tests/

# Type checking
mypy src/secretzero

# Run CLI
secretzero --help

# Run API server
secretzero-api
```

## Code Style & Standards

### General Principles

- **Python 3.12+** - Use modern Python features (type hints, walrus operators, etc.)
- **Type safety first** - All functions must have type hints (see mypy config)
- **Pydantic models** - Use Pydantic v2 for all data validation
- **Line length** - 100 characters (Black and Ruff configured)
- **Imports** - Organized with Ruff; no wildcard imports except in `__init__.py`

### Code Standards

```python
# ✓ DO: Full type hints
def rotate_secret(
    secret_name: str,
    provider: BaseProvider,
    rotation_days: int = 90,
) -> SecretRotationResult:
    """Rotate a secret using the specified provider."""
    pass

# ✗ DON'T: Incomplete type hints
def rotate_secret(secret_name, provider, rotation_days=90):
    pass

# ✓ DO: Pydantic models for validation
class RotationPolicy(BaseModel):
    """Policy for automatic secret rotation."""
    frequency_days: int = Field(gt=0, description="Rotation frequency in days")
    enabled: bool = True
    skip_on_creation: bool = False

# ✓ DO: Docstrings for modules, classes, and public functions
def sync_secrets(config_path: str, dry_run: bool = False) -> SyncResult:
    """Generate and sync secrets to all configured targets.
    
    Args:
        config_path: Path to Secretfile configuration
        dry_run: Preview changes without applying
        
    Returns:
        SyncResult with status and changes
        
    Raises:
        ConfigValidationError: If configuration is invalid
        ProviderError: If provider connectivity fails
    """
    pass
```

### Documentation

- Add docstrings to all public functions, classes, and modules
- Use type hints in docstrings (they're validated by mypy)
- Include examples in docstrings for complex functions
- Document error conditions and exceptions

## Testing

### Test Structure

```python
# tests/test_module.py - One test file per source module
import pytest
from secretzero.module import MyClass

def test_my_feature():
    """Test basic functionality."""
    obj = MyClass()
    assert obj.method() == expected_value

@pytest.mark.asyncio
async def test_async_operation():
    """Test async operations."""
    result = await async_function()
    assert result.status == "success"

def test_error_handling():
    """Test error conditions."""
    with pytest.raises(ConfigValidationError):
        invalid_config = {}
        parse_config(invalid_config)
```

### Testing Guidelines

- **Coverage target**: Maintain >80% code coverage
- **Async tests**: Mark with `@pytest.mark.asyncio` 
- **Mocking**: Use `unittest.mock` for external dependencies
- **Fixtures**: Use pytest fixtures for reusable test data
- **Naming**: Test functions must start with `test_`
- **One assertion per test** when possible (or group related assertions with comments)

## Provider & Generator Implementation

### Adding a New Provider

Providers retrieve secrets from external sources (Vault, cloud KMS, etc.).

```python
# src/secretzero/providers/my_provider.py
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
from secretzero.models import AuthKind

class MyProviderConfig(BaseModel):
    """Configuration for MyProvider."""
    endpoint: str = Field(description="Provider endpoint URL")
    auth_kind: AuthKind = Field(default=AuthKind.TOKEN)
    timeout: int = Field(default=30, gt=0)

class MyProvider(BaseProvider):
    """Provider for MyService."""
    
    config: MyProviderConfig
    
    @property
    def provider_kind(self) -> str:
        """Return provider type identifier."""
        return "my_provider"
    
    def validate_connection(self) -> bool:
        """Test connectivity to provider."""
        # Implementation
        pass
    
    def get_secret(self, secret_name: str) -> str:
        """Retrieve secret value from provider."""
        # Implementation
        pass
    
    def store_secret(self, secret_name: str, secret_value: str) -> None:
        """Store secret value in provider (if dual-purpose)."""
        # Implementation
        pass
```

### Adding a New Generator

Generators create secret values (passwords, strings, certs, etc.).

```python
# src/secretzero/generators/my_generator.py
from secretzero.models import GeneratorKind

class MyGeneratorConfig(BaseModel):
    """Configuration for MyGenerator."""
    length: int = Field(default=32, gt=0)

class MyGenerator(BaseGenerator):
    """Generate secrets using custom algorithm."""
    
    config: MyGeneratorConfig
    
    @property
    def generator_kind(self) -> str:
        """Return generator type identifier."""
        return "my_generator"
    
    def generate(self) -> str:
        """Generate a new secret value."""
        # Implementation
        pass
```

### Adding a New Target

Targets store secrets in external systems (files, K8s, cloud vaults, CI/CD).

```python
# src/secretzero/targets/my_target.py
class MyTargetConfig(BaseModel):
    """Configuration for MyTarget."""
    path: str = Field(description="Target location/path")
    
class MyTarget(BaseTarget):
    """Target for storing secrets in MyService."""
    
    config: MyTargetConfig
    
    @property
    def target_kind(self) -> str:
        """Return target type identifier."""
        return "my_target"
    
    def deploy(self, secrets: dict[str, str]) -> None:
        """Deploy secrets to target."""
        # Implementation
        pass
    
    def verify(self) -> bool:
        """Verify secrets are correctly deployed."""
        # Implementation
        pass
```

## CLI & API Design

### CLI Commands

CLI commands use Click framework with consistent patterns:

```python
# src/secretzero/cli.py
import click
from secretzero.models import OutputFormat

@click.command()
@click.option('--config', '-c', type=click.Path(), help='Path to Secretfile')
@click.option('--dry-run', is_flag=True, help='Preview changes without applying')  
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def sync(config: str, dry_run: bool, verbose: bool) -> None:
    """Generate and sync secrets to all targets."""
    # Implementation
    pass

@click.group()
def cli() -> None:
    """SecretZero secrets orchestration engine."""
    pass

cli.add_command(sync)
cli.add_command(validate)
cli.add_command(rotate)
```

### API Endpoints

REST API uses FastAPI with consistent patterns:

```python
# src/secretzero/api/server.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="SecretZero API")

@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy"}

@app.post("/sync")
async def sync_secrets(config: ConfigRequest) -> SyncResponse:
    """Generate and sync secrets."""
    try:
        result = sync_operation(config)
        return SyncResponse(status="success", result=result)
    except ConfigValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

## Configuration & Validation

### Secretfile Structure

Secretfiles are declarative YAML configurations:

```yaml
version: "1.0"
secrets:
  database_password:
    description: "Database credentials"
    generator: random_password
    generator_config:
      length: 32
    targets:
      - kind: file
        config:
          path: .env
          format: dotenv
      - kind: kubernetes_secret
        config:
          namespace: production
          name: db-creds
    
  api_key:
    description: "External API key"
    generator: static
    generator_config:
      value: "${API_KEY_ENV_VAR}"
    targets:
      - kind: github_secret
        config:
          repository: my-repo
```

### Configuration Best Practices

- **Validation first**: Always validate config with Pydantic before use
- **Schema validation**: Provide JSON schema for Secretfile validation
- **Error messages**: Clear, actionable error messages with context
- **Defaults**: Sensible defaults for optional fields
- **Environment variables**: Support `${VAR_NAME}` substitution

## Security & Secret Handling

### Secret Safety Guidelines

```python
# ✓ DO: Avoid logging secrets
logger.info(f"Syncing secrets to {target_name}")

# ✗ DON'T: Log secret values
logger.info(f"Secret value: {secret_value}")  # DANGEROUS!

# ✓ DO: Use masked representation in logs/output
def safe_repr(value: str) -> str:
    """Return masked representation of secret."""
    if len(value) <= 4:
        return "****"
    return f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"

# ✓ DO: Clear secrets from memory when done
import secrets as secrets_module

def generate_password() -> str:
    """Generate secure password."""
    password = secrets_module.token_urlsafe(32)
    return password

# ✓ DO: Use type hints to indicate sensitive data
SecretValue: TypeAlias = str  # Indicates this contains sensitive data
```

### Error Handling

```python
# ✓ DO: Provide context without exposing secrets
try:
    secret = provider.get_secret("api_key")
except ProviderError as e:
    logger.error(f"Failed to retrieve secret from {provider.kind}: {e.code}")
    raise

# ✗ DON'T: Expose configuration or credentials in error messages
except ProviderError as e:
    logger.error(f"Failed to connect to {provider.config.url}:{provider.config.password}")
```

## Common Patterns

### Lockfile Management

```python
# Track secret state and rotation history
from secretzero.lockfile import Lockfile, SecretEntry

lockfile = Lockfile.load("Secretfile.lock")
entry = SecretEntry(
    name="database_password",
    rotated_at=datetime.now(timezone.utc),
    rotation_count=5,
)
lockfile.update_entry(entry)
lockfile.save()
```

### Async Operations

SecretZero supports async for I/O operations:

```python
# ✓ DO: Use async for provider/target operations
async def sync_secrets_async(config: Config) -> SyncResult:
    """Async sync with parallel operations."""
    tasks = [
        target.deploy_async(secrets) 
        for target in config.targets
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return process_results(results)
```

### Enumerations for Constants

Use Pydantic enums for predefined values:

```python
from enum import Enum
from pydantic import BaseModel

class RotationFrequency(str, Enum):
    """Rotation frequency options."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"

class RotationConfig(BaseModel):
    frequency: RotationFrequency
```

## Testing Providers, Generators & Targets

```python
# tests/test_providers.py
def test_provider_connection_validation():
    """Test provider validates connectivity."""
    config = MyProviderConfig(endpoint="http://invalid")
    provider = MyProvider(config=config)
    assert not provider.validate_connection()

def test_provider_retrieves_secret():
    """Test provider retrieves existing secrets."""
    provider = MyProvider(config=valid_config)
    secret = provider.get_secret("test_secret")
    assert isinstance(secret, str)
    assert len(secret) > 0

def test_target_deployment():
    """Test target deploys secrets correctly."""
    target = MyTarget(config=valid_config)
    secrets = {"key1": "value1", "key2": "value2"}
    target.deploy(secrets)
    assert target.verify()
```

## Documentation Requirements

When adding new features, please:

1. **Update schema documentation** in `Secretfile.schema.json`
2. **Add examples** to `examples/` directory
3. **Update user guides** in `docs/user-guide/`
4. **Add API documentation** if affecting REST API
5. **Update CHANGELOG** in roadmap phase documents
6. **Include inline docstrings** as shown above

## Performance Considerations

- **Lazy loading**: Load providers/targets only when needed
- **Parallel operations**: Use asyncio for independent operations
- **Connection pooling**: Reuse connections to providers/targets
- **Caching**: Cache validated configurations
- **Streaming**: For large secrets, stream instead of loading entirely

## Special Notes

### Version Management

SecretZero uses `setuptools-scm` for automatic versioning from git tags:

```python
# src/secretzero/_version.py is generated automatically
from secretzero import __version__
```

### Multi-environment Support

Always consider multiple environments:

```yaml
profiles:
  dev:
    targets:
      - kind: file
        config: {path: .env.dev}
  prod:
    targets:
      - kind: azure_keyvault
        config: {vault_name: prod-secrets}
```

## Resources

- **Homepage**: https://github.com/zloeber/SecretZero
- **Documentation**: https://secret0.com
- **Issues**: https://github.com/zloeber/SecretZero/issues
- **License**: Apache-2.0

---

**Last Updated**: February 2026  
**For**: GitHub Copilot and AI Development Assistants
