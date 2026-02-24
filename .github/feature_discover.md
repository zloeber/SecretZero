# Feature: AI-Powered Secret Discovery with LangGraph/LangChain

## Overview

Add a `secretzero discover` CLI subcommand that uses LangGraph or LangChain to invoke an AI agent for intelligent secret discovery across project codebases. The agent analyzes project structure, configuration files, and code patterns to automatically generate a `Secretfile.detect.yml` with recommended secret definitions, generators, and targets.

## Goals

- **Automated Discovery**: Leverage AI to identify secrets, credentials, and configuration in project files
- **Intelligent Recommendations**: Use agent reasoning to suggest appropriate generators and targets based on project structure
- **Configurable LLM Backend**: Support local (Ollama) and remote LLM providers with flexible configuration
- **Privacy-First**: Enable local-only secret analysis to prevent sensitive data exposure
- **Integration**: Seamlessly integrate with existing SecretZero workflow and schema validation

## Architecture

### High-Level Flow

```
┌──────────────────┐
│  CLI Invocation  │
│ secretzero       │
│   discover       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Load LLM Config  │
│ (secretzero.yml) │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Initialize      │
│  LangGraph/Chain │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Discovery Agent │
│  - Scan files    │
│  - Analyze code  │
│  - Reason about  │
│    patterns      │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Generate        │
│  Secretfile      │
│  .detect.yml     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Validate        │
│  Schema          │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Output Summary  │
│  - Secrets found │
│  - Confidence    │
│  - Next steps    │
└──────────────────┘
```

## Configuration System

### Configuration File: `secretzero.yml`

A new configuration file for SecretZero CLI settings, separate from `Secretfile.yml`.

**Configuration Loading Priority:**
1. Environment variable: `SECRETZERO_CONFIG` (absolute path)
2. Local project path: `./secretzero.yml`
3. User home directory: `~/.config/secretzero/secretzero.yml`

**Schema:**

```yaml
# secretzero.yml - SecretZero CLI configuration
version: "1.0"

# LLM provider configuration for AI-powered features
llm:
  # Default provider to use (ollama, openai, anthropic, azure_openai)
  default_provider: ollama
  
  # Provider-specific configurations
  providers:
    ollama:
      # Base URL for Ollama server
      base_url: "${OLLAMA_HOST:-http://localhost:11434}"
      
      # Model to use for general tasks
      model: "${OLLAMA_MODEL:-llama3.2:3b}"
      
      # Model for reasoning-intensive tasks (optional)
      reasoning_model: "${OLLAMA_REASONING_MODEL:-llama3.2:70b}"
      
      # Request timeout in seconds
      timeout: 120
      
      # Temperature for generation (0.0 - 1.0)
      temperature: 0.7
      
      # Maximum tokens to generate
      max_tokens: 4096
    
    openai:
      # API key (prefer env var: OPENAI_API_KEY)
      api_key: "${OPENAI_API_KEY}"
      
      # Model to use
      model: "gpt-4"
      
      # Organization ID (optional)
      organization: "${OPENAI_ORG_ID}"
      
      timeout: 120
      temperature: 0.7
      max_tokens: 4096
    
    anthropic:
      api_key: "${ANTHROPIC_API_KEY}"
      model: "claude-3-5-sonnet-20241022"
      timeout: 120
      temperature: 0.7
      max_tokens: 4096
    
    azure_openai:
      api_key: "${AZURE_OPENAI_API_KEY}"
      endpoint: "${AZURE_OPENAI_ENDPOINT}"
      deployment: "${AZURE_OPENAI_DEPLOYMENT}"
      api_version: "2024-02-15-preview"
      timeout: 120
      temperature: 0.7
      max_tokens: 4096

# Discovery-specific settings
discovery:
  # Enable/disable external script execution
  allow_script_execution: false
  
  # Confidence threshold for including secrets (0.0 - 1.0)
  confidence_threshold: 0.6
  
  # Maximum files to scan
  max_files: 1000
  
  # File patterns to scan (glob patterns)
  include_patterns:
    - "*.env*"
    - "*.yml"
    - "*.yaml"
    - "*.json"
    - "*.toml"
    - "*.tf"
    - "*.tfvars"
    - "**/.github/workflows/*.yml"
    - "**/k8s/**/*.yaml"
    - "**/kubernetes/**/*.yaml"
  
  # File patterns to exclude
  exclude_patterns:
    - "**/node_modules/**"
    - "**/venv/**"
    - "**/.venv/**"
    - "**/dist/**"
    - "**/build/**"
    - "**/.git/**"
    - "**/vendor/**"
  
  # Script URL for external secret detection (optional)
  script_url: "https://raw.githubusercontent.com/secretzero-dev/secretzero/main/scripts/discover-secrets.sh"

# Output preferences
output:
  # Default output format (text, json, yaml)
  format: text
  
  # Verbosity level (0-3)
  verbosity: 1
  
  # Color output
  color: true
```

