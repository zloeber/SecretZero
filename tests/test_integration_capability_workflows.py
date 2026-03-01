"""Integration tests for provider capability workflows."""

from unittest.mock import MagicMock, patch

import pytest

from secretzero.generators.provider_backed import ProviderBackedGenerator
from secretzero.providers.aws import AWSProvider
from secretzero.providers.vault import VaultProvider


class TestProviderBackedGeneratorIntegration:
    """Test provider-backed generator integration with providers."""

    def test_aws_generate_and_store_workflow(self):
        """Test generating password with AWS and storing in same provider."""
        config = {"region": "us-east-1"}
        provider = AWSProvider("test-aws", config=config)

        # Mock the boto3 client for storage only
        # (generate_password uses Python secrets locally)
        mock_client = MagicMock()

        # Mock exceptions class
        mock_exceptions = MagicMock()
        mock_exceptions.ResourceNotFoundException = Exception
        mock_client.exceptions = mock_exceptions

        # update_secret should fail (secret doesn't exist yet)
        mock_client.update_secret.side_effect = Exception("ResourceNotFound")

        mock_client.create_secret.return_value = {
            "ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
            "Name": "test-secret",
        }

        # Mock auth to return client
        provider.auth = MagicMock()
        provider.auth.get_client.return_value = mock_client

        # Generate password (local generation, no AWS API call)
        password = provider.generate_password(length=32)
        assert isinstance(password, str)
        assert len(password) == 32

        # Store the generated password
        result = provider.store_secret("test-secret", password)
        assert result is True

        # Verify storage was called
        mock_client.create_secret.assert_called_once()

    def test_vault_generate_and_store_workflow(self):
        """Test generating password with Vault and storing in same provider."""
        config = {"url": "http://localhost:8200", "token": "s.test"}
        provider = VaultProvider("test-vault", config=config)

        # Mock auth and client
        mock_client = MagicMock()
        mock_client.secrets.kv.v2.create_or_update_secret.return_value = {"data": {"version": 1}}
        mock_client.is_authenticated.return_value = True

        provider.auth = MagicMock()
        provider.auth.is_authenticated.return_value = True
        provider.auth.get_client.return_value = mock_client

        with patch("secretzero.providers.vault.isinstance", return_value=True):
            # Generate password
            password = provider.generate_password(length=32)
            assert isinstance(password, str)
            assert len(password) == 32

            # Store the generated password
            result = provider.store_secret("test-secret", password)
            assert result is True

    def test_provider_backed_generator_with_aws(self):
        """Test ProviderBackedGenerator using AWS provider."""
        # Setup AWS provider
        aws_config = {"region": "us-east-1"}
        aws_provider = AWSProvider("aws", config=aws_config)

        # AWS generate_password is local, no mocking needed

        # Create provider-backed generator
        generator_config = {
            "provider": aws_provider,
            "method": "generate_password",
            "method_args": {"length": 24, "special_chars": True},
        }
        generator = ProviderBackedGenerator(config=generator_config)

        # Generate secret
        secret = generator.generate()
        assert isinstance(secret, str)
        assert len(secret) == 24

    def test_provider_backed_generator_with_vault(self):
        """Test ProviderBackedGenerator using Vault provider."""
        # Setup Vault provider
        vault_config = {"url": "http://localhost:8200", "token": "s.test"}
        vault_provider = VaultProvider("vault", config=vault_config)

        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        vault_provider.auth = MagicMock()
        vault_provider.auth.is_authenticated.return_value = True
        vault_provider.auth.get_client.return_value = mock_client

        # Create provider-backed generator
        generator_config = {
            "provider": vault_provider,
            "method": "generate_password",
            "method_args": {"length": 32},
        }
        generator = ProviderBackedGenerator(config=generator_config)

        with patch("secretzero.providers.vault.isinstance", return_value=True):
            # Generate secret
            secret = generator.generate()
            assert isinstance(secret, str)
            assert len(secret) == 32


