"""Tests for Kubernetes provider and targets."""

import base64
from unittest.mock import Mock, patch

import pytest


class TestKubernetesProvider:
    """Tests for Kubernetes provider."""

    def test_import_kubernetes_provider(self):
        """Test importing Kubernetes provider."""
        from secretzero.providers.kubernetes import KubernetesProvider, KubernetesAuth

        assert KubernetesProvider is not None
        assert KubernetesAuth is not None

    def test_kubernetes_auth_initialization(self):
        """Test Kubernetes auth initialization."""
        from secretzero.providers.kubernetes import KubernetesAuth

        auth = KubernetesAuth({"kubeconfig": "/path/to/kubeconfig", "context": "test"})
        assert auth.config["kubeconfig"] == "/path/to/kubeconfig"
        assert auth.config["context"] == "test"

    def test_authenticate_with_kubeconfig(self):
        """Test authentication using kubeconfig file."""
        from secretzero.providers.kubernetes import KubernetesAuth

        with (
            patch("kubernetes.config.load_kube_config") as mock_load_config,
            patch("kubernetes.client.ApiClient") as mock_api_client_class,
            patch("kubernetes.client.CoreV1Api") as mock_core_v1_class,
        ):

            # Setup mocks
            mock_api_client = Mock()
            mock_core_v1 = Mock()
            mock_api_client_class.return_value = mock_api_client
            mock_core_v1_class.return_value = mock_core_v1
            mock_core_v1.list_namespace.return_value = Mock()

            config = {
                "kubeconfig": "/path/to/kubeconfig",
                "context": "my-context",
            }
            auth = KubernetesAuth(config)

            # Authenticate
            result = auth.authenticate()

            assert result is True
            mock_load_config.assert_called_once_with(
                config_file="/path/to/kubeconfig", context="my-context"
            )
            mock_core_v1.list_namespace.assert_called_once_with(limit=1)

    def test_authenticate_in_cluster(self):
        """Test authentication using in-cluster config."""
        from secretzero.providers.kubernetes import KubernetesAuth

        with (
            patch("kubernetes.config.load_incluster_config") as mock_load_config,
            patch("kubernetes.client.ApiClient") as mock_api_client_class,
            patch("kubernetes.client.CoreV1Api") as mock_core_v1_class,
        ):

            # Setup mocks
            mock_api_client = Mock()
            mock_core_v1 = Mock()
            mock_api_client_class.return_value = mock_api_client
            mock_core_v1_class.return_value = mock_core_v1
            mock_core_v1.list_namespace.return_value = Mock()

            config = {"in_cluster": True}
            auth = KubernetesAuth(config)

            # Authenticate
            result = auth.authenticate()

            assert result is True
            mock_load_config.assert_called_once()
            mock_core_v1.list_namespace.assert_called_once_with(limit=1)

    def test_provider_initialization(self):
        """Test provider initialization."""
        from secretzero.providers.kubernetes import KubernetesProvider

        config = {"auth": {"kubeconfig": "/path/to/kubeconfig"}}
        provider = KubernetesProvider(name="k8s", config=config)

        assert provider.name == "k8s"
        assert provider.config == config
        assert provider.auth is not None

    def test_test_connection_success(self):
        """Test successful connection test."""
        from secretzero.providers.kubernetes import KubernetesProvider

        with (
            patch("kubernetes.config.load_incluster_config"),
            patch("kubernetes.client.ApiClient") as mock_api_client_class,
            patch("kubernetes.client.CoreV1Api") as mock_core_v1_class,
        ):

            # Setup mocks
            mock_api_client = Mock()
            mock_core_v1 = Mock()
            mock_api_client_class.return_value = mock_api_client
            mock_core_v1_class.return_value = mock_core_v1
            mock_core_v1.list_namespace.return_value = Mock()

            # Setup the api_client property on CoreV1Api
            mock_core_v1.api_client = mock_api_client

            # Mock version call
            mock_api_client.call_api.return_value = ({"gitVersion": "v1.28.0"}, None, None)

            # Use in_cluster mode to avoid needing kubeconfig
            config = {"auth": {"in_cluster": True}}
            provider = KubernetesProvider(name="k8s", config=config)

            success, message = provider.test_connection()
            assert success is True, f"Connection failed: {message}"
            assert "v1.28.0" in message

    def test_get_supported_targets(self):
        """Test getting list of supported targets."""
        from secretzero.providers.kubernetes import KubernetesProvider

        provider = KubernetesProvider(name="k8s", config={})
        targets = provider.get_supported_targets()

        assert "kubernetes_secret" in targets
        assert "external_secret" in targets