### Configuration Loading Module

**New file:** `src/secretzero/cli_config.py`

```python
"""CLI configuration loading for SecretZero."""

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


class OllamaConfig(BaseModel):
    """Ollama provider configuration."""
    
    base_url: str = Field(default="http://localhost:11434")
    model: str = Field(default="llama3.2:3b")
    reasoning_model: str | None = None
    timeout: int = Field(default=120, gt=0)
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    max_tokens: int = Field(default=4096, gt=0)


class OpenAIConfig(BaseModel):
    """OpenAI provider configuration."""
    
    api_key: str
    model: str = Field(default="gpt-4")
    organization: str | None = None
    timeout: int = Field(default=120, gt=0)
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    max_tokens: int = Field(default=4096, gt=0)


class AnthropicConfig(BaseModel):
    """Anthropic provider configuration."""
    
    api_key: str
    model: str = Field(default="claude-3-5-sonnet-20241022")
    timeout: int = Field(default=120, gt=0)
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    max_tokens: int = Field(default=4096, gt=0)


class AzureOpenAIConfig(BaseModel):
    """Azure OpenAI provider configuration."""
    
    api_key: str
    endpoint: str
    deployment: str
    api_version: str = Field(default="2024-02-15-preview")
    timeout: int = Field(default=120, gt=0)
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    max_tokens: int = Field(default=4096, gt=0)


class LLMProviders(BaseModel):
    """LLM provider configurations."""
    
    ollama: OllamaConfig | None = None
    openai: OpenAIConfig | None = None
    anthropic: AnthropicConfig | None = None
    azure_openai: AzureOpenAIConfig | None = None


class LLMConfig(BaseModel):
    """LLM configuration for AI-powered features."""
    
    default_provider: str = Field(default="ollama")
    providers: LLMProviders = Field(default_factory=LLMProviders)
    
    @field_validator("default_provider")
    @classmethod
    def validate_default_provider(cls, v: str) -> str:
        """Validate default provider is a known type."""
        valid_providers = ["ollama", "openai", "anthropic", "azure_openai"]
        if v not in valid_providers:
            raise ValueError(
                f"Invalid provider: {v}. Must be one of {valid_providers}"
            )
        return v


class DiscoveryConfig(BaseModel):
    """Configuration for secret discovery."""
    
    allow_script_execution: bool = Field(default=False)
    confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    max_files: int = Field(default=1000, gt=0)
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
        ]
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
        ]
    )
    script_url: str = Field(
        default="https://raw.githubusercontent.com/secretzero-dev/secretzero/main/scripts/discover-secrets.sh"
    )


class OutputConfig(BaseModel):
    """Output preferences configuration."""
    
    format: str = Field(default="text")
    verbosity: int = Field(default=1, ge=0, le=3)
    color: bool = Field(default=True)


class CliConfig(BaseModel):
    """SecretZero CLI configuration."""
    
    version: str = Field(default="1.0")
    llm: LLMConfig = Field(default_factory=LLMConfig)
    discovery: DiscoveryConfig = Field(default_factory=DiscoveryConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)


class CliConfigLoader:
    """Load CLI configuration from multiple sources."""
    
    def __init__(self) -> None:
        """Initialize the config loader."""
        self._config: CliConfig | None = None
    
    def get_config_path(self) -> Path | None:
        """Determine the configuration file path.
        
        Priority:
        1. SECRETZERO_CONFIG environment variable
        2. ./secretzero.yml (local project)
        3. ~/.config/secretzero/secretzero.yml (user home)
        
        Returns:
            Path to config file, or None if not found
        """
        # 1. Check environment variable
        env_path = os.environ.get("SECRETZERO_CONFIG")
        if env_path:
            path = Path(env_path).expanduser().resolve()
            if path.exists():
                return path
        
        # 2. Check local project directory
        local_path = Path.cwd() / "secretzero.yml"
        if local_path.exists():
            return local_path
        
        # 3. Check user home directory
        home_path = Path.home() / ".config" / "secretzero" / "secretzero.yml"
        if home_path.exists():
            return home_path
        
        return None
    
    def load(self, config_path: Path | None = None) -> CliConfig:
        """Load CLI configuration.
        
        Args:
            config_path: Optional explicit path to config file
            
        Returns:
            CliConfig instance with loaded configuration
        """
        if self._config:
            return self._config
        
        # Use provided path or auto-detect
        path = config_path or self.get_config_path()
        
        if not path:
            # Return default configuration if no file found
            self._config = CliConfig()
            return self._config
        
        with open(path) as f:
            raw_data = yaml.safe_load(f)
        
        if not raw_data:
            self._config = CliConfig()
            return self._config
        
        # Interpolate environment variables in the config
        interpolated = self._interpolate_env_vars(raw_data)
        
        # Validate and load with Pydantic
        self._config = CliConfig(**interpolated)
        return self._config
    
    def _interpolate_env_vars(self, data: Any) -> Any:
        """Recursively interpolate environment variables.
        
        Supports ${VAR_NAME:-default} syntax.
        
        Args:
            data: Data structure to interpolate
            
        Returns:
            Data with environment variables interpolated
        """
        import re
        
        if isinstance(data, dict):
            return {
                key: self._interpolate_env_vars(value)
                for key, value in data.items()
            }
        elif isinstance(data, list):
            return [self._interpolate_env_vars(item) for item in data]
        elif isinstance(data, str):
            # Pattern: ${VAR_NAME:-default_value}
            def replace_env(match: Any) -> str:
                var_expr = match.group(1)
                if ":-" in var_expr:
                    var_name, default = var_expr.split(":-", 1)
                    return os.environ.get(var_name, default)
                else:
                    return os.environ.get(var_expr, match.group(0))
            
            return re.sub(r"\$\{([^}]+)\}", replace_env, data)
        return data
```

