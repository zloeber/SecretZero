"""Tests for Kubernetes provider and targets."""

import base64
from unittest.mock import MagicMock, Mock, patch

import pytest

from secretzero.providers.kubernetes import KubernetesAuth, KubernetesProvider
from secretzero.targets.kubernetes import ExternalSecretTarget, KubernetesSecretTarget


class TestKubernetesAuth:
    """Tests for Kubernetes authentication."""

    @patch("secretzero.providers.kubernetes.client")
    @patch("secretzero.providers.kubernetes.config")
    def test_authenticate_with_kubeconfig(self, mock_config, mock_client):
        """Test authentication using kubeconfig file."""
        # Setup mocks
        mock_api_client = Mock()
        mock_core_v1 = Mock()
        mock_client.ApiClient.return_value = mock_api_client
        mock_client.CoreV1Api.return_value = mock_core_v1
        mock_core_v1.list_namespace.return_value = Mock()

        config = {
            "kubeconfig": "/path/to/kubeconfig",
            "context": "my-context",
        }
        auth = KubernetesAuth(config)

        # Authenticate
        result = auth.authenticate()

        assert result is True
        mock_config.load_kube_config.assert_called_once_with(
            config_file="/path/to/kubeconfig", context="my-context"
        )
        mock_core_v1.list_namespace.assert_called_once_with(limit=1)

    @patch("secretzero.providers.kubernetes.client")
    @patch("secretzero.providers.kubernetes.config")
    def test_authenticate_in_cluster(self, mock_config, mock_client):
        """Test authentication using in-cluster config."""
        # Setup mocks
        mock_api_client = Mock()
        mock_core_v1 = Mock()
        mock_client.ApiClient.return_value = mock_api_client
        mock_client.CoreV1Api.return_value = mock_core_v1
        mock_core_v1.list_namespace.return_value = Mock()

        config = {"in_cluster": True}
        auth = KubernetesAuth(config)

        # Authenticate
        result = auth.authenticate()

        assert result is True
        mock_config.load_incluster_config.assert_called_once()
        mock_core_v1.list_namespace.assert_called_once_with(limit=1)

    def test_authenticate_import_error(self):
        """Test authentication failure when kubernetes module not available."""
        config = {}
        auth = KubernetesAuth(config)

        with patch.dict("sys.modules", {"kubernetes": None}):
            result = auth.authenticate()
            assert result is False

    @patch("secretzero.providers.kubernetes.client")
    @patch("secretzero.providers.kubernetes.config")
    def test_authenticate_connection_error(self, mock_config, mock_client):
        """Test authentication failure on connection error."""
        mock_config.load_kube_config.side_effect = Exception("Connection failed")

        config = {}
        auth = KubernetesAuth(config)

        result = auth.authenticate()
        assert result is False

    @patch("secretzero.providers.kubernetes.client")
    @patch("secretzero.providers.kubernetes.config")
    def test_is_authenticated(self, mock_config, mock_client):
        """Test authentication status check."""
        mock_api_client = Mock()
        mock_core_v1 = Mock()
        mock_client.ApiClient.return_value = mock_api_client
        mock_client.CoreV1Api.return_value = mock_core_v1
        mock_core_v1.list_namespace.return_value = Mock()

        config = {}
        auth = KubernetesAuth(config)

        assert auth.is_authenticated() is False

        auth.authenticate()
        assert auth.is_authenticated() is True

    @patch("secretzero.providers.kubernetes.client")
    @patch("secretzero.providers.kubernetes.config")
    def test_get_client(self, mock_config, mock_client):
        """Test getting authenticated client."""
        mock_api_client = Mock()
        mock_core_v1 = Mock()
        mock_client.ApiClient.return_value = mock_api_client
        mock_client.CoreV1Api.return_value = mock_core_v1
        mock_core_v1.list_namespace.return_value = Mock()

        config = {}
        auth = KubernetesAuth(config)
        auth.authenticate()

        client = auth.get_client()
        assert client == mock_core_v1


