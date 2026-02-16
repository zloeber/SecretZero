# Extending SecretZero

This guide explains how to extend SecretZero with custom secret types, providers, and target implementations.

## Architecture Overview

SecretZero follows a modular architecture with three main components:

1. **Secret Types**: Define how secrets are generated (e.g., random passwords, API keys, certificates)
2. **Providers**: Handle authentication and API access to secret sources and storage backends
3. **Targets**: Define where and how secrets are stored (e.g., AWS Secrets Manager, local files, Kubernetes)

## Adding a New Secret Type

Secret types are defined using the `GeneratorKind` enum in `models.py` and implemented in the generator module.

### Step 1: Define the Generator Kind

Add your new generator type to the `GeneratorKind` enum:

```python
class GeneratorKind(str, Enum):
    """Generator kind for secret values."""
    
    STATIC = "static"
    RANDOM_PASSWORD = "random_password"
    # Add your new type here
    CERTIFICATE = "certificate"
```

### Step 2: Implement the Generator

Create a generator class that implements the secret generation logic:

```python
from secretzero.generators.base import BaseGenerator

class CertificateGenerator(BaseGenerator):
    """Generate TLS certificates."""
    
    def generate(self, config: Dict[str, Any]) -> str:
        """Generate a certificate based on configuration.
        
        Args:
            config: Generator configuration containing:
                - common_name: Certificate common name
                - validity_days: Certificate validity period
                - key_size: RSA key size (default: 2048)
        
        Returns:
            Generated certificate in PEM format
        """
        # Implementation here
        pass
```

### Step 3: Register the Generator

Register your generator in the generator factory:

```python
GENERATORS = {
    "static": StaticGenerator,
    "random_password": RandomPasswordGenerator,
    "certificate": CertificateGenerator,
}
```

### Step 4: Update CLI Documentation

Add documentation for your new secret type in `cli.py`:

```python
type_details = {
    "certificate": {
        "description": "Generate self-signed TLS certificates",
        "config": {
            "common_name": "Certificate common name (CN)",
            "validity_days": "Certificate validity period in days",
            "key_size": "RSA key size (default: 2048)",
        },
        "example": """...""",
    },
}
```

## Adding a New Provider

Providers handle authentication to external services and may provide both secret generation and storage capabilities.

### Step 1: Define the Provider

Create a provider class that handles authentication:

```python
from secretzero.providers.base import BaseProvider

class MyCloudProvider(BaseProvider):
    """Provider for MyCloud services."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client = None
    
    def authenticate(self) -> bool:
        """Authenticate with MyCloud API.
        
        Returns:
            True if authentication successful
        """
        # Implementation here
        pass
    
    def test_connection(self) -> tuple[bool, str]:
        """Test provider connectivity.
        
        Returns:
            Tuple of (success, message)
        """
        # Implementation here
        pass
```

### Step 2: Implement Target Storage

If your provider supports secret storage, implement target handlers:

```python
class MyCloudSecretStore(BaseTarget):
    """Store secrets in MyCloud Secret Vault."""
    
    def store(self, secret_name: str, secret_value: str) -> bool:
        """Store a secret in MyCloud.
        
        Args:
            secret_name: Name of the secret
            secret_value: Secret value to store
        
        Returns:
            True if storage successful
        """
        # Implementation here
        pass
```

### Step 3: Register the Provider

Register your provider in the provider factory:

```python
PROVIDERS = {
    "aws": AWSProvider,
    "azure": AzureProvider,
    "mycloud": MyCloudProvider,
}
```

## Adding a New Target Type

Target types define where secrets are stored.

### Step 1: Define the Target Kind

Add your target type to the `TargetKind` enum:

```python
class TargetKind(str, Enum):
    """Target storage kind."""
    
    FILE = "file"
    SSM_PARAMETER = "ssm_parameter"
    # Add your new target
    MYCLOUD_VAULT = "mycloud_vault"
```

### Step 2: Implement the Target

Create a target class that handles secret storage:

```python
from secretzero.targets.base import BaseTarget

class MyCloudVaultTarget(BaseTarget):
    """Store secrets in MyCloud Vault."""
    
    def store(self, secret: Secret, value: str) -> bool:
        """Store a secret in MyCloud Vault.
        
        Args:
            secret: Secret definition
            value: Secret value to store
        
        Returns:
            True if storage successful
        """
        # Implementation here
        pass
    
    def retrieve(self, secret: Secret) -> Optional[str]:
        """Retrieve a secret from MyCloud Vault.
        
        Args:
            secret: Secret definition
        
        Returns:
            Secret value if found, None otherwise
        """
        # Implementation here
        pass
```

### Step 3: Register the Target

Register your target in the target factory:

```python
TARGETS = {
    "file": FileTarget,
    "ssm_parameter": SSMParameterTarget,
    "mycloud_vault": MyCloudVaultTarget,
}
```

## Testing Your Extensions

Always add comprehensive tests for your extensions:

```python
def test_mycloud_provider_authentication():
    """Test MyCloud provider authentication."""
    provider = MyCloudProvider(config={"api_key": "test"})
    assert provider.authenticate()

def test_mycloud_vault_store():
    """Test storing secrets in MyCloud Vault."""
    target = MyCloudVaultTarget(provider="mycloud", config={})
    secret = Secret(name="test", kind="static", targets=[])
    assert target.store(secret, "test-value")
```

## Configuration Examples

Once your extension is complete, provide configuration examples:

```yaml
# Secretfile.yml with MyCloud provider
version: '1.0'

providers:
  mycloud:
    kind: mycloud
    auth:
      kind: api_key
      config:
        api_key: "{{var.mycloud_api_key}}"

secrets:
  - name: app_secret
    kind: random_password
    targets:
      - provider: mycloud
        kind: mycloud_vault
        config:
          vault_name: my-vault
          path: /secrets/app
```

## Best Practices

1. **Type Safety**: Use Pydantic models for all configuration
2. **Error Handling**: Provide clear error messages
3. **Validation**: Validate configuration before use
4. **Testing**: Write comprehensive unit and integration tests
5. **Documentation**: Document all configuration options
6. **Security**: Never log or expose secret values
7. **Idempotency**: Ensure operations can be safely retried

## Contributing

When contributing extensions to SecretZero:

1. Follow the existing code style
2. Add comprehensive tests (aim for >90% coverage)
3. Update documentation
4. Add examples to the docs folder
5. Submit a pull request with a clear description

For questions or help, please open an issue on GitHub.
