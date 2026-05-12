"""AWS target implementations for SecretZero."""

import json
from typing import Any

from secretzero.targets.base import BaseTarget


def _serialize_aws_target_value(secret_value: Any, format_name: str | None) -> str:
    """Serialize AWS target payloads, optionally enforcing JSON validity."""
    fmt = str(format_name or "raw").strip().lower()

    if fmt == "json":
        if isinstance(secret_value, str):
            try:
                json.loads(secret_value)
            except json.JSONDecodeError as exc:
                raise ValueError("Invalid JSON payload for AWS target format 'json'") from exc
            return secret_value
        try:
            return json.dumps(secret_value)
        except TypeError as exc:
            raise ValueError("Secret value is not JSON serializable") from exc

    if fmt in {"", "raw"}:
        if isinstance(secret_value, dict):
            return json.dumps(secret_value)
        return str(secret_value)

    raise ValueError(f"Unsupported AWS target format: {format_name}")


def _deserialize_aws_target_value(secret_value: str, format_name: str | None) -> Any:
    """Deserialize AWS target payloads when an explicit format requires it."""
    fmt = str(format_name or "raw").strip().lower()

    if fmt == "json":
        try:
            return json.loads(secret_value)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON payload stored in AWS target") from exc

    if fmt in {"", "raw"}:
        return secret_value

    raise ValueError(f"Unsupported AWS target format: {format_name}")


class SSMParameterTarget(BaseTarget):
    """AWS Systems Manager Parameter Store target."""

    def __init__(
        self,
        provider: Any,
        config: dict[str, Any] | None = None,
    ):
        """Initialize SSM Parameter target.

        Args:
            provider: AWS provider instance
            config: Target configuration including:
                - name: Parameter name/path
                - type: Parameter type (String, SecureString, StringList)
                - overwrite: Whether to overwrite existing parameter
                - description: Parameter description (optional)
                - tier: Parameter tier (Standard, Advanced, Intelligent-Tiering)
        """
        super().__init__(provider=provider, config=config)

    def store(self, secret_name: str, secret_value: Any) -> bool:
        """Store secret in SSM Parameter Store.

        Args:
            secret_name: Name of the secret
            secret_value: Value to store

        Returns:
            True if successful, False otherwise
        """
        try:
            from botocore.exceptions import ClientError
        except ImportError:
            raise ValueError("boto3 not installed. Install with: pip install secretzero[aws]")

        from secretzero.providers.aws import AWSAuth

        if not isinstance(self.provider.auth, AWSAuth):
            return False

        ssm = self.provider.auth.get_client("ssm")

        param_name = self.config.get("name")
        if not param_name:
            return False

        param_type = self.config.get("type", "SecureString")
        overwrite = self.config.get("overwrite", True)
        description = self.config.get("description", f"Managed by SecretZero: {secret_name}")
        tier = self.config.get("tier", "Standard")

        value_str = _serialize_aws_target_value(secret_value, self.config.get("format"))

        try:
            ssm.put_parameter(
                Name=param_name,
                Value=value_str,
                Type=param_type,
                Description=description,
                Overwrite=overwrite,
                Tier=tier,
            )
            return True
        except ClientError:
            return False

    def retrieve(self, secret_name: str) -> Any | None:
        """Retrieve secret from SSM Parameter Store.

        Args:
            secret_name: Name of the secret

        Returns:
            Secret value or None if not found
        """
        try:
            from botocore.exceptions import ClientError
        except ImportError:
            return None

        from secretzero.providers.aws import AWSAuth

        if not isinstance(self.provider.auth, AWSAuth):
            return None

        ssm = self.provider.auth.get_client("ssm")

        param_name = self.config.get("name")
        if not param_name:
            return None

        try:
            response = ssm.get_parameter(Name=param_name, WithDecryption=True)
            return _deserialize_aws_target_value(
                response["Parameter"]["Value"], self.config.get("format")
            )
        except ClientError:
            return None

    def delete(self, secret_name: str) -> bool:
        """Delete secret from SSM Parameter Store.

        Args:
            secret_name: Name of the secret

        Returns:
            True if successful, False otherwise
        """
        try:
            from botocore.exceptions import ClientError
        except ImportError:
            return False

        from secretzero.providers.aws import AWSAuth

        if not isinstance(self.provider.auth, AWSAuth):
            return False

        ssm = self.provider.auth.get_client("ssm")

        param_name = self.config.get("name")
        if not param_name:
            return False

        try:
            ssm.delete_parameter(Name=param_name)
            return True
        except ClientError:
            return False


