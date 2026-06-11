---
name: gitlab-bundle-extension
description: Extend GitLab provider bundle with variables, group targets, project auto-resolve, and project access tokens.
triggers:
  - "gitlab variable"
  - "gitlab project token"
  - "gitlab_group_variable"
  - "project auto"
edges:
  - target: patterns/add-bundle.md
    condition: when registering new GitLab bundle kinds
  - target: patterns/schema-doc-parity.md
    condition: when updating GeneratorKind/TargetKind enums
last_updated: 2026-06-11
---

# GitLab Bundle Extension

## Context

GitLab CI/CD variable sync and project access token generation live in:

- `src/secretzero/providers/gitlab_variables.py` — REST upsert/get helpers
- `src/secretzero/providers/gitlab_project_resolve.py` — `project: auto` chain
- `src/secretzero/providers/gitlab.py` — provider + `generate_project_access_token()`
- `src/secretzero/targets/gitlab.py` — `gitlab_variable`, `gitlab_group_variable`
- `src/secretzero/generators/gitlab_project_token.py` — thin generator

GitLab Secrets Manager (`gitlab_ci_secret`) is **deferred** — variables + project tokens only.

## Steps

1. Register all target/generator kinds in `_get_bundle_manifest()`.
2. Use shared variable helpers; always set `filter={'environment_scope': ...}` before variable `save()` when scope is not `*`.
3. Use `resolve_gitlab_project()` for `project: auto`; never hard-code CI env reads in targets.
4. Project access tokens require bootstrap PAT; default `revoke_existing: true` on generate.
5. Run `task schema:update` and `task docs:generate:provider-bundles` after enum/manifest changes.

## Gotchas

- `gitlab_group_variable` was documented before bundle registration — verify manifest lists it.
- Masked variables must be single-line and ≥8 characters or GitLab silently rejects saves.
- Project access tokens cannot create other project access tokens (PAT required).
- `python-gitlab` is optional extra `secretzero[gitlab]`; import `gitlab.exceptions` with ImportError fallback in helpers.

## Verify

- [ ] `pytest tests/test_gitlab_*.py` passes
- [ ] `gitlab_group_variable` and `gitlab_project_token` appear in bundle listing
- [ ] `examples/gitlab-project-token.yml` validates
