# Provider identity policies

Provider identity policies are `Secretfile.yml` rules with `kind: provider_identity`. They compare the **currently authenticated principal** for each configured provider (via `get_actor_info()` / STS, Vault `lookup-self`, etc.) against patterns you define. If a rule fails, **`secretzero sync`** (CLI, REST API, agent sync, and `secretzero web` actions) stops before writing secrets—so you cannot accidentally sync production targets while logged into a dev account or the wrong AWS profile.

This is separate from **rotation** and **access** policies (`secretzero policy`), which check secret metadata and allowed target *kinds*. Provider identity policies gate **sync** based on *who* is authenticated.

## When this is useful

- **AWS account / role guardrails** — Ensure callers are in account `123456789012`, or that the IAM ARN matches `arn:aws:iam::123...:role/Prod*`, before any `secrets_manager` or `ssm_parameter` write.
- **Vault token shape** — Require Vault `scopes` (from token metadata) to include `prod-*` or an admin policy name, so staging tokens cannot push to prod paths.
- **Multi-environment laptops** — Combine with `variables` / `.szvar` so `{{ var.expected_aws_account }}` in a `glob` resolves per env file; wrong var file + wrong credentials fails fast.
- **CI vs human** — Narrow allowed ARNs or accounts for the CI role used in pipelines vs interactive roles (same manifest, different interpolation or policies per branch).
- **Target-specific enforcement** — Use `identity_policies: [policy_name]` on a single target so only that lane requires an extra check when it is in scope.

## Example

```yaml
variables:
  expected_aws_account: "123456789012"

policies:
  prod_aws_caller:
    kind: provider_identity
    description: Only sync AWS targets when STS identity matches prod account
    providers: [aws]
    match: all
    rules:
      - field: account
        glob: "{{ var.expected_aws_account }}"
      - field: arn
        glob: "arn:aws:iam::{{ var.expected_aws_account }}:role/*"

secrets:
  - name: app_secret
    kind: random_string
    config: { length: 32 }
    targets:
      - provider: aws
        kind: secrets_manager
        config:
          name: prod/app/credential
```

Optional: attach the same policy only to one target:

```yaml
    targets:
      - provider: aws
        kind: secrets_manager
        identity_policies: [prod_aws_caller]
        config:
          name: prod/app/credential
```

### Rule shapes

Each rule sets exactly one of:

| Field | Use |
|-------|-----|
| `glob` | `fnmatchcase` on a scalar field (string form). |
| `regex` | Full string match (`re.fullmatch`) on a scalar. |
| `any_glob` | List field: at least one element matches at least one pattern. |
| `all_glob` | List field: every element matches at least one pattern. |

Use `field` with dotted paths supported for nested keys in the actor dict (when present). Common fields include AWS `account`, `arn`, `region`; Vault `user`, `scopes`, `url`. See `.mex/patterns/secretfile-authoring.md` for a provider-oriented table.

## Validation and surfaces

- **`secretzero validate`** — Loads the manifest (including var files) and checks `provider_identity` shape and `identity_policies` references. It does **not** call cloud APIs for policy evaluation.
- **Sync-time enforcement** — After target access checks, applicable policies are evaluated with live `get_actor_info()`.
- **`secretzero web`** — The dashboard shows **Authentication vs identity policies**: a preflight table (same logic as sync) so you see pass/fail before clicking Sync.
- **API** — `POST /config/validate` rejects invalid policy documents (see Tavern E2E `tests/e2e/test_provider_identity_policy.tavern.yaml`).

## Schema reference

JSON Schema: `Secretfile.schema.json` → `$defs.ProviderIdentityPolicy` and `$defs.ProviderIdentityRule`.

## See also

- [Configuration overview](index.md)
- [Validation](validation.md)
- [Secretfile reference](secretfile.md)
