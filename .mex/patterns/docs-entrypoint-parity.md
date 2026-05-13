---
name: docs-entrypoint-parity
description: Keep the docs landing page and repo README aligned for installation, onboarding, and agent-facing entrypoint guidance.
triggers:
  - "README"
  - "docs landing page"
  - "installation docs"
  - "agent skill install"
edges:
  - target: "context/setup.md"
    condition: "when setup or onboarding commands change"
  - target: "context/conventions.md"
    condition: "before verifying documentation-only updates"
last_updated: 2026-05-12
---

# Docs Entrypoint Parity

## Context

This project has two public entrypoints for onboarding:

- `README.md` for GitHub/repo visitors
- `docs/index.md` for the hosted documentation landing page

When install, onboarding, or agent workflow guidance changes, these two files should present the same high-level message even if the surrounding formatting differs.

## Steps

1. Read `README.md`, `docs/index.md`, and `context/setup.md`.
2. Identify the exact audience split that needs to be documented (for example human operators vs agent runtimes).
3. Update both entrypoints in the same session so neither becomes the stale version.
4. Prefer direct commands, concrete file paths, and named skill files over vague prose.
5. If the workflow depends on repo-local assets (for example `skills/.../SKILL.md`), document both:
   - the "works immediately from this repo" path
   - the "install globally or from a local checkout" path when applicable
6. For remote readers (GitHub UI, `gh`, `curl`, MCP fetchers), keep the fastest agent install path near the top of the page and prefer raw GitHub URLs when that improves copy/pasteability.

## Gotchas

- Do not describe agent skill installation as if it were the same as the human CLI install path.
- Avoid linking MkDocs pages to repo-relative files outside `docs/`; use explicit file paths in prose or GitHub URLs when needed.
- If one entrypoint uses raw install commands, ensure the other entrypoint includes the same commands or a clearly equivalent flow.
- If you add a helper downloader script, document both the raw `curl ... | zsh` usage and the local script path so remote and local users can follow the same workflow.

## Verify

- Confirm `README.md` and `docs/index.md` both mention the same install targets and skill names.
- Confirm commands are copy/pasteable and use the correct agent-specific paths.
- Confirm wording clearly distinguishes human operator setup from agent skill setup.

## Debug

- If documentation feels repetitive, keep the same commands but shorten the surrounding prose instead of deleting parity-critical instructions.
- If a hosted-docs link cannot point at a repo-local file, switch to explicit path references or public GitHub URLs.

## Update Scaffold

- [ ] Update `.mex/ROUTER.md` "Current Project State" if public onboarding changed materially
- [ ] Update any `.mex/context/` files that are now out of date
- [ ] If this is a new task type without a pattern, create one in `.mex/patterns/` and add to `INDEX.md`
