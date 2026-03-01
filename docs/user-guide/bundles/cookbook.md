# Bundle Cookbook

Advanced patterns for SecretZero provider bundle authors. For the basics, start with [Extending SecretZero](../../extending.md).

## Multi-target Bundles

A single provider can support multiple target kinds. Declare each in the manifest and document them via `target_details`:

```python
BUNDLE_MANIFEST = BundleManifest(
    name="mycloud",
    version="1.0.0",
    provider_class="secretzero_mycloud.provider:MyCloudProvider",
    targets={
        "mycloud_secret": "secretzero_mycloud.targets:MyCloudSecretTarget",
        "mycloud_parameter": "secretzero_mycloud.targets:MyCloudParameterTarget",
        "mycloud_cert": "secretzero_mycloud.targets:MyCloudCertTarget",
    },
    target_kinds=["mycloud_secret", "mycloud_parameter", "mycloud_cert"],
)
```

In your provider class, list them in `get_supported_targets()` and add `target_details` entries:

```python
class MyCloudProvider(BaseProvider):
    target_details = {
        "mycloud_secret": {
            "description": "Key-value secrets",
            "config": {"path": "Secret path"},
            "example": "...",
        },
        "mycloud_parameter": {
            "description": "Configuration parameters",
            "config": {"namespace": "Parameter namespace"},
            "example": "...",
        },
    }

    def get_supported_targets(self) -> list[str]:
        return ["mycloud_secret", "mycloud_parameter", "mycloud_cert"]
```

---

## Multiple Auth Methods

Providers can support multiple authentication strategies. Declare them in `auth_methods` and handle routing in your `ProviderAuth` subclass:

```python
class MyCloudAuth(ProviderAuth):
    ENV_TOKEN: str = "MYCLOUD_TOKEN"

    def authenticate(self) -> bool:
        auth_kind = self.config.get("kind", "token")

        if auth_kind == "token":
            return self._auth_token()
        elif auth_kind == "service_account":
            return self._auth_service_account()
        elif auth_kind == "ambient":
            return self._auth_ambient()
        return False

    def _auth_token(self) -> bool:
        import os
        self._token = self.config.get("token") or os.environ.get(self.ENV_TOKEN)
        return self._token is not None

    def _auth_service_account(self) -> bool:
        # Load from service account credentials file
        creds_path = self.config.get("credentials_file")
        if not creds_path:
            return False
        # ... load and validate credentials
        return True

    def _auth_ambient(self) -> bool:
        # Use SDK's default credential chain
        # ... similar to AWS ambient/Azure DefaultCredential
        return True


class MyCloudProvider(BaseProvider):
    auth_class = MyCloudAuth

    auth_methods = {
        "token": "Use a MyCloud API token (MYCLOUD_TOKEN)",
        "service_account": "Use a service account credentials file",
        "ambient": "Use the default SDK credential chain",
    }
```

Secretfile usage:

```yaml
providers:
  mycloud:
    kind: mycloud
    auth:
      kind: service_account
      config:
        credentials_file: /etc/mycloud/sa.json
```

---

## Provider Capabilities

SecretZero's capability introspection system auto-discovers methods on your provider. Methods prefixed with `generate_`, `retrieve_`, `store_`, `rotate_`, or `delete_` are automatically registered as capabilities:

```python
class MyCloudProvider(BaseProvider):
    def generate_api_key(self, name: str, scopes: list[str] | None = None) -> str:
        """Generate a new API key in MyCloud.

        Args:
            name: Key display name.
            scopes: Permission scopes for the key.

        Returns:
            The generated API key string.
        """
        client = self.auth.get_client()
        return client.create_key(name=name, scopes=scopes or [])

    def retrieve_secret(self, path: str) -> str | None:
        """Retrieve a secret by path.

        Args:
            path: Secret path in the vault.

        Returns:
            Secret value or None if not found.
        """
        client = self.auth.get_client()
        return client.get_secret(path)

    def rotate_api_key(self, name: str) -> str:
        """Rotate an existing API key.

        Args:
            name: Key to rotate.

        Returns:
            The new key value.
        """
        client = self.auth.get_client()
        return client.rotate_key(name)
```

These capabilities are discoverable via:

```bash
secretzero providers --provider mycloud --capabilities
```

---

## Optional Dependencies

Bundles that depend on external SDKs should declare the dependency and use `required_package` for graceful degradation:

