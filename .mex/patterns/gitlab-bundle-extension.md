---
name: gitlab-bundle-extension
description: Extend GitLab provider bundle with variables, group targets, tokens, and service accounts.
triggers:
  - "gitlab variable"
  - "gitlab project token"
  - "gitlab group token"
  - "gitlab service account"
  - "gitlab_group_variable"
  - "project auto"
  - "group auto"
edges:
  - target: patterns/add-bundle.md
    condition: when registering new GitLab bundle kinds
  - target: patterns/schema-doc-parity.md
    condition: when updating GeneratorKind/TargetKind enums
last_updated: 2026-08-19
---

# GitLab Bundle Extension

## Context

GitLab CI/CD integration lives in:

- `src/secretzero/providers/gitlab_variables.py` — REST upsert/get helpers
- `src/secretzero/providers/gitlab_project_resolve.py` — `project: auto`
- `src/secretzero/providers/gitlab_group_resolve.py` — `group: auto`, top-level group detection
- `src/secretzero/providers/gitlab_tokens.py` — group/project access token helpers
- `src/secretzero/providers/gitlab_service_accounts.py` — group service account lifecycle
- `src/secretzero/providers/gitlab.py` — provider + token/SA generation
- `src/secretzero/targets/gitlab.py` — variables, group variables, SA membership
- `src/secretzero/generators/gitlab_project_token.py`
- `src/secretzero/generators/gitlab_group_token.py`
- `src/secretzero/generators/gitlab_group_service_account.py`

GitLab Secrets Manager (`gitlab_ci_secret`) remains **deferred**.

Structured SA payloads use target `value_field: token` (sync extracts scalar before store).

## Steps

1. Register all target/generator kinds in `_get_bundle_manifest()`.
2. Use shared helpers; set `environment_scope` filter before variable save when scope is not `*`.
3. Use `resolve_gitlab_project()` / `resolve_gitlab_group()` for `auto` resolution.
4. Bootstrap PAT required; group tokens need Owner role; group SA APIs need top-level group.
5. Run `task schema:update` and `task docs:generate:provider-bundles` after enum/manifest changes.

## Gotchas

- Group access tokens on GitLab.com require Premium+.
- Service account PAT plaintext is one-time only — lockfile stores hash + metadata IDs.
- `python-gitlab` optional extra `secretzero[gitlab]`.

## Verify

- [ ] `pytest tests/test_gitlab_*.py` passes
- [ ] Bundle lists `gitlab_group_token`, `gitlab_group_service_account`, `gitlab_service_account_member`
- [ ] `examples/gitlab-group-token.yml` and `examples/gitlab-group-service-account.yml` validate
