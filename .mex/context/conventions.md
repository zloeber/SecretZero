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
  - target: context/stack.md
    condition: when a convention relates to a specific library or tool
  - target: patterns/add-bundle.md
    condition: when writing a new provider, generator, or target
last_updated: 2026-04-09
---

# Conventions

## Naming

- **Files**: `snake_case` (`sync.py`, `cli_format.py`, `terraform_export.py`, `random_password.py`)
- **Classes**: `PascalCase` (`SyncEngine`, `BundleRegistry`, `BaseProvider`, `RandomPasswordGenerator`)
- **Tests**: `test_<module_or_feature>.py` in `tests/` directory (e.g., `test_sync_by_name.py`)
- **Provider capability methods**: prefixed with `generate_`, `retrieve_`, `store_`, `rotate_`, or `delete_` — this is how `BaseProvider.get_capabilities()` discovers them via introspection
- **Bundle factory function**: every provider module exposes `_get_bundle_manifest() -> BundleManifest` (underscore prefix = private, not exported via `__all__`)
- **Generator/target kind strings**: `snake_case` matching the enum value (`"random_password"`, `"vault_kv"`, `"github_secret"`)

## Structure

- `src/secretzero/` — all library code; one concern per file
- `src/secretzero/providers/` — one file per provider (`aws.py`, `vault.py`, etc.); each exports `_get_bundle_manifest()`
- `src/secretzero/generators/` — one file per generator kind; each subclasses `BaseGenerator`
- `src/secretzero/targets/` — one file per target kind or provider's target collection; each subclasses `BaseTarget`
- `src/secretzero/bundles/` — `registry.py` (BundleRegistry singleton + bootstrap), `loader.py` (dotted-path class loader), `__init__.py` (re-exports)
- `tests/` — test files only, not co-located with source; `pythonpath = ["src"]` in pytest config means imports work as `from secretzero.X import Y`
- `examples/` — example `Secretfile.yml` files; not executable, documentation only

## Patterns

**1. Registering a new provider/generator/target via BundleManifest:**
```python
# In src/secretzero/providers/myprovider.py
def _get_bundle_manifest() -> BundleManifest:
    return BundleManifest(
        name="myprovider",
        version="1.0.0",
        provider_class="secretzero.providers.myprovider:MyProvider",
        generators={"my_generator": "secretzero.generators.my_gen:MyGenerator"},
        targets={"my_target": "secretzero.targets.my_target:MyTarget"},
    )

# Register in bundles/registry.py _register_builtin_bundles():
("secretzero.providers.myprovider", "_get_bundle_manifest"),
```

**2. Pydantic v2 API — always use v2 methods:**
```python
# Correct (Pydantic v2)
data = model.model_dump()
json_str = model.model_dump_json(indent=2)

# Wrong (Pydantic v1 — will raise AttributeError)
data = model.dict()
json_str = model.json()
```

**3. Generator env-var fallback — always call `generate_with_fallback`, never `generate` directly:**
```python
# Correct — checks env var first, then generates
value = generator.generate_with_fallback(env_var_name="MY_SECRET")

# Wrong — skips env var check
value = generator.generate()
```

**4. Template secret naming — field secrets in lockfile use dot notation:**
```
# Secret named "app_creds" with template "db_credentials"
# Field "password" is tracked in lockfile as:
"app_creds.password"
```

**5. CLI output — always use Rich Console, never plain print:**
```python
from rich.console import Console
console = Console()
console.print("[green]✓[/green] Success message")
console.print("[red]✗[/red] Error message")
```

## Verify Checklist

Before presenting any code change:
- [ ] Uses `model_dump()` / `model_dump_json()` not `.dict()` / `.json()` (Pydantic v2)
- [ ] New provider/generator/target registers via `_get_bundle_manifest()` factory and is listed in `_register_builtin_bundles()` in `bundles/registry.py`
- [ ] No secret plaintext values in logs, lockfile, or exception messages — only hashes
- [ ] New CLI commands added to `main` group in `cli.py`; output uses `Console.print()` with Rich markup
- [ ] Tests live in `tests/` directory using pytest style; no `self.assert*` patterns
- [ ] Line length ≤ 100 characters (ruff/black config)
- [ ] Provider capability methods use the correct prefix (`generate_`, `retrieve_`, `store_`, `rotate_`, `delete_`) so auto-introspection discovers them
