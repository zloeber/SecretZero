"""Pydantic models for SecretZero configuration."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from secretzero.cli_config import AppConfig


class AutomationLevel(str, Enum):
    """Level of automation possible for secret acquisition."""

    FULLY_AUTOMATED = "fully_automated"
    SEMI_AUTOMATED = "semi_automated"
    MANUAL_ONLY = "manual_only"
    REQUIRES_APPROVAL = "requires_approval"


class AgentInstructionStep(BaseModel):
    """Single step in agent instruction workflow."""

    action: str = Field(description="Action to perform (CLI command, URL, or description)")
    description: str = Field(description="Human-readable context for the action")
    params: dict[str, Any] | None = Field(
        default=None, description="Optional parameters for API calls"
    )
    required: bool = Field(default=True, description="Whether this step is required or optional")


class AgentInstructions(BaseModel):
    """Instructions for agents to obtain a secret."""

    summary: str = Field(description="Brief overview of the acquisition process")
    steps: list[AgentInstructionStep] = Field(description="Step-by-step instructions")
    prerequisites: list[str] | None = Field(
        default=None, description="Requirements before starting"
    )
    automation_hint: str | None = Field(
        default=None, description="Guidance on automation feasibility"
    )
    estimated_time: str | None = Field(default=None, description="Expected time to complete")
    fallback: str | None = Field(default=None, description="What to do if automation fails")
    required_tools: list[str] | None = Field(
        default=None, description="CLI tools or dependencies needed"
    )
    documentation_url: str | None = Field(
        default=None, description="Link to official documentation"
    )


class AuthKind(str, Enum):
    """Authentication kind for providers."""

    AMBIENT = "ambient"
    TOKEN = "token"
    ASSUME_ROLE = "assume_role"
    STATIC = "static"


class GeneratorKind(str, Enum):
    """Generator kind for secret values.

    This enum is intentionally *open*: unknown string values passed by
    third-party bundles are accepted at runtime via :meth:`_missing_`
    instead of raising a ``ValueError``.  Built-in kinds are enumerated
    below; bundle authors may declare any additional string as a kind.
    """

    STATIC = "static"
    RANDOM_PASSWORD = "random_password"
    RANDOM_STRING = "random_string"
    SCRIPT = "script"
    API = "api"
    PROVIDER_BACKED = "provider_backed"
    GITHUB_PAT = "github_pat"

    @classmethod
    def _missing_(cls, value: object) -> GeneratorKind | None:
        """Accept unknown generator kinds registered by third-party bundles.

        Args:
            value: The string value that was not found in the enum.

        Returns:
            A new pseudo-member for the value if it is a non-empty string,
            otherwise ``None``.
        """
        if isinstance(value, str) and value:
            obj = str.__new__(cls, value)
            obj._name_ = value
            obj._value_ = value
            return obj
        return None


class TargetKind(str, Enum):
    """Target storage kind.

    This enum is intentionally *open*: unknown string values passed by
    third-party bundles are accepted at runtime via :meth:`_missing_`
    instead of raising a ``ValueError``.  Built-in kinds are enumerated
    below; bundle authors may declare any additional string as a kind.
    """

    FILE = "file"
    TEMPLATE = "template"
    SSM_PARAMETER = "ssm_parameter"
    SECRETS_MANAGER = "secrets_manager"
    VAULT_KV = "vault_kv"
    AZURE_KEYVAULT = "azure_keyvault"
    KUBERNETES_SECRET = "kubernetes_secret"
    GITHUB_SECRET = "github_secret"
    GITLAB_VARIABLE = "gitlab_variable"
    JENKINS_CREDENTIAL = "jenkins_credential"

    @classmethod
    def _missing_(cls, value: object) -> TargetKind | None:
        """Accept unknown target kinds registered by third-party bundles.

        Args:
            value: The string value that was not found in the enum.

        Returns:
            A new pseudo-member for the value if it is a non-empty string,
            otherwise ``None``.
        """
        if isinstance(value, str) and value:
            obj = str.__new__(cls, value)
            obj._name_ = value
            obj._value_ = value
            return obj
        return None


class FileFormat(str, Enum):
    """File format for file-based targets."""

    DOTENV = "dotenv"
    JSON = "json"
    YAML = "yaml"
    TOML = "toml"


class AuthProfile(BaseModel):
    """Authentication profile configuration."""

    kind: AuthKind
    config: dict[str, Any] = Field(default_factory=dict)


class ProviderAuth(BaseModel):
    """Provider authentication configuration."""

    kind: AuthKind | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    fallback_generator: str | None = None
    profiles: dict[str, AuthProfile] = Field(default_factory=dict)


class Provider(BaseModel):
    """Provider configuration for secret sources and targets."""

    kind: str | None = None
    auth: ProviderAuth | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    fallback_generator: str | None = None


class GeneratorConfig(BaseModel):
    """Generator configuration for secret values."""

    kind: GeneratorKind
    config: dict[str, Any] = Field(default_factory=dict)


class TargetConfig(BaseModel):
    """Target storage configuration."""

    provider: str
    kind: TargetKind | str
    config: dict[str, Any] = Field(default_factory=dict)


class TemplateField(BaseModel):
    """Template field definition."""

    description: str
    generator: GeneratorConfig
    targets: list[TargetConfig] = Field(default_factory=list)


class Template(BaseModel):
    """Secret template definition."""

    description: str
    fields: dict[str, TemplateField]
    targets: list[TargetConfig] = Field(default_factory=list)


class Secret(BaseModel):
    """Secret definition."""

    name: str
    kind: str
    vars: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    one_time: bool = False
    rotation_period: str | None = None
    targets: list[TargetConfig] = Field(default_factory=list)
    agent_instructions: AgentInstructions | None = Field(
        default=None,
        description="Instructions for agents to obtain this secret",
    )


class Metadata(BaseModel):
    """Metadata about the secrets configuration."""

    project: str | None = None
    owner: str | None = None
    environments: list[str] = Field(default_factory=list)
    compliance: list[str] = Field(default_factory=list)


class Secretfile(BaseModel):
    """Root configuration model for Secretfile.yml."""

    version: str
    variables: dict[str, Any] = Field(default_factory=dict)
    metadata: Metadata | None = None
    providers: dict[str, Provider] = Field(default_factory=dict)
    secrets: list[Secret] = Field(default_factory=list)
    templates: dict[str, Template] = Field(default_factory=dict)
    policies: dict[str, Any] = Field(default_factory=dict)
    labels: dict[str, Any] = Field(default_factory=dict)
    annotations: dict[str, Any] = Field(default_factory=dict)
    config: AppConfig | None = Field(
        default=None,
        description="Optional centralized app config (LLM, discovery, output); overrides config.yml and defaults",
    )

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Validate version format."""
        if not v:
            raise ValueError("version is required")
        return v
