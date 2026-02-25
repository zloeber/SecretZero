# Feature: Agent-Guided Secret Synchronization

## Overview

Enable AI agents to autonomously sync secrets from SecretZero Secretfiles by providing structured instructions when secrets require manual intervention or external acquisition. This transforms SecretZero into a "guiding post" for agents, enabling them to either follow instructions autonomously or coordinate with users/other agents to fulfill secret requirements.

## Problem Statement

When AI agents clone a project and attempt to sync secrets, they often encounter blockers:
- API keys requiring manual sign-up and generation
- OAuth flows requiring browser interaction
- Credentials requiring admin approval
- Service account keys requiring cloud console access

Currently, these scenarios fail silently or with generic error messages, leaving agents unable to proceed.

## Solution: Agent Instructions Framework

Add optional `agent_instructions` field to secret definitions that provide structured guidance for obtaining secrets. When running `secretzero agent sync`, the system returns actionable instructions instead of failing.

## Use Cases

### 1. Third-Party API Keys
```yaml
secrets:
  stripe_api_key:
    description: "Stripe API key for payment processing"
    generator: static
    agent_instructions:
      summary: "Sign up for Stripe and generate API key"
      steps:
        - action: "Visit https://dashboard.stripe.com/register"
          description: "Create a Stripe account"
        - action: "Navigate to Developers > API Keys"
          description: "Access API key management"
        - action: "Click 'Create secret key'"
          description: "Generate new secret key"
        - action: "Copy the key (starts with sk_)"
          description: "Save the key securely"
      automation_hint: "This requires browser interaction and cannot be fully automated"
      fallback: "Request user assistance for Stripe account creation"
```

### 2. OAuth Workflows
```yaml
secrets:
  github_oauth_token:
    description: "GitHub OAuth token for repository access"
    generator: script
    agent_instructions:
      summary: "Complete GitHub OAuth flow"
      steps:
        - action: "Use GitHub OAuth Device Flow"
          description: "https://docs.github.com/en/developers/apps/building-oauth-apps/authorizing-oauth-apps#device-flow"
        - action: "Request code: POST https://github.com/login/device/code"
          params: {client_id: "${GITHUB_CLIENT_ID}", scope: "repo"}
        - action: "Display user_code to user and open verification_uri"
          description: "User must approve in browser"
        - action: "Poll token endpoint until authorized"
          description: "POST https://github.com/login/oauth/access_token"
      automation_hint: "Agent can automate API calls, user must approve in browser"
      estimated_time: "2-5 minutes"
```

### 3. Cloud Service Accounts
```yaml
secrets:
  gcp_service_account_key:
    description: "GCP service account for Terraform"
    generator: static
    agent_instructions:
      summary: "Create GCP service account and download key"
      prerequisites:
        - "GCP project must exist"
        - "User must have 'Service Account Admin' role"
      steps:
        - action: "gcloud iam service-accounts create terraform-sa"
          description: "Create service account"
        - action: "gcloud projects add-iam-policy-binding PROJECT_ID --member='serviceAccount:terraform-sa@PROJECT_ID.iam.gserviceaccount.com' --role='roles/editor'"
          description: "Grant permissions"
        - action: "gcloud iam service-accounts keys create key.json --iam-account=terraform-sa@PROJECT_ID.iam.gserviceaccount.com"
          description: "Download JSON key"
      automation_hint: "Fully automatable via gcloud CLI if authenticated"
      required_tools: ["gcloud"]
```

## Implementation Plan

### Phase 1: Schema Extension

#### 1.1 Update Pydantic Models

**File**: `src/secretzero/models.py`

Add new models for agent instructions:

```python
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class AgentInstructionStep(BaseModel):
    """Single step in agent instruction workflow."""
    action: str = Field(description="Action to perform (CLI command, URL, or description)")
    description: str = Field(description="Human-readable context for the action")
    params: Optional[Dict[str, Any]] = Field(default=None, description="Optional parameters for API calls")
    required: bool = Field(default=True, description="Whether this step is required or optional")

class AgentInstructions(BaseModel):
    """Instructions for agents to obtain a secret."""
    summary: str = Field(description="Brief overview of the acquisition process")
    steps: List[AgentInstructionStep] = Field(description="Step-by-step instructions")
    prerequisites: Optional[List[str]] = Field(default=None, description="Requirements before starting")
    automation_hint: Optional[str] = Field(default=None, description="Guidance on automation feasibility")
    estimated_time: Optional[str] = Field(default=None, description="Expected time to complete")
    fallback: Optional[str] = Field(default=None, description="What to do if automation fails")
    required_tools: Optional[List[str]] = Field(default=None, description="CLI tools or dependencies needed")
    documentation_url: Optional[str] = Field(default=None, description="Link to official documentation")

class AutomationLevel(str, Enum):
    """Level of automation possible for secret acquisition."""
    FULLY_AUTOMATED = "fully_automated"  # Can be done by agent without intervention
    SEMI_AUTOMATED = "semi_automated"    # Agent can help, user input required
    MANUAL_ONLY = "manual_only"          # Requires full manual intervention
    REQUIRES_APPROVAL = "requires_approval"  # Needs admin/user approval
```

#### 1.2 Update Secret Configuration Model

**File**: `src/secretzero/models.py`

Add `agent_instructions` to `SecretConfig`:

```python
class SecretConfig(BaseModel):
    """Configuration for a single secret."""
    description: str = Field(description="Human-readable secret description")
    generator: str = Field(description="Generator type")
    generator_config: Optional[Dict[str, Any]] = Field(default=None)
    targets: List[TargetConfig] = Field(default_factory=list)
    rotation_policy: Optional[RotationPolicy] = Field(default=None)
    
    # New field
    agent_instructions: Optional[AgentInstructions] = Field(
        default=None,
        description="Instructions for agents to obtain this secret"
    )
```

#### 1.3 Update JSON Schema

**File**: `Secretfile.schema.json`

Add agent_instructions to the schema:

```json
{
  "properties": {
    "agent_instructions": {
      "type": "object",
      "description": "Instructions for AI agents to obtain this secret",
      "properties": {
        "summary": {
          "type": "string",
          "description": "Brief overview of acquisition process"
        },
        "steps": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "action": {"type": "string"},
              "description": {"type": "string"},
              "params": {"type": "object"},
              "required": {"type": "boolean", "default": true}
            },
            "required": ["action", "description"]
          }
        },
        "prerequisites": {
          "type": "array",
          "items": {"type": "string"}
        },
        "automation_hint": {"type": "string"},
        "estimated_time": {"type": "string"},
        "fallback": {"type": "string"},
        "required_tools": {
          "type": "array",
          "items": {"type": "string"}
        },
        "documentation_url": {"type": "string", "format": "uri"}
      },
      "required": ["summary", "steps"]
    }
  }
}
```

### Phase 2: Agent Sync Command

#### 2.1 Create Agent Module

**File**: `src/secretzero/agent.py`