## CLI Implementation

### New Command: `secretzero discover`

**Location:** `src/secretzero/cli.py`

```python
@main.command()
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="Secretfile.detect.yml",
    help="Output file for detected secrets",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    help="Path to secretzero.yml config file",
)
@click.option(
    "--provider",
    type=click.Choice(["ollama", "openai", "anthropic", "azure_openai"]),
    help="Override default LLM provider",
)
@click.option(
    "--model",
    help="Override default LLM model",
)
@click.option(
    "--local-only",
    is_flag=True,
    default=False,
    help="Use only local models (equivalent to --provider ollama)",
)
@click.option(
    "--allow-scripts",
    is_flag=True,
    default=False,
    help="Allow execution of external detection scripts",
)
@click.option(
    "--confidence-threshold",
    type=float,
    default=0.6,
    help="Minimum confidence level for including secrets (0.0-1.0)",
)
@click.option(
    "--format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format for summary",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview discovery without writing files",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output",
)
def discover(
    output: str,
    config: str | None,
    provider: str | None,
    model: str | None,
    local_only: bool,
    allow_scripts: bool,
    confidence_threshold: float,
    format: str,
    dry_run: bool,
    verbose: bool,
) -> None:
    """Discover secrets in the project using AI analysis.
    
    This command uses LangGraph/LangChain to analyze your project structure,
    configuration files, and code patterns to automatically identify secrets
    and generate a Secretfile.detect.yml with recommended configurations.
    
    Examples:
    
        # Basic discovery with local Ollama model
        secretzero discover
        
        # Use OpenAI with specific model
        secretzero discover --provider openai --model gpt-4
        
        # Allow external script execution for enhanced detection
        secretzero discover --allow-scripts
        
        # Use only local models (privacy-first)
        secretzero discover --local-only
    """
    from secretzero.cli_config import CliConfigLoader
    from secretzero.discovery import DiscoveryAgent
    
    try:
        # Load CLI configuration
        cli_config_loader = CliConfigLoader()
        cli_config = cli_config_loader.load(
            Path(config) if config else None
        )
        
        # Override with command-line options
        if local_only:
            provider = "ollama"
        if provider:
            cli_config.llm.default_provider = provider
        if allow_scripts:
            cli_config.discovery.allow_script_execution = True
        if confidence_threshold:
            cli_config.discovery.confidence_threshold = confidence_threshold
        
        # Initialize discovery agent
        agent = DiscoveryAgent(
            config=cli_config,
            verbose=verbose,
            model_override=model,
        )
        
        # Confirm with user before proceeding
        if not dry_run:
            console.print(
                "\n[yellow]⚠ Warning:[/yellow] This command will scan your "
                "project for secrets and configuration."
            )
            
            if cli_config.llm.default_provider != "ollama":
                console.print(
                    f"[yellow]You are using '{cli_config.llm.default_provider}' "
                    "which may send data to external services.[/yellow]"
                )
                console.print(
                    "[green]Recommendation:[/green] Use --local-only flag "
                    "to keep all analysis local with Ollama."
                )
            
            if not click.confirm("\nProceed with secret discovery?", default=True):
                console.print("[yellow]Discovery cancelled.[/yellow]")
                sys.exit(0)
        
        # Run discovery
        console.print("\n[cyan]🔍 Starting secret discovery...[/cyan]\n")
        
        result = agent.discover(
            project_root=Path.cwd(),
            output_path=Path(output),
            dry_run=dry_run,
        )
        
        # Display summary
        if format == "json":
            console.print_json(data=result.to_dict())
        else:
            _display_discovery_summary(result)
        
        if not dry_run:
            console.print(f"\n[green]✓[/green] Detection complete!")
            console.print(f"[green]Generated:[/green] {output}")
            console.print(
                f"\n[cyan]Next steps:[/cyan]\n"
                f"  1. Review {output} for accuracy\n"
                f"  2. Validate: secretzero validate -f {output}\n"
                f"  3. Rename to Secretfile.yml when ready\n"
                f"  4. Run: secretzero sync\n"
            )
        
        sys.exit(EXIT_SUCCESS)
        
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(EXIT_CONFIG_ERROR)
    except Exception as e:
        console.print(f"[red]Error:[/red] Discovery failed: {e}")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        sys.exit(EXIT_UNKNOWN_ERROR)


def _display_discovery_summary(result: "DiscoveryResult") -> None:
    """Display a formatted summary of discovery results."""
    table = Table(title="Secret Discovery Summary", box=box.ROUNDED)
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")
    
    table.add_row("Secrets Discovered", str(result.total_secrets))
    table.add_row("High Confidence", str(result.high_confidence_count))
    table.add_row("Medium Confidence", str(result.medium_confidence_count))
    table.add_row("Low Confidence", str(result.low_confidence_count))
    table.add_row("Files Scanned", str(result.files_scanned))
    table.add_row("Execution Time", f"{result.duration_seconds:.2f}s")
    
    console.print(table)
    
    if result.warnings:
        console.print("\n[yellow]Warnings:[/yellow]")
        for warning in result.warnings:
            console.print(f"  • {warning}")
```

