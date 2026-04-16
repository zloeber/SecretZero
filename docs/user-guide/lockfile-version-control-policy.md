# Lockfile Version Control Policy

This page defines the recommended policy for handling SecretZero lockfiles in Git repositories and GitOps/IaC pipelines.

## Why this matters

SecretZero lockfiles (default `.gitsecrets.lock`) capture deployment state and audit metadata without storing plaintext secrets. Teams need a consistent decision for whether lockfiles are committed, where they live, and how they are used per environment.

## Recommended default

Commit lockfiles to version control.

The lockfile contains hashes and metadata (timestamps, target sync state, rotation/provenance data), not secret values. Committing enables:

- deterministic idempotent sync behavior across collaborators and CI
- auditable history for change review and compliance evidence
- drift/rotation workflows that rely on shared state

## Environment strategy (GitOps/IaC)

Use one lockfile per environment lane.

Examples:

- `.gitsecrets.dev.lock`
- `.gitsecrets.staging.lock`
- `.gitsecrets.prod.lock`

Pair each lane consistently:

- one `Secretfile.yml` (or explicit manifest path)
- one `.szvar` context (`dev.szvar`, `staging.szvar`, `prod.szvar`)
- one lane lockfile (`--lockfile`)

If using Secretfile `environments.profiles`, define each lane's `var_files` and `lockfile` there
and select lanes by name (`--environment` for CLI, `environment` for API, lane selector in web UI).

Example:

```bash
secretzero sync \
  -f Secretfile.yml \
  --var-file envs/prod.szvar \
  --lockfile .gitsecrets.prod.lock
```

## CI/CD policy

For each environment pipeline:

1. Validate with environment context:
   - `secretzero validate --var-file <lane>.szvar`
2. Dry-run with lane lockfile:
   - `secretzero sync --dry-run --var-file <lane>.szvar --lockfile <lane-lockfile>`
3. Apply sync when approved.
4. Commit updated lane lockfile changes with the corresponding manifest/policy changes.

## When not to commit lockfiles

If your organization treats lockfile metadata as sensitive (for example, strict controls on operational metadata/provenance), you may choose not to commit lockfiles.

In that case:

- store lockfiles in secured state storage (artifact store, encrypted bucket, or equivalent)
- use stable per-environment paths
- maintain retention and backup policy
- accept reduced Git-native audit visibility

This should be an explicit exception, not an ad-hoc team decision.

## Do and don't

- Do commit lockfiles by default for GitOps/IaC workflows.
- Do separate lockfiles by environment.
- Do review lockfile diffs in PRs with manifest changes.
- Don't store plaintext secrets in manifests, var files, logs, or commits.
- Don't reuse one lockfile across multiple environment contexts.

## Related docs

- [Variable Files (.szvar)](variable-files.md)
- [Configuration Overview](configuration/index.md)
- [FAQ](../reference/faq.md#lockfile)
