"""CLI configuration models and loader for SecretZero.

Handles loading and validation of the ``secretzero.yml`` configuration file
that controls CLI behaviour, LLM provider settings, and discovery preferences.

Configuration loading priority:
1. ``SECRETZERO_CONFIG`` environment variable (absolute path)
2. ``./secretzero.yml`` (local project)
3. ``~/.config/secretzero/secretzero.yml`` (user home)
"""

import os
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
# Top-level CLI config
# ---------------------------------------------------------------------------


class CliConfig(BaseModel):
    """Root configuration model for the SecretZero CLI (``secretzero.yml``)."""

    version: str = Field(default="1.0", description="Configuration file schema version")
    llm: LLMConfig = Field(default_factory=LLMConfig)
    discovery: DiscoveryConfig = Field(default_factory=DiscoveryConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)


# ---------------------------------------------------------------------------
# Configuration loader
# ---------------------------------------------------------------------------

_DEFAULT_PATHS: list[Path] = [
    Path("secretzero.yml"),
    Path.home() / ".config" / "secretzero" / "secretzero.yml",
]


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
