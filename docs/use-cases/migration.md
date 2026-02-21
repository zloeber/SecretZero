# Migration Guides

Guidance for moving secrets into SecretZero without downtime.

## Suggested Approach

1. Inventory existing secret stores
2. Model secrets in a Secretfile
3. Run `secretzero sync --dry-run`
4. Rotate or reconcile stale secrets
5. Decommission legacy tooling
