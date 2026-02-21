"""Tests for AWS provider capability methods."""

import pytest
from unittest.mock import Mock, MagicMock, patch, call

from secretzero.providers.aws import AWSProvider, AWSAuth


class TestAWSGeneratePassword:
    """Tests for AWSProvider.generate_password() method."""

    def test_generate_password_defaults(self):
        """Test password generation with default parameters."""
        config = {"region": "us-east-1"}
        provider = AWSProvider("test-aws", config=config)

        password = provider.generate_password()

        assert isinstance(password, str)
        assert len(password) == 32
        # With defaults, should have mix of character types (not all identical)
        assert len(set(password)) > 1
        assert any(c in "!@#$%^&*-_+=()[]{}|:;<>,.?/" for c in password)  # Has special

    def test_generate_password_custom_length(self):
        """Test password generation with custom length."""
        config = {"region": "us-east-1"}
        provider = AWSProvider("test-aws", config=config)

        password = provider.generate_password(length=64)

        assert len(password) == 64

    def test_generate_password_no_special_chars(self):
        """Test password without special characters."""
        config = {"region": "us-east-1"}
        provider = AWSProvider("test-aws", config=config)

        password = provider.generate_password(special_chars=False)

        assert not any(c in "!@#$%^&*-_+=()[]{}|:;<>,.?/" for c in password)

    def test_generate_password_only_lowercase(self):
        """Test password with only lowercase letters."""
        config = {"region": "us-east-1"}
        provider = AWSProvider("test-aws", config=config)

        password = provider.generate_password(uppercase=False, numbers=False, special_chars=False)

        assert password.islower()
        assert all(c in "abcdefghijklmnopqrstuvwxyz" for c in password)

    def test_generate_password_invalid_length_too_short(self):
        """Test that password length < 8 raises ValueError."""
        config = {"region": "us-east-1"}
        provider = AWSProvider("test-aws", config=config)

        with pytest.raises(ValueError, match="Password length must be between 8 and 256"):
            provider.generate_password(length=7)

    def test_generate_password_invalid_length_too_long(self):
        """Test that password length > 256 raises ValueError."""
        config = {"region": "us-east-1"}
        provider = AWSProvider("test-aws", config=config)

        with pytest.raises(ValueError, match="Password length must be between 8 and 256"):
            provider.generate_password(length=257)

    def test_generate_password_no_char_types_selected(self):
        """Test that selecting no character types raises ValueError."""
        config = {"region": "us-east-1"}
        provider = AWSProvider("test-aws", config=config)

        with pytest.raises(ValueError, match="At least one character type must be selected"):
            provider.generate_password(
                uppercase=False, lowercase=False, numbers=False, special_chars=False
            )

    def test_generate_password_randomness(self):
        """Test that multiple calls generate different passwords."""
        config = {"region": "us-east-1"}
        provider = AWSProvider("test-aws", config=config)

        passwords = [provider.generate_password() for _ in range(10)]

        # All should be different (extremely high probability)
        assert len(set(passwords)) == 10


