"""Test Kubernetes provider capability methods."""

import pytest
from unittest.mock import MagicMock, patch
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

        # Mock the client
        import base64

        mock_client = MagicMock()
        mock_secret = MagicMock()
        encoded_value = base64.b64encode(b"secret-value").decode("utf-8")
        mock_secret.data = {"password": encoded_value}
        mock_client.read_namespaced_secret.return_value = mock_secret
        provider.client = mock_client

        result = provider.retrieve_secret("my-secret", key="password")

        assert result == "secret-value"

    def test_store_secret_success(self):
        """Test successful secret storage."""
        config = {
            "context": "test-context",
            "namespace": "default",
        }
        provider = KubernetesProvider("test-k8s", config=config)

        # Mock the client
        mock_client = MagicMock()
        mock_client.create_namespaced_secret.return_value = MagicMock()
        provider.client = mock_client

        result = provider.store_secret("my-secret", "secret-value", key="password")

        assert result is True

    def test_delete_secret_success(self):
        """Test successful secret deletion."""
        config = {
            "context": "test-context",
            "namespace": "default",
        }
        provider = KubernetesProvider("test-k8s", config=config)

        # Mock the client
        mock_client = MagicMock()
        mock_client.delete_namespaced_secret.return_value = MagicMock()
        provider.client = mock_client

        result = provider.delete_secret("my-secret")

        assert result is True

    def test_list_secrets_success(self):
        """Test listing secrets."""
        config = {
            "context": "test-context",
            "namespace": "default",
        }
        provider = KubernetesProvider("test-k8s", config=config)

        # Mock the client
        mock_client = MagicMock()
        mock_secret1 = MagicMock()
        mock_secret1.metadata.name = "secret1"
        mock_secret2 = MagicMock()
        mock_secret2.metadata.name = "secret2"
        mock_list = MagicMock()
        mock_list.items = [mock_secret1, mock_secret2]
        mock_client.list_namespaced_secret.return_value = mock_list
        provider.client = mock_client

        result = provider.list_secrets()

        assert result == ["secret1", "secret2"]

    def test_rotate_secret_success(self):
        """Test successful secret rotation."""
        config = {
            "context": "test-context",
            "namespace": "default",
        }
        provider = KubernetesProvider("test-k8s", config=config)

        # Mock the client
        import base64

        mock_client = MagicMock()
        mock_secret = MagicMock()
        encoded_value = base64.b64encode(b"old-value").decode("utf-8")
        mock_secret.data = {"password": encoded_value}
        mock_client.read_namespaced_secret.return_value = mock_secret
        mock_client.patch_namespaced_secret.return_value = MagicMock()
        provider.client = mock_client

        new_value = provider.rotate_secret("my-secret", key="password")

        assert isinstance(new_value, str)
        assert len(new_value) == 32  # Default length
        assert new_value != "old-value"

    def test_update_secret_success(self):
        """Test successful secret update."""
        config = {
            "context": "test-context",
            "namespace": "default",
        }
        provider = KubernetesProvider("test-k8s", config=config)

        # Mock the client
        mock_client = MagicMock()
        mock_client.patch_namespaced_secret.return_value = MagicMock()
        provider.client = mock_client

        result = provider.store_secret("my-secret", "new-value", key="password")

        assert result is True

    def test_retrieve_secret_not_found(self):
        """Test retrieval of non-existent secret."""
        config = {
            "context": "test-context",
            "namespace": "default",
        }
        provider = KubernetesProvider("test-k8s", config=config)

        # Mock the client to raise exception
        from kubernetes.client.rest import ApiException

        mock_client = MagicMock()
        mock_client.read_namespaced_secret.side_effect = ApiException(status=404)
        provider.client = mock_client

        with pytest.raises(ValueError, match="Failed to retrieve secret"):
            provider.retrieve_secret("nonexistent", key="password")
