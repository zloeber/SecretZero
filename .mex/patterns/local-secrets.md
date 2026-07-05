# Local-only secrets (`.gitsecrets.local.lock`)

## When to use

Developers need generated credentials (MySQL root, local API keys) that must not create merge conflicts in the shared `.gitsecrets.lock`.

## Pattern

1. Add `local: true` (or `local: ${IS_LOCAL_ENV:-false}`) on the secret in `Secretfile.yml`.
2. Restrict targets to `local/file` or `local/template` unless `local_allow_cloud: true`.
3. Run `secretzero sync` — hashes and provenance go to `.gitsecrets.local.lock` (gitignored).
4. Commit only the `Secretfile.yml` definition; each workstation generates its own value on first sync.

## Code touchpoints

- `src/secretzero/local_secrets.py` — routing helpers
- `src/secretzero/models.py` — `local`, `local_allow_cloud` on `Secret`
- `src/secretzero/sync.py` — `_lockfile_for(secret)` diversion
- `tests/test_local_secrets.py` — two-workstation merge scenario

## Docs

- `docs/user-guide/local-secrets.md`
- `examples/local-mysql-dev.yml`
