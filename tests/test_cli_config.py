"""Tests for the CLI configuration module (cli_config.py)."""

import os
from pathlib import Path

import pytest
import yaml

from secretzero.cli_config import (
    AnthropicConfig,
    AzureOpenAIConfig,
    CliConfig,
    CliConfigLoader,
    DiscoveryConfig,
    LLMConfig,
    LLMProviders,
    OllamaConfig,
    OpenAIConfig,
    OutputConfig,
)

# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestOllamaConfig:
    """Tests for OllamaConfig model."""

    def test_defaults(self) -> None:
        cfg = OllamaConfig()
        assert cfg.base_url == "http://localhost:11434"
        assert cfg.model == "llama3.2:3b"
        assert cfg.reasoning_model is None
        assert cfg.timeout == 120
        assert cfg.temperature == 0.7
        assert cfg.max_tokens == 4096

    def test_custom_values(self) -> None:
        cfg = OllamaConfig(base_url="http://my-server:11434", model="mistral:7b", timeout=60)
        assert cfg.base_url == "http://my-server:11434"
        assert cfg.model == "mistral:7b"
        assert cfg.timeout == 60

    def test_temperature_bounds(self) -> None:
        with pytest.raises(Exception):
            OllamaConfig(temperature=1.5)
        with pytest.raises(Exception):
            OllamaConfig(temperature=-0.1)


class TestOpenAIConfig:
    def test_defaults(self) -> None:
        cfg = OpenAIConfig()
        assert cfg.api_key is None
        assert cfg.model == "gpt-4o-mini"
        assert cfg.organization is None

    def test_custom_api_key(self) -> None:
        cfg = OpenAIConfig(api_key="sk-test123", model="gpt-4")
        assert cfg.api_key == "sk-test123"
        assert cfg.model == "gpt-4"


class TestAnthropicConfig:
    def test_defaults(self) -> None:
        cfg = AnthropicConfig()
        assert cfg.api_key is None
        assert "claude" in cfg.model


class TestAzureOpenAIConfig:
    def test_defaults(self) -> None:
        cfg = AzureOpenAIConfig()
        assert cfg.api_key is None
        assert cfg.endpoint is None
        assert cfg.deployment is None
        assert "2024" in cfg.api_version


class TestLLMConfig:
    def test_defaults(self) -> None:
        cfg = LLMConfig()
        assert cfg.default_provider == "ollama"
        assert isinstance(cfg.providers, LLMProviders)

    def test_custom_provider(self) -> None:
        cfg = LLMConfig(default_provider="openai")
        assert cfg.default_provider == "openai"


class TestDiscoveryConfig:
    def test_defaults(self) -> None:
        cfg = DiscoveryConfig()
        assert cfg.allow_script_execution is False
        assert cfg.confidence_threshold == 0.6
        assert cfg.max_files == 1000
        assert len(cfg.include_patterns) > 0
        assert len(cfg.exclude_patterns) > 0
        assert "*.env*" in cfg.include_patterns
        assert "**/node_modules/**" in cfg.exclude_patterns

    def test_confidence_bounds(self) -> None:
        with pytest.raises(Exception):
            DiscoveryConfig(confidence_threshold=1.5)
        with pytest.raises(Exception):
            DiscoveryConfig(confidence_threshold=-0.1)


class TestOutputConfig:
    def test_defaults(self) -> None:
        cfg = OutputConfig()
        assert cfg.format == "text"
        assert cfg.verbosity == 1
        assert cfg.color is True


class TestCliConfig:
    def test_defaults(self) -> None:
        cfg = CliConfig()
        assert cfg.version == "1.0"
        assert isinstance(cfg.llm, LLMConfig)
        assert isinstance(cfg.discovery, DiscoveryConfig)
        assert isinstance(cfg.output, OutputConfig)

    def test_nested_access(self) -> None:
        cfg = CliConfig()
        assert cfg.llm.providers.ollama.model == "llama3.2:3b"
        assert cfg.discovery.confidence_threshold == 0.6


# ---------------------------------------------------------------------------
# CliConfigLoader
# ---------------------------------------------------------------------------