```python
"""Agent-specific functionality for autonomous secret synchronization."""

from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel
from secretzero.models import AgentInstructions, AutomationLevel
from secretzero.config import Config
import logging

logger = logging.getLogger(__name__)

class AgentSyncResult(BaseModel):
    """Result of agent sync operation."""
    synced_secrets: List[str] = Field(default_factory=list, description="Successfully synced secrets")
    pending_secrets: Dict[str, AgentInstructions] = Field(
        default_factory=dict,
        description="Secrets requiring manual intervention with instructions"
    )
    failed_secrets: Dict[str, str] = Field(
        default_factory=dict,
        description="Secrets that failed to sync"
    )
    automation_summary: Dict[str, int] = Field(
        default_factory=dict,
        description="Count by automation level"
    )

class AgentSecretSynchronizer:
    """Synchronizer with agent-specific intelligence."""
    
    def __init__(self, config: Config, dry_run: bool = False):
        self.config = config
        self.dry_run = dry_run
    
    def sync(self) -> AgentSyncResult:
        """Perform agent-aware secret synchronization."""
        result = AgentSyncResult()
        
        for secret_name, secret_config in self.config.secrets.items():
            try:
                # Try to sync automatically
                if self._can_auto_sync(secret_config):
                    self._sync_secret(secret_name, secret_config)
                    result.synced_secrets.append(secret_name)
                else:
                    # Secret requires intervention
                    if secret_config.agent_instructions:
                        result.pending_secrets[secret_name] = secret_config.agent_instructions
                        logger.info(f"Secret '{secret_name}' requires manual intervention")
                    else:
                        result.failed_secrets[secret_name] = "No agent instructions provided"
                        
            except Exception as e:
                result.failed_secrets[secret_name] = str(e)
                logger.error(f"Failed to sync '{secret_name}': {e}")
        
        result.automation_summary = self._calculate_automation_summary(result)
        return result
    
    def _can_auto_sync(self, secret_config) -> bool:
        """Determine if secret can be automatically synced."""
        # Check if generator is static and requires input
        if secret_config.generator == "static":
            if not secret_config.generator_config or not secret_config.generator_config.get("value"):
                return False
        
        # Auto-generated secrets can be synced
        if secret_config.generator in ["random_password", "random_string", "uuid"]:
            return True
            
        return False
    
    def _sync_secret(self, secret_name: str, secret_config):
        """Perform actual secret synchronization."""
        # Use existing sync logic from sync.py
        from secretzero.sync import sync_secret
        sync_secret(secret_name, secret_config, dry_run=self.dry_run)
    
    def _calculate_automation_summary(self, result: AgentSyncResult) -> Dict[str, int]:
        """Calculate automation level statistics."""
        return {
            "fully_synced": len(result.synced_secrets),
            "requires_intervention": len(result.pending_secrets),
            "failed": len(result.failed_secrets)
        }

def detect_automation_level(secret_config) -> AutomationLevel:
    """Detect automation level for a secret based on its configuration."""
    if not secret_config.agent_instructions:
        # No instructions, assume fully automated if auto-generator
        if secret_config.generator in ["random_password", "random_string", "uuid"]:
            return AutomationLevel.FULLY_AUTOMATED
        return AutomationLevel.MANUAL_ONLY
    
    # Parse automation_hint if present
    hint = secret_config.agent_instructions.automation_hint
    if hint:
        if "fully automat" in hint.lower():
            return AutomationLevel.FULLY_AUTOMATED
        elif "cannot be" in hint.lower() or "manual" in hint.lower():
            return AutomationLevel.MANUAL_ONLY
        elif "approval" in hint.lower():
            return AutomationLevel.REQUIRES_APPROVAL
    
    return AutomationLevel.SEMI_AUTOMATED
```

#### 2.2 Add CLI Command

**File**: `src/secretzero/cli.py`