class TestCrossProviderWorkflows:
    """Test workflows that span multiple providers."""

    def test_generate_in_aws_store_in_vault(self):
        """Test generating password in AWS and storing in Vault."""
        # Setup AWS provider
        aws_config = {"region": "us-east-1"}
        aws_provider = AWSProvider("aws", config=aws_config)

        # Generate password with AWS (local generation)
        password = aws_provider.generate_password(length=32)
        assert isinstance(password, str)
        assert len(password) == 32

        # Setup Vault provider
        vault_config = {"url": "http://localhost:8200", "token": "s.test"}
        vault_provider = VaultProvider("vault", config=vault_config)

        mock_vault_client = MagicMock()
        mock_vault_client.secrets.kv.v2.create_or_update_secret.return_value = {
            "data": {"version": 1}
        }
        mock_vault_client.is_authenticated.return_value = True

        vault_provider.auth = MagicMock()
        vault_provider.auth.is_authenticated.return_value = True
        vault_provider.auth.get_client.return_value = mock_vault_client

        with patch("secretzero.providers.vault.isinstance", return_value=True):
            # Store in Vault
            result = vault_provider.store_secret("cross-provider-secret", password)
            assert result is True

            # Verify storage was called
            mock_vault_client.secrets.kv.v2.create_or_update_secret.assert_called_once()

    def test_generate_in_vault_store_in_aws(self):
        """Test generating password in Vault and storing in AWS."""
        # Setup Vault provider
        vault_config = {"url": "http://localhost:8200", "token": "s.test"}
        vault_provider = VaultProvider("vault", config=vault_config)

        mock_vault_client = MagicMock()
        mock_vault_client.is_authenticated.return_value = True
        vault_provider.auth = MagicMock()
        vault_provider.auth.is_authenticated.return_value = True
        vault_provider.auth.get_client.return_value = mock_vault_client

        with patch("secretzero.providers.vault.isinstance", return_value=True):
            # Generate password with Vault
            password = vault_provider.generate_password(length=32)
            assert isinstance(password, str)

        # Setup AWS provider
        aws_config = {"region": "us-east-1"}
        aws_provider = AWSProvider("aws", config=aws_config)

        mock_aws_client = MagicMock()

        # Mock exceptions class
        mock_exceptions = MagicMock()
        mock_exceptions.ResourceNotFoundException = Exception
        mock_aws_client.exceptions = mock_exceptions

        # update_secret should fail (secret doesn't exist yet)
        mock_aws_client.update_secret.side_effect = Exception("ResourceNotFound")

        mock_aws_client.create_secret.return_value = {
            "ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
            "Name": "test-secret",
        }

        aws_provider.auth = MagicMock()
        aws_provider.auth.get_client.return_value = mock_aws_client

        # Store in AWS
        result = aws_provider.store_secret("vault-generated-secret", password)
        assert result is True
        mock_aws_client.create_secret.assert_called_once()


class TestRotationWorkflows:
    """Test secret rotation workflows across providers."""

    def test_aws_rotation_workflow(self):
        """Test complete rotation workflow in AWS."""
        config = {"region": "us-east-1"}
        provider = AWSProvider("test-aws", config=config)

        mock_client = MagicMock()

        # Mock initial secret retrieval
        mock_client.get_secret_value.return_value = {"SecretString": "OldPassword123!"}

        # Mock rotation (AWS rotate expects new_value parameter)
        mock_client.update_secret.return_value = {
            "ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
            "Name": "test-secret",
            "VersionId": "new-version",
        }

        provider.auth = MagicMock()
        provider.auth.get_client.return_value = mock_client

        # Retrieve old secret
        old_secret = provider.retrieve_secret("test-secret")
        assert old_secret == "OldPassword123!"

        # Generate new password locally
        new_password = provider.generate_password(length=32)
        assert isinstance(new_password, str)

        # Rotate secret with new value
        result = provider.rotate_secret("test-secret", new_password)
        assert result is True

        # Verify operations
        mock_client.get_secret_value.assert_called_once()
        mock_client.update_secret.assert_called_once()

    def test_vault_rotation_workflow(self):
        """Test complete rotation workflow in Vault."""
        config = {"url": "http://localhost:8200", "token": "s.test"}
        provider = VaultProvider("test-vault", config=config)

        mock_client = MagicMock()

        # Mock initial secret retrieval
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"password": "OldVaultPassword123!"}}
        }

        # Mock rotation
        mock_client.secrets.kv.v2.create_or_update_secret.return_value = {"data": {"version": 2}}
        mock_client.is_authenticated.return_value = True

        provider.auth = MagicMock()
        provider.auth.is_authenticated.return_value = True
        provider.auth.get_client.return_value = mock_client

        with patch("secretzero.providers.vault.isinstance", return_value=True):
            # Retrieve old secret
            old_secret = provider.retrieve_secret("test-secret", field="password")
            assert old_secret == "OldVaultPassword123!"

            # Generate new password
            new_password = provider.generate_password(length=32)
            assert isinstance(new_password, str)

            # Rotate secret (Vault also needs new_value)
            result = provider.rotate_secret("test-secret", new_password)
            assert result is True


