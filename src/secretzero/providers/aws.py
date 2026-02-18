"""AWS provider implementation for SecretZero."""

import os
from typing import Any

from secretzero.providers.base import BaseProvider, ProviderAuth


class AWSAuth(ProviderAuth):
    """AWS authentication handler."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize AWS authentication.

        Args:
            config: Authentication configuration including:
                - kind: Authentication method (ambient, profile, assume_role)
                - region: AWS region (optional)
                - profile: AWS profile name (for profile auth)
                - role_arn: Role ARN (for assume_role auth)
        """
        super().__init__(config)
        self._session = None
        self._client = None

    def authenticate(self) -> bool:
        """Authenticate with AWS.

        Returns:
            True if authentication successful, False otherwise
        """
        try:
            import boto3
            from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
        except ImportError:
            return False

        try:
            auth_kind = self.config.get("kind", "ambient")
            region = self.config.get("region", os.environ.get("AWS_REGION", "us-east-1"))

            if auth_kind == "profile":
                profile_name = self.config.get("profile", "default")
                self._session = boto3.Session(profile_name=profile_name, region_name=region)
            elif auth_kind == "assume_role":
                role_arn = self.config.get("role_arn")
                if not role_arn:
                    return False

                # Create base session
                base_session = boto3.Session(region_name=region)
                sts = base_session.client("sts")

                # Assume the role
                response = sts.assume_role(RoleArn=role_arn, RoleSessionName="secretzero-session")

                credentials = response["Credentials"]
                self._session = boto3.Session(
                    aws_access_key_id=credentials["AccessKeyId"],
                    aws_secret_access_key=credentials["SecretAccessKey"],
                    aws_session_token=credentials["SessionToken"],
                    region_name=region,
                )
            else:  # ambient authentication
                self._session = boto3.Session(region_name=region)

            # Test authentication by getting caller identity
            sts = self._session.client("sts")
            sts.get_caller_identity()
            return True

        except (NoCredentialsError, BotoCoreError, ClientError):
            return False

    def is_authenticated(self) -> bool:
        """Check if authenticated.

        Returns:
            True if authenticated, False otherwise
        """
        if not self._session:
            return False

        try:
            sts = self._session.client("sts")
            sts.get_caller_identity()
            return True
        except Exception:
            return False

    def get_client(self, service: str = "secretsmanager") -> Any:
        """Get AWS service client.

        Args:
            service: AWS service name

        Returns:
            Boto3 client instance or None
        """
        if self._session:
            return self._session.client(service)
        return None


class AWSProvider(BaseProvider):
    """AWS provider for SecretZero."""

    def __init__(
        self,
        name: str = "aws",
        config: dict[str, Any] | None = None,
        auth: AWSAuth | None = None,
    ):
        """Initialize AWS provider.

        Args:
            name: Provider name
            config: Provider configuration
            auth: AWS authentication instance
        """
        if auth is None and config:
            auth_config = config.get("auth", {})
            auth = AWSAuth(auth_config)

        super().__init__(name, config, auth)

    def test_connection(self) -> tuple[bool, str | None]:
        """Test AWS connectivity.

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            import boto3
            from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
        except ImportError:
            return False, "boto3 not installed. Install with: pip install secretzero[aws]"

        if isinstance(self.auth, AWSAuth):
            auth_kind = self.auth.config.get("kind", "ambient")
            if auth_kind == "assume_role":
                role_arn = self.auth.config.get("role_arn")
                if not role_arn:
                    return False, "AWS assume_role requires role_arn."

                region = self.auth.config.get("region", os.environ.get("AWS_REGION", "us-east-1"))
                session_name = self.auth.config.get("session_name", "secretzero-session")

                try:
                    # Validate that the current credentials can assume the role.
                    base_session = boto3.Session(region_name=region)
                    base_sts = base_session.client("sts")
                    base_identity = base_sts.get_caller_identity()

                    response = base_sts.assume_role(RoleArn=role_arn, RoleSessionName=session_name)
                    credentials = response["Credentials"]
                    assumed_session = boto3.Session(
                        aws_access_key_id=credentials["AccessKeyId"],
                        aws_secret_access_key=credentials["SecretAccessKey"],
                        aws_session_token=credentials["SessionToken"],
                        region_name=region,
                    )
                    assumed_sts = assumed_session.client("sts")
                    assumed_identity = assumed_sts.get_caller_identity()

                    return (
                        True,
                        "Assume role OK "
                        f"(Source: {base_identity.get('Arn')}, "
                        f"Role: {role_arn}, "
                        f"Assumed ARN: {assumed_identity.get('Arn')})",
                    )
                except (NoCredentialsError, BotoCoreError, ClientError) as e:
                    return False, f"Assume role validation failed: {str(e)}"

        if not self.is_authenticated():
            auth_success = self.authenticate()
            if not auth_success:
                return False, "AWS authentication failed. Check credentials and configuration."

        try:
            # Test STS connectivity
            if isinstance(self.auth, AWSAuth):
                sts = self.auth.get_client("sts")
                identity = sts.get_caller_identity()
                account = identity.get("Account")
                arn = identity.get("Arn")
                return True, f"Connected to AWS (Account: {account}, ARN: {arn})"
            return False, "Invalid auth instance"

        except (NoCredentialsError, BotoCoreError, ClientError) as e:
            return False, f"AWS connection test failed: {str(e)}"

    def get_supported_targets(self) -> list[str]:
        """Get supported target types.

        Returns:
            List of supported target type names
        """
        return ["ssm_parameter", "secrets_manager"]