class TestKubernetesProvider:
    """Tests for Kubernetes provider."""

    def test_provider_initialization(self):
        """Test provider initialization."""
        config = {"auth": {"kubeconfig": "/path/to/kubeconfig"}}
        provider = KubernetesProvider(name="k8s", config=config)

        assert provider.name == "k8s"
        assert provider.config == config
        assert provider.auth is not None

    def test_provider_with_auth(self):
        """Test provider initialization with pre-configured auth."""
        auth = KubernetesAuth({})
        provider = KubernetesProvider(name="k8s", config={}, auth=auth)

        assert provider.auth == auth

    def test_test_connection_import_error(self):
        """Test connection test when kubernetes not installed."""
        provider = KubernetesProvider(name="k8s", config={})

        with patch.dict("sys.modules", {"kubernetes": None}):
            success, message = provider.test_connection()
            assert success is False
            assert "kubernetes not installed" in message

    @patch("secretzero.providers.kubernetes.client")
    @patch("secretzero.providers.kubernetes.config")
    def test_test_connection_auth_failure(self, mock_config, mock_client):
        """Test connection test with authentication failure."""
        mock_config.load_kube_config.side_effect = Exception("Auth failed")

        config = {"auth": {}}
        provider = KubernetesProvider(name="k8s", config=config)

        success, message = provider.test_connection()
        assert success is False
        assert "Authentication failed" in message

    @patch("secretzero.providers.kubernetes.client")
    @patch("secretzero.providers.kubernetes.config")
    def test_test_connection_success(self, mock_config, mock_client):
        """Test successful connection test."""
        # Setup mocks
        mock_api_client = Mock()
        mock_core_v1 = Mock()
        mock_client.ApiClient.return_value = mock_api_client
        mock_client.CoreV1Api.return_value = mock_core_v1
        mock_core_v1.list_namespace.return_value = Mock()

        # Mock version call
        mock_api_client.call_api.return_value = ({"gitVersion": "v1.28.0"}, None, None)

        config = {"auth": {}}
        provider = KubernetesProvider(name="k8s", config=config)

        success, message = provider.test_connection()
        assert success is True
        assert "v1.28.0" in message

    def test_get_supported_targets(self):
        """Test getting list of supported targets."""
        provider = KubernetesProvider(name="k8s", config={})
        targets = provider.get_supported_targets()

        assert "kubernetes_secret" in targets
        assert "external_secret" in targets


class TestKubernetesSecretTarget:
    """Tests for Kubernetes Secret target."""

    def test_target_initialization(self):
        """Test target initialization."""
        provider = Mock()
        config = {
            "namespace": "default",
            "secret_name": "my-secret",
            "secret_type": "Opaque",
        }
        target = KubernetesSecretTarget(provider, config)

        assert target.namespace == "default"
        assert target.secret_name == "my-secret"
        assert target.secret_type == "Opaque"

    def test_target_missing_secret_name(self):
        """Test target initialization without secret_name."""
        provider = Mock()
        config = {"namespace": "default"}

        with pytest.raises(ValueError, match="requires 'secret_name'"):
            KubernetesSecretTarget(provider, config)

    @patch("secretzero.targets.kubernetes.client")
    def test_store_secret_new(self, mock_client):
        """Test storing a new secret."""
        # Setup mocks
        mock_api = Mock()
        mock_api.read_namespaced_secret.side_effect = mock_client.rest.ApiException(
            status=404, reason="Not Found"
        )

        provider = Mock()
        provider.auth.get_client.return_value = mock_api

        config = {"namespace": "default", "secret_name": "my-secret"}
        target = KubernetesSecretTarget(provider, config)

        # Store secret
        result = target.store("password", "mysecretvalue")

        assert result is True
        mock_api.create_namespaced_secret.assert_called_once()

    @patch("secretzero.targets.kubernetes.client")
    def test_store_secret_update(self, mock_client):
        """Test updating an existing secret."""
        # Setup mocks
        existing_secret = Mock()
        existing_secret.data = {"old_key": "old_value"}

        mock_api = Mock()
        mock_api.read_namespaced_secret.return_value = existing_secret

        provider = Mock()
        provider.auth.get_client.return_value = mock_api

        config = {"namespace": "default", "secret_name": "my-secret"}
        target = KubernetesSecretTarget(provider, config)

        # Store secret
        result = target.store("password", "mysecretvalue")

        assert result is True
        mock_api.replace_namespaced_secret.assert_called_once()
        assert "password" in existing_secret.data

    @patch("secretzero.targets.kubernetes.client")
    def test_store_secret_with_data_key(self, mock_client):
        """Test storing secret with custom data key."""
        # Setup mocks
        mock_api = Mock()
        mock_api.read_namespaced_secret.side_effect = mock_client.rest.ApiException(
            status=404, reason="Not Found"
        )

        provider = Mock()
        provider.auth.get_client.return_value = mock_api

        config = {
            "namespace": "default",
            "secret_name": "my-secret",
            "data_key": "custom_key",
        }
        target = KubernetesSecretTarget(provider, config)

        # Store secret
        result = target.store("password", "mysecretvalue")

        assert result is True
        # Verify the secret was created with custom_key
        call_args = mock_api.create_namespaced_secret.call_args
        secret_data = call_args[1]["body"].data
        assert "custom_key" in secret_data

    @patch("secretzero.targets.kubernetes.client")
    def test_retrieve_secret(self, mock_client):
        """Test retrieving a secret."""
        # Setup mocks
        encoded_value = base64.b64encode(b"mysecretvalue").decode()
        existing_secret = Mock()
        existing_secret.data = {"password": encoded_value}

        mock_api = Mock()
        mock_api.read_namespaced_secret.return_value = existing_secret

        provider = Mock()
        provider.auth.get_client.return_value = mock_api

        config = {"namespace": "default", "secret_name": "my-secret"}
        target = KubernetesSecretTarget(provider, config)

        # Retrieve secret
        result = target.retrieve("password")

        assert result == "mysecretvalue"

    @patch("secretzero.targets.kubernetes.client")
    def test_retrieve_secret_not_found(self, mock_client):
        """Test retrieving a non-existent secret."""
        # Setup mocks
        mock_api = Mock()
        mock_api.read_namespaced_secret.side_effect = mock_client.rest.ApiException(
            status=404, reason="Not Found"
        )

        provider = Mock()
        provider.auth.get_client.return_value = mock_api

        config = {"namespace": "default", "secret_name": "my-secret"}
        target = KubernetesSecretTarget(provider, config)

        # Retrieve secret
        result = target.retrieve("password")

        assert result is None

    def test_store_import_error(self):
        """Test store with missing kubernetes module."""
        provider = Mock()
        config = {"namespace": "default", "secret_name": "my-secret"}
        target = KubernetesSecretTarget(provider, config)

        with patch.dict("sys.modules", {"kubernetes": None}):
            result = target.store("password", "value")
            assert result is False


