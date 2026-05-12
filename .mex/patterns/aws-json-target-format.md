---
name: aws-json-target-format
description: Add or modify structured JSON support for AWS `ssm_parameter` / `secrets_manager` targets, including round-trip sync behavior.
triggers:
  - "aws json target"
  - "format: json"
  - "ssm_parameter"
  - "secrets_manager"
  - "structured aws secret"
edges:
  - target: "patterns/schema-doc-parity.md"
    condition: "When target config surface, examples, or generated docs need to stay aligned"
  - target: "patterns/debug-sync.md"
    condition: "When partial sync or target read-back behaves unexpectedly"
last_updated: 2026-05-12
---

# AWS JSON Target Format

## Context
AWS target writes happen in `src/secretzero/targets/aws.py`, but the user-visible target contract is exposed through `AWSProvider.target_details`, example manifests, and generated bundle docs. If you add or change `config.format: json`, you also need to consider partial-sync read-back in `SyncEngine`, not just store-time serialization.

## Steps
1. Run GitNexus impact before editing the relevant AWS target or sync symbols.
2. Add a failing test first for the exact JSON behavior you want (`store`, `retrieve`, or partial sync).
3. Keep `config.format: json` explicit: validate JSON payloads on write rather than silently accepting malformed JSON strings.
4. Parse JSON-formatted AWS values back into Python objects on retrieve so lockfile hashing and read-back comparisons stay stable.
5. If target retrieval can now return falsey structured values (`{}`, `[]`, `false`, `0`), update partial-sync/template-sync paths to distinguish `None` ("not found") from other falsey values.
6. Update `AWSProvider.target_details`, at least one example manifest, and regenerate `docs/reference/provider-bundles-auto.md`.

## Gotchas
- Store-only JSON support is incomplete. If retrieve still returns raw strings, unchanged structured secrets can hash differently later.
- Sync code that checks `if secret_value:` will misclassify valid falsey JSON payloads as missing; use `is not None` for retrieved target values.
- Top-level JSON `null` is a poor fit for target retrieval because `None` also means "not found" in sync code. Treat that case deliberately.

## Verify
- `uv run pytest tests/test_aws_targets.py tests/test_sync_json_falsey.py tests/test_sync_force_target.py`
- `uv run secretzero validate -f examples/aws-only.yml`
- `task docs:generate:provider-bundles`
- `./scripts/agent.pre-commit.sh --mode fast --quiet`

## Debug
- If an AWS JSON target writes correctly but partial sync still regenerates/skips, inspect `SyncEngine._sync_secret()` / `_sync_template_secret()` for truthiness checks.
- If CLI/provider docs do not show the new option, confirm `AWSProvider.target_details` changed and `docs/reference/provider-bundles-auto.md` was regenerated.

## Update Scaffold
- [ ] Update `.mex/ROUTER.md` when AWS target JSON behavior changes
- [ ] Update `examples/` with at least one structured AWS JSON target example
- [ ] Keep this pattern aligned with `src/secretzero/targets/aws.py`, `src/secretzero/providers/aws.py`, and sync partial-retrieval behavior