class TestCliConfigLoader:
    def test_returns_default_when_no_file_found(self, tmp_path: Path) -> None:
        """Loader should return default CliConfig when no file exists."""
        loader = CliConfigLoader()
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            cfg = loader.load()
        finally:
            os.chdir(original_cwd)
        assert isinstance(cfg, CliConfig)
        assert cfg.llm.default_provider == "ollama"

    def test_raises_when_explicit_path_missing(self) -> None:
        loader = CliConfigLoader()
        with pytest.raises(ValueError, match="not found"):
            loader.load(config_path="/nonexistent/secretzero.yml")

    def test_loads_local_config(self, tmp_path: Path) -> None:
        config_file = tmp_path / "secretzero.yml"
        config_file.write_text(
            yaml.dump(
                {
                    "version": "1.0",
                    "llm": {"default_provider": "openai"},
                }
            )
        )
        loader = CliConfigLoader()
        cfg = loader.load(config_path=config_file)
        assert cfg.llm.default_provider == "openai"

    def test_loads_explicit_path(self, tmp_path: Path) -> None:
        config_file = tmp_path / "myconfig.yml"
        config_file.write_text(
            yaml.dump(
                {
                    "version": "1.0",
                    "llm": {"default_provider": "anthropic"},
                    "discovery": {"confidence_threshold": 0.8},
                }
            )
        )
        loader = CliConfigLoader()
        cfg = loader.load(config_path=str(config_file))
        assert cfg.llm.default_provider == "anthropic"
        assert cfg.discovery.confidence_threshold == 0.8

    def test_env_var_override(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        config_file = tmp_path / "secretzero.yml"
        config_file.write_text(
            yaml.dump({"version": "1.0", "llm": {"default_provider": "anthropic"}})
        )
        monkeypatch.setenv("SECRETZERO_CONFIG", str(config_file))
        loader = CliConfigLoader()
        cfg = loader.load()
        assert cfg.llm.default_provider == "anthropic"

    def test_expands_env_vars_in_yaml(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TEST_OLLAMA_MODEL", "deepseek-r1:7b")
        config_file = tmp_path / "secretzero.yml"
        config_file.write_text(
            "version: '1.0'\n"
            "llm:\n"
            "  providers:\n"
            "    ollama:\n"
            "      model: '${TEST_OLLAMA_MODEL:-llama3.2:3b}'\n"
        )
        loader = CliConfigLoader()
        cfg = loader.load(config_path=config_file)
        assert cfg.llm.providers.ollama.model == "deepseek-r1:7b"

    def test_expands_env_vars_default_fallback(self, tmp_path: Path) -> None:
        config_file = tmp_path / "secretzero.yml"
        config_file.write_text(
            "version: '1.0'\n"
            "llm:\n"
            "  providers:\n"
            "    ollama:\n"
            "      model: '${UNSET_VAR:-fallback-model}'\n"
        )
        loader = CliConfigLoader()
        cfg = loader.load(config_path=config_file)
        assert cfg.llm.providers.ollama.model == "fallback-model"

    def test_invalid_yaml_raises(self, tmp_path: Path) -> None:
        config_file = tmp_path / "secretzero.yml"
        config_file.write_text("not: valid: yaml: [")
        loader = CliConfigLoader()
        with pytest.raises(ValueError, match="Failed to parse YAML"):
            loader.load(config_path=config_file)

    def test_non_mapping_yaml_raises(self, tmp_path: Path) -> None:
        config_file = tmp_path / "secretzero.yml"
        config_file.write_text("- item1\n- item2\n")
        loader = CliConfigLoader()
        with pytest.raises(ValueError, match="Expected a YAML mapping"):
            loader.load(config_path=config_file)

    def test_cwd_discovery(self, tmp_path: Path) -> None:
        """Loader should find ./secretzero.yml in the CWD."""
        config_file = tmp_path / "secretzero.yml"
        config_file.write_text(yaml.dump({"version": "1.0", "output": {"verbosity": 3}}))
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            loader = CliConfigLoader()
            cfg = loader.load()
            assert cfg.output.verbosity == 3
        finally:
            os.chdir(original_cwd)
