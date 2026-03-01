"""Test Kubernetes provider capability methods."""

from unittest.mock import MagicMock, patch

import pytest

from secretzero.providers.kubernetes import KubernetesProvider


class TestKubernetesCapabilityMethods:
    """Test Kubernetes provider capability methods."""

    def test_generate_password_defaults(self):
        """Test password generation with default settings."""
        config = {
            "context": "test-context",
            "namespace": "default",
        }
        provider = KubernetesProvider("test-k8s", config=config)

        password = provider.generate_password()

        assert isinstance(password, str)
        assert len(password) == 32  # Default length

    def test_generate_password_custom_length(self):
        """Test password generation with custom length."""
        config = {
            "context": "test-context",
            "namespace": "default",
        }
        provider = KubernetesProvider("test-k8s", config=config)

        password = provider.generate_password(length=16)

        assert isinstance(password, str)
        assert len(password) == 16

    def test_retrieve_secret_success(self):
        """Test successful secret retrieval."""
        config = {
            "context": "test-context",
            "namespace": "default",
        }
        provider = KubernetesProvider("test-k8s", config=config)

        # Mock the auth and client
        import base64

        mock_auth = MagicMock()
        mock_client = MagicMock()
        mock_secret = MagicMock()
        encoded_value = base64.b64encode(b"secret-value").decode("utf-8")
        mock_secret.data = {"password": encoded_value}
        mock_client.read_namespaced_secret.return_value = mock_secret
        mock_auth.get_client.return_value = mock_client
        provider.auth = mock_auth

        result = provider.retrieve_secret("my-secret")

        assert result is not None
        assert "password" in result

    def test_store_secret_success(self):
        """Test successful secret storage."""
        config = {
            "context": "test-context",
            "namespace": "default",
        }
        provider = KubernetesProvider("test-k8s", config=config)

        # Mock the auth and client
        mock_auth = MagicMock()
        mock_client = MagicMock()
        mock_client.create_namespaced_secret.return_value = MagicMock()
        mock_auth.get_client.return_value = mock_client
        provider.auth = mock_auth

        result = provider.store_secret("my-secret", {"password": "secret-value"})

        assert result is True

    def test_delete_secret_success(self):
        """Test successful secret deletion."""
        config = {
            "context": "test-context",
            "namespace": "default",
        }
        provider = KubernetesProvider("test-k8s", config=config)

        # Mock the auth and client
        mock_auth = MagicMock()
        mock_client = MagicMock()
        mock_client.delete_namespaced_secret.return_value = MagicMock()
        mock_auth.get_client.return_value = mock_client
        provider.auth = mock_auth

        result = provider.delete_secret("my-secret")

        assert result is True

    def test_rotate_secret_with_new_data(self):
        """Test successful secret rotation with new data."""
        config = {
            "context": "test-context",
            "namespace": "default",
        }
        provider = KubernetesProvider("test-k8s", config=config)

        # Mock the auth and client
        mock_auth = MagicMock()
        mock_client = MagicMock()
        mock_secret = MagicMock()
        mock_secret.data = {"password": "old-value"}
        mock_client.read_namespaced_secret.return_value = mock_secret
        mock_client.patch_namespaced_secret.return_value = MagicMock()
        mock_auth.get_client.return_value = mock_client
        provider.auth = mock_auth

        new_data = {"password": "new-value"}
        result = provider.rotate_secret("my-secret", new_data)

        assert result is True
