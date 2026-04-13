# Python Client

The SecretZero Python client provides a high-level, Pythonic interface to the SecretZero API. This guide shows you how to use it in your applications.

## Installation

```bash
pip install secretzero[api]
```

This installs both the SecretZero package and the required dependencies for API access.

## Quick Start

```python
from secretzero.client import SecretZeroClient

# Create client
client = SecretZeroClient(
    base_url="http://localhost:8000",
    api_key="your-api-key-here"
)

# Check health
health = client.health_check()
print(f"API Status: {health['status']}")

# List secrets
secrets = client.list_secrets()
print(f"Found {secrets['count']} secrets")

# Sync secrets (dry run)
result = client.sync_secrets(dry_run=True)
print(result['message'])
```

## Client Reference

### Creating a Client

#### Basic Client

```python
from secretzero.client import SecretZeroClient

client = SecretZeroClient(
    base_url="http://localhost:8000",
    api_key="your-api-key-here"
)
```

#### With Custom Configuration

```python
import os
from secretzero.client import SecretZeroClient

client = SecretZeroClient(
    base_url=os.environ.get("SECRETZERO_URL", "http://localhost:8000"),
    api_key=os.environ["SECRETZERO_API_KEY"],
    timeout=30,  # Request timeout in seconds
    verify_ssl=True  # SSL certificate verification
)
```

#### Without Authentication (Development Only)

```python
client = SecretZeroClient(base_url="http://localhost:8000")
```

### Client Methods

#### health_check()

Check API health and version.

```python
health = client.health_check()
# Returns: {"status": "healthy", "version": "0.1.0", "timestamp": "..."}
```

#### list_secrets()

List all secrets from the Secretfile.

```python
secrets = client.list_secrets()
# Returns: {"secrets": [...], "count": 5}

for secret in secrets['secrets']:
    print(f"Secret: {secret['name']}, Type: {secret['kind']}")
```

#### get_secret_status(secret_name)

Get status of a specific secret.

```python
status = client.get_secret_status("database_password")

if status['exists']:
    print(f"Created: {status['created_at']}")
    print(f"Rotated {status['rotation_count']} times")
else:
    print("Secret not yet generated")
```

#### sync_secrets(dry_run=True, force=False, secret_name=None)

Generate and store secrets.

```python
# Dry run (preview)
result = client.sync_secrets(dry_run=True)
print(f"Would generate: {result['secrets_generated']}")

# Actual sync
result = client.sync_secrets(dry_run=False)
print(f"Generated: {result['secrets_generated']}")

# Sync specific secret
result = client.sync_secrets(
    dry_run=False,
    secret_name="database_password"
)

# Force regeneration
result = client.sync_secrets(dry_run=False, force=True)
```

#### check_rotation(secret_name=None)

Check which secrets need rotation.

```python
# Check all secrets
rotation = client.check_rotation()
print(f"Checked: {rotation['secrets_checked']}")
print(f"Due: {rotation['secrets_due']}")
print(f"Overdue: {rotation['secrets_overdue']}")

# Check specific secret
rotation = client.check_rotation("database_password")
```

#### execute_rotation(secret_name=None, force=False)

Execute secret rotation.

```python
# Rotate all due secrets
result = client.execute_rotation()
print(f"Rotated: {result['rotated']}")

# Force rotate specific secret
result = client.execute_rotation(
    secret_name="database_password",
    force=True
)

# Rotate all with force
result = client.execute_rotation(force=True)
```

#### check_policy(fail_on_warning=False)

Check policy compliance.

```python
policy = client.check_policy()

if policy['compliant']:
    print("All policies pass!")
else:
    print(f"Errors: {len(policy['errors'])}")
    for error in policy['errors']:
        print(f"  {error['secret']}: {error['message']}")

# Treat warnings as failures
policy = client.check_policy(fail_on_warning=True)
```

#### check_drift(secret_name=None)

Check for configuration drift.

```python
# Check all secrets
drift = client.check_drift()

if drift['has_drift']:
    print("Drift detected!")
    for secret in drift['secrets_with_drift']:
        print(f"  - {secret}")
else:
    print("No drift detected")

# Check specific secret
drift = client.check_drift("database_password")
```

