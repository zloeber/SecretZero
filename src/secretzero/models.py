"""Pydantic models for SecretZero configuration."""

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator


class AuthKind(str, Enum):
    """Authentication kind for providers."""

    AMBIENT = "ambient"
    TOKEN = "token"
    ASSUME_ROLE = "assume_role"
    STATIC = "static"


class GeneratorKind(str, Enum):
    """Generator kind for secret values."""

    STATIC = "static"
    RANDOM_PASSWORD = "random_password"
    RANDOM_STRING = "random_string"
    SCRIPT = "script"
    API = "api"


class TargetKind(str, Enum):
    """Target storage kind."""

    FILE = "file"
    TEMPLATE = "template"
    SSM_PARAMETER = "ssm_parameter"
    SECRETS_MANAGER = "secrets_manager"
    VAULT_KV = "vault_kv"
    AZURE_KEYVAULT = "azure_keyvault"
    KUBERNETES_SECRET = "kubernetes_secret"
    GITHUB_SECRET = "github_secret"
    GITLAB_VARIABLE = "gitlab_variable"


class FileFormat(str, Enum):
    """File format for file-based targets."""

    DOTENV = "dotenv"
    JSON = "json"
    YAML = "yaml"
    TOML = "toml"


class AuthProfile(BaseModel):
    """Authentication profile configuration."""

    kind: AuthKind
    config: Dict[str, Any] = Field(default_factory=dict)


class ProviderAuth(BaseModel):
    """Provider authentication configuration."""

    kind: Optional[AuthKind] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    fallback_generator: Optional[str] = None
    profiles: Dict[str, AuthProfile] = Field(default_factory=dict)


class Provider(BaseModel):
    """Provider configuration for secret sources and targets."""

    kind: Optional[str] = None
    auth: Optional[ProviderAuth] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    fallback_generator: Optional[str] = None


class GeneratorConfig(BaseModel):
    """Generator configuration for secret values."""

    kind: GeneratorKind
    config: Dict[str, Any] = Field(default_factory=dict)


class TargetConfig(BaseModel):
    """Target storage configuration."""

    provider: str
    kind: Union[TargetKind, str]
    config: Dict[str, Any] = Field(default_factory=dict)


class TemplateField(BaseModel):
    """Template field definition."""

    description: str
    generator: GeneratorConfig
    targets: List[TargetConfig] = Field(default_factory=list)


class Template(BaseModel):
    """Secret template definition."""

    description: str
    fields: Dict[str, TemplateField]
    targets: List[TargetConfig] = Field(default_factory=list)


class Secret(BaseModel):
    """Secret definition."""

    name: str
    kind: str
    vars: Dict[str, Any] = Field(default_factory=dict)
    config: Dict[str, Any] = Field(default_factory=dict)
    one_time: bool = False
    rotation_period: Optional[str] = None
    targets: List[TargetConfig] = Field(default_factory=list)


class Metadata(BaseModel):
    """Metadata about the secrets configuration."""

    project: Optional[str] = None
    owner: Optional[str] = None
    environments: List[str] = Field(default_factory=list)
    compliance: List[str] = Field(default_factory=list)


class Secretfile(BaseModel):
    """Root configuration model for Secretfile.yml."""

    version: str
    variables: Dict[str, Any] = Field(default_factory=dict)
    metadata: Optional[Metadata] = None
    providers: Dict[str, Provider] = Field(default_factory=dict)
    secrets: List[Secret] = Field(default_factory=list)
    templates: Dict[str, Template] = Field(default_factory=dict)
    policies: Dict[str, Any] = Field(default_factory=dict)
    labels: Dict[str, Any] = Field(default_factory=dict)
    annotations: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Validate version format."""
        if not v:
            raise ValueError("version is required")
        return v