class TestKubernetesSecretTarget:
    """Tests for Kubernetes Secret target."""

    def test_import_kubernetes_target(self):
        """Test importing Kubernetes target."""
        from secretzero.targets.kubernetes import KubernetesSecretTarget

        assert KubernetesSecretTarget is not None

    def test_target_initialization(self):
        """Test target initialization."""
        from secretzero.targets.kubernetes import KubernetesSecretTarget

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
        from secretzero.targets.kubernetes import KubernetesSecretTarget

        provider = Mock()
        config = {"namespace": "default"}

        with pytest.raises(ValueError, match="requires 'secret_name'"):
            KubernetesSecretTarget(provider, config)

    def test_store_secret_new(self):
        """Test storing a new secret."""
        from secretzero.targets.kubernetes import KubernetesSecretTarget

        with patch("kubernetes.client") as mock_client_module:
            # Setup mocks
            mock_api = Mock()

            # Create ApiException properly
            api_exception = Exception("Not Found")
            api_exception.status = 404
            api_exception.reason = "Not Found"

            mock_api.read_namespaced_secret.side_effect = api_exception

            provider = Mock()
            provider.auth.get_client.return_value = mock_api

            config = {"namespace": "default", "secret_name": "my-secret"}
            target = KubernetesSecretTarget(provider, config)

            # Store secret
            result = target.store("password", "mysecretvalue")

            assert result is True
            mock_api.create_namespaced_secret.assert_called_once()

    def test_store_secret_update(self):
        """Test updating an existing secret."""
        from secretzero.targets.kubernetes import KubernetesSecretTarget

        with patch("kubernetes.client") as mock_client_module:
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

    def test_retrieve_secret(self):
        """Test retrieving a secret."""
        from secretzero.targets.kubernetes import KubernetesSecretTarget

        with patch("kubernetes.client") as mock_client_module:
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


class TestExternalSecretTarget:
    """Tests for External Secret target."""

    def test_import_external_secret_target(self):
        """Test importing External Secret target."""
        from secretzero.targets.kubernetes import ExternalSecretTarget

        assert ExternalSecretTarget is not None

    def test_target_initialization(self):
        """Test target initialization."""
        from secretzero.targets.kubernetes import ExternalSecretTarget

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
        from secretzero.targets.kubernetes import ExternalSecretTarget

        provider = Mock()
        config = {"output_path": "/tmp/test.yaml"}

        with pytest.raises(ValueError, match="requires 'secret_name'"):
            ExternalSecretTarget(provider, config)

    def test_target_missing_output_path(self):
        """Test target initialization without output_path."""
        from secretzero.targets.kubernetes import ExternalSecretTarget

        provider = Mock()
        config = {"secret_name": "my-secret"}

        with pytest.raises(ValueError, match="requires 'output_path'"):
            ExternalSecretTarget(provider, config)

    def test_generate_manifest(self, tmp_path):
        """Test generating ExternalSecret manifest."""
        import yaml
        from secretzero.targets.kubernetes import ExternalSecretTarget

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
        from secretzero.targets.kubernetes import ExternalSecretTarget

        provider = Mock()
        config = {
            "secret_name": "my-secret",
            "output_path": "/tmp/test.yaml",
        }
        target = ExternalSecretTarget(provider, config)

        result = target.retrieve("key")
        assert result is None