class TestErrorHandlingIntegration:
    """Test error handling across provider interactions."""

    def test_generate_failure_does_not_store(self):
        """Test that storage is skipped if generation fails."""
        config = {"region": "us-east-1"}
        provider = AWSProvider("test-aws", config=config)

        # AWS generate_password is local and unlikely to fail,
        # but we can test with invalid parameters
        mock_client = MagicMock()
        provider.auth = MagicMock()
        provider.auth.get_client.return_value = mock_client

        # Test with invalid length
        with pytest.raises(ValueError, match="Password length must be between"):
            provider.generate_password(length=5)  # Too short

        # Store should not be called
        mock_client.create_secret.assert_not_called()

    def test_store_failure_after_successful_generate(self):
        """Test handling when storage fails after successful generation."""
        config = {"region": "us-east-1"}
        provider = AWSProvider("test-aws", config=config)

        mock_client = MagicMock()
        # Generation succeeds
        mock_client.get_random_password.return_value = {"RandomPassword": "Generated123!"}
        # Storage fails
        mock_client.create_secret.side_effect = Exception("Storage failed")
        provider.client = mock_client

        # Generate succeeds
        password = provider.generate_password()
        assert isinstance(password, str)

        # Store fails
        with pytest.raises(ValueError, match="Failed to store secret in AWS"):
            provider.store_secret("test-secret", password)

    def test_retry_on_retrieve_failure(self):
        """Test that retrieve operations can be retried."""
        config = {"region": "us-east-1"}
        provider = AWSProvider("test-aws", config=config)

        mock_client = MagicMock()
        # First call fails, second succeeds
        mock_client.get_secret_value.side_effect = [
            Exception("Temporary failure"),
            {"SecretString": "Retrieved123!"},
        ]
        provider.client = mock_client
        provider.auth = MagicMock()
        provider.auth.get_client.return_value = mock_client

        # First attempt fails
        with pytest.raises(ValueError):
            provider.retrieve_secret("test-secret")

        # Second attempt succeeds
        secret = provider.retrieve_secret("test-secret")
        assert secret == "Retrieved123!"
        assert mock_client.get_secret_value.call_count == 2


class TestCapabilityValidation:
    """Test capability validation in workflows."""

    def test_provider_backed_generator_validates_method_exists(self):
        """Test that generator validates method exists on provider."""
        aws_config = {"region": "us-east-1"}
        aws_provider = AWSProvider("aws", config=aws_config)

        # Valid method should work
        valid_config = {"provider": aws_provider, "method": "generate_password", "method_args": {}}
        generator = ProviderBackedGenerator(config=valid_config)
        assert generator.gen_config.method == "generate_password"

        # Invalid method should fail during instantiation
        invalid_config = {
            "provider": aws_provider,
            "method": "nonexistent_method",
            "method_args": {},
        }
        with pytest.raises(AttributeError, match="has no method"):
            ProviderBackedGenerator(config=invalid_config)

    def test_aws_provider_has_required_methods(self):
        """Test that AWS provider has all required capability methods."""
        config = {"region": "us-east-1"}
        provider = AWSProvider("test-aws", config=config)

        # Check all required methods exist
        assert hasattr(provider, "generate_password")
        assert hasattr(provider, "retrieve_secret")
        assert hasattr(provider, "store_secret")
        assert hasattr(provider, "rotate_secret")
        assert hasattr(provider, "delete_secret")

        # Check methods are callable
        assert callable(provider.generate_password)
        assert callable(provider.retrieve_secret)
        assert callable(provider.store_secret)
        assert callable(provider.rotate_secret)
        assert callable(provider.delete_secret)

    def test_vault_provider_has_required_methods(self):
        """Test that Vault provider has all required capability methods."""
        config = {"url": "http://localhost:8200", "token": "s.test"}
        provider = VaultProvider("test-vault", config=config)

        # Check all required methods exist
        assert hasattr(provider, "generate_password")
        assert hasattr(provider, "retrieve_secret")
        assert hasattr(provider, "store_secret")
        assert hasattr(provider, "rotate_secret")
        assert hasattr(provider, "delete_secret")

        # Check methods are callable
        assert callable(provider.generate_password)
        assert callable(provider.retrieve_secret)
        assert callable(provider.store_secret)
        assert callable(provider.rotate_secret)
        assert callable(provider.delete_secret)
