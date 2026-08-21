# Gated live validations

Optional live provider checks under `tests/validations/`. They are **skipped by default** and only run when the required environment variables are present.

## GitLab group automation

```bash
export GITLAB_TOKEN=glpat-...
export GITLAB_TEST_GROUP=myorg/mygroup   # Owner role recommended
# optional:
export GITLAB_URL=https://gitlab.com

uv run pytest tests/validations/test_gitlab_group_live.py -v
```

## Azure DevOps Services

```bash
export AZDO_PAT=...
export AZDO_ORG=myorg
export AZDO_TEST_PROJECT=my-project
# optional:
export AZDO_TEST_VARIABLE_GROUP=secretzero-live-validation

uv run pytest tests/validations/test_azdo_live.py -v
```

## Notes

- These tests never print secret values.
- GitLab group-token live test creates and immediately revokes a short-lived token.
- Azure DevOps variable-group live test upserts a secret variable and asserts retrieve remains `None` (metadata-only).
- Example-manifest validation remains `task test:validations` (dry `secretzero validate` over `examples/*.yml`).