```python
@click.group()
def agent():
    """Agent-specific commands for autonomous operation."""
    pass

@agent.command()
@click.option('--config', '-c', type=click.Path(exists=True), default='Secretfile.yml',
              help='Path to Secretfile')
@click.option('--dry-run', is_flag=True, help='Preview without applying changes')
@click.option('--json', 'output_json', is_flag=True, help='Output results as JSON')
@click.option('--interactive', is_flag=True, help='Prompt for manual secrets interactively')
def sync(config: str, dry_run: bool, output_json: bool, interactive: bool):
    """Agent-aware secret synchronization with guided instructions.
    
    Automatically syncs secrets that can be generated, and provides
    structured instructions for secrets requiring manual intervention.
    """
    from secretzero.agent import AgentSecretSynchronizer
    from secretzero.config import load_config
    import json
    
    try:
        cfg = load_config(config)
        synchronizer = AgentSecretSynchronizer(cfg, dry_run=dry_run)
        result = synchronizer.sync()
        
        if output_json:
            click.echo(json.dumps(result.model_dump(), indent=2))
        else:
            _display_agent_sync_results(result, interactive)
            
    except Exception as e:
        logger.error(f"Agent sync failed: {e}")
        raise click.ClickException(str(e))

def _display_agent_sync_results(result, interactive: bool):
    """Display human-readable sync results with instructions."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.markdown import Markdown
    
    console = Console()
    
    # Synced secrets
    if result.synced_secrets:
        console.print(f"\n✅ Successfully synced {len(result.synced_secrets)} secrets:", style="green bold")
        for secret in result.synced_secrets:
            console.print(f"  • {secret}", style="green")
    
    # Pending secrets with instructions
    if result.pending_secrets:
        console.print(f"\n⏳ {len(result.pending_secrets)} secrets require manual intervention:", style="yellow bold")
        
        for secret_name, instructions in result.pending_secrets.items():
            console.print(f"\n[bold cyan]{secret_name}[/bold cyan]")
            console.print(f"  Summary: {instructions.summary}")
            
            if instructions.prerequisites:
                console.print("\n  Prerequisites:", style="yellow")
                for prereq in instructions.prerequisites:
                    console.print(f"    • {prereq}")
            
            console.print("\n  Steps:", style="blue bold")
            for i, step in enumerate(instructions.steps, 1):
                console.print(f"    {i}. {step.action}")
                console.print(f"       {step.description}", style="dim")
                if step.params:
                    console.print(f"       Params: {step.params}", style="italic")
            
            if instructions.automation_hint:
                console.print(f"\n  💡 Automation: {instructions.automation_hint}", style="italic")
            
            if instructions.estimated_time:
                console.print(f"  ⏱️  Estimated time: {instructions.estimated_time}", style="italic")
            
            if instructions.documentation_url:
                console.print(f"  📚 Docs: {instructions.documentation_url}", style="blue")
            
            if interactive:
                if click.confirm(f"\nHave you obtained the value for '{secret_name}'?"):
                    value = click.prompt("Enter the secret value", hide_input=True)
                    # Store the secret
                    console.print(f"✅ Stored {secret_name}", style="green")
    
    # Failed secrets
    if result.failed_secrets:
        console.print(f"\n❌ {len(result.failed_secrets)} secrets failed:", style="red bold")
        for secret, error in result.failed_secrets.items():
            console.print(f"  • {secret}: {error}", style="red")
    
    # Summary
    console.print(f"\n📊 Summary:", style="bold")
    console.print(f"  Synced: {result.automation_summary.get('fully_synced', 0)}")
    console.print(f"  Pending: {result.automation_summary.get('requires_intervention', 0)}")
    console.print(f"  Failed: {result.automation_summary.get('failed', 0)}")

# Add agent group to main CLI
cli.add_command(agent)
```

### Phase 3: Examples and Documentation

#### 3.1 Create Example Secretfile

**File**: `examples/agent-guided.yml`

