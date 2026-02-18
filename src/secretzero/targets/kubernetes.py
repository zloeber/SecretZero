"""Kubernetes secret targets."""

import base64
from typing import Any

from secretzero.targets.base import BaseTarget


class KubernetesSecretTarget(BaseTarget):
    """Store secrets in Kubernetes cluster as native Secret objects."""

    def __init__(self, provider: Any, config: dict[str, Any] | None = None):
        """Initialize Kubernetes secret target.

        Args:
            provider: Kubernetes provider instance.
            config: Target configuration containing:
                - namespace: Kubernetes namespace (default: "default")
                - secret_name: Name of the Kubernetes Secret object
                - secret_type: Type of secret (default: "Opaque")
                  Options: Opaque, kubernetes.io/tls, kubernetes.io/dockerconfigjson,
                          kubernetes.io/basic-auth, kubernetes.io/ssh-auth
                - labels: Optional dict of labels to apply
                - annotations: Optional dict of annotations to apply
                - data_key: Optional key name within the secret (default: use secret name)
        """
        super().__init__(config)
        self.provider = provider
        self.namespace = self.config.get("namespace", "default")
        self.secret_name = self.config.get("secret_name")
        self.secret_type = self.config.get("secret_type", "Opaque")
        self.labels = self.config.get("labels", {})
        self.annotations = self.config.get("annotations", {})
        self.data_key = self.config.get("data_key")

        if not self.secret_name:
            raise ValueError("Kubernetes target requires 'secret_name' in config")

    def store(self, secret_name: str, secret_value: str) -> bool:
        """Store secret in Kubernetes cluster.

        Args:
            secret_name: Name/key of the secret within the Secret object.
            secret_value: Value of the secret.

        Returns:
            True if storage successful, False otherwise.
        """
        try:
            from kubernetes import client
            from kubernetes.client.rest import ApiException
        except ImportError:
            print("kubernetes not installed (pip install kubernetes)")
            return False

        try:
            api = self.provider.auth.get_client()

            # Use data_key if provided, otherwise use the secret_name
            key = self.data_key or secret_name

            # Encode secret value to base64 (Kubernetes requirement)
            encoded_value = base64.b64encode(secret_value.encode()).decode()

            # Create secret metadata
            metadata = client.V1ObjectMeta(
                name=self.secret_name,
                namespace=self.namespace,
                labels=self.labels if self.labels else None,
                annotations=self.annotations if self.annotations else None,
            )

            # Create secret object
            secret = client.V1Secret(
                api_version="v1",
                kind="Secret",
                metadata=metadata,
                type=self.secret_type,
                data={key: encoded_value},
            )

            try:
                # Try to read existing secret
                existing = api.read_namespaced_secret(
                    name=self.secret_name, namespace=self.namespace
                )

                # Update existing secret by merging data
                if existing.data:
                    existing.data[key] = encoded_value
                else:
                    existing.data = {key: encoded_value}

                # Update the secret
                api.replace_namespaced_secret(
                    name=self.secret_name, namespace=self.namespace, body=existing
                )
            except ApiException as e:
                if e.status == 404:
                    # Secret doesn't exist, create it
                    api.create_namespaced_secret(namespace=self.namespace, body=secret)
                else:
                    raise

            return True
        except Exception as e:
            print(f"Failed to store secret in Kubernetes: {e}")
            return False

    def retrieve(self, secret_name: str) -> str | None:
        """Retrieve secret from Kubernetes cluster.

        Args:
            secret_name: Name/key of the secret within the Secret object.

        Returns:
            Secret value if found, None otherwise.
        """
        try:
            from kubernetes import client
            from kubernetes.client.rest import ApiException
        except ImportError:
            return None

        try:
            api = self.provider.auth.get_client()

            # Use data_key if provided, otherwise use the secret_name
            key = self.data_key or secret_name

            # Read the secret
            secret = api.read_namespaced_secret(name=self.secret_name, namespace=self.namespace)

            if not secret.data or key not in secret.data:
                return None

            # Decode base64 value
            encoded_value = secret.data[key]
            decoded_value = base64.b64decode(encoded_value).decode()
            return decoded_value
        except ApiException as e:
            if e.status == 404:
                return None
            print(f"Failed to retrieve secret from Kubernetes: {e}")
            return None
        except Exception as e:
            print(f"Failed to retrieve secret from Kubernetes: {e}")
            return None