class SecretsManagerTarget(BaseTarget):
    """AWS Secrets Manager target."""

    def __init__(
        self,
        provider: Any,
        config: dict[str, Any] | None = None,
    ):
        """Initialize Secrets Manager target.

        Args:
            provider: AWS provider instance
            config: Target configuration including:
                - name: Secret name
                - description: Secret description (optional)
                - kms_key_id: KMS key for encryption (optional)
        """
        super().__init__(provider=provider, config=config)

    def store(self, secret_name: str, secret_value: Any) -> bool:
        """Store secret in AWS Secrets Manager.

        Args:
            secret_name: Name of the secret
            secret_value: Value to store

        Returns:
            True if successful, False otherwise
        """
        try:
            from botocore.exceptions import ClientError
        except ImportError:
            raise ValueError("boto3 not installed. Install with: pip install secretzero[aws]")

        from secretzero.providers.aws import AWSAuth

        if not isinstance(self.provider.auth, AWSAuth):
            return False

        sm = self.provider.auth.get_client("secretsmanager")

        secret_id = self.config.get("name")
        if not secret_id:
            return False

        description = self.config.get("description", f"Managed by SecretZero: {secret_name}")
        kms_key_id = self.config.get("kms_key_id")

        value_str = _serialize_aws_target_value(secret_value, self.config.get("format"))

        try:
            # Try to create the secret
            params: dict[str, Any] = {
                "Name": secret_id,
                "Description": description,
                "SecretString": value_str,
            }
            if kms_key_id:
                params["KmsKeyId"] = kms_key_id

            sm.create_secret(**params)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceExistsException":
                # Secret exists, update it
                try:
                    sm.update_secret(SecretId=secret_id, SecretString=value_str)
                    return True
                except ClientError:
                    return False
            return False

    def retrieve(self, secret_name: str) -> Any | None:
        """Retrieve secret from AWS Secrets Manager.

        Args:
            secret_name: Name of the secret

        Returns:
            Secret value or None if not found
        """
        try:
            from botocore.exceptions import ClientError
        except ImportError:
            return None

        from secretzero.providers.aws import AWSAuth

        if not isinstance(self.provider.auth, AWSAuth):
            return None

        sm = self.provider.auth.get_client("secretsmanager")

        secret_id = self.config.get("name")
        if not secret_id:
            return None

        try:
            response = sm.get_secret_value(SecretId=secret_id)
            raw_value = response.get("SecretString")
            if raw_value is None:
                return None
            return _deserialize_aws_target_value(raw_value, self.config.get("format"))
        except ClientError:
            return None

    def delete(self, secret_name: str) -> bool:
        """Delete secret from AWS Secrets Manager.

        Args:
            secret_name: Name of the secret

        Returns:
            True if successful, False otherwise
        """
        try:
            from botocore.exceptions import ClientError
        except ImportError:
            return False

        from secretzero.providers.aws import AWSAuth

        if not isinstance(self.provider.auth, AWSAuth):
            return False

        sm = self.provider.auth.get_client("secretsmanager")

        secret_id = self.config.get("name")
        if not secret_id:
            return False

        try:
            # Force immediate deletion (no recovery window)
            sm.delete_secret(SecretId=secret_id, ForceDeleteWithoutRecovery=True)
            return True
        except ClientError:
            return False