```python
class MyCloudProvider(BaseProvider):
    # (import_name, pip_install_name)
    required_package: tuple[str, str] | None = ("mycloud_sdk", "mycloud-sdk")
```

SecretZero checks availability and shows actionable error messages:

```
Error: mycloud provider requires 'mycloud-sdk'. Install with: pip install mycloud-sdk
```

For bundles that provide generators or targets alongside the provider, wrap imports defensively:

```python
class MyCloudSecretTarget(BaseTarget):
    def store(self, secret_name: str, secret_value: str) -> bool:
        try:
            from mycloud_sdk import Client
        except ImportError as exc:
            raise RuntimeError(
                "mycloud-sdk is required for MyCloudSecretTarget. "
                "Install with: pip install mycloud-sdk"
            ) from exc

        client = Client(token=self.provider.auth._token)
        client.put_secret(name=secret_name, value=secret_value)
        return True
```

---

## Generator-Only Bundles

You can create bundles that contribute only generators — no provider needed:

```python
# secretzero_certgen/__init__.py
from secretzero.bundles.registry import BundleManifest

BUNDLE_MANIFEST = BundleManifest(
    name="certgen",
    version="1.0.0",
    provider_class=None,  # No provider
    generators={
        "x509_cert": "secretzero_certgen.generators:X509CertGenerator",
        "ssh_keypair": "secretzero_certgen.generators:SSHKeypairGenerator",
    },
    generator_kinds=["x509_cert", "ssh_keypair"],
)
```

Users reference the generators directly in their Secretfile:

```yaml
secrets:
  tls_cert:
    generator: x509_cert
    generator_config:
      common_name: "app.example.com"
      validity_days: 365
```

---

## Target Validation

Implement `validate()` on your targets to catch configuration errors early, before the sync engine attempts to store secrets:

```python
class MyCloudSecretTarget(BaseTarget):
    def validate(self) -> tuple[bool, str | None]:
        """Validate configuration before use."""
        if not self.config.get("path"):
            return False, "Target 'path' is required"

        path = self.config["path"]
        if not path.startswith("/"):
            return False, f"Target path must be absolute, got: {path}"

        if len(path) > 256:
            return False, f"Target path too long ({len(path)} chars, max 256)"

        return True, None
```

The sync engine calls `validate()` before `store()`, and validation failures are reported clearly:

```
Error: Target validation failed for mycloud_secret:
  Target 'path' is required
```

---

## Testing Patterns

### Mocking external SDKs

```python
from unittest.mock import MagicMock, patch

def test_store_calls_sdk(self) -> None:
    """Verify store() calls the SDK with correct arguments."""
    mock_client = MagicMock()

    provider = MagicMock()
    provider.auth.get_client.return_value = mock_client

    target = MyCloudSecretTarget(provider=provider, config={"path": "/secrets"})
    result = target.store("db_pass", "s3cret")

    assert result is True
    mock_client.put_secret.assert_called_once_with(
        path="/secrets/db_pass", value="s3cret"
    )
```

### Integration testing with the registry

```python
from secretzero.bundles.registry import BundleRegistry

def test_bundle_registers_correctly() -> None:
    """Full round-trip: register manifest, then look up classes."""
    from secretzero_mycloud import BUNDLE_MANIFEST

    registry = BundleRegistry()
    registry.register_bundle(BUNDLE_MANIFEST)

    assert registry.get_provider_class("mycloud") is not None
    assert registry.get_target_class("mycloud_secret") is not None
    assert "mycloud" in registry.list_bundles()
```

### End-to-end with CliRunner

```python
from click.testing import CliRunner
from secretzero.cli import main

def test_providers_list_shows_bundle() -> None:
    """Installed bundle appears in 'providers list'."""
    runner = CliRunner()
    result = runner.invoke(main, ["providers", "list"])
    assert "mycloud" in result.output
```

---

## Packaging Checklist

Before publishing your bundle:

- [ ] `secretzero validate-bundle .` passes
- [ ] All tests pass (`pytest`)
- [ ] `pip install -e .` registers the entry point
- [ ] `secretzero providers list` shows your provider
- [ ] `pyproject.toml` has correct `entry_points`
- [ ] `secretzero>=0.2` pinned as dependency
- [ ] README documents authentication, configuration, and usage
- [ ] Generator/target kinds are namespaced (`mycloud_*`)
