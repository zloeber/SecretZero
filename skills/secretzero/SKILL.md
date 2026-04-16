---
name: secretzero
description: |
  Compatibility entrypoint for SecretZero skills. Route to the focused skills:
  secretzero-author (manifest authoring/discovery) and secretzero-agent
  (agentic/runtime workflows).
---

# SecretZero Skill Router

This skill is retained for backwards compatibility and publishing stability.
Use one of the focused skills below for all new work.

## Use `secretzero-author` when

- Creating or editing `Secretfile.yml`.
- Performing schema-first, high-quality manifest authoring.
- Doing safe, contextless discovery and `.szvar` environment breakout.
- Adding least-privilege provider identity policy binding for targets.

File: `skills/secretzero-author/SKILL.md`

## Use `secretzero-agent` when

- Running agentic sync workflows (Vector 1/2/3).
- Operating CLI/API orchestration flows.
- Managing secure human-in-the-loop runtime scenarios.
- Handling install/onboarding/automation checks.

File: `skills/secretzero-agent/SKILL.md`

## Universal installation baseline

```bash
uv tool install -U "secretzero[all]"
```

The two focused skills include detailed workflows, safety rules, and usage examples.