```yaml
version: "1.0"

secrets:
  # Fully automated - no instructions needed
  database_password:
    description: "Auto-generated database password"
    generator: random_password
    generator_config:
      length: 32
    targets:
      - kind: file
        config:
          path: .env
          format: dotenv

  # Semi-automated - API can be called, requires user login
  github_token:
    description: "GitHub personal access token"
    generator: static
    agent_instructions:
      summary: "Generate GitHub Personal Access Token via OAuth Device Flow"
      prerequisites:
        - "GitHub account must exist"
        - "GITHUB_CLIENT_ID environment variable must be set"
      steps:
        - action: "curl -X POST https://github.com/login/device/code -d 'client_id=$GITHUB_CLIENT_ID&scope=repo,workflow'"
          description: "Request device code from GitHub"
        - action: "Display device_code to user and open verification_uri in browser"
          description: "User approves access at https://github.com/login/device"
        - action: "Poll https://github.com/login/oauth/access_token every 5 seconds"
          description: "Wait for user authorization (max 15 minutes)"
          params:
            grant_type: "urn:ietf:params:oauth:grant-type:device_code"
            device_code: "${DEVICE_CODE}"
            client_id: "${GITHUB_CLIENT_ID}"
      automation_hint: "Semi-automated: Agent calls APIs, user approves in browser"
      estimated_time: "2-5 minutes"
      documentation_url: "https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps#device-flow"
    targets:
      - kind: file
        config:
          path: .env

  # Manual only - requires third-party sign-up
  sendgrid_api_key:
    description: "SendGrid API key for email service"
    generator: static
    agent_instructions:
      summary: "Create SendGrid account and generate API key"
      steps:
        - action: "Visit https://signup.sendgrid.com"
          description: "Create a free SendGrid account"
        - action: "Verify email address"
          description: "Check inbox for verification email"
        - action: "Navigate to Settings > API Keys"
          description: "Access API key management dashboard"
        - action: "Click 'Create API Key', give it a name, select 'Full Access'"
          description: "Generate new API key with required permissions"
        - action: "Copy the API key (it starts with 'SG.')"
          description: "Save immediately - it won't be shown again"
      automation_hint: "Manual only: Requires browser interaction and email verification"
      estimated_time: "5-10 minutes"
      fallback: "Request user to complete SendGrid sign-up and provide API key"
      documentation_url: "https://docs.sendgrid.com/ui/account-and-settings/api-keys"
    targets:
      - kind: file
        config:
          path: .env

  # Requires tooling - can be automated if authenticated
  aws_access_key:
    description: "AWS access key for Terraform"
    generator: script
    generator_config:
      command: "aws iam create-access-key --user-name terraform-user --output json | jq -r '.AccessKey.AccessKeyId'"
    agent_instructions:
      summary: "Create AWS IAM access key via AWS CLI"
      prerequisites:
        - "AWS CLI must be installed and configured"
        - "User must have IAM permissions"
        - "IAM user 'terraform-user' must exist"
      steps:
        - action: "aws iam create-user --user-name terraform-user"
          description: "Create IAM user (if doesn't exist)"
        - action: "aws iam attach-user-policy --user-name terraform-user --policy-arn arn:aws:iam::aws:policy/AdministratorAccess"
          description: "Grant necessary permissions"
        - action: "aws iam create-access-key --user-name terraform-user"
          description: "Generate access key pair"
      automation_hint: "Fully automated if AWS CLI is authenticated"
      required_tools: ["aws", "jq"]
      documentation_url: "https://docs.aws.amazon.com/cli/latest/reference/iam/create-access-key.html"
    targets:
      - kind: file
        config:
          path: .env
```

#### 3.2 Documentation

**File**: `docs/user-guide/agent-sync.md`

```markdown
# Agent-Guided Secret Synchronization

SecretZero's agent sync feature enables AI agents and automation tools to autonomously manage secrets while gracefully handling scenarios that require manual intervention.

## Overview

When cloning a project with a Secretfile, agents can run:

```bash
secretzero agent sync
```

This intelligently:
- ✅ Auto-generates secrets that don't require external input
- 📋 Provides step-by-step instructions for secrets requiring manual acquisition
- 🔄 Handles mixed automation scenarios gracefully

## Use Cases

### 1. Autonomous Project Bootstrapping

An AI agent clones a new project and needs to set up all secrets:

```bash
# Agent runs this command
secretzero agent sync --json

# Gets structured output with:
# - Auto-synced secrets (database passwords, encryption keys)
# - Instructions for manual secrets (OAuth tokens, API keys)
```

### 2. CI/CD Integration

In CI/CD pipelines where some secrets exist and others need generation:

```bash
secretzero agent sync --dry-run  # Preview what will happen
secretzero agent sync            # Execute sync
```

### 3. Interactive Setup

For user-assisted setup with agent guidance:

```bash
secretzero agent sync --interactive
```

Agent provides instructions, user follows steps, agent continues.

## Agent Instructions Format

### Basic Structure

```yaml
secrets:
  my_secret:
    generator: static
    agent_instructions:
      summary: "Brief overview of acquisition process"
      steps:
        - action: "What to do"
          description: "Why to do it"
      automation_hint: "Can this be automated?"
