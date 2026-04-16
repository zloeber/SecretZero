---
name: secretzero
description: |
  Use whenever a Secretfile.yml exists in the repository (or sub-directory). 
  Ideal for bootstrapping secrets, running sync/rotate operations, authoring schema-compliant manifests, 
  or handling secure human-in-the-loop secret-zero workflows with AI agents. 
  Supports fully automated, agent-instructed, and secure web-UI assisted secret seeding.
---

# SecretZero for Coding Agents

**Always operate from the repository root** where `Secretfile.yml` lives (unless the manifest specifies a different path — then use `-f` / `--file` consistently for all commands).

## Core Principles for Agents
- **Never** request or receive plaintext secret values in your context, logs, or history.
- Prefer the **unified `secretzero agent sync`** command for all secret-zero scenarios.
- Use `--json` output when possible for reliable parsing.
- Keep the agent loop simple: call the command → act on results → repeat until clean.

## Unified Agent Workflow (Covers All Secret-Zero Vectors)

SecretZero now provides **one primary command** that intelligently handles every common secret bootstrapping case:

```bash
secretzero agent sync --json [--web] [--dry-run] [--verbose]
```

### The Three Vectors (Handled Automatically)

**Vector 1 – Agent instructs human (CLI-guided seeding)**  
Human is expected to perform steps (create keys in consoles, run commands, etc.).  
- Run: `secretzero agent sync --json`  
- Parse `pending_secrets` → relay the rendered `summary` + ordered `steps` to the human.  
- Human follows instructions (often running `secretzero sync` locally or external actions).  
- Re-run the command until `pending_secrets` is empty.

**Vector 2 – Secure human input via local web UI (no value leakage)**  
Agent triggers a temporary, localhost-only form for the human to enter values.  
- Run: `secretzero agent sync --web`  
- Tell the human: “A secure local page has opened at http://127.0.0.1:XXXX — please enter the requested secrets there and submit. Do **not** paste them here.”  
- The web UI feeds values directly into the sync engine; values never enter your context or logs.  
- Server auto-shuts down after submission.

**Vector 3 – Fully automated (no human intervention)**  
Providers have sufficient authentication.  
- Set `SZ_AGENT=true` in the environment, or rely on `Secretfile.agent.mode: auto`.  
- Run: `secretzero agent sync --json` (or plain `secretzero sync`).  
- Everything that can be generated or pulled automatically is handled; any remaining issues appear clearly in `failed_secrets`.

**Recommended Agent Loop (works for all vectors):**
1. Execute `secretzero agent sync --json` (add `--web` when appropriate).
2. If `pending_secrets` exist:
   - For Vector 1: Present templated instructions to the human.
   - For Vector 2: Trigger `--web` and guide the user to the local form.
3. Re-run the command after human action.
4. If `failed_secrets` appear, fix the `Secretfile.yml` (usually by adding better `agent_instructions`) and retry.
5. Proceed only when `pending_secrets` and `failed_secrets` are empty.

**Top-level configuration** (in `Secretfile.yml`):
```yaml
agent:
  mode: auto | human | web   # default: auto
  web_port_min: 49152        # optional bounds for the Vector 2 localhost form
  web_port_max: 65535
```

### REST API (same contract as the CLI)

Remote clients should call **`POST /agent/sync`** with JSON fields aligned to the CLI: `dry_run`, `web`, optional `lockfile`, and optional `sz_agent` (per-request override of the `SZ_AGENT` environment on the server). Responses mirror `secretzero agent sync --json` (no plaintext secret values).

- **Vector 2 over HTTP:** when manual secrets are pending and `web` is true, the response includes `status: awaiting_web_input`, a `web_url` on `127.0.0.1`, and `web_session_id`. Poll **`GET /agent/sync/web/{session_id}`** until `done` is true; structured results are in `result` (still no secret values).

Example:

```bash
curl -s -X POST "http://127.0.0.1:8000/agent/sync" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true}'
```

## Installation

