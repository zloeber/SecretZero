---
name: docs-links-lychee
description: Validate hyperlinks in README.md and docs/ with lychee.
triggers:
  - "broken link"
  - "lychee"
  - "docs:links"
last_updated: 2026-06-04
---

# Docs hyperlink check (lychee)

## Command

```bash
task docs:links
```

Scans `README.md` and `docs/` using `lychee.toml` (loopback excluded, example URLs excluded).

## When it runs

- **CI:** `.github/workflows/test.yaml` job `docs-links` (every push/PR); `.github/workflows/docs.yaml` before MkDocs build on `main`
- End of agent work: `./scripts/agent.pre-commit.sh` (fast and full)
- Pre-commit hook: `secretzero-docs-links` in `.pre-commit-config.yaml`
- After editing docs or README

## Fixing failures

1. Prefer fixing the URL (404/410) or pointing to `https://secret0.com` / `https://github.com/zloeber/SecretZero/issues` instead of disabled GitHub Discussions.
2. For intentional non-checkable URLs (localhost docs, placeholders), add a regex to `lychee.toml` `exclude` — do not disable the task.
3. Install tool: `mise install` (see `mise.toml` `lychee` tool).
4. CI installs via `scripts/ci-install-lychee.sh` (handles v0.24+ nested release tarballs; `lychee-action` v2.8.0 still expects a flat `lychee` binary).

## Example manifest links

Jenkins CI example manifest: `examples/multi-cicd.yml` (not `jenkins-credentials.yml`).
