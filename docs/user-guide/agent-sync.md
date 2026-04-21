# Agent-Guided Secret Synchronisation

SecretZero's agent sync feature enables AI agents and automation tools to
autonomously manage secrets while gracefully handling scenarios that require
manual intervention.

## Overview

When an AI agent clones a project with a Secretfile, it can run:

```bash
secretzero agent sync
```

This intelligently:

- ✅ Auto-generates secrets that require no external input (random passwords, UUIDs, etc.)
- 📋 Provides step-by-step instructions for secrets that require manual acquisition
- 🔄 Handles mixed automation scenarios gracefully

## Quick Start

```bash
# Human-readable output (default)
secretzero agent sync

# Machine-readable JSON for further processing
secretzero agent sync --json

# Preview changes without applying them
secretzero agent sync --dry-run

# Sync without pre-sync lockfile target refresh
secretzero agent sync --no-refresh

# Interactively supply values for pending secrets
secretzero agent sync --interactive
```

By default, `agent sync` performs an automatic lockfile target refresh immediately
before sync. In dry-run mode this only reports mismatches; in non-dry-run mode
stale lockfile target entries are pruned before synchronization.

## Use Cases

### 1. Autonomous Project Bootstrapping

An AI agent clones a new project and sets up all secrets automatically:

```bash
# Agent runs this and processes the structured output
secretzero agent sync --json
```

The agent receives:

- Auto-synced secrets (database passwords, encryption keys)
- Structured instructions for manual secrets (OAuth tokens, API keys)

### 2. CI/CD Pipeline Integration

```yaml
# .github/workflows/setup.yml
- name: Sync auto-generated secrets
  run: secretzero agent sync --json > sync_result.json

- name: Process results
  run: |
    python - <<'EOF'
    import json
    result = json.load(open("sync_result.json"))
    for name, instructions in result["pending_secrets"].items():
        print(f"Manual action required for: {name}")
        print(f"  {instructions['summary']}")
    EOF
```

### 3. Interactive Setup

For user-assisted setup with agent guidance:

```bash
secretzero agent sync --interactive
```

The agent provides instructions, the user follows the steps, and the agent records the value.

### 4. Entra Agent ID Blueprint Workflows

For `kind: entra-agent-blueprint`, use the same flow with provider auth:

```bash
secretzero agent sync --json
secretzero agent sync --web
```

This supports:
- Blueprint create/update with `@odata.type: microsoft.graph.agentIdentityBlueprint`
- Credential reconciliation (client secrets, federated credentials, certificates)
- Child `agentIdentity` creation
- Sponsor/manual approval fallback through secure local web UI

## Defining Agent Instructions

Add `agent_instructions` to any secret in your Secretfile:

```yaml
secrets:
  - name: stripe_api_key
    kind: static
    config: {}
    agent_instructions:
      summary: "Sign up for Stripe and generate API key"
      steps:
        - action: "Visit https://dashboard.stripe.com/register"
          description: "Create a Stripe account"
        - action: "Navigate to Developers > API Keys"
          description: "Access API key management"
        - action: "Click 'Create secret key'"
          description: "Generate a new secret key"
        - action: "Copy the key (starts with sk_)"
          description: "Save securely – shown only once"
      automation_hint: "Manual only – requires email verification and business info"
      estimated_time: "5-10 minutes"
      fallback: "Request user assistance for Stripe account creation"
      documentation_url: "https://stripe.com/docs/keys"
```

### Field Reference

| Field | Required | Description |
|-------|----------|-------------|
| `summary` | ✅ | Brief overview of the acquisition process |
| `steps` | ✅ | Ordered list of steps to follow |
| `prerequisites` | ❌ | Requirements before starting |
| `automation_hint` | ❌ | Guidance on automation feasibility |
| `estimated_time` | ❌ | Expected time to complete |
| `fallback` | ❌ | What to do if automation fails |
| `required_tools` | ❌ | CLI tools or dependencies needed |
| `documentation_url` | ❌ | Link to official documentation |

Each step has the following fields:

| Field | Required | Description |
|-------|----------|-------------|
| `action` | ✅ | CLI command, URL, or description of what to do |
| `description` | ✅ | Human-readable context explaining why |
| `params` | ❌ | Optional key-value parameters for API calls |
| `required` | ❌ | Whether the step is mandatory (default: `true`) |

## Automation Levels

SecretZero classifies secrets by automation feasibility using the
`automation_hint` field and the generator type:

### Fully Automated

Can be completed without any human intervention:

- `random_password` and `random_string` generators
- Secrets sourced from authenticated CLIs when `automation_hint` contains
  `"fully automat"`

### Semi-Automated

The agent can automate parts, but user input is needed:

- OAuth Device Flows (agent polls, user approves in browser)
- When `automation_hint` does not match fully-automated or manual-only patterns

### Manual Only

Requires full manual intervention:

- Third-party service sign-ups
- Email verification flows
- `automation_hint` contains `"manual only"` or `"manual"`

### Requires Approval

Technically automatable but blocked by policy:

- `automation_hint` contains `"approval"`

## Output Formats

### Human-Readable (default)