#### validate_config(config)

Validate a Secretfile configuration.

```python
config = {
    "secrets": [
        {
            "name": "test_secret",
            "kind": "random_password"
        }
    ]
}

validation = client.validate_config(config)

if validation['valid']:
    print("Configuration is valid")
else:
    for error in validation['errors']:
        print(f"Error: {error}")
```

#### get_audit_logs(limit=50, offset=0, action=None, resource=None)

Retrieve audit logs.

```python
# Get recent logs
logs = client.get_audit_logs(limit=10)

for entry in logs['entries']:
    print(f"{entry['timestamp']}: {entry['action']} on {entry['resource']}")

# Get specific action logs
sync_logs = client.get_audit_logs(action="sync", limit=100)

# Pagination
page1 = client.get_audit_logs(limit=50, offset=0)
page2 = client.get_audit_logs(limit=50, offset=50)
```

## Complete Example Client

Here's a complete, production-ready client implementation:

```python
"""SecretZero API Client

A complete client for interacting with the SecretZero API.
"""

import os
from typing import Any, Dict, List, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class SecretZeroClient:
    """SecretZero API Client with error handling and retries."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: int = 30,
        verify_ssl: bool = True,
        max_retries: int = 3
    ):
        """Initialize the SecretZero client.

        Args:
            base_url: API base URL
            api_key: API key for authentication (optional)
            timeout: Request timeout in seconds
            verify_ssl: Whether to verify SSL certificates
            max_retries: Maximum number of retry attempts
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        
        # Set up session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set up headers
        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["X-API-Key"] = api_key

    def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Make an HTTP request to the API.

        Args:
            method: HTTP method
            endpoint: API endpoint (without base URL)
            **kwargs: Additional arguments for requests

        Returns:
            Response JSON data

        Raises:
            requests.HTTPError: If request fails
        """
        url = f"{self.base_url}{endpoint}"
        
        # Merge headers
        headers = {**self.headers, **kwargs.pop('headers', {})}
        
        # Make request
        response = self.session.request(
            method=method,
            url=url,
            headers=headers,
            timeout=self.timeout,
            verify=self.verify_ssl,
            **kwargs
        )
        
        # Raise for error status codes
        response.raise_for_status()
        
        return response.json()

    def health_check(self) -> Dict[str, Any]:
        """Check API health."""
        return self._request("GET", "/health")

    def list_secrets(self) -> Dict[str, Any]:
        """List all secrets."""
        return self._request("GET", "/secrets")

    def get_secret_status(self, secret_name: str) -> Dict[str, Any]:
        """Get status of a specific secret."""
        return self._request("GET", f"/secrets/{secret_name}/status")

    def sync_secrets(
        self,
        dry_run: bool = True,
        force: bool = False,
        secret_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Sync secrets."""
        data = {
            "dry_run": dry_run,
            "force": force
        }
        if secret_name:
            data["secret_name"] = secret_name
        
        return self._request("POST", "/sync", json=data)

    def check_rotation(
        self,
        secret_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Check rotation status."""
        data = {"dry_run": True}
        if secret_name:
            data["secret_name"] = secret_name
        
        return self._request("POST", "/rotation/check", json=data)

    def execute_rotation(
        self,
        secret_name: Optional[str] = None,
        force: bool = False
    ) -> Dict[str, Any]:
        """Execute secret rotation."""
        data = {"force": force}
        if secret_name:
            data["secret_name"] = secret_name
        
        return self._request("POST", "/rotation/execute", json=data)

    def check_policy(
        self,
        fail_on_warning: bool = False
    ) -> Dict[str, Any]:
        """Check policy compliance."""
        data = {"fail_on_warning": fail_on_warning}
        return self._request("POST", "/policy/check", json=data)

    def check_drift(
        self,
        secret_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Check for drift."""
        data = {}
        if secret_name:
            data["secret_name"] = secret_name
        
        return self._request("POST", "/drift/check", json=data)

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a Secretfile configuration."""
        data = {"config": config}
        return self._request("POST", "/config/validate", json=data)

    def get_audit_logs(
        self,
        limit: int = 50,
        offset: int = 0,
        action: Optional[str] = None,
        resource: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get audit logs."""
        params = {"limit": limit, "offset": offset}
        if action:
            params["action"] = action
        if resource:
            params["resource"] = resource
        
        return self._request("GET", "/audit/logs", params=params)

    def close(self):
        """Close the client session."""
        self.session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, *args):
        """Context manager exit."""
        self.close()


# Usage example
if __name__ == "__main__":
    # Create client from environment
    with SecretZeroClient(
        base_url=os.environ.get("SECRETZERO_URL", "http://localhost:8000"),
        api_key=os.environ.get("SECRETZERO_API_KEY")
    ) as client:
        # Health check
        health = client.health_check()
        print(f"API Status: {health['status']}, Version: {health['version']}")
        
        # List secrets
        secrets = client.list_secrets()
        print(f"\nFound {secrets['count']} secrets:")
        for secret in secrets['secrets']:
            print(f"  - {secret['name']} ({secret['kind']})")
        
        # Check rotation
        rotation = client.check_rotation()
        if rotation['secrets_due'] or rotation['secrets_overdue']:
            print(f"\nSecrets needing rotation:")
            for secret in rotation['secrets_due']:
                print(f"  - {secret} (due)")
            for secret in rotation['secrets_overdue']:
                print(f"  - {secret} (overdue)")
        
        # Check policy
        policy = client.check_policy()
        if not policy['compliant']:
            print(f"\nPolicy violations found:")
            for error in policy['errors']:
                print(f"  - {error['secret']}: {error['message']}")
```