## LangGraph Agent Implementation

### New Module: `src/secretzero/discovery.py`

```python
"""AI-powered secret discovery using LangGraph."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import time

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_community.chat_models import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

from secretzero.cli_config import CliConfig
from secretzero.config import ConfigLoader
from secretzero.models import Secretfile


@dataclass
class DiscoveryResult:
    """Result of secret discovery operation."""
    
    total_secrets: int
    high_confidence_count: int
    medium_confidence_count: int
    low_confidence_count: int
    files_scanned: int
    duration_seconds: float
    warnings: list[str]
    secretfile_data: dict[str, Any]
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON output."""
        return {
            "total_secrets": self.total_secrets,
            "high_confidence": self.high_confidence_count,
            "medium_confidence": self.medium_confidence_count,
            "low_confidence": self.low_confidence_count,
            "files_scanned": self.files_scanned,
            "duration_seconds": self.duration_seconds,
            "warnings": self.warnings,
        }


@dataclass
class AgentState:
    """State for the discovery agent graph."""
    
    project_root: Path
    files: list[Path]
    scanned_content: dict[str, str]
    discovered_secrets: list[dict[str, Any]]
    confidence_scores: dict[str, float]
    recommendations: dict[str, Any]
    errors: list[str]
    current_step: str


class DiscoveryAgent:
    """AI-powered secret discovery agent using LangGraph."""
    
    def __init__(
        self,
        config: CliConfig,
        verbose: bool = False,
        model_override: str | None = None,
    ) -> None:
        """Initialize the discovery agent.
        
        Args:
            config: CLI configuration
            verbose: Enable verbose logging
            model_override: Override configured model
        """
        self.config = config
        self.verbose = verbose
        self.model_override = model_override
        
        # Initialize LLM based on configuration
        self.llm = self._init_llm()
        
        # Build the agent graph
        self.graph = self._build_graph()
    
    def _init_llm(self) -> Any:
        """Initialize the LLM based on configuration."""
        provider = self.config.llm.default_provider
        providers_config = self.config.llm.providers
        
        if provider == "ollama":
            ollama_config = providers_config.ollama or OllamaConfig()
            return ChatOllama(
                base_url=ollama_config.base_url,
                model=self.model_override or ollama_config.model,
                temperature=ollama_config.temperature,
                timeout=ollama_config.timeout,
            )
        
        elif provider == "openai":
            if not providers_config.openai:
                raise ValueError("OpenAI configuration not found")
            openai_config = providers_config.openai
            return ChatOpenAI(
                api_key=openai_config.api_key,
                model=self.model_override or openai_config.model,
                organization=openai_config.organization,
                temperature=openai_config.temperature,
                max_tokens=openai_config.max_tokens,
                timeout=openai_config.timeout,
            )
        
        elif provider == "anthropic":
            if not providers_config.anthropic:
                raise ValueError("Anthropic configuration not found")
            anthropic_config = providers_config.anthropic
            return ChatAnthropic(
                api_key=anthropic_config.api_key,
                model=self.model_override or anthropic_config.model,
                temperature=anthropic_config.temperature,
                max_tokens=anthropic_config.max_tokens,
                timeout=anthropic_config.timeout,
            )
        
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow for secret discovery."""
        workflow = StateGraph(AgentState)
        
        # Define nodes
        workflow.add_node("scan_files", self._scan_files)
        workflow.add_node("analyze_patterns", self._analyze_patterns)
        workflow.add_node("identify_secrets", self._identify_secrets)
        workflow.add_node("generate_recommendations", self._generate_recommendations)
        workflow.add_node("build_secretfile", self._build_secretfile)
        
        # Define edges
        workflow.set_entry_point("scan_files")
        workflow.add_edge("scan_files", "analyze_patterns")
        workflow.add_edge("analyze_patterns", "identify_secrets")
        workflow.add_edge("identify_secrets", "generate_recommendations")
        workflow.add_edge("generate_recommendations", "build_secretfile")
        workflow.add_edge("build_secretfile", END)
        
        return workflow.compile()
    
    def _scan_files(self, state: AgentState) -> AgentState:
        """Scan project files based on patterns."""
        # Implementation for file scanning
        # Uses glob patterns from config to find relevant files
        ...
        return state
    
    def _analyze_patterns(self, state: AgentState) -> AgentState:
        """Analyze file patterns using LLM."""
        # Use LLM to analyze file contents and identify potential secrets
        ...
        return state
    
    def _identify_secrets(self, state: AgentState) -> AgentState:
        """Identify specific secrets with confidence scores."""
        # Use LLM reasoning to identify and score secrets
        ...
        return state
    
    def _generate_recommendations(self, state: AgentState) -> AgentState:
        """Generate generator and target recommendations."""
        # Use LLM to recommend appropriate generators and targets
        ...
        return state
    
    def _build_secretfile(self, state: AgentState) -> AgentState:
        """Build the Secretfile.detect.yml structure."""
        # Construct valid Secretfile structure from discoveries
        ...
        return state
    
    def discover(
        self,
        project_root: Path,
        output_path: Path,
        dry_run: bool = False,
    ) -> DiscoveryResult:
        """Run the discovery process.
        
        Args:
            project_root: Root directory of the project
            output_path: Path to write Secretfile.detect.yml
            dry_run: Preview without writing files
            
        Returns:
            DiscoveryResult with summary and details
        """
        start_time = time.time()
        
        # Initialize state
        initial_state = AgentState(
            project_root=project_root,
            files=[],
            scanned_content={},
            discovered_secrets=[],
            confidence_scores={},
            recommendations={},
            errors=[],
            current_step="init",
        )
        
        # Run the graph
        final_state = self.graph.invoke(initial_state)
        
        # Build result
        duration = time.time() - start_time
        
        # Count confidence levels
        high = sum(1 for score in final_state.confidence_scores.values() if score >= 0.8)
        medium = sum(
            1 for score in final_state.confidence_scores.values() 
            if 0.6 <= score < 0.8
        )
        low = sum(1 for score in final_state.confidence_scores.values() if score < 0.6)
        
        result = DiscoveryResult(
            total_secrets=len(final_state.discovered_secrets),
            high_confidence_count=high,
            medium_confidence_count=medium,
            low_confidence_count=low,
            files_scanned=len(final_state.files),
            duration_seconds=duration,
            warnings=final_state.errors,
            secretfile_data=final_state.recommendations,
        )
        
        # Write output file if not dry run
        if not dry_run:
            self._write_secretfile(output_path, final_state.recommendations)
            self._validate_secretfile(output_path)
        
        return result
    
    def _write_secretfile(
        self,
        output_path: Path,
        secretfile_data: dict[str, Any],
    ) -> None:
        """Write the detected Secretfile to disk."""
        import yaml
        
        with open(output_path, "w") as f:
            yaml.safe_dump(
                secretfile_data,
                f,
                default_flow_style=False,
                sort_keys=False,
            )
    
    def _validate_secretfile(self, path: Path) -> None:
        """Validate generated Secretfile against schema."""
        loader = ConfigLoader()
        try:
            loader.load_file(path)
        except Exception as e:
            raise ValueError(f"Generated Secretfile is invalid: {e}")
```

