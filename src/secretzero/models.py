"""Pydantic models for SecretZero configuration."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from secretzero.cli_config import AppConfig

SECRETFILE_MANIFEST_SPEC_VERSION = "1"


class AgentMode(str, Enum):
    """How the unified ``agent sync`` workflow should obtain manual secrets."""

    AUTO = "auto"
    HUMAN = "human"
    WEB = "web"


class AgentConfig(BaseModel):
    """Top-level defaults for ``secretzero agent sync`` (CLI and API)."""

    mode: AgentMode = Field(
        default=AgentMode.AUTO,
        description="Preferred workflow: auto (best effort), human (instructions only), or web (local form)",
    )
    web_port_min: int = Field(
        default=49152,
        ge=1024,
        le=65535,
        description="Lower bound (inclusive) for the temporary localhost web UI",
    )
    web_port_max: int = Field(
        default=65535,
        ge=1024,
        le=65535,
        description="Upper bound (inclusive) for the temporary localhost web UI",
    )

    @model_validator(mode="after")
    def _validate_port_range(self) -> AgentConfig:
        """Ensure web port range is ordered."""
        if self.web_port_min > self.web_port_max:
            raise ValueError("web_port_min must be <= web_port_max")
        return self


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

    def render_for_secret(
        self,
        *,
        variables: dict[str, Any],
        secret_name: str,
        secret: Secret,
    ) -> AgentInstructions:
        """Return a copy with string fields rendered using Secretfile variables and secret context.

        Templates may use ``{{ var.name }}`` (same as the Secretfile), ``{{ secret_name }}``,
        and ``{{ target.kind }}`` / keys from the first target's ``config`` (exposed as
        ``target`` in the template context).
        """
        from secretzero.config import render_template_with_agent_context

        def _rt(text: str | None) -> str | None:
            if text is None:
                return None
            return render_template_with_agent_context(
                text,
                variables=variables,
                secret_name=secret_name,
                secret=secret,
            )

        new_steps: list[AgentInstructionStep] = []
        for step in self.steps:
            new_params = step.params
            if step.params:
                new_params = {
                    k: (
                        render_template_with_agent_context(
                            str(v), variables=variables, secret_name=secret_name, secret=secret
                        )
                        if isinstance(v, str)
                        else v
                    )
                    for k, v in step.params.items()
                }
            new_steps.append(
                AgentInstructionStep(
                    action=_rt(step.action) or step.action,
                    description=_rt(step.description) or step.description,
                    params=new_params,
                    required=step.required,
                )
            )
        new_prereq = (
            [_rt(p) or "" for p in self.prerequisites] if self.prerequisites is not None else None
        )
        return AgentInstructions(
            summary=_rt(self.summary) or self.summary,
            steps=new_steps,
            prerequisites=new_prereq,
            automation_hint=_rt(self.automation_hint),
            estimated_time=_rt(self.estimated_time),
            fallback=_rt(self.fallback),
            required_tools=(
                [_rt(t) or "" for t in self.required_tools]
                if self.required_tools is not None
                else None
            ),
            documentation_url=_rt(self.documentation_url),
        )


class AuthKind(str, Enum):
    """Authentication kind for providers."""

    AMBIENT = "ambient"
    TOKEN = "token"
    ASSUME_ROLE = "assume_role"
    STATIC = "static"
    DEFAULT = "default"
    SERVICE_PRINCIPAL = "service_principal"
    MANAGED_IDENTITY = "managed_identity"
    CLI = "cli"
    PROFILE = "profile"


class GeneratorKind(str, Enum):
    """Generator kind for secret values.

    This enum is intentionally *open*: unknown string values passed by
    third-party bundles are accepted at runtime via :meth:`_missing_`
    instead of raising a ``ValueError``.  Built-in kinds are enumerated
    below; bundle authors may declare any additional string as a kind.
    """

    STATIC = "static"
    AZURE_APP_REG = "azure_app_reg"
    ENTRA_AGENT_BLUEPRINT = "entra-agent-blueprint"
    RANDOM_PASSWORD = "random_password"
    RANDOM_STRING = "random_string"
    SCRIPT = "script"
    API = "api"
    PROVIDER_BACKED = "provider_backed"
    GITHUB_PAT = "github_pat"
    GITLAB_PROJECT_TOKEN = "gitlab_project_token"
    GITLAB_GROUP_TOKEN = "gitlab_group_token"
    GITLAB_GROUP_SERVICE_ACCOUNT = "gitlab_group_service_account"

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


class SecretSourceKind(str, Enum):
    """Non-human source kinds for resolving secret values."""

    FILE = "file"
    ENV = "env"
    SECRET_REF = "secret_ref"
    PROVIDER_READ = "provider_read"


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
    GITLAB_GROUP_VARIABLE = "gitlab_group_variable"
    GITLAB_SERVICE_ACCOUNT_MEMBER = "gitlab_service_account_member"
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
    TFVARS = "tfvars"


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
    identity_policies: list[str] = Field(
        default_factory=list,
        description=(
            "Optional names of root `policies` entries with `kind: provider_identity` to enforce "
            "when this target participates in sync (in addition to policies that already apply via "
            "`providers:` overlap)."
        ),
    )


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


class SecretSource(BaseModel):
    """Optional non-human source for resolving a secret value."""

    kind: SecretSourceKind
    required: bool = Field(
        default=True,
        description=(
            "If true, sync fails when the source cannot resolve. "
            "If false, generation flow is attempted as fallback."
        ),
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Source-specific configuration. "
            "file: {path, format? (dotenv|json|yaml|toml|tfvars), key?, encoding?}; "
            "env: {name, trim?}; "
            "secret_ref: {secret, field?}; "
            "provider_read: {provider, kind, read, field?, profile?, method?}."
        ),
    )

    @model_validator(mode="after")
    def _validate_source_config(self) -> SecretSource:
        """Validate known source config shapes."""
        cfg = self.config or {}

        def _require_non_empty_str(key: str) -> None:
            val = cfg.get(key)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"source.config.{key} must be a non-empty string")

        if self.kind == SecretSourceKind.FILE:
            _require_non_empty_str("path")
            if "format" in cfg and not isinstance(cfg.get("format"), str):
                raise ValueError("source.config.format must be a string when provided")
            if "key" in cfg and not isinstance(cfg.get("key"), str):
                raise ValueError("source.config.key must be a string when provided")
            if "encoding" in cfg and not isinstance(cfg.get("encoding"), str):
                raise ValueError("source.config.encoding must be a string when provided")

        elif self.kind == SecretSourceKind.ENV:
            _require_non_empty_str("name")
            if "trim" in cfg and not isinstance(cfg.get("trim"), bool):
                raise ValueError("source.config.trim must be a boolean when provided")

        elif self.kind == SecretSourceKind.SECRET_REF:
            _require_non_empty_str("secret")
            if "field" in cfg and not isinstance(cfg.get("field"), str):
                raise ValueError("source.config.field must be a string when provided")

        elif self.kind == SecretSourceKind.PROVIDER_READ:
            _require_non_empty_str("provider")
            _require_non_empty_str("kind")
            read_cfg = cfg.get("read")
            if not isinstance(read_cfg, dict):
                raise ValueError("source.config.read must be an object")
            if "field" in cfg and not isinstance(cfg.get("field"), str):
                raise ValueError("source.config.field must be a string when provided")
            if "profile" in cfg and not isinstance(cfg.get("profile"), str):
                raise ValueError("source.config.profile must be a string when provided")
            if "method" in cfg and not isinstance(cfg.get("method"), str):
                raise ValueError("source.config.method must be a string when provided")

        return self


class Secret(BaseModel):
    """Secret definition."""

    name: str
    kind: str
    vars: dict[str, Any] = Field(default_factory=dict)
    source: SecretSource | None = Field(
        default=None,
        description=(
            "Optional non-human source resolved before generator execution. "
            "When omitted, generation flow behaves as before."
        ),
    )
    config: dict[str, Any] = Field(default_factory=dict)
    one_time: bool = False
    rotation_period: str | None = None
    targets: list[TargetConfig] = Field(default_factory=list)
    agent_instructions: AgentInstructions | None = Field(
        default=None,
        description="Instructions for agents to obtain this secret",
    )
    process_tags: list[str] = Field(
        default_factory=list,
        description=(
            "Optional labels that associate this secret with execution flows / processes "
            "(e.g. auth_flow, payment_gateway) for graph tooling and policy filtering."
        ),
    )
    local: bool = Field(
        default=False,
        description=(
            "When true, sync state is stored in .gitsecrets.local.lock on this workstation "
            "instead of the shared .gitsecrets.lock. Supports variable interpolation "
            "(e.g. local: ${IS_LOCAL_ENV:-false})."
        ),
    )
    local_allow_cloud: bool = Field(
        default=False,
        description=(
            "When local is true, allow non-local cloud targets. Default false restricts "
            "local secrets to local/file or local/template targets only."
        ),
    )

    @field_validator("local", "local_allow_cloud", mode="before")
    @classmethod
    def _coerce_local_flags(cls, value: Any) -> bool:
        from secretzero.local_secrets import coerce_local_flag

        return coerce_local_flag(value)

    @model_validator(mode="after")
    def _validate_local_targets(self) -> Secret:
        from secretzero.local_secrets import validate_local_secret_targets

        validate_local_secret_targets(self)
        return self


class Metadata(BaseModel):
    """Metadata about the secrets configuration."""

    project: str | None = None
    owner: str | None = None
    environments: list[str] = Field(default_factory=list)
    compliance: list[str] = Field(default_factory=list)


class EnvironmentProfile(BaseModel):
    """Named environment lane configuration."""

    var_files: list[str] = Field(
        default_factory=list,
        description="Default .szvar files for this lane (later entries win).",
    )
    lockfile: str | None = Field(
        default=None,
        description="Default lockfile path for this lane.",
    )
    target_profile: str | None = Field(
        default=None,
        description="Optional target profile applied for this lane.",
    )
    labels: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional metadata labels for UI and automation.",
    )


class EnvironmentsConfig(BaseModel):
    """Top-level environment lane map."""

    default: str | None = Field(
        default=None,
        description="Default lane name used when no explicit environment is selected.",
    )
    profiles: dict[str, EnvironmentProfile] = Field(
        default_factory=dict,
        description="Named environment profiles keyed by lane name.",
    )


class TargetProfile(BaseModel):
    """Reusable target defaults/overrides applied by environment lane."""

    identity_policies: list[str] = Field(
        default_factory=list,
        description="Identity policies applied by default to lane targets.",
    )
    provider_overrides: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Provider alias keyed overrides merged into target config.",
    )
    target_overrides: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Target kind keyed overrides merged into target config.",
    )


class Secretfile(BaseModel):
    """Root configuration model for Secretfile.yml."""

    variables: dict[str, Any] = Field(default_factory=dict)
    metadata: Metadata | None = None
    environments: EnvironmentsConfig | None = Field(
        default=None,
        description="Optional multi-environment lane map with defaults for var files and lockfile.",
    )
    target_profiles: dict[str, TargetProfile] = Field(
        default_factory=dict,
        description="Reusable target defaults selected by environment profile.",
    )
    providers: dict[str, Provider] = Field(default_factory=dict)
    secrets: list[Secret] = Field(default_factory=list)
    templates: dict[str, Template] = Field(default_factory=dict)
    policies: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Optional policy definitions. Supported `kind` values include `rotation`, `compliance`, "
            "`access`, and `provider_identity` (restrict sync to matching provider authentication; "
            "see schema $defs ProviderIdentityPolicy)."
        ),
    )
    labels: dict[str, Any] = Field(default_factory=dict)
    annotations: dict[str, Any] = Field(default_factory=dict)
    config: AppConfig | None = Field(
        default=None,
        description="Optional centralized app config (LLM, discovery, output); overrides config.yml and defaults",
    )
    agent: AgentConfig | None = Field(
        default=None,
        description="Defaults for unified agent sync (CLI and API): mode and optional web UI port range",
    )

    def effective_agent_config(self) -> AgentConfig:
        """Return top-level agent settings with defaults when omitted."""
        return self.agent if self.agent is not None else AgentConfig()

    @model_validator(mode="after")
    def _validate_environment_references(self) -> Secretfile:
        """Validate environment and target-profile references."""
        if self.environments is None:
            return self

        profiles = self.environments.profiles or {}
        if self.environments.default and self.environments.default not in profiles:
            raise ValueError(
                f"environments.default '{self.environments.default}' is not defined in environments.profiles"
            )

        for env_name, profile in profiles.items():
            seen_var_files: set[str] = set()
            for var_file in profile.var_files:
                vf = var_file.strip()
                if not vf:
                    raise ValueError(f"Environment '{env_name}' contains an empty var_files entry")
                if vf in seen_var_files:
                    raise ValueError(
                        f"Environment '{env_name}' has duplicate var_files entry: {vf}"
                    )
                seen_var_files.add(vf)

            if profile.target_profile and profile.target_profile not in self.target_profiles:
                raise ValueError(
                    f"Environment '{env_name}' references unknown target_profile '{profile.target_profile}'"
                )

        policy_names = set((self.policies or {}).keys())
        for profile_name, tprof in (self.target_profiles or {}).items():
            for policy_name in tprof.identity_policies:
                if policy_name not in policy_names:
                    raise ValueError(
                        f"target_profiles.{profile_name}.identity_policies references unknown policy '{policy_name}'"
                    )

        return self
