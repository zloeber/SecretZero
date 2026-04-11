---
name: conventions
description: How code is written in this project — naming, structure, patterns, and style. Load when writing new code or reviewing existing code.
triggers:
  - "convention"
  - "pattern"
  - "naming"
  - "style"
  - "how should I"
  - "what's the right way"
edges:
  - target: context/architecture.md
    condition: when a convention depends on understanding the system structure
  - target: patterns/add-bundle.md
    condition: when implementing new provider/generator/target classes
  - target: patterns/add-cli-command.md
    condition: when extending `secretzero` CLI commands and options
last_updated: 2026-04-10
---

# Conventions

## Naming
- Files and modules use `snake_case` (`provider_backed.py`, `terraform_export.py`).
- Classes use `PascalCase` (`SyncEngine`, `BundleRegistry`, `BaseTarget`).
- Test modules use `test_*.py` under `tests/`.
- Provider capability methods are prefix-based (`generate_`, `retrieve_`, `store_`, `rotate_`, `delete_`).
- Bundle factory naming is `_get_bundle_manifest()` in provider modules.

## Structure
- Core code is under `src/secretzero/`; tests are centralized in `tests/`.
- Provider modules live in `src/secretzero/providers/`; generators and targets in sibling folders.
- Registration/bootstrap logic is centralized in `src/secretzero/bundles/registry.py`.
- CLI command implementations are in `src/secretzero/cli.py` on the `main` Click group.
- Task automation and verification commands are in `Taskfile.yml` and should be used for project-wide checks.

## Patterns
Always dispatch through `BundleRegistry`, not ad-hoc conditionals:
```python
# Correct
generator_class = registry.get_generator_class(kind)

# Wrong
if kind == "random_password":
    ...
```

Always use Pydantic v2 model serialization APIs:
```python
# Correct
config_dict = provider_config.model_dump()

# Wrong
config_dict = provider_config.dict()
```

Always use generator fallback wrapper when generating values:
```python
# Correct
value = generator.generate_with_fallback(env_var_name)

# Wrong
value = generator.generate()
```

## Verify Checklist
- [ ] No plaintext secret values are logged, surfaced, or written to versioned artifacts.
- [ ] Any new provider/generator/target is registered via bundle manifest + registry path.
- [ ] New serialization calls use Pydantic v2 methods (`model_dump*`).
- [ ] CLI output paths use Rich (`Console.print`) and integrate with existing command patterns.
- [ ] Formatting/lint expectations remain compatible with Ruff/Black (line length 100).
- [ ] Relevant tests under `tests/` are added or updated for behavior changes.