class TestAWSRetrieveSecret:
    """Tests for AWSProvider.retrieve_secret() method."""

    def test_retrieve_secret_success(self):
        """Test successful secret retrieval."""
        config = {"region": "us-east-1"}
        provider = AWSProvider("test-aws", config=config)

        # Mock the boto3 client
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {"SecretString": "my-secret-value"}
        provider.auth = MagicMock()
        provider.auth.get_client.return_value = mock_client

        result = provider.retrieve_secret("my-secret")

        assert result == "my-secret-value"
        mock_client.get_secret_value.assert_called_once_with(SecretId="my-secret")

    def test_retrieve_secret_with_version(self):
        """Test secret retrieval with specific version."""
        config = {"region": "us-east-1"}
        provider = AWSProvider("test-aws", config=config)

        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {"SecretString": "versioned-secret"}
        provider.auth = MagicMock()
        provider.auth.get_client.return_value = mock_client

        result = provider.retrieve_secret("my-secret", version_id="v123")

        assert result == "versioned-secret"
        mock_client.get_secret_value.assert_called_once_with(SecretId="my-secret", VersionId="v123")

    def test_retrieve_secret_not_found(self):
        """Test retrieval when secret doesn't exist."""
        config = {"region": "us-east-1"}
        provider = AWSProvider("test-aws", config=config)

        mock_client = MagicMock()
        mock_client.get_secret_value.side_effect = Exception("ResourceNotFoundException")
        provider.auth = MagicMock()
        provider.auth.get_client.return_value = mock_client

        with pytest.raises(ValueError, match="Failed to retrieve secret from AWS:"):
            provider.retrieve_secret("nonexistent-secret")

    def test_retrieve_secret_no_auth(self):
        """Test that missing auth raises ValueError."""
        config = {"region": "us-east-1"}
        provider = AWSProvider("test-aws", config=config)
        provider.auth = None

        with pytest.raises(ValueError, match="Failed to retrieve secret from AWS:"):
            provider.retrieve_secret("my-secret")


class TestAWSStoreSecret:
    """Tests for AWSProvider.store_secret() method."""

    def test_store_secret_create_new(self):
        """Test creating a new secret."""
        config = {"region": "us-east-1"}
        provider = AWSProvider("test-aws", config=config)

        mock_client = MagicMock()
        # For new secret, update fails, then create succeeds
        mock_client.create_secret.return_value = {"ARN": "arn:aws:secretsmanager:..."}
        # Mock the exceptions attribute properly
        mock_exception = Exception
        mock_client.exceptions.ResourceNotFoundException = mock_exception
        mock_client.update_secret.side_effect = mock_exception("Not found")

        provider.auth = MagicMock()
        provider.auth.get_client.return_value = mock_client

        result = provider.store_secret("new-secret", "secret-value")

        assert result is True
        mock_client.create_secret.assert_called_once()

    def test_store_secret_update_existing(self):
        """Test updating an existing secret."""
        config = {"region": "us-east-1"}
        provider = AWSProvider("test-aws", config=config)

        mock_client = MagicMock()
        mock_client.update_secret.return_value = {"ARN": "arn:aws:secretsmanager:..."}
        provider.auth = MagicMock()
        provider.auth.get_client.return_value = mock_client

        result = provider.store_secret("existing-secret", "new-value")

        assert result is True
        mock_client.update_secret.assert_called_once()

    def test_store_secret_with_tags(self):
        """Test storing secret with tags."""
        config = {"region": "us-east-1"}
        provider = AWSProvider("test-aws", config=config)

        mock_client = MagicMock()
        # Use update_secret for existing secret
        mock_client.update_secret.return_value = {"ARN": "arn:aws:secretsmanager:..."}
        # Mock the exceptions attribute
        mock_client.exceptions.ResourceNotFoundException = Exception

        provider.auth = MagicMock()
        provider.auth.get_client.return_value = mock_client

        tags = {"environment": "prod", "team": "backend"}
        result = provider.store_secret("tagged-secret", "value", tags=tags)

        assert result is True

    def test_store_secret_no_auth(self):
        """Test that missing auth raises ValueError."""
        config = {"region": "us-east-1"}
        provider = AWSProvider("test-aws", config=config)
        provider.auth = None

        with pytest.raises(ValueError, match="Failed to store secret in AWS:"):
            provider.store_secret("secret", "value")


