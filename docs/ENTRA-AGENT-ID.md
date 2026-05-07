# Entra Agent ID Workflows

This guide covers native SecretZero support for Microsoft Entra Agent ID
blueprints and agent identity lifecycle management.

## Manifest Mapping Note

SecretZero uses `kind/config/targets`. If your source uses `type/source/target`,
map as follows:

- `type` -> `kind`
- `source.*` -> `config.spec.*`
- `target.entra_agent_id.*` -> `config.spec.*` + `config.provider`
- `agent_identities` -> `config.spec.agent_identities`

## Requested Shape Reference (verbatim)

```yaml
secrets:
  - name: hr-assistant-blueprint
    type: entra-agent-blueprint
    description: "Blueprint for all HR Assistant agents (Foundry + Copilot Studio)"
    source:
      generator: random  # or azure-key-vault, etc.
      length: 64
      rotation_policy:
        days: 90
        notify_days: 14
    target:
      entra_agent_id:
        tenant_id: "{{ env.TENANT_ID }}"
        blueprint:
          display_name: "HR Assistant Blueprint"
          sponsors: ["user:hr-lead@contoso.com"]
          owners: ["user:sec-team@contoso.com"]
          identifier_uris: ["api://{{ blueprint.app_id }}"]
          oauth_scopes:
            - value: "access_agent"
              admin_consent_display_name: "Access HR Assistant Agent"
        credentials:
          - type: client_secret
            display_name: "blueprint-secret-v1"
            end_date_time: "{{ now() + 90d }}"
          - type: federated_identity_credential  # preferred for prod
            name: "azure-mi-hr-assistant"
            issuer: "https://login.microsoftonline.com/{{ env.TENANT_ID }}/v2.0"
            subject: "{{ env.MANAGED_IDENTITY_CLIENT_ID }}"
            audiences: ["api://AzureADTokenExchange"]
    agent_identities:  # optional: declaratively create child agents
      - display_name: "HR Assistant - Onboarding v1"
        sponsor: "user:hr-lead@contoso.com"
        tags: ["hr", "onboarding", "foundry"]
```

## Canonical SecretZero Example

```yaml
secrets:
  - name: hr_assistant_blueprint
    kind: entra-agent-blueprint
    config:
      provider: entra_agent_id
      secret_name: hr-assistant-blueprint
      spec:
        tenant_id: "{{ env.TENANT_ID }}"
        blueprint:
          display_name: HR Assistant Blueprint
          sponsors: ["user:hr-lead@contoso.com"]
          owners: ["user:sec-team@contoso.com"]
          identifier_uris: ["api://{{ env.TENANT_ID }}/hr-assistant-blueprint"]
          oauth_scopes:
            - value: access_agent
              admin_consent_display_name: Access HR Assistant Agent
        credentials:
          - type: client_secret
            display_name: blueprint-secret-v1
            end_date_time: "2026-12-31T00:00:00Z"
          - type: federated_identity_credential
            name: azure-mi-hr-assistant
            issuer: "https://login.microsoftonline.com/{{ env.TENANT_ID }}/v2.0"
            subject: "{{ env.MANAGED_IDENTITY_CLIENT_ID }}"
            audiences: ["api://AzureADTokenExchange"]
        rotation_policy:
          days: 90
          notify_days: 14
        agent_identities:
          - display_name: HR Assistant - Onboarding v1
            sponsor: user:hr-lead@contoso.com
            tags: [hr, onboarding, foundry]
```

## 1) Standard GitOps Workflow

1. `secretzero validate`
2. `secretzero sync --dry-run`
3. `secretzero sync`

What happens:
- SecretZero upserts the `microsoft.graph.agentIdentityBlueprint`.
- Credentials are reconciled on the blueprint application.
- Declared child agent identities are created idempotently.
- `.gitsecrets.lock` stores metadata/hash state only.

## 2) Agentic Workflow

- `secretzero agent sync --json`
- `secretzero agent sync --web` when approvals/manual steps are needed.
- Fully automated mode is supported when `SZ_AGENT=true` and Graph auth is valid.

## 3) Rotation and Drift

- Rotate:
  - `secretzero rotate --secret hr_assistant_blueprint --force`
- Drift:
  - `secretzero drift`

Use provider identity policies and environment profiles to enforce stronger
production posture (for example requiring federated credentials in prod lanes).

## 4) Scenarios

### Scenario A: Microsoft Foundry Agent Lifecycle

Foundry-created blueprints can be reconciled in SecretZero so credential
rotation, drift checks, and audit trails remain Git-native.

### Scenario B: Organization-wide agent governance

Security teams define blueprint templates in SecretZero; application teams
consume and extend them with lane-specific overrides.

### Scenario C: Hybrid Multi-Environment

Use environment profiles to target dev/staging/prod tenants with different
credential types (client secrets in dev, federated credentials in prod).

### Scenario D: Zero-Trust Agent Onboarding

Use `agent sync --web` for sponsor-assisted approval and seeding while keeping
sensitive values out of agent context.
