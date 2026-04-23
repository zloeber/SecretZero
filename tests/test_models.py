"""Tests for SecretZero data models."""

import pytest
from secretzero.models import (
    AuthKind,
    AuthProfile,
    GeneratorConfig,
    GeneratorKind,
    Metadata,
    Provider,
    ProviderAuth,
    Secret,
    SecretSource,
    SecretSourceKind,
    Secretfile,
    TargetConfig,
    TargetKind,
    Template,
    TemplateField,
)


def test_auth_profile_creation() -> None:
    """Test creating an auth profile."""
    profile = AuthProfile(kind=AuthKind.TOKEN, config={"token": "test"})
    assert profile.kind == AuthKind.TOKEN
    assert profile.config["token"] == "test"


def test_provider_creation() -> None:
    """Test creating a provider."""
    provider = Provider(
        kind="aws",
        auth=ProviderAuth(kind=AuthKind.AMBIENT, config={"region": "us-east-1"}),
    )
    assert provider.kind == "aws"
    assert provider.auth.kind == AuthKind.AMBIENT


def test_generator_config_creation() -> None:
    """Test creating a generator config."""
    generator = GeneratorConfig(
        kind=GeneratorKind.RANDOM_PASSWORD, config={"length": 32, "special": True}
    )
    assert generator.kind == GeneratorKind.RANDOM_PASSWORD
    assert generator.config["length"] == 32


def test_target_config_creation() -> None:
    """Test creating a target config."""
    target = TargetConfig(
        provider="local",
        kind=TargetKind.FILE,
        config={"path": ".env", "format": "dotenv"},
    )
    assert target.provider == "local"
    assert target.kind == TargetKind.FILE


def test_template_field_creation() -> None:
    """Test creating a template field."""
    field = TemplateField(
        description="Test field",
        generator=GeneratorConfig(kind=GeneratorKind.STATIC, config={"default": "value"}),
        targets=[TargetConfig(provider="local", kind=TargetKind.FILE, config={"path": ".env"})],
    )
    assert field.description == "Test field"
    assert field.generator.kind == GeneratorKind.STATIC


def test_template_creation() -> None:
    """Test creating a template."""
    template = Template(
        description="Test template",
        fields={
            "field1": TemplateField(
                description="Field 1",
                generator=GeneratorConfig(kind=GeneratorKind.STATIC, config={"default": "value"}),
            )
        },
    )
    assert template.description == "Test template"
    assert "field1" in template.fields


def test_secret_creation() -> None:
    """Test creating a secret."""
    secret = Secret(
        name="test_secret",
        kind="random_password",
        config={"length": 32},
        targets=[TargetConfig(provider="local", kind=TargetKind.FILE, config={"path": ".env"})],
    )
    assert secret.name == "test_secret"
    assert secret.kind == "random_password"
    assert len(secret.targets) == 1


def test_metadata_creation() -> None:
    """Test creating metadata."""
    metadata = Metadata(
        project="test-project",
        owner="test-team",
        environments=["dev", "prod"],
        compliance=["soc2"],
    )
    assert metadata.project == "test-project"
    assert "dev" in metadata.environments


def test_secretfile_creation() -> None:
    """Test creating a Secretfile."""
    secretfile = Secretfile(
        variables={"environment": "dev"},
        providers={
            "local": Provider(kind="local", config={}),
        },
        secrets=[
            Secret(
                name="test",
                kind="random_password",
                targets=[
                    TargetConfig(provider="local", kind=TargetKind.FILE, config={"path": ".env"})
                ],
            )
        ],
    )
    assert "environment" in secretfile.variables
    assert "local" in secretfile.providers
    assert len(secretfile.secrets) == 1


def test_secretfile_allows_missing_version() -> None:
    """Test that Secretfile no longer requires a root version field."""
    secretfile = Secretfile(secrets=[])
    assert secretfile.secrets == []


def test_secret_with_rotation() -> None:
    """Test secret with rotation period."""
    secret = Secret(
        name="rotating_secret",
        kind="random_password",
        one_time=False,
        rotation_period="90d",
        targets=[],
    )
    assert secret.rotation_period == "90d"
    assert not secret.one_time


def test_secret_source_creation() -> None:
    """Test creating a secret with non-human source config."""
    secret = Secret(
        name="seeded_secret",
        kind="static",
        source=SecretSource(
            kind=SecretSourceKind.ENV,
            required=False,
            config={"name": "SEEDED_SECRET"},
        ),
        targets=[],
    )
    assert secret.source is not None
    assert secret.source.kind == SecretSourceKind.ENV
    assert secret.source.required is False


def test_secret_source_secret_ref_requires_secret_key() -> None:
    """secret_ref source requires config.secret."""
    with pytest.raises(ValueError, match="source.config.secret"):
        SecretSource(kind=SecretSourceKind.SECRET_REF, config={})


def test_secret_source_provider_read_requires_read_object() -> None:
    """provider_read source requires an object read config."""
    with pytest.raises(ValueError, match="source.config.read"):
        SecretSource(
            kind=SecretSourceKind.PROVIDER_READ,
            config={"provider": "aws", "kind": "secrets_manager", "read": "bad"},
        )


def test_one_time_secret() -> None:
    """Test one-time secret."""
    secret = Secret(
        name="one_time_secret",
        kind="random_password",
        one_time=True,
        targets=[],
    )
    assert secret.one_time
