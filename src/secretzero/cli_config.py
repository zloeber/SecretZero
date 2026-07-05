"""CLI configuration models and loader for SecretZero.

Handles loading and validation of the ``secretzero.yml`` configuration file
that controls CLI behaviour, LLM provider settings, and discovery preferences.

Configuration loading priority:
1. ``SECRETZERO_CONFIG`` environment variable (absolute path)
2. ``./secretzero.yml`` (local project)
3. ``~/.config/secretzero/secretzero.yml`` (user home)

Centralized app config (LLM, discovery, output) resolution order:
  defaults ← ~/.config/secretzero/config.yml ← Secretfile ``config`` block.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# LLM provider configuration models
# ---------------------------------------------------------------------------


class OllamaConfig(BaseModel):
    """Configuration for a locally-hosted Ollama LLM server."""

    base_url: str = Field(
        default="http://localhost:11434",
        description="Base URL for the Ollama server",
    )
    model: str = Field(
        default="llama3.2:3b",
        description="Default model name for general tasks",
    )
    reasoning_model: str | None = Field(
        default=None,
        description="Model name for reasoning-intensive tasks (optional)",
    )
    timeout: int = Field(default=120, gt=0, description="Request timeout in seconds")
    temperature: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Generation temperature (0.0–1.0)"
    )
    max_tokens: int = Field(default=4096, gt=0, description="Maximum number of tokens to generate")


class OpenAIConfig(BaseModel):
    """Configuration for the OpenAI LLM provider."""

    api_key: str | None = Field(
        default=None,
        description="OpenAI API key (prefer OPENAI_API_KEY env var)",
    )
    model: str = Field(default="gpt-4o-mini", description="OpenAI model name")
    organization: str | None = Field(default=None, description="OpenAI organisation ID (optional)")
    timeout: int = Field(default=120, gt=0, description="Request timeout in seconds")
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    max_tokens: int = Field(default=4096, gt=0)


class AnthropicConfig(BaseModel):
    """Configuration for the Anthropic (Claude) LLM provider."""

    api_key: str | None = Field(
        default=None,
        description="Anthropic API key (prefer ANTHROPIC_API_KEY env var)",
    )
    model: str = Field(default="claude-3-5-sonnet-20241022", description="Anthropic model name")
    timeout: int = Field(default=120, gt=0, description="Request timeout in seconds")
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    max_tokens: int = Field(default=4096, gt=0)


class AzureOpenAIConfig(BaseModel):
    """Configuration for Azure-hosted OpenAI models."""

    api_key: str | None = Field(
        default=None,
        description="Azure OpenAI API key (prefer AZURE_OPENAI_API_KEY env var)",
    )
    endpoint: str | None = Field(
        default=None,
        description="Azure OpenAI endpoint URL (prefer AZURE_OPENAI_ENDPOINT env var)",
    )
    deployment: str | None = Field(
        default=None,
        description="Azure deployment name (prefer AZURE_OPENAI_DEPLOYMENT env var)",
    )
    api_version: str = Field(default="2024-02-15-preview", description="Azure OpenAI API version")
    timeout: int = Field(default=120, gt=0)
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    max_tokens: int = Field(default=4096, gt=0)


class LLMProviders(BaseModel):
    """Configures all available LLM provider backends."""

    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    anthropic: AnthropicConfig = Field(default_factory=AnthropicConfig)
    azure_openai: AzureOpenAIConfig = Field(default_factory=AzureOpenAIConfig)


class LLMConfig(BaseModel):
    """Top-level LLM configuration for AI-powered features."""

    default_provider: str = Field(
        default="ollama",
        description="Default LLM provider: ollama, openai, anthropic, azure_openai",
    )
    providers: LLMProviders = Field(default_factory=LLMProviders)


# ---------------------------------------------------------------------------
# Discovery configuration
# ---------------------------------------------------------------------------


class DiscoveryConfig(BaseModel):
    """Settings that control the AI-powered secret discovery process."""

    allow_script_execution: bool = Field(
        default=False,
        description="Enable/disable external script execution during discovery",
    )
    confidence_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score to include a secret in the output",
    )
    max_files: int = Field(default=1000, gt=0, description="Maximum number of files to scan")
    include_patterns: list[str] = Field(
        default_factory=lambda: [
            "*.env*",
            "*.yml",
            "*.yaml",
            "*.json",
            "*.toml",
            "*.tf",
            "*.tfvars",
            "**/.github/workflows/*.yml",
            "**/k8s/**/*.yaml",
            "**/kubernetes/**/*.yaml",
        ],
        description="Glob patterns for files to include in the scan",
    )
    exclude_patterns: list[str] = Field(
        default_factory=lambda: [
            "**/node_modules/**",
            "**/venv/**",
            "**/.venv/**",
            "**/.terraform/**",
            "**/dist/**",
            "**/build/**",
            "**/.git/**",
            "**/vendor/**",
        ],
        description="Glob patterns for files to exclude from the scan",
    )
    script_url: str | None = Field(
        default=None,
        description="URL for an external secret-detection script (optional)",
    )


# ---------------------------------------------------------------------------
# Output preferences
# ---------------------------------------------------------------------------


class OutputConfig(BaseModel):
    """Output formatting preferences."""

    format: str = Field(
        default="text",
        description="Default output format: text, json, yaml",
    )
    verbosity: int = Field(
        default=1,
        ge=0,
        le=3,
        description="Verbosity level (0 = quiet, 3 = very verbose)",
    )
    color: bool = Field(default=True, description="Enable colour output")


# ---------------------------------------------------------------------------
# MCP configuration
# ---------------------------------------------------------------------------


class McpConfig(BaseModel):
    """MCP host integration: client config generation and server tool defaults."""

    workspace: str | None = Field(
        default=None,
        description="Default repository root for MCP tools and generated client config",
    )
    client_format: str = Field(
        default="generic",
        description="Default host config shape: generic, cursor, or claude",
    )
    server_name: str = Field(
        default="secretzero",
        description="Server key in generated MCP host configuration",
    )
    sz_agent_mode: bool = Field(
        default=True,
        description="Include SZ_AGENT_MODE=true in generated client env",
    )
    command: str | None = Field(
        default=None,
        description="Override MCP server executable (default: secretzero on PATH)",
    )
    serve_args: list[str] = Field(
        default_factory=lambda: ["mcp", "serve"],
        description="Arguments for the MCP server command in generated host config",
    )
    discover_local_only: bool = Field(
        default=True,
        description="Default local-only mode for sz_discover / discover",
    )
    discover_provider: str | None = Field(
        default="ollama",
        description="Default LLM provider for sz_discover when not overridden",
    )


# ---------------------------------------------------------------------------
# App config block (Secretfile config key / config.yml)
# ---------------------------------------------------------------------------


class AppConfig(BaseModel):
    """Application config block: Secretfile root ``config`` key or ``~/.config/secretzero/config.yml``.

    Same shape as the mergeable app config (llm, discovery, output, mcp). Used for
    centralized configuration resolution: defaults ← config.yml ← Secretfile.config.
    """

    llm: LLMConfig = Field(default_factory=LLMConfig)
    discovery: DiscoveryConfig = Field(default_factory=DiscoveryConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    mcp: McpConfig = Field(default_factory=McpConfig)


# ---------------------------------------------------------------------------
# Top-level CLI config
# ---------------------------------------------------------------------------


class CliConfig(BaseModel):
    """Root configuration model for the SecretZero CLI (``secretzero.yml``)."""

    version: str = Field(default="1.0", description="Configuration file schema version")
    llm: LLMConfig = Field(default_factory=LLMConfig)
    discovery: DiscoveryConfig = Field(default_factory=DiscoveryConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    mcp: McpConfig = Field(default_factory=McpConfig)


# ---------------------------------------------------------------------------
# Configuration loader
# ---------------------------------------------------------------------------

_DEFAULT_PATHS: list[Path] = [
    Path("secretzero.yml"),
    Path.home() / ".config" / "secretzero" / "secretzero.yml",
]

# User-level app config (same shape as Secretfile ``config`` block).
DEFAULT_CONFIG_YML_PATH: Path = Path.home() / ".config" / "secretzero" / "config.yml"


def _deep_merge_dict(base: dict[str, Any], overlay: dict[str, Any]) -> None:
    """Merge overlay into base in place. Nested dicts are merged; other values are replaced."""
    for key, value in overlay.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge_dict(base[key], value)
        else:
            base[key] = value


@dataclass
class EffectiveConfigResult:
    """Result of resolving effective app config (defaults ← config.yml ← Secretfile.config)."""

    config: CliConfig
    sources: list[str]  # e.g. ["defaults", "config_yml", "secretfile"]


def get_effective_config(
    secretfile_path: Path | None = None,
    config_yml_path: Path | None = None,
) -> EffectiveConfigResult:
    """Resolve effective app config from defaults, config.yml, and optional Secretfile config block.

    Merge order: defaults ← config.yml ← Secretfile.config (later overrides earlier).

    Args:
        secretfile_path: Path to Secretfile.yml; if present and contains a ``config`` key, it is
            merged last (highest precedence).
        config_yml_path: Path to user config YAML; defaults to ``~/.config/secretzero/config.yml``
            if None.

    Returns:
        EffectiveConfigResult with merged CliConfig and list of source names applied.
    """
    sources: list[str] = ["defaults"]
    base = CliConfig().model_dump()
    config_yml = config_yml_path if config_yml_path is not None else DEFAULT_CONFIG_YML_PATH

    if config_yml.exists():
        try:
            raw = yaml.safe_load(config_yml.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and raw:
                raw = _expand_env_vars(raw)
                overlay = AppConfig(**raw).model_dump(exclude_none=True)
                _deep_merge_dict(base, overlay)
                sources.append("config_yml")
        except (yaml.YAMLError, ValueError):
            pass

    if secretfile_path is not None and secretfile_path.exists():
        try:
            raw = yaml.safe_load(secretfile_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and "config" in raw and isinstance(raw["config"], dict):
                raw_config = _expand_env_vars(raw["config"])
                overlay = AppConfig(**raw_config).model_dump(exclude_none=True)
                _deep_merge_dict(base, overlay)
                sources.append("secretfile")
        except (yaml.YAMLError, ValueError):
            pass

    return EffectiveConfigResult(config=CliConfig(**base), sources=sources)


def _expand_env_vars(value: Any) -> Any:  # noqa: ANN401
    """Recursively expand ``${VAR:-default}`` expressions in string values.

    Args:
        value: Scalar, list, or dict to process.

    Returns:
        Value with environment variable references resolved.
    """
    if isinstance(value, str):
        import re

        def _replace(match: re.Match) -> str:  # type: ignore[type-arg]
            var_name, _, default = match.group(1).partition(":-")
            return os.environ.get(var_name, default or "")

        return re.sub(r"\$\{([^}]+)\}", _replace, value)
    if isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env_vars(item) for item in value]
    return value


class CliConfigLoader:
    """Loads and validates :class:`CliConfig` from YAML files.

    Priority order:
    1. Path supplied via the ``SECRETZERO_CONFIG`` environment variable.
    2. ``./secretzero.yml`` in the current working directory.
    3. ``~/.config/secretzero/secretzero.yml`` in the user home directory.

    If no configuration file is found, a default :class:`CliConfig` is returned.
    """

    def load(self, config_path: str | Path | None = None) -> CliConfig:
        """Load the CLI configuration.

        Args:
            config_path: Explicit path to ``secretzero.yml``; overrides all
                other search paths when provided.

        Returns:
            Validated :class:`CliConfig` instance.

        Raises:
            ValueError: If the specified path does not exist or cannot be parsed.
        """
        path = self._resolve_path(config_path)
        if path is None:
            return CliConfig()

        raw = self._read_yaml(path)
        raw = _expand_env_vars(raw)
        return CliConfig(**raw)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_path(self, config_path: str | Path | None) -> Path | None:
        """Determine which configuration file to load.

        Args:
            config_path: Caller-supplied explicit path, or ``None`` to use
                the standard search order.

        Returns:
            Resolved :class:`Path` to use, or ``None`` if no file was found.

        Raises:
            ValueError: If the explicit path is supplied but does not exist.
        """
        if config_path is not None:
            p = Path(config_path)
            if not p.exists():
                raise ValueError(f"Configuration file not found: {p}")
            return p

        env_path = os.environ.get("SECRETZERO_CONFIG")
        if env_path:
            p = Path(env_path)
            if p.exists():
                return p

        for candidate in _DEFAULT_PATHS:
            if candidate.exists():
                return candidate

        return None

    def _read_yaml(self, path: Path) -> dict[str, Any]:
        """Read and parse a YAML configuration file.

        Args:
            path: Path to the YAML file.

        Returns:
            Parsed content as a dictionary.

        Raises:
            ValueError: If the file cannot be parsed as YAML.
        """
        try:
            content = path.read_text(encoding="utf-8")
            data = yaml.safe_load(content)
            if not isinstance(data, dict):
                raise ValueError(f"Expected a YAML mapping in {path}, got {type(data).__name__}")
            return data
        except yaml.YAMLError as exc:
            raise ValueError(f"Failed to parse YAML in {path}: {exc}") from exc