## Dependencies

Add to `pyproject.toml`:

```toml
[project.optional-dependencies]
discovery = [
    "langgraph>=0.0.28",
    "langchain>=0.1.0",
    "langchain-community>=0.0.20",
    "langchain-openai>=0.0.5",
    "langchain-anthropic>=0.1.0",
]
```

## Testing Strategy

### Unit Tests

**New file:** `tests/test_discovery.py`

```python
"""Tests for AI-powered secret discovery."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from secretzero.cli_config import CliConfigLoader, CliConfig
from secretzero.discovery import DiscoveryAgent, DiscoveryResult


def test_cli_config_loading_priority(tmp_path):
    """Test configuration loading priority."""
    # Create config files in different locations
    local_config = tmp_path / "secretzero.yml"
    local_config.write_text("version: '1.0'\nllm:\n  default_provider: ollama")
    
    with patch.dict("os.environ", {"SECRETZERO_CONFIG": str(local_config)}):
        loader = CliConfigLoader()
        config_path = loader.get_config_path()
        assert config_path == local_config


def test_default_config_when_no_file():
    """Test that default config is returned when no file exists."""
    loader = CliConfigLoader()
    config = loader.load()
    
    assert config.llm.default_provider == "ollama"
    assert config.discovery.confidence_threshold == 0.6


def test_discovery_agent_initialization():
    """Test discovery agent initializes with config."""
    config = CliConfig()
    agent = DiscoveryAgent(config=config, verbose=False)
    
    assert agent.config == config
    assert agent.llm is not None


@pytest.mark.asyncio
async def test_discovery_workflow(tmp_path):
    """Test complete discovery workflow."""
    # Create test project structure
    project = tmp_path / "test_project"
    project.mkdir()
    
    env_file = project / ".env"
    env_file.write_text("DATABASE_URL=postgres://localhost/db\nAPI_KEY=secret123")
    
    # Run discovery
    config = CliConfig()
    agent = DiscoveryAgent(config=config)
    
    result = agent.discover(
        project_root=project,
        output_path=project / "Secretfile.detect.yml",
        dry_run=True,
    )
    
    assert result.total_secrets > 0
    assert result.files_scanned > 0


def test_confidence_scoring():
    """Test confidence scoring for discovered secrets."""
    config = CliConfig()
    agent = DiscoveryAgent(config=config)
    
    # Test high confidence detection (well-defined patterns)
    # Test medium confidence (ambiguous patterns)
    # Test low confidence (guesses)
    ...
```