Requires **Python 3.12+** and [`uv`](https://docs.astral.sh/uv/) (preferred) or `pip`.

```bash
# Minimal install
uv tool install secretzero

# Add extras for your providers (or use [all] if unsure)
uv tool install secretzero[aws]
uv tool install secretzero[azure]
uv tool install secretzero[vault]
uv tool install secretzero[kubernetes]
uv tool install secretzero[cicd]
uv tool install secretzero[all]
```

Verify: `secretzero --help`

## Baseline Onboarding Commands (Run in Order)

1. `secretzero validate` — Validates structure and variables (`--var-file` if needed).
2. `secretzero init --install` — Installs declared provider extras.
3. `secretzero test` — Checks provider connectivity.
4. `secretzero sync --dry-run` — Previews the full sync (may prompt for manual secrets).

Default lockfile: `.gitsecrets.lock` (derived automatically from the manifest filename).

## Authoring `Secretfile.yml` Rules (Whole Secrets First)

Use the schema as the source of truth, and keep definitions predictable for humans and agents.

### Rule 1: Model secrets as whole units by default
- Prefer one secret entry per real secret value (`DB_PASSWORD`, `JWT_SIGNING_KEY`, `API_TOKEN`).
- Keep each secret self-contained: `name`, `kind`, `config`, and `targets` in the same item.
- Do not split one logical secret across multiple entries unless targets force it.
- Use `templates.<name>` only when several fields must travel together as one credential set.

### Rule 2: Choose the simplest valid generator
- `random_password` for passwords.
- `random_string` for opaque tokens/ids.
- `static` for seeded values coming from controlled external inputs (variables, provider-backed reads, human seeding).
- `script`/`api` only when built-in generators cannot represent the source.
- Keep `config` minimal; avoid adding options that do not change behavior you need.

### Rule 3: Keep template usage straightforward
- Use templates for stable multi-field bundles (for example host/user/password, OAuth client_id/client_secret).
- Keep template `fields` flat and explicit; avoid over-nesting.
- Prefer template-level `targets`; add field-level targets only when a field truly needs a different destination.
- Avoid using templates for single-value secrets.
- Avoid chaining complexity (template + many per-field overrides + heavy interpolation) unless strictly required.

### Rule 4: Keep interpolation and templating boring
- Prefer direct values and simple `${VAR}` style substitutions for manifest-time values.
- Use `{{ ... }}` only in `agent_instructions` text (summary/steps/etc.) where agent context rendering is intended.
- Keep templated instructions short, deterministic, and action-oriented.
- Avoid hidden magic from deeply composed templates; if a human cannot read it quickly, simplify it.

### Rule 5: Keep provider and target mappings explicit
- Define provider aliases once under `providers:` and reference the same alias in every target.
- Every secret should have clear targets unless intentionally deferred.
- Prefer one canonical target path/name per secret; duplicate targets only for real distribution needs.
- Avoid ambiguous naming in target config (for example inconsistent key/path conventions across similar secrets).

### Rule 6: Use `agent_instructions` whenever humans must act
- If a secret cannot be fully automated, include `agent_instructions` to avoid `failed_secrets`.
- Include at least:
  - `summary`: one-sentence purpose.
  - `steps`: ordered steps with concrete actions.
- Optionally include: `prerequisites`, `automation_hint`, `fallback`, `required_tools`, `documentation_url`.
- Use placeholders sparingly (`{{ secret_name }}`, `{{ target.kind }}`, target config keys) and keep instructions readable when rendered.

### Rule 7: Keep naming and structure consistent
- Secret names should be stable and environment-agnostic where possible.
- Use `vars` only for true per-secret overrides, not as a second general config store.
- Keep global defaults in `variables`; keep secret-specific behavior in each secret's `config`.
- Group related secrets together in the list to improve reviewability.

### Rule 8: Validate every edit through the same loop
1. `secretzero validate`
2. `secretzero render` (when interpolation or `agent_instructions` templating is involved)
3. `secretzero sync --dry-run`
4. `secretzero agent sync --json` (or `--web`) when testing human-in-the-loop flows

### Rule 9: Write narrowly scoped identity guardrails for provider-backed targets
- Prefer explicit, least-privilege `kind: provider_identity` policies over broad wildcard matching.
- For AWS, constrain both `account` and `region` whenever possible.
- Attach targeted policies at the secret target via `identity_policies` when only some targets require stricter controls.
- Avoid auto-broadening policies (`*`, catch-all regex) unless a human explicitly approves the trade-off.

#### AWS account + region guardrail (baseline)
```yaml
policies:
  aws_prod_identity:
    kind: provider_identity
    providers: [aws]
    match: all
    rules:
      - field: account
        glob: "111111111111"
      - field: region
        glob: us-east-1
```

#### AWS prod account allowlist + bounded regions
```yaml
policies:
  aws_prod_accounts_and_regions:
    kind: provider_identity
    providers: [aws]
    match: all
    rules:
      - field: account
        any_glob: ["111111111111", "222222222222"]
      - field: region
        any_glob: ["us-east-1", "us-west-2"]
```

#### Per-target strictness with `identity_policies`
```yaml
policies:
  aws_prod_use1:
    kind: provider_identity
    providers: [aws]
    match: all
    rules:
      - field: account
        glob: "111111111111"
      - field: region
        glob: us-east-1

secrets:
  - name: app_token
    kind: random_string
    config: { length: 40 }
    targets:
      - provider: aws
        kind: secrets_manager
        identity_policies: [aws_prod_use1]
        config:
          name: /prod/app/token
```

#### Cross-provider pattern (similar scenario, non-AWS)
```yaml
policies:
  azure_prod_tenant:
    kind: provider_identity
    providers: [azure]
    rules:
      - field: tenant_id
        glob: "00000000-0000-0000-0000-000000000000"
```

### Discovery-assisted policy authoring loop (agent-safe)
Use discovery to observe real authenticated identity metadata, then author minimally permissive rules.

1. Discover current authenticated provider identities:
   - `secretzero status --format json`
   - (optional) `secretzero test --verbose`
2. Extract provider actor fields (`account`, `region`, `arn`, `tenant_id`, `namespace`, etc.) from machine-readable output.
3. Propose policy fragments that match only required contexts.
4. Validate and enforce:
   - `secretzero validate`
   - `secretzero sync --dry-run`
5. Tighten rules before commit (prefer exact account/region over wildcards).

### Agent-friendly discovery contract (for robust context handling)
When an agent consumes discovery output, normalize it into a stable shape before generating policies.

```json
{
  "providers": [
    {
      "alias": "aws",
      "kind": "aws",
      "auth_status": "ok",
      "actor": {
        "account": "111111111111",
        "region": "us-east-1",
        "arn": "arn:aws:sts::111111111111:assumed-role/ci-role/session"
      }
    }
  ],
  "candidate_policy_fragments": [
    {
      "name": "aws_prod_identity",
      "kind": "provider_identity",
      "providers": ["aws"],
      "rules": [
        { "field": "account", "glob": "111111111111" },
        { "field": "region", "glob": "us-east-1" }
      ],
      "confidence": "high",
      "safe_to_enforce": true
    }
  ]
}
```

Agent constraints for discovery-driven authoring:
- Never include or request secret values while discovering identity.
- Prefer deterministic scalar matching (`glob`) before broader pattern matching (`regex`).
- Mark wide matches as "needs human confirmation".
- Re-run discovery and dry-run validation after any policy edit.

### Practical default pattern
Use this shape unless you have a concrete reason not to:

```yaml
variables:
  env: production

providers:
  aws:
    kind: aws
    auth:
      kind: ambient

secrets:
  - name: db_password
    kind: random_password
    config:
      length: 32
      special: true
    rotation_period: 90d
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: /${env}/db/password
```

### When to use templates
Use templates only for multi-field credentials that are consumed together:

```yaml
templates:
  database_credentials:
    description: Application database credentials
    fields:
      username:
        description: Service user name
        generator:
          kind: static
          config:
            default: appuser
      password:
        description: Service user password
        generator:
          kind: random_password
          config:
            length: 32
            special: true
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: /production/database

secrets:
  - name: app_database
    kind: templates.database_credentials
```

## Common Pitfalls to Avoid

- Missing or incomplete `agent_instructions` on non-auto secrets → results in `failed_secrets`.
- Forgetting `--var-file` when variables are used.
- Running commands from the wrong directory.
- Expecting plaintext values — always use the agent workflow instead.
- Running `secretzero get --reveal` in an AI session; keep output metadata-only to avoid leakage.
- Installing without the correct provider extras.

## Quick Reference Cheat Sheet

```bash
secretzero validate
secretzero schema export -o Secretfile.schema.json
secretzero agent sync --json          # Vector 1 & 3
secretzero agent sync --web           # Vector 2
secretzero sync --dry-run
secretzero secret-types --verbose
```

## Tips for Effective Agent Use

- Always prefer `--json` output when parsing results programmatically.
- When guiding the human, quote the exact rendered `summary` and `steps` from the JSON.
- For Vector 2, clearly communicate that the web UI is temporary, localhost-only, and secure.
- After any manual changes or human actions, re-run `secretzero agent sync --json` to confirm state.
- Combine with `secretzero drift` or `secretzero rotate` when maintenance is needed post-bootstrap.

This workflow keeps secrets **out of agent context**, provides clear guidance, and scales from fully manual to fully automated scenarios with minimal friction.

For the absolute latest behavior, run `secretzero --help` and `secretzero agent sync --help` in the target repository.