## Common Usage Patterns

### Configuration Management

```python
import os
from secretzero.client import SecretZeroClient

# Load from environment
client = SecretZeroClient(
    base_url=os.environ["SECRETZERO_URL"],
    api_key=os.environ["SECRETZERO_API_KEY"]
)

# Or use defaults with fallback
client = SecretZeroClient(
    base_url=os.getenv("SECRETZERO_URL", "http://localhost:8000"),
    api_key=os.getenv("SECRETZERO_API_KEY")
)
```

### Error Handling

```python
import requests
from secretzero.client import SecretZeroClient

client = SecretZeroClient(
    base_url="https://api.example.com",
    api_key=os.environ["API_KEY"]
)

try:
    secrets = client.list_secrets()
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 401:
        print("Authentication failed - check API key")
    elif e.response.status_code == 404:
        print("Resource not found")
    else:
        print(f"HTTP error: {e}")
except requests.exceptions.ConnectionError:
    print("Failed to connect to API")
except requests.exceptions.Timeout:
    print("Request timed out")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### Context Manager

```python
from secretzero.client import SecretZeroClient

# Automatically close connection
with SecretZeroClient(
    base_url="https://api.example.com",
    api_key=os.environ["API_KEY"]
) as client:
    secrets = client.list_secrets()
    # Connection automatically closed after block
```

### Pagination

```python
def get_all_audit_logs(client, action=None):
    """Retrieve all audit logs with pagination."""
    all_logs = []
    offset = 0
    limit = 100
    
    while True:
        response = client.get_audit_logs(
            limit=limit,
            offset=offset,
            action=action
        )
        
        entries = response['entries']
        all_logs.extend(entries)
        
        # Stop if we got fewer entries than requested
        if len(entries) < limit:
            break
        
        offset += limit
    
    return all_logs
```

### Scheduled Rotation

```python
import schedule
import time
from secretzero.client import SecretZeroClient

def rotate_secrets():
    """Check and rotate secrets if needed."""
    client = SecretZeroClient(
        base_url=os.environ["SECRETZERO_URL"],
        api_key=os.environ["SECRETZERO_API_KEY"]
    )
    
    # Check what needs rotation
    rotation = client.check_rotation()
    
    if rotation['secrets_due'] or rotation['secrets_overdue']:
        print(f"Rotating {len(rotation['secrets_due'])} secrets...")
        result = client.execute_rotation()
        print(f"Rotated: {result['rotated']}")
        
        if result['failed']:
            print(f"Failed: {result['failed']}")
    else:
        print("No secrets need rotation")