```
✅ Successfully synced 2 secret(s):
  • database_password
  • jwt_secret

⏳ 1 secret(s) require manual intervention:

──────────────── stripe_api_key ────────────────
  Summary: Sign up for Stripe and generate API key

  Steps:
    1. Visit https://dashboard.stripe.com/register
       Create a Stripe account
    2. Navigate to Developers > API Keys
       Access API key management
    ...

  💡 Automation: Manual only – requires email verification
  ⏱️  Estimated time: 5-10 minutes
  📚 Docs: https://stripe.com/docs/keys

📊 Summary:
  Synced:   2
  Pending:  1
  Failed:   0
```

### JSON Output

```bash
secretzero agent sync --json
```

```json
{
  "synced_secrets": ["database_password", "jwt_secret"],
  "pending_secrets": {
    "stripe_api_key": {
      "summary": "Sign up for Stripe and generate API key",
      "steps": [
        {
          "action": "Visit https://dashboard.stripe.com/register",
          "description": "Create a Stripe account",
          "required": true
        }
      ],
      "automation_hint": "Manual only – requires email verification",
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

## Integrating with AI Agent Workflows

```python
import subprocess
import json

result = subprocess.run(
    ["secretzero", "agent", "sync", "--json"],
    capture_output=True,
    text=True,
)
sync_data = json.loads(result.stdout)

# Auto-synced secrets are ready to use
for secret in sync_data["synced_secrets"]:
    print(f"✅ {secret} is ready")

# Decide how to handle pending secrets
for name, instructions in sync_data["pending_secrets"].items():
    hint = instructions.get("automation_hint", "")
    if "fully automat" in hint.lower():
        follow_instructions(instructions["steps"])
    else:
        delegate_to_user(name, instructions)
```

## Best Practices

### Writing Effective Agent Instructions

1. **Be specific**: Provide exact URLs, commands, and parameters.
2. **Provide context**: Explain *why* each step is needed, not just *what* to do.
3. **Set realistic expectations**: Include `estimated_time` and complexity hints.
4. **Provide fallbacks**: Specify what the agent should do if automation fails.
5. **Link to documentation**: Include `documentation_url` for official references.

### For Fully Automatable Secrets

If a secret *can* be created via an API, provide the exact commands:

```yaml
agent_instructions:
  steps:
    - action: "curl -X POST https://api.example.com/v1/keys -H 'Authorization: Bearer $TOKEN'"
      description: "Generate API key via REST API"
      params:
        name: "terraform-key"
        scopes: ["read", "write"]
  automation_hint: "Fully automated if TOKEN is set"
```

### For Manual Secrets

Provide detailed, step-by-step browser guidance:

```yaml
agent_instructions:
  steps:
    - action: "Open browser to https://console.example.com"
      description: "Access the service web interface"
    - action: "Click Settings → API Keys → Generate New Key"
      description: "Navigate to the key generation interface"
  automation_hint: "Manual only – requires browser interaction"
```

### Keeping Secrets Safe

Never include actual credentials in `agent_instructions`. Reference environment
variables or placeholder names instead:

```yaml
# ✅ Correct
prerequisites:
  - "AWS CLI must be authenticated (run 'aws configure')"

# ❌ Wrong – exposes credentials
prerequisites:
  - "Set AWS_SECRET_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE"
```

## See Also

- [Configuration Reference](configuration/index.md)
- [Generator Types](generators/index.md)
- [Target Types](targets/index.md)
- [CLI Reference](cli/index.md)

## Tavern API Workflow Scenarios

The end-to-end Tavern suite now includes workflow-focused API scenarios beyond the
core three vectors. These scenarios are designed as usage playbooks and contract
tests for common operator workflows.

### Credential Rotation Workflow

Validates forced rotation through the API for a single secret and confirms status
metadata reflects the rotation.

```mermaid
flowchart LR
  A[POST /sync secret_name force] --> B[Seed secret in target]
  B --> C[POST /rotation/execute secret_name force]
  C --> D[GET /secrets/{name}/status]
  D --> E[rotation_count incremented]
```

### Multiple Target Environments via `.szvar`

Verifies the API can load `var_files` to render environment-specific target paths
from the same Secretfile.

```mermaid
flowchart LR
  A[POST /sync with dev.szvar] --> B[e2e-dev.env written]
  B --> C[POST /sync with prod.szvar]
  C --> D[e2e-prod.env written]
```

### Single-Target Forced Rotation

Confirms one secret can be explicitly forced to rotate without rotating all secrets.

```mermaid
flowchart LR
  A[POST /rotation/execute] --> B[secret_name=rotatable_password]
  B --> C[force=true]
  C --> D[Only requested secret appears in rotated list]
```

### Cross-Target Sync Update

Ensures one generated value is propagated to multiple targets in the same sync run.

```mermaid
flowchart LR
  A[POST /sync secret_name=cross_target_shared force=true] --> B[Generate shared value]
  B --> C[Write target A file]
  B --> D[Write target B file]
```

### Azure App Registration Secret Request

Covers pending-manual behavior for `azure_app_reg` static-like requests, including
agent instruction rendering without exposing secret values.

```mermaid
flowchart LR
  A[POST /agent/sync dry_run=true] --> B[Detect azure_app_reg fields need input]
  B --> C[Return pending_secrets entry]
  C --> D[Expose instructions only]
```