class TestAWSRotateSecret:
    """Tests for AWSProvider.rotate_secret() method."""

    def test_rotate_secret_success(self):
        """Test successful secret rotation."""
        config = {"region": "us-east-1"}
        provider = AWSProvider("test-aws", config=config)

        mock_client = MagicMock()
        mock_client.update_secret.return_value = {"ARN": "arn:aws:secretsmanager:..."}
        provider.auth = MagicMock()
        provider.auth.get_client.return_value = mock_client

        result = provider.rotate_secret("my-secret", "new-secret-value")

        assert result is True
        mock_client.update_secret.assert_called_once_with(
            SecretId="my-secret", SecretString="new-secret-value"
        )

    def test_rotate_secret_failure(self):
        """Test rotation failure."""
        config = {"region": "us-east-1"}
        provider = AWSProvider("test-aws", config=config)

        mock_client = MagicMock()
        mock_client.update_secret.side_effect = Exception("Permission denied")
        provider.auth = MagicMock()
        provider.auth.get_client.return_value = mock_client

        with pytest.raises(ValueError, match="Failed to rotate secret"):
            provider.rotate_secret("my-secret", "new-value")


class TestAWSDeleteSecret:
    """Tests for AWSProvider.delete_secret() method."""

    def test_delete_secret_with_recovery_window(self):
        """Test soft delete with recovery window."""
        config = {"region": "us-east-1"}
        provider = AWSProvider("test-aws", config=config)

        mock_client = MagicMock()
        mock_client.delete_secret.return_value = {
            "ARN": "arn:aws:secretsmanager:...",
            "DeletionDate": "2025-02-27T...",
        }
        provider.auth = MagicMock()
        provider.auth.get_client.return_value = mock_client

        result = provider.delete_secret("my-secret", force_delete=False)

        assert result is True
        # Should not use force delete
        call_kwargs = mock_client.delete_secret.call_args[1]
        assert call_kwargs.get("ForceDeleteWithoutRecovery") is not True

    def test_delete_secret_force_delete(self):
        """Test immediate force delete."""
        config = {"region": "us-east-1"}
        provider = AWSProvider("test-aws", config=config)

        mock_client = MagicMock()
        mock_client.delete_secret.return_value = {"ARN": "arn:aws:secretsmanager:..."}
        provider.auth = MagicMock()
        provider.auth.get_client.return_value = mock_client

        result = provider.delete_secret("my-secret", force_delete=True)

        assert result is True
        # Should use force delete
        call_kwargs = mock_client.delete_secret.call_args[1]
        assert call_kwargs.get("ForceDeleteWithoutRecovery") is True

    def test_delete_secret_not_found(self):
        """Test deleting non-existent secret."""
        config = {"region": "us-east-1"}
        provider = AWSProvider("test-aws", config=config)

        mock_client = MagicMock()
        mock_client.delete_secret.side_effect = Exception("ResourceNotFoundException")
        provider.auth = MagicMock()
        provider.auth.get_client.return_value = mock_client

        with pytest.raises(ValueError, match="Failed to delete secret"):
            provider.delete_secret("nonexistent-secret")


class TestAWSCapabilityIntegration:
    """Integration tests for AWS provider capabilities."""

    def test_aws_capabilities_discoverable(self):
        """Test that AWS provider capabilities are discoverable."""
        from secretzero.providers.capabilities import CapabilityType

        capabilities = AWSProvider.get_capabilities()

        assert capabilities.provider_kind == "aws"
        assert len(capabilities.capabilities) == 5

        capability_names = [cap.method.name for cap in capabilities.capabilities]
        assert "generate_password" in capability_names
        assert "retrieve_secret" in capability_names
        assert "store_secret" in capability_names
        assert "rotate_secret" in capability_names
        assert "delete_secret" in capability_names

    def test_aws_generate_method_has_params(self):
        """Test that generate_password has correct parameters."""
        capabilities = AWSProvider.get_capabilities()
        gen_cap = capabilities.get_capability("generate_password")

        assert gen_cap is not None
        assert gen_cap.method.parameters is not None

    def test_all_capability_methods_documented(self):
        """Test that all methods have documentation."""
        capabilities = AWSProvider.get_capabilities()

        for capability in capabilities.capabilities:
            assert capability.method.description is not None
            assert len(capability.method.description) > 0
            assert capability.method.return_type is not None