```

### Full Example

```yaml
secrets:
  stripe_key:
    description: "Stripe API key"
    generator: static
    agent_instructions:
      summary: "Sign up for Stripe and generate API key"
      
      prerequisites:
        - "Valid email address"
        - "Business information ready"
      
      steps:
        - action: "Visit https://dashboard.stripe.com/register"
          description: "Create account with business email"
        - action: "Complete email verification"
          description: "Check inbox and verify email"
        - action: "Navigate to Developers > API Keys"
          description: "Access key management"
        - action: "Click 'Create secret key'"
          description: "Generate new secret key"
        - action: "Copy key starting with sk_"
          description: "Store securely - shown once"
      
      automation_hint: "Manual only - requires email verification and business info"
      estimated_time: "5-10 minutes"
      fallback: "Contact user to complete Stripe sign-up"
      documentation_url: "https://stripe.com/docs/keys"
```

## Automation Levels

SecretZero classifies secrets by automation feasibility:

### Fully Automated
Can be completed without any intervention:
- Random passwords
- UUID generation
- Key pair generation
- Secrets from authenticated CLIs

### Semi-Automated
Agent can automate parts, user input needed:
- OAuth device flows (agent polls, user approves)
- CLI commands requiring user credentials
- API calls requiring one-time setup

### Manual Only
Requires full manual intervention:
- Third-party service sign-ups
- Email verification flows
- Admin approval processes
- Browser-based configuration

### Requires Approval
Technical automation possible but blocked by policy:
- Cloud resource creation requiring approval
- Credential generation requiring manager approval
- Production environment access

## Output Formats

### Human-Readable (Default)

```bash
secretzero agent sync
```

```
✅ Successfully synced 3 secrets:
  • database_password
  • jwt_secret
  • encryption_key

⏳ 2 secrets require manual intervention:

stripe_api_key
  Summary: Sign up for Stripe and generate API key
  
  Steps:
    1. Visit https://dashboard.stripe.com/register
       Create account with business email
    2. Complete email verification
       Check inbox and verify email
    ...
  
  💡 Automation: Manual only - requires email verification
  ⏱️  Estimated time: 5-10 minutes
  📚 Docs: https://stripe.com/docs/keys
```

### JSON Output

```bash
secretzero agent sync --json
```

```json
{
  "synced_secrets": [
    "database_password",
    "jwt_secret"
  ],
  "pending_secrets": {
    "stripe_api_key": {
      "summary": "Sign up for Stripe and generate API key",
      "steps": [
        {
          "action": "Visit https://dashboard.stripe.com/register",
          "description": "Create account with business email",
          "required": true
        }
      ],
      "automation_hint": "Manual only - requires email verification",
      "estimated_time": "5-10 minutes"
    }
  },
  "failed_secrets": {},
  "automation_summary": {
    "fully_synced": 2,
    "requires_intervention": 1,
    "failed": 0
  }
}
```

## Best Practices

### Writing Agent Instructions

1. **Be Specific**: Provide exact URLs, commands, and parameters
2. **Include Context**: Explain why each step is needed
3. **Set Expectations**: Specify estimated time and complexity
4. **Provide Fallbacks**: What should agent do if automation fails
5. **Link Documentation**: Include official docs for reference

### For Fully Automatable Secrets

If a secret CAN be automated (e.g., via API), provide the exact commands:

```yaml
agent_instructions:
  steps:
    - action: "curl -X POST https://api.service.com/v1/keys -H 'Authorization: Bearer $TOKEN'"
      description: "Generate API key via REST API"
      params:
        name: "terraform-key"
        scopes: ["read", "write"]
```

### For Manual Secrets

Provide detailed step-by-step guidance:

```yaml
agent_instructions:
  steps:
    - action: "Open browser to https://console.service.com"
      description: "Access service web interface"
    - action: "Click 'Settings' → 'API Keys' → 'Generate New Key'"
      description: "Navigate to key generation interface"
```

### Handling Sensitive Prerequisites

Don't expose credentials in instructions:

```yaml
agent_instructions:
  prerequisites:
    - "AWS CLI must be authenticated (run 'aws configure')"
    - "User must have IAM permissions"
  # DON'T include actual credentials in yaml
```

## Integration with Other Tools

### GitHub Actions

```yaml
- name: Sync secrets
  run: |
    secretzero agent sync --json > sync_result.json
    # Parse JSON and handle pending secrets