### Integration Tests

**New file:** `tests/test_cli_discover.py`

```python
"""Integration tests for discover CLI command."""

import pytest
from click.testing import CliRunner
from pathlib import Path

from secretzero.cli import main


def test_discover_command_basic(tmp_path):
    """Test basic discover command execution."""
    runner = CliRunner()
    
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Create test files
        Path(".env").write_text("SECRET_KEY=test123")
        
        result = runner.invoke(
            main,
            ["discover", "--dry-run", "--local-only"],
            input="y\n"  # Confirm discovery
        )
        
        assert result.exit_code == 0
        assert "Starting secret discovery" in result.output


def test_discover_with_config_file(tmp_path):
    """Test discover with custom config file."""
    config_file = tmp_path / "secretzero.yml"
    config_file.write_text("""
version: '1.0'
llm:
  default_provider: ollama
  providers:
    ollama:
      model: llama3.2:3b
""")
    
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["discover", "--config", str(config_file), "--dry-run"],
        input="y\n"
    )
    
    assert result.exit_code == 0


def test_discover_json_output(tmp_path):
    """Test JSON output format."""
    runner = CliRunner()
    
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(
            main,
            ["discover", "--dry-run", "--format", "json"],
            input="y\n"
        )
        
        assert result.exit_code == 0
        # Output should be valid JSON
        import json
        json.loads(result.output)
```

