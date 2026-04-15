"""AWS provider implementation for SecretZero."""

import os
import secrets
import string
from typing import Any

from secretzero.providers.base import BaseProvider, ProviderAuth


class AWSAuth(ProviderAuth):
    """AWS authentication handler.

    Supports authentication via:
    - Ambient credentials (IAM role, environment variables, credentials file, etc.)
    - AWS profile from ~/.aws/config and ~/.aws/credentials
    - Assume role with STS
    - Explicit credentials via environment variables

    Environment variables checked:
    - AWS_REGION: AWS region (default: us-east-1)
    - AWS_PROFILE: AWS profile name for profile authentication
    - AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY: Explicit credentials
    """

    # Environment variables for AWS configuration
    ENV_REGION = "AWS_REGION"
    ENV_PROFILE = "AWS_PROFILE"

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize AWS authentication.

        Args:
            config: Authentication configuration including:
                - kind: Authentication method (ambient, profile, assume_role)
                - region: AWS region (or set AWS_REGION env var)
                - profile: AWS profile name (or set AWS_PROFILE env var, for profile auth)
                - role_arn: Role ARN (for assume_role auth)
        """
        super().__init__(config)
        self._session = None
        self._client = None

    def authenticate(self) -> bool:
        """Authenticate with AWS.

        Returns:
            True if authentication successful, False otherwise

        Attempts to authenticate using:
            1. Explicit auth kind from config
            2. Environment variables (AWS_REGION, AWS_PROFILE, AWS_*_KEY_ID, etc.)
            3. AWS credentials file and config
        """
        try:
            import boto3
            from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
        except ImportError:
            return False

        try:
            auth_kind = self.config.get("kind", "ambient")
            region = self.config.get("region") or os.environ.get(self.ENV_REGION, "us-east-1")

            if auth_kind == "profile":
                profile_name = self.config.get("profile") or os.environ.get(
                    self.ENV_PROFILE, "default"
                )
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

    def get_token_info(self) -> dict[str, Any]:
        """Return the current IAM principal from STS GetCallerIdentity."""
        if not self._session:
            raise RuntimeError("Not authenticated with AWS")
        try:
            sts = self._session.client("sts")
            ident = sts.get_caller_identity()
        except Exception as e:
            raise RuntimeError(f"AWS identity lookup failed: {e}") from e
        arn = ident.get("Arn", "")
        uid = ident.get("UserId")
        region = (
            getattr(self._session, "region_name", None)
            or self.config.get("region")
            or os.environ.get(self.ENV_REGION)
            or "us-east-1"
        )
        return {
            "user": arn,
            "arn": arn,
            "account": ident.get("Account"),
            "principal_id": uid,
            "user_id": uid,
            "region": region,
            "scopes": [],
            "token_type": "aws_iam",
        }


class AWSProvider(BaseProvider):
    """AWS provider for SecretZero."""

    display_name = "Amazon Web Services"
    description = "AWS Secrets Manager and other services"
    required_package = ("boto3", "secretzero[aws]")
    auth_class = AWSAuth
    auth_methods = {
        "ambient": "Use AWS SDK default credential chain (environment, instance profile, etc.)",
        "token": "Use static AWS access key and secret key",
        "assume_role": "Assume an IAM role for additional permissions",
    }
    config_options = {
        "region": "AWS region (default: us-east-1)",
        "profile": "AWS profile name from ~/.aws/config",
    }
    config_example = """providers:
  aws:
    kind: aws
    auth:
      kind: ambient
      config:
        region: us-east-1
    fallback_generator: static
    profiles:
      default:
        kind: ambient
      admin:
        kind: assume_role
        config:
          role_arn: arn:aws:iam::123456789012:role/SecretAdmin"""
    target_details = {
        "ssm_parameter": {
            "description": "AWS Systems Manager Parameter Store",
            "config": {
                "name": "Parameter name/path (required)",
                "type": "Parameter type: String, SecureString, or StringList (default: SecureString)",
                "overwrite": "Whether to overwrite existing parameter (default: true)",
                "description": "Parameter description (optional)",
                "tier": "Parameter tier: Standard, Advanced, or Intelligent-Tiering (default: Standard)",
                "region": "AWS region override (optional)",
                "endpoint_url": "Custom endpoint URL for LocalStack or other AWS-compatible services (optional)",
            },
            "example": """targets:
  - provider: aws
    kind: ssm_parameter
    config:
      name: /prod/database/password
      type: SecureString
      overwrite: true
      description: RDS master password
      tier: Standard""",
        },
        "secrets_manager": {
            "description": "AWS Secrets Manager",
            "config": {
                "name": "Secret name (required)",
                "description": "Secret description (optional)",
                "kms_key_id": "KMS key ID for encryption (optional)",
                "recovery_period": "Recovery period in days for scheduled deletion (default: 7)",
                "region": "AWS region override (optional)",
                "endpoint_url": "Custom endpoint URL for LocalStack or other AWS-compatible services (optional)",
            },
            "example": """targets:
  - provider: aws
    kind: secrets_manager
    config:
      name: prod/database-credentials
      description: RDS master credentials
      kms_key_id: arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012""",
        },
    }

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

    @property
    def provider_kind(self) -> str:
        """Return provider type identifier."""
        return "aws"

    def get_actor_info(self) -> dict[str, Any]:
        """Return information about the current AWS identity."""
        info = super().get_actor_info()
        region = (self.config or {}).get("region") or os.environ.get(AWSAuth.ENV_REGION)
        if region:
            info.setdefault("region", region)
        return info

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

                region = self.auth.config.get("region") or os.environ.get(
                    AWSAuth.ENV_REGION, "us-east-1"
                )
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
            elif auth_kind == "profile":
                profile_name = self.auth.config.get("profile") or os.environ.get(
                    AWSAuth.ENV_PROFILE, "default"
                )
                return True, f"AWS profile authentication configured for profile: {profile_name}"

        if not self.is_authenticated():
            auth_success = self.authenticate()
            if not auth_success:
                return (
                    False,
                    "AWS authentication failed. Check credentials and configuration. See AWS_* environment variables or ~/.aws/credentials",
                )

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

    # ============================================================================
    # Capability Methods: Generate
    # ============================================================================

    def generate_password(
        self,
        length: int = 32,
        special_chars: bool = True,
        uppercase: bool = True,
        lowercase: bool = True,
        numbers: bool = True,
    ) -> str:
        """Generate a random password using cryptographic randomness.

        Args:
            length: Password length (min 8, max 256)
            special_chars: Include special characters
            uppercase: Include uppercase letters
            lowercase: Include lowercase letters
            numbers: Include digits

        Returns:
            Generated password string
        """
        if length < 8 or length > 256:
            raise ValueError("Password length must be between 8 and 256")

        if not any([special_chars, uppercase, lowercase, numbers]):
            raise ValueError("At least one character type must be selected")

        # Build character pool
        char_pool = ""
        if uppercase:
            char_pool += string.ascii_uppercase
        if lowercase:
            char_pool += string.ascii_lowercase
        if numbers:
            char_pool += string.digits
        if special_chars:
            char_pool += "!@#$%^&*-_+=()[]{}|:;<>,.?/"

        # Generate password
        password = "".join(secrets.choice(char_pool) for _ in range(length))
        return password

    # ============================================================================
    # Capability Methods: Retrieve
    # ============================================================================

    def retrieve_secret(
        self,
        secret_name: str,
        version_id: str | None = None,
    ) -> str:
        """Retrieve secret from AWS Secrets Manager.

        Args:
            secret_name: Secret name or ARN
            version_id: Specific version to retrieve

        Returns:
            Secret value as string

        Raises:
            ValueError: If secret not found
        """
        try:
            client = self.auth.get_client("secretsmanager")
            kwargs = {"SecretId": secret_name}
            if version_id:
                kwargs["VersionId"] = version_id

            response = client.get_secret_value(**kwargs)
            return response.get("SecretString", "")

        except Exception as e:
            raise ValueError(f"Failed to retrieve secret from AWS: {str(e)}")

    # ============================================================================
    # Capability Methods: Store
    # ============================================================================

    def store_secret(
        self,
        secret_name: str,
        secret_value: str,
        tags: dict[str, str] | None = None,
    ) -> bool:
        """Create or update secret in AWS Secrets Manager.

        Args:
            secret_name: Secret name
            secret_value: Secret value
            tags: Optional tags to apply

        Returns:
            True if successful
        """
        try:
            client = self.auth.get_client("secretsmanager")
            kwargs = {
                "Name": secret_name,
                "SecretString": secret_value,
            }
            if tags:
                kwargs["Tags"] = [{"Key": k, "Value": v} for k, v in tags.items()]

            # Try to update, if secret doesn't exist create it
            try:
                client.update_secret(**kwargs)
            except client.exceptions.ResourceNotFoundException:
                client.create_secret(**kwargs)

            return True

        except Exception as e:
            raise ValueError(f"Failed to store secret in AWS: {str(e)}")

    # ============================================================================
    # Capability Methods: Rotate
    # ============================================================================

    def rotate_secret(
        self,
        secret_name: str,
        new_value: str,
    ) -> bool:
        """Rotate a secret in AWS Secrets Manager.

        Args:
            secret_name: Secret name
            new_value: New secret value

        Returns:
            True if successful
        """
        try:
            client = self.auth.get_client("secretsmanager")
            client.update_secret(
                SecretId=secret_name,
                SecretString=new_value,
            )
            return True

        except Exception as e:
            raise ValueError(f"Failed to rotate secret in AWS: {str(e)}")

    # ============================================================================
    # Capability Methods: Delete
    # ============================================================================

    def delete_secret(
        self,
        secret_name: str,
        force_delete: bool = False,
    ) -> bool:
        """Delete secret from AWS Secrets Manager.

        Args:
            secret_name: Secret name or ARN
            force_delete: Force immediate deletion (skip recovery window)

        Returns:
            True if successful
        """
        try:
            client = self.auth.get_client("secretsmanager")
            kwargs = {"SecretId": secret_name}
            if force_delete:
                kwargs["ForceDeleteWithoutRecovery"] = True
            else:
                kwargs["RecoveryWindowInDays"] = 7

            client.delete_secret(**kwargs)
            return True

        except Exception as e:
            raise ValueError(f"Failed to delete secret from AWS: {str(e)}")


# ---------------------------------------------------------------------------
# Bundle manifest – makes this provider extractable as a standalone package.
# When extracted, expose this via entry_points:
#   [project.entry-points."secretzero.providers"]
#   aws = "secretzero_aws:BUNDLE_MANIFEST"
# ---------------------------------------------------------------------------


def _get_bundle_manifest() -> "BundleManifest":  # noqa: F821
    """Lazily construct the AWS bundle manifest."""
    from secretzero.bundles.registry import BundleManifest

    return BundleManifest(
        name="aws",
        version="1.0.0",
        provider_class="secretzero.providers.aws:AWSProvider",
        generators={},
        targets={
            "ssm_parameter": "secretzero.targets.aws:SSMParameterTarget",
            "secrets_manager": "secretzero.targets.aws:SecretsManagerTarget",
        },
        generator_kinds=[],
        target_kinds=["ssm_parameter", "secrets_manager"],
        terraform_provider={
            "name": "aws",
            "source": "hashicorp/aws",
            "version": "~> 5.0",
            "default_config": {},
        },
    )
