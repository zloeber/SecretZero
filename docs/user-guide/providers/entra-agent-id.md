# Entra Agent ID Provider

The `entra-agent-id` provider manages Microsoft Entra Agent Identity Blueprints
and their credentials through Microsoft Graph.

## Required Microsoft Graph Permissions

- `AgentIdentityBlueprint.Create`
- `AgentIdentityBlueprint.AddRemoveCreds.All`
- `AgentIdentityBlueprint.UpdateAuthProperties.All`
- `Application.ReadWrite.All`
- `Directory.ReadWrite.All`

## Install

```bash
pip install secretzero[entra_agent_id]
```

## Provider Configuration

```yaml
providers:
  entra_agent_id:
    kind: entra-agent-id
    auth:
      kind: service_principal
      config:
        tenant_id: ${AZURE_TENANT_ID}
        client_id: ${AZURE_CLIENT_ID}
        client_secret: ${AZURE_CLIENT_SECRET}
```

You can also provide a pre-issued Graph access token via:

```bash
export ENTRA_AGENT_ID_ACCESS_TOKEN=eyJ...
```

## Secret Example (`kind/config/targets` model)

```yaml
secrets:
  - name: hr_assistant_blueprint
    kind: entra-agent-blueprint
    config:
      provider: entra_agent_id
      secret_name: hr-assistant-blueprint
      spec:
        tenant_id: ${AZURE_TENANT_ID}
        blueprint:
          display_name: HR Assistant Blueprint
          sponsors: ["user:hr-lead@contoso.com"]
          owners: ["user:sec-team@contoso.com"]
          identifier_uris: ["api://hr-assistant-blueprint"]
          oauth_scopes:
            - value: access_agent
              admin_consent_display_name: Access HR Assistant Agent
        rotation_policy:
          days: 90
          notify_days: 14
        credentials:
          - type: client_secret
            display_name: blueprint-secret-v1
            end_date_time: "2026-12-31T00:00:00Z"
          - type: federated_identity_credential
            name: azure-mi-hr-assistant
            issuer: https://login.microsoftonline.com/${AZURE_TENANT_ID}/v2.0
            subject: ${MANAGED_IDENTITY_CLIENT_ID}
            audiences: ["api://AzureADTokenExchange"]
        agent_identities:
          - display_name: HR Assistant - Onboarding v1
            sponsor: user:hr-lead@contoso.com
            tags: [hr, onboarding, foundry]
    targets:
      - provider: local
        kind: file
        config:
          path: generated/entra-blueprint.json
          format: json
          merge: true
```

## Notes

- SecretZero stores only metadata/hashes in lockfiles.
- Graph responses are sanitized to avoid leaking secret values (`secretText`).
- For sponsor approvals or permission blockers, use `secretzero agent sync --web`
  to complete manual steps without placing values in agent context.
