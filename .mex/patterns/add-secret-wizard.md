---
name: add-secret-wizard
description: Change the `secretzero add` / `new` walkthrough or `POST /secrets` authoring path.
triggers:
  - "secretzero add"
  - "secretzero new"
  - "add secret wizard"
edges:
  - target: patterns/add-cli-command.md
    condition: when changing Click options or help text
  - target: patterns/secretfile-authoring.md
    condition: when the written Secretfile shape changes
last_updated: 2026-09-25
---

# Add Secret Wizard

## Context
`secretzero add` (alias `new`) and `POST /secrets` share `apply_secret_draft()` in `src/secretzero/secret_author.py`. The CLI prompts live in `src/secretzero/cli_add.py`.

## Steps
1. Change the draft model and YAML merge in `secret_author.py` first.
2. Keep CLI flags and the API request body on that same function.
3. Reject plaintext `value` / `default` for generators with `PROMPTS_LIKE_STATIC`.
4. Preserve existing comments with ruamel round-trip YAML.
5. Do not resolve `--environment` into the file. `add` edits the raw manifest so interpolated values are not baked in.
6. JSON and API responses omit generator config.
7. Add a CLI test and an API test under `tests/test_cli_add.py`.

## Gotchas
- Editing without `--source-kind` must leave an existing `source:` block alone. Pass `update_source=True` only when the caller set a source or `clear_source` / `--source-kind none`.
- Default edit behavior appends targets. `--replace-targets` replaces them.
- A new provider alias is an ambient stub (`auth.kind: ambient`), except `local`, which gets `config: {}`.
- Interactive prompts must stay usable via Click so `CliRunner` can drive `--interactive`.

## Verify
- [ ] `secretzero add --help` and `secretzero new --help` both describe the walkthrough.
- [ ] Creating a secret keeps existing comments and unrelated secret fields.
- [ ] A static literal value fails and does not write the file.
- [ ] `POST /secrets` returns the same metadata-only payload.