# Schedule rotation check
schedule.every().day.at("02:00").do(rotate_secrets)

# Run scheduler
while True:
    schedule.run_pending()
    time.sleep(60)
```

### CI/CD Integration

```python
#!/usr/bin/env python3
"""
CI/CD script to sync secrets before deployment
"""
import sys
import os
from secretzero.client import SecretZeroClient

def main():
    client = SecretZeroClient(
        base_url=os.environ["SECRETZERO_URL"],
        api_key=os.environ["SECRETZERO_API_KEY"]
    )
    
    # Validate configuration
    print("Checking policy compliance...")
    policy = client.check_policy(fail_on_warning=True)
    
    if not policy['compliant']:
        print("❌ Policy violations found:")
        for error in policy['errors']:
            print(f"  {error['message']}")
        sys.exit(1)
    
    # Check for drift
    print("Checking for drift...")
    drift = client.check_drift()
    
    if drift['has_drift']:
        print("⚠️  Drift detected:")
        for detail in drift['details']:
            print(f"  {detail['message']}")
        # Decide whether to fail or continue
    
    # Sync secrets
    print("Syncing secrets...")
    result = client.sync_secrets(dry_run=False)
    
    print(f"✅ Synced {len(result['secrets_generated'])} secrets")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### Monitoring Script

```python
#!/usr/bin/env python3
"""
Monitoring script for SecretZero API
"""
import sys
from secretzero.client import SecretZeroClient

def check_health(client):
    """Check API health."""
    try:
        health = client.health_check()
        return health['status'] == 'healthy'
    except Exception:
        return False

def check_rotation_status(client):
    """Check if any secrets are overdue."""
    rotation = client.check_rotation()
    return len(rotation['secrets_overdue']) == 0

def check_policy_compliance(client):
    """Check policy compliance."""
    policy = client.check_policy()
    return policy['compliant']

def check_drift(client):
    """Check for drift."""
    drift = client.check_drift()
    return not drift['has_drift']

def main():
    client = SecretZeroClient(
        base_url=os.environ["SECRETZERO_URL"],
        api_key=os.environ["SECRETZERO_API_KEY"]
    )
    
    checks = {
        "Health": check_health(client),
        "Rotation Status": check_rotation_status(client),
        "Policy Compliance": check_policy_compliance(client),
        "Drift Detection": check_drift(client)
    }
    
    all_passed = all(checks.values())
    
    for check, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"{status} {check}")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
```

## Testing

### Unit Testing

```python
import unittest
from unittest.mock import Mock, patch
from secretzero.client import SecretZeroClient

class TestSecretZeroClient(unittest.TestCase):
    def setUp(self):
        self.client = SecretZeroClient(
            base_url="http://localhost:8000",
            api_key="test-key"
        )
    
    @patch('requests.Session.request')
    def test_health_check(self, mock_request):
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "healthy",
            "version": "0.1.0"
        }
        mock_request.return_value = mock_response
        
        health = self.client.health_check()
        
        self.assertEqual(health['status'], 'healthy')
        mock_request.assert_called_once()
    
    @patch('requests.Session.request')
    def test_list_secrets(self, mock_request):
        mock_response = Mock()
        mock_response.json.return_value = {
            "secrets": [{"name": "test"}],
            "count": 1
        }
        mock_request.return_value = mock_response
        
        secrets = self.client.list_secrets()
        
        self.assertEqual(secrets['count'], 1)

if __name__ == '__main__':
    unittest.main()
```

### Integration Testing

```python
import pytest
from secretzero.client import SecretZeroClient

@pytest.fixture
def client():
    return SecretZeroClient(
        base_url="http://localhost:8000"
    )

def test_health_check(client):
    health = client.health_check()
    assert health['status'] == 'healthy'
    assert 'version' in health

def test_list_secrets(client):
    secrets = client.list_secrets()
    assert 'secrets' in secrets
    assert 'count' in secrets
    assert isinstance(secrets['secrets'], list)
```

## Next Steps

- Learn about [deployment](deployment.md) in production
- Check out [examples](../../examples/index.md) for common use cases
- Review the [endpoint reference](endpoints.md) for detailed API documentation