```

### AI Agent Workflows

```python
import subprocess
import json

result = subprocess.run(
    ["secretzero", "agent", "sync", "--json"],
    capture_output=True,
    text=True
)
sync_data = json.loads(result.stdout)

# Auto-synced secrets are ready
for secret in sync_data["synced_secrets"]:
    print(f"✅ {secret} is ready")

# Pending secrets need attention
for secret_name, instructions in sync_data["pending_secrets"].items():
    print(f"⏳ {secret_name} needs manual work:")
    print(f"   {instructions['summary']}")
    
    # Agent decides: can it follow these instructions?
    if "fully automat" in instructions.get("automation_hint", ""):
        # Agent attempts to follow steps
        follow_instructions(instructions["steps"])
    else:
        # Delegate to user or another specialized agent
        delegate_to_user(secret_name, instructions)
```

## Future Enhancements

Planned improvements to agent sync:

1. **Interactive step execution**: Agent asks for confirmation after each step
2. **Parallel instruction following**: Execute multiple manual flows concurrently
3. **Instruction templates**: Reusable instruction sets for common services
4. **Credential store integration**: Auto-populate from 1Password, LastPass, etc.
5. **Multi-agent coordination**: Delegate different secrets to specialized agents

## See Also

- [Configuration Reference](../reference/configuration.md)
- [Generator Types](generators.md)
- [Target Types](targets.md)
- [CLI Reference](cli-reference.md)
```

### Phase 4: Testing

#### 4.1 Unit Tests

**File**: `tests/test_agent_sync.py`

```python
"""Tests for agent-guided secret synchronization."""

import pytest
from secretzero.agent import AgentSecretSynchronizer, AgentSyncResult, detect_automation_level
from secretzero.models import AgentInstructions, AgentInstructionStep, AutomationLevel, SecretConfig
from secretzero.config import Config

def test_agent_instructions_validation():
    """Test AgentInstructions model validation."""
    instructions = AgentInstructions(
        summary="Test instruction",
        steps=[
            AgentInstructionStep(
                action="Do something",
                description="Because reasons"
            )
        ]
    )
    assert instructions.summary == "Test instruction"
    assert len(instructions.steps) == 1

def test_detect_automation_level_fully_automated():
    """Test detection of fully automated secrets."""
    config = SecretConfig(
        description="Test",
        generator="random_password",
        targets=[]
    )
    level = detect_automation_level(config)
    assert level == AutomationLevel.FULLY_AUTOMATED

def test_detect_automation_level_manual():
    """Test detection of manual secrets."""
    config = SecretConfig(
        description="Test",
        generator="static",
        agent_instructions=AgentInstructions(
            summary="Manual process",
            steps=[],
            automation_hint="Manual only - requires browser"
        ),
        targets=[]
    )
    level = detect_automation_level(config)
    assert level == AutomationLevel.MANUAL_ONLY

def test_agent_sync_auto_secrets(tmp_path):
    """Test syncing fully automated secrets."""
    config = Config(
        version="1.0",
        secrets={
            "auto_pwd": SecretConfig(
                description="Auto password",
                generator="random_password",
                targets=[]
            )
        }
    )
    
    synchronizer = AgentSecretSynchronizer(config, dry_run=True)
    result = synchronizer.sync()
    
    assert "auto_pwd" in result.synced_secrets
    assert len(result.pending_secrets) == 0

def test_agent_sync_manual_secrets_with_instructions():
    """Test handling of manual secrets with agent instructions."""
    instructions = AgentInstructions(
        summary="Manual setup required",
        steps=[
            AgentInstructionStep(
                action="Visit website",
                description="Sign up for service"
            )
        ]
    )
    
    config = Config(
        version="1.0",
        secrets={
            "manual_key": SecretConfig(
                description="Manual API key",
                generator="static",
                agent_instructions=instructions,
                targets=[]
            )
        }
    )
    
    synchronizer = AgentSecretSynchronizer(config, dry_run=True)
    result = synchronizer.sync()
    
    assert "manual_key" in result.pending_secrets
    assert result.pending_secrets["manual_key"].summary == "Manual setup required"

def test_agent_sync_mixed_secrets():
    """Test sync with mix of auto and manual secrets."""
    config = Config(
        version="1.0",
        secrets={
            "auto1": SecretConfig(
                description="Auto",
                generator="random_password",
                targets=[]
            ),
            "manual1": SecretConfig(
                description="Manual",
                generator="static",
                agent_instructions=AgentInstructions(
                    summary="Manual",
                    steps=[]
                ),
                targets=[]
            ),
            "auto2": SecretConfig(
                description="Auto UUID",
                generator="uuid",
                targets=[]
            )
        }
    )
    
    synchronizer = AgentSecretSynchronizer(config, dry_run=True)
    result = synchronizer.sync()
    
    assert len(result.synced_secrets) == 2
    assert len(result.pending_secrets) == 1
    assert result.automation_summary["fully_synced"] == 2
    assert result.automation_summary["requires_intervention"] == 1

@pytest.mark.parametrize("hint,expected_level", [
    ("Fully automated via CLI", AutomationLevel.FULLY_AUTOMATED),
    ("Manual only - requires browser", AutomationLevel.MANUAL_ONLY),
    ("Requires admin approval", AutomationLevel.REQUIRES_APPROVAL),
    ("Semi-automated process", AutomationLevel.SEMI_AUTOMATED),
])
def test_automation_hint_parsing(hint, expected_level):
    """Test automation level detection from hints."""
    config = SecretConfig(
        description="Test",
        generator="static",
        agent_instructions=AgentInstructions(
            summary="Test",
            steps=[],
            automation_hint=hint
        ),
        targets=[]
    )
    level = detect_automation_level(config)
    assert level == expected_level
```