class TestExternalSecretTarget:
    """Tests for External Secret target."""

    def test_target_initialization(self):
        """Test target initialization."""
        provider = Mock()
        config = {
            "namespace": "default",
            "secret_name": "my-secret",
            "secret_store_ref": "aws-store",
            "backend_type": "aws",
            "output_path": "/tmp/external-secret.yaml",
        }
        target = ExternalSecretTarget(provider, config)

        assert target.namespace == "default"
        assert target.secret_name == "my-secret"
        assert target.secret_store_ref == "aws-store"
        assert target.backend_type == "aws"
        assert target.output_path == "/tmp/external-secret.yaml"

    def test_target_missing_secret_name(self):
        """Test target initialization without secret_name."""
        provider = Mock()
        config = {"output_path": "/tmp/test.yaml"}

        with pytest.raises(ValueError, match="requires 'secret_name'"):
            ExternalSecretTarget(provider, config)

    def test_target_missing_output_path(self):
        """Test target initialization without output_path."""
        provider = Mock()
        config = {"secret_name": "my-secret"}

        with pytest.raises(ValueError, match="requires 'output_path'"):
            ExternalSecretTarget(provider, config)

    def test_generate_manifest(self, tmp_path):
        """Test generating ExternalSecret manifest."""
        import yaml

        provider = Mock()
        output_file = tmp_path / "external-secret.yaml"
        config = {
            "namespace": "default",
            "secret_name": "my-secret",
            "secret_store_ref": "aws-store",
            "backend_type": "aws",
            "backend_key": "prod/db/password",
            "output_path": str(output_file),
            "refresh_interval": "5m",
            "labels": {"app": "myapp"},
            "annotations": {"description": "Database password"},
        }
        target = ExternalSecretTarget(provider, config)

        # Generate manifest
        result = target.store("db_password", "not_used")

        assert result is True
        assert output_file.exists()

        # Load and verify manifest
        with open(output_file) as f:
            manifest = yaml.safe_load(f)

        assert manifest["apiVersion"] == "external-secrets.io/v1beta1"
        assert manifest["kind"] == "ExternalSecret"
        assert manifest["metadata"]["name"] == "my-secret"
        assert manifest["metadata"]["namespace"] == "default"
        assert manifest["metadata"]["labels"] == {"app": "myapp"}
        assert manifest["metadata"]["annotations"] == {"description": "Database password"}
        assert manifest["spec"]["refreshInterval"] == "5m"
        assert manifest["spec"]["secretStoreRef"]["name"] == "aws-store"
        assert manifest["spec"]["target"]["name"] == "my-secret"
        assert len(manifest["spec"]["data"]) == 1
        assert manifest["spec"]["data"][0]["secretKey"] == "db_password"
        assert manifest["spec"]["data"][0]["remoteRef"]["key"] == "prod/db/password"

    def test_retrieve_not_supported(self):
        """Test that retrieve is not supported."""
        provider = Mock()
        config = {
            "secret_name": "my-secret",
            "output_path": "/tmp/test.yaml",
        }
        target = ExternalSecretTarget(provider, config)

        result = target.retrieve("key")
        assert result is None

    def test_generate_manifest_import_error(self):
        """Test manifest generation with missing yaml module."""
        provider = Mock()
        config = {
            "secret_name": "my-secret",
            "output_path": "/tmp/test.yaml",
        }
        target = ExternalSecretTarget(provider, config)

        with patch.dict("sys.modules", {"yaml": None}):
            result = target.store("key", "value")
            assert result is False