class ExternalSecretTarget(BaseTarget):
    """Generate External Secrets Operator manifests for GitOps workflows."""

    def __init__(self, provider: Any, config: dict[str, Any] | None = None):
        """Initialize External Secret target.

        Args:
            provider: Kubernetes provider instance (for validation).
            config: Target configuration containing:
                - namespace: Kubernetes namespace (default: "default")
                - secret_name: Name of the target Kubernetes Secret
                - external_secret_name: Name of the ExternalSecret CR (default: same as secret_name)
                - secret_store_ref: Reference to SecretStore/ClusterSecretStore
                - backend_type: Backend type (aws, azure, vault, etc.)
                - backend_key: Key/path in the backend system
                - output_path: Path to write manifest YAML file
                - refresh_interval: Optional refresh interval (default: "1h")
                - labels: Optional dict of labels
                - annotations: Optional dict of annotations
        """
        super().__init__(config)
        self.provider = provider
        self.namespace = self.config.get("namespace", "default")
        self.secret_name = self.config.get("secret_name")
        self.external_secret_name = self.config.get("external_secret_name") or self.secret_name
        self.secret_store_ref = self.config.get("secret_store_ref", "default")
        self.backend_type = self.config.get("backend_type", "aws")
        self.backend_key = self.config.get("backend_key")
        self.output_path = self.config.get("output_path")
        self.refresh_interval = self.config.get("refresh_interval", "1h")
        self.labels = self.config.get("labels", {})
        self.annotations = self.config.get("annotations", {})

        if not self.secret_name:
            raise ValueError("ExternalSecret target requires 'secret_name' in config")
        if not self.output_path:
            raise ValueError("ExternalSecret target requires 'output_path' in config")

    def store(self, secret_name: str, secret_value: str) -> bool:
        """Generate ExternalSecret manifest.

        This doesn't actually store the secret, but generates a manifest
        that External Secrets Operator will use to sync from a backend.

        Args:
            secret_name: Name/key of the secret.
            secret_value: Not used (manifest generation only).

        Returns:
            True if manifest generation successful, False otherwise.
        """
        try:
            import yaml
        except ImportError:
            print("pyyaml not installed")
            return False

        try:
            # Determine backend key path
            backend_key = self.backend_key or secret_name

            # Create ExternalSecret manifest
            manifest = {
                "apiVersion": "external-secrets.io/v1beta1",
                "kind": "ExternalSecret",
                "metadata": {
                    "name": self.external_secret_name,
                    "namespace": self.namespace,
                },
                "spec": {
                    "refreshInterval": self.refresh_interval,
                    "secretStoreRef": {"name": self.secret_store_ref, "kind": "SecretStore"},
                    "target": {"name": self.secret_name, "creationPolicy": "Owner"},
                    "data": [{"secretKey": secret_name, "remoteRef": {"key": backend_key}}],
                },
            }

            # Add labels if provided
            if self.labels:
                manifest["metadata"]["labels"] = self.labels

            # Add annotations if provided
            if self.annotations:
                manifest["metadata"]["annotations"] = self.annotations

            # Write manifest to file
            import os

            output_dir = os.path.dirname(self.output_path)
            if output_dir:  # Only create directory if path includes a directory
                os.makedirs(output_dir, exist_ok=True)

            with open(self.output_path, "w") as f:
                yaml.dump(manifest, f, default_flow_style=False, sort_keys=False)

            return True
        except Exception as e:
            print(f"Failed to generate ExternalSecret manifest: {e}")
            return False

    def retrieve(self, secret_name: str) -> str | None:
        """External Secrets don't support direct retrieval.

        Args:
            secret_name: Name of the secret.

        Returns:
            None (manifest generation only).
        """
        return None