## Implementation Checklist

- [ ] Update `models.py` with new AgentInstructions models
- [ ] Update `Secretfile.schema.json` with agent_instructions
- [ ] Create `agent.py` module with synchronization logic
- [ ] Add `agent sync` command to CLI
- [ ] Add Rich console formatting for instructions
- [ ] Create example Secretfile with various instruction types
- [ ] Write comprehensive documentation
- [ ] Add unit tests for agent functionality
- [ ] Add integration tests with real workflows
- [ ] Update main README with agent sync feature
- [ ] Add to CHANGELOG in appropriate roadmap phase

## Benefits

1. **Agent Autonomy**: AI agents can make progress without getting blocked
2. **User Guidance**: Clear instructions when manual intervention needed
3. **Workflow Flexibility**: Mix automated and manual secret acquisition
4. **Documentation as Code**: Secret acquisition process is version-controlled
5. **Onboarding**: New developers/agents get step-by-step guidance
6. **Audit Trail**: Instructions are explicit and reviewable
7. **Future-Proof**: Foundation for more complex orchestration

## Migration Path

For existing projects:
1. `agent_instructions` is optional - existing Secretfiles work as-is
2. Add instructions incrementally to secrets that commonly cause issues
3. Start with high-value secrets (OAuth, cloud credentials, third-party APIs)
4. Templates can be shared across projects for common services

## Security Considerations

- **Never include credentials in instructions**: Use environment variable references
- **Avoid sensitive URLs**: Don't expose internal endpoints
- **Audit trail**: Log when agent instructions are used
- **Principle of least privilege**: Instructions should request minimal permissions
- **Time-bound credentials**: Prefer short-lived tokens when possible

---

## Questions for Implementation

1. Should agent_instructions support conditional steps (e.g., "if X then Y")?
2. Should we support instruction templates/imports to DRY common patterns?
3. How should agents signal back that they've completed manual steps?
4. Should there be a validation mode that checks if prerequisites are met?
5. Integration with secret scanning tools to verify obtained secrets?

## Related Features

- Rotation policies (instructions for rotating credentials)
- Compliance checks (validate obtained secrets meet policy)
- Drift detection (verify manual secrets haven't changed unexpectedly)
- Provider auto-discovery (detect available authentication methods)