## Documentation Updates

### User Guide

**New file:** `docs/user-guide/discovery.md`

```markdown
# AI-Powered Secret Discovery

SecretZero's `discover` command uses artificial intelligence to automatically
identify secrets in your project and generate a starter `Secretfile.yml`.

## Quick Start

```bash
# Basic discovery with local Ollama model
secretzero discover

# Use OpenAI for more accurate detection
secretzero discover --provider openai

# Privacy-first: ensure only local models are used
secretzero discover --local-only
```

## Configuration

Create a `secretzero.yml` file to configure discovery behavior...

[Full documentation content]
```

## Implementation Tasks

- [ ] Create `src/secretzero/cli_config.py` with configuration models
- [ ] Implement configuration loading with priority (env -> local -> home)
- [ ] Create `src/secretzero/discovery.py` with LangGraph agent
- [ ] Add `discover` command to CLI
- [ ] Implement file scanning with glob patterns
- [ ] Implement LLM-based pattern analysis
- [ ] Implement confidence scoring system
- [ ] Implement generator/target recommendation engine
- [ ] Add Secretfile generation and validation
- [ ] Create unit tests for config loading
- [ ] Create unit tests for discovery agent
- [ ] Create integration tests for CLI command
- [ ] Add documentation for configuration file
- [ ] Add user guide for discovery command
- [ ] Update dependencies in `pyproject.toml`
- [ ] Add example `secretzero.yml` to repository
- [ ] Update README with discovery feature

## Success Criteria

- [ ] `secretzero discover` command executes successfully
- [ ] Configuration loads from correct priority locations
- [ ] LangGraph agent correctly identifies secrets in test projects
- [ ] Generated `Secretfile.detect.yml` validates against schema
- [ ] Confidence scores accurately reflect detection quality
- [ ] Local-only mode works without external API calls
- [ ] All tests pass with >80% coverage
- [ ] Documentation is complete and accurate

## Future Enhancements

- Support for additional LLM providers (Gemini, Cohere)
- Interactive mode for reviewing/editing discoveries
- Integration with GitGuardian/Gitleaks for enhanced detection
- Machine learning model fine-tuning on user feedback
- Secret usage analysis (where secrets are used in code)
- Automatic rotation policy recommendations
- Integration with existing secret management tools

---

**Feature Status**: Specification Complete  
**Target Version**: 0.3.0  
**Priority**: Medium  
**Estimated Effort**: 3-4 weeks
