---
name: schema-doc-parity
description: Required parity checklist for any schema/model/feature surface changes.
triggers:
  - "schema change"
  - "models.py"
  - "Secretfile.schema.json"
  - "new feature config surface"
edges:
  - target: context/conventions.md
    condition: when running final verification for model/schema/doc updates
  - target: patterns/secretfile-authoring.md
    condition: when the change affects Secretfile structure or examples
last_updated: 2026-04-20
---

# Schema + Docs Parity

## Context
Use this pattern whenever a task changes:
- `src/secretzero/models.py`
- `Secretfile.schema.json` behavior or generated fields
- Secretfile-facing configuration semantics (new fields, changed meaning, changed constraints)
- examples/docs that define canonical authoring patterns

## Steps
1. Implement model/runtime behavior changes first.
2. Add or update tests that validate new field shape and validation constraints.
3. Run `task schema:update` immediately after model edits.
4. Update both docs surfaces:
   - `docs/schema.md` (schema reference)
   - `docs/user-guide/configuration/index.md` (authoring guide)
5. Update at least one concrete example manifest when the change affects user-authored config.
6. Verify generated schema actually includes the new/changed fields and descriptions.
7. Run focused tests for the changed behavior and re-run schema update if models changed again.

## Gotchas
- Updating runtime behavior without documenting it in both docs pages creates drift.
- Updating docs but not model validators leaves schema under-specified.
- `secret_ref` and similar cross-secret behavior must document ordering/constraints explicitly.
- If examples are not updated, users copy stale patterns despite correct docs.

## Verify
- [ ] `task schema:update` run after final model changes.
- [ ] `Secretfile.schema.json` diff matches intended field shape/description.
- [ ] `docs/schema.md` includes the new/changed field semantics.
- [ ] `docs/user-guide/configuration/index.md` includes usage guidance and examples.
- [ ] Relevant tests exist for validation + runtime behavior and pass.
- [ ] At least one example manifest/docs flow reflects the new feature when applicable.

## Debug
- If behavior exists but schema is missing fields: re-check model annotations/Field metadata.
- If schema has fields but docs are stale: update both docs surfaces in same change.
- If docs and schema disagree: treat models + tests as source of truth, then regenerate schema/docs.

## Update Scaffold
- [ ] Update `.mex/ROUTER.md` "Current Project State" if schema or docs workflow changed
- [ ] Update `.mex/context/conventions.md` verify checklist if new parity checks were added
- [ ] Add follow-up gotchas from this change back into this pattern
