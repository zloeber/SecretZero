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

`docs/schema.md` links to committed `../Secretfile.schema.json` (not gitignored `docs/Secretfile.schema.json`). CI may still run `scripts/ci-prepare-docs-links.sh` to materialize the MkDocs copy. Then scans `README.md` and `docs/` using `lychee.toml`.

## When it runs

- **CI:** `.github/workflows/test.yaml` job `docs-links` (every push/PR); `.github/workflows/docs.yaml` before MkDocs build on `main`
- End of agent work: `./scripts/agent.pre-commit.sh` (fast and full)
- Pre-commit hook: `secretzero-docs-links` in `.pre-commit-config.yaml`
- After editing docs or README

## Fixing failures

1. Prefer fixing the URL (404/410) or pointing to `https://secret0.com` / `https://github.com/zloeber/SecretZero/issues` instead of disabled GitHub Discussions.
2. For intentional non-checkable URLs (localhost docs, placeholders, CI-blocked hosts like `kubernetes.io`), add a regex to `lychee.toml` `exclude` — do not disable the task.
3. `kubernetes.io` links are valid but often fail lychee on GitHub Actions with "connection failed"; they remain excluded until upstream egress is reliable.
4. Install tool: `mise install` (see `mise.toml` `lychee` tool).
5. CI installs via `scripts/ci-install-lychee.sh` (handles v0.24+ nested release tarballs).

## Example manifest links

Jenkins CI example manifest: `examples/multi-cicd.yml` (not `jenkins-credentials.yml`).
