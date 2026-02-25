# Discover Command

Automatically discover secrets in your project using AI-powered analysis and generate a starter Secretfile.

## Overview

The `discover` command uses artificial intelligence to analyze your project structure, configuration files, and code patterns to automatically identify secrets, credentials, and sensitive configuration. This generates a `Secretfile.detect.yml` with recommended secret definitions, generators, and targets.

!!! info "Local-First Approach"
    **By default, all discovery analysis is completely local and does not send any data outside your environment.** AI assistance uses local models via Ollama. If you choose to use remote LLM providers, explicit configuration and command-line flags are required.

## Quick Start

```bash
# Discover secrets with default local analysis (Ollama required)
secretzero discover

# Confirm the discovery analysis (interactive)
# Output: Secretfile.detect.yml
```

## Prerequisites

For local AI-assisted discovery (recommended):
- [Ollama](https://ollama.ai) installed and running (`ollama serve`)
- At least one model downloaded (e.g., `ollama pull llama3.2:3b`)

For non-AI discovery (manual file scanning):
- No additional requirements

## Basic Usage

### Discover with Default Settings

```bash
secretzero discover
```

This command will:
1. ✅ Scan your project files locally
2. ✅ Analyze patterns using your local Ollama model
3. ✅ Identify potential secrets with confidence scores
4. ✅ Generate `Secretfile.detect.yml` with recommendations
5. ✅ Validate the output against Secretfile schema

**All processing is local - no data is sent externally.**

### Preview Discovery Without Saving

```bash
secretzero discover --dry-run
```

Shows what would be discovered without creating the output file.

### JSON Output Format

```bash
secretzero discover --format json
```

Returns structured JSON output suitable for parsing by other tools.

## Configuration

### Configuration File: `secretzero.yml`

Control discovery behavior through a `secretzero.yml` configuration file:

```yaml
version: "1.0"

# LLM provider configuration
llm:
  # Use local Ollama by default (no external calls)
  default_provider: ollama
  providers:
    ollama:
      # Local Ollama server (default is localhost:11434)
      base_url: "http://localhost:11434"
      
      # Model to use (must be downloaded locally)
      model: "llama3.2:3b"
      
      # Optional: larger model for reasoning tasks
      reasoning_model: "llama3.2:70b"
      
      # Settings
      temperature: 0.7
      timeout: 120
```

### Configuration Loading Priority

SecretZero looks for `secretzero.yml` in this order:

1. **Environment Variable**: `SECRETZERO_CONFIG` (takes precedence)
   ```bash
   export SECRETZERO_CONFIG=/path/to/secretzero.yml
   secretzero discover
   ```

2. **Local Project**: `./secretzero.yml`
   ```bash
   # Place in project root and run
   secretzero discover
   ```

3. **User Home**: `~/.config/secretzero/secretzero.yml`
   ```bash
   # Global defaults for your machine
   secretzero discover
   ```

## Command Options

### Model Selection

```bash
# Override the default model with a larger one
secretzero discover --model llama3.2:70b

# But remember: larger models are slower and require more resources
```

### Local-Only Mode (Recommended)

```bash
# Ensure only local models are used (default behavior)
secretzero discover --local-only
```

This flag explicitly prevents any remote API calls and is useful as a safety check.

### File Scanning Options

```bash
# Control which files to scan
secretzero discover --include-patterns "*.env*" "*.yml" "**/.github/workflows/*"

# Exclude sensitive directories
secretzero discover --exclude-patterns "**/node_modules/**" "**/.git/**"
```

### Confidence Threshold

```bash
# Only include secrets with 80%+ confidence
secretzero discover --confidence-threshold 0.8

# Be more permissive (60% confidence minimum)
secretzero discover --confidence-threshold 0.6
```

### Experimental: Optional External Script

```bash
# CAUTION: Only use if you trust the external script
# Downloads and runs detection script from GitHub (requires network)
secretzero discover --allow-scripts

# ⚠️  This downloads code from the internet - review before enabling
```

!!! warning "Script Execution Safety"
    The `--allow-scripts` flag is **disabled by default** for security. Only enable if you:
    - Understand what the script does
    - Trust the source (official SecretZero repository)
    - Are in a controlled environment

## Workflow

### Step 1: Discover Secrets

Run the discovery command:

```bash
$ secretzero discover

⚠ Warning: This command will scan your project for secrets and configuration.
You are using 'ollama' which keeps all analysis local.
Recommendation: Use --local-only flag to ensure local-only processing.

Proceed with secret discovery? [Y/n]: y

🔍 Starting secret discovery...

┌─────────────────────────────────────┐
│ Secret Discovery Summary            │
├──────────────────┬──────────────────┤
│ Metric           │ Value            │
├──────────────────┼──────────────────┤
│ Secrets Found    │ 8                │
│ High Confidence  │ 6                │
│ Medium Confidence│ 2                │
│ Low Confidence   │ 0                │
│ Files Scanned    │ 45               │
│ Duration         │ 12.34s           │
└──────────────────┴──────────────────┘

✓ Detection complete!
Generated: Secretfile.detect.yml

Next steps:
  1. Review Secretfile.detect.yml for accuracy
  2. Validate: secretzero validate -f Secretfile.detect.yml
  3. Rename to Secretfile.yml when ready
  4. Run: secretzero sync
```

### Step 2: Review the Generated File

```bash
cat Secretfile.detect.yml
```

Example output:

```yaml
version: "1.0"

metadata:
  project: my-app
  detected_at: "2024-02-24T10:30:00Z"
  confidence_summary:
    high: 6
    medium: 2
    low: 0

secrets:
  database_password:
    description: "Database password - detected in .env file"
    kind: random_password
    confidence: 0.95
    detected_in:
      - ".env"
      - "docker-compose.yml"
    config:
      length: 32
    targets:
      - kind: file
        config:
          path: .env
          format: dotenv
      - kind: file
        config:
          path: terraform/terraform.tfvars
  
  api_key:
    description: "API key for external service"
    kind: random_string
    confidence: 0.85
    detected_in:
      - ".env.example"
      - "config.yml"
    config:
      length: 64
    targets:
      - kind: file
        config:
          path: .env
          format: dotenv
```

### Step 3: Validate the Generated File

```bash
secretzero validate -f Secretfile.detect.yml

✓ Configuration is valid
✓ Found 8 secret(s)
✓ All targets are valid
```

### Step 4: Refine and Deploy

Edit the file as needed, then rename and deploy:

```bash
# Rename to active Secretfile
mv Secretfile.detect.yml Secretfile.yml

# Sync to targets
secretzero sync

# Review changes in lockfile
git diff .gitsecrets.lock
```

## Privacy & Security

### Local-First by Default

The discovery command respects your privacy:

- 🔒 **No data leaves your machine** when using local Ollama models
- 🔒 **No file contents are sent** to external services
- 🔒 **All analysis runs locally** on your hardware
- 🔒 **No telemetry** is collected

### When Using Remote Models

If you choose to use OpenAI, Anthropic, or other remote providers:

```bash
# This WILL send data to external APIs
secretzero discover --provider openai --model gpt-4
```

**Understand the implications:**
- Your project structure and file patterns are analyzed
- File contents may be sent to external services (depending on provider)
- Review the provider's privacy policy before use
- Consider using local models instead

### Recommended Setup

For maximum privacy and control:

```bash
# 1. Install Ollama
# https://ollama.ai

# 2. Start Ollama server
ollama serve

# 3. In another terminal, pull a model
ollama pull llama3.2:3b

# 4. Run discovery (all local)
secretzero discover --local-only
```

## Advanced Configuration

### Using a Larger Model

For more accurate discovery, use a larger model:

```bash
# Download larger model (requires 30GB+ disk space)
ollama pull llama3.2:70b

# Configure in secretzero.yml
echo 'version: "1.0"
llm:
  default_provider: ollama
  providers:
    ollama:
      model: "llama3.2:70b"' > secretzero.yml

# Run discovery
secretzero discover
```

### Remote Ollama Server

Connect to Ollama running on another machine:

```bash
# Configure remote server
echo 'version: "1.0"
llm:
  default_provider: ollama
  providers:
    ollama:
      base_url: "http://ollama-server.example.com:11434"
      model: "llama3.2:3b"' > secretzero.yml

# Run discovery
secretzero discover
```

### Custom File Patterns

Create `secretzero.yml`:

```yaml
version: "1.0"

discovery:
  # Files to include in scan
  include_patterns:
    - "*.env*"
    - "*.yml"
    - "*.yaml"
    - "*.json"
    - "*.tf"
    - "Dockerfile*"
    - "**/k8s/**/*.yaml"
    - "**/helm/**/*.yaml"
  
  # Directories to skip
  exclude_patterns:
    - "**/node_modules/**"
    - "**/venv/**"
    - "**/.venv/**"
    - "**/dist/**"
    - "**/.git/**"
```

## Examples

### Example 1: Discover in a Python Project

```bash
# Python project with .env and config files
$ secretzero discover

# Generated Secretfile.detect.yml will include:
# - DATABASE_URL (from .env)
# - API_KEYS (from config.py)
# - SECRET_KEY (from settings)
```

### Example 2: Discover in a Kubernetes Project

```bash
# Project with k8s manifests
$ secretzero discover

# Generated Secretfile.detect.yml will include:
# - Docker registry credentials
# - Database secrets
# - API tokens
# Recommended targets: kubernetes_secret
```

### Example 3: Multi-Environment Discovery

```bash
# Scan and generate for multiple environments
$ secretzero discover --output Secretfile.detect-dev.yml
$ SECRETZERO_CONFIG=prod-config.yml secretzero discover --output Secretfile.detect-prod.yml

# Review both files and merge as needed
```

## Troubleshooting

### "Failed to connect to Ollama"

```
Error: Could not connect to Ollama server at http://localhost:11434
```

**Solution:**
```bash
# Make sure Ollama is running
ollama serve

# Or connect to remote server
echo 'version: "1.0"
llm:
  providers:
    ollama:
      base_url: "http://remote-ollama:11434"' > secretzero.yml
```

### "Model not found"

```
Error: Model 'llama3.2:3b' not found
```

**Solution:**
```bash
# Download the model
ollama pull llama3.2:3b

# Check available models
ollama list
```

### Discovery is Very Slow

**For slow discovery:**
1. Use a smaller model: `ollama pull llama3.2:1b`
2. Use `--confidence-threshold 0.8` to skip lower-confidence items
3. Reduce files to scan with `--exclude-patterns`
4. Use a larger machine or remote Ollama server

### Discovered Secrets Seem Inaccurate

**To improve accuracy:**
1. Use a larger model: `ollama pull llama3.2:70b`
2. Review [`Secretfile.detect.yml`](#step-2-review-the-generated-file) for false positives
3. Update `secretzero.yml` to adjust `confidence_threshold`
4. Add comments to your code to help the AI understand context

## See Also

- [Creating Secretfiles](../../getting-started/first-project.md)
- [Validating Configuration](validate.md)
- [Secret Generators](../generators/index.md)
- [Target Configuration](../targets/index.md)
- [Best Practices](../best-practices.md)
