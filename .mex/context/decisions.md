---
name: decisions
description: Key architectural and technical decisions with reasoning. Load when making design choices or understanding why something is built a certain way.
triggers:
  - "why do we"
  - "why is it"
  - "decision"
  - "alternative"
  - "we chose"
edges:
  - target: context/architecture.md
    condition: when a decision relates to system structure
  - target: context/stack.md
    condition: when a decision relates to technology choice
  - target: patterns/add-bundle.md
    condition: when the bundle extensibility decision affects implementation choices
last_updated: 2026-04-09
---

# Decisions

<!-- When a decision changes: DO NOT delete the old entry. Mark it superseded and add the new entry above. -->

## Decision Log

### Bundle registry via entry_points — not hard-coded provider chains
**Date:** 2024-01-01 (inferred from architecture)
**Status:** Active
**Decision:** All providers, generators, and targets are registered through `BundleRegistry` using Python `entry_points` (group `"secretzero.providers"`), not `if/elif` chains in `SyncEngine`.
**Reasoning:** Enables third-party packages to ship their own providers as pip-installable bundles without modifying core SecretZero code. Built-in providers are also registered as BundleManifests so they can be extracted to standalone packages trivially.
**Alternatives considered:** Hard-coded if/elif in SyncEngine (rejected — prevents extensibility, requires core changes for each new provider); plugin framework like stevedore (rejected — adds dependency; `importlib.metadata` entry_points are sufficient and built-in since Python 3.9).
**Consequences:** All new providers, generators, and targets MUST register via `_get_bundle_manifest()` and be listed in `_register_builtin_bundles()`. Provider dispatch in `SyncEngine` never references provider kinds by name.

### Lockfile stores only SHA-256 hashes — never plaintext values
**Date:** 2024-01-01 (inferred from design)
**Status:** Active
**Decision:** The lockfile (`.gitsecrets.lock`) stores SHA-256 hashes of secret values, creation/update timestamps, and rotation counts — never plaintext values.
**Reasoning:** The lockfile is committed to version control (it is the audit trail / drift detection mechanism). Storing plaintext in a VCS-tracked file would be a critical security vulnerability.
**Alternatives considered:** Encrypting values in lockfile (rejected — adds key management complexity; hashes are sufficient for change detection and rotation tracking).
**Consequences:** Rotation detection works by comparing hashes. Partial sync (syncing new targets without regenerating) must retrieve the existing value from a known target, not from the lockfile.

### Open GeneratorKind and TargetKind enums via `_missing_`
**Date:** 2024-01-01 (inferred from models.py)
**Status:** Active
**Decision:** `GeneratorKind` and `TargetKind` enums accept unknown string values via `_missing_` instead of raising `ValueError`, returning pseudo-members at runtime.
**Reasoning:** Third-party bundles declare new generator and target kind strings. If the enums rejected unknown values, Secretfiles using bundle-provided kinds would fail to parse.
**Alternatives considered:** Using plain `str` type instead of enums (rejected — loses type-hinting and IDE support for built-in kinds); separate enum per bundle (rejected — fragmented, hard to introspect).
**Consequences:** Validation of kind strings is deferred to bundle registry lookup at sync time, not at Secretfile parse time.

### Jinja2 + shell-style variable interpolation — two syntaxes
**Date:** 2024-01-01 (inferred from config.py)
**Status:** Active
**Decision:** Secretfiles support both Jinja2-style (`{{var.name}}`) and shell-style (`${VAR_NAME}`) variable interpolation, with shell-style resolved first.
**Reasoning:** Shell-style is intuitive for environment variable references and is compatible with `.env` files. Jinja2-style enables nested variable access (`var.nested.key`) using the `var` context object. Both are common in infrastructure-as-code tooling.
**Alternatives considered:** Jinja2 only (rejected — `${VAR}` is more familiar for environment substitution); Go template style (rejected — unfamiliar to Python ecosystem).
**Consequences:** Variable interpolation in `ConfigLoader._interpolate_string()` applies shell-style regex first, then Jinja2. Undefined Jinja2 variables silently become empty string (via `SilentUndefined`) rather than raising errors.

### Provider optional extras as pip extras — not a monolithic install
**Date:** 2024-01-01 (inferred from pyproject.toml)
**Status:** Active
**Decision:** Provider dependencies (boto3, hvac, PyGithub, etc.) are declared as optional extras (`secretzero[aws]`, `secretzero[vault]`, etc.) not required dependencies.
**Reasoning:** A user only syncing to local files should not be required to install AWS, Azure, Vault, and Kubernetes libraries. Missing extras fail gracefully — `BundleRegistry` silently skips bundles whose provider class cannot be imported.
**Alternatives considered:** Separate pip packages per provider (e.g., `secretzero-aws`) — rejected at time of writing as extra complexity; the bundle entry_points mechanism already supports this if needed in the future.
**Consequences:** Code must never assume a provider's optional dependency is installed. `BaseProvider.required_package` class attribute stores `(import_name, pip_install_name)` for CLI error messages.

### Secretfile.yml + .szvar variable override files
**Date:** 2024-01-01 (inferred from config.py and CLI)
**Status:** Active
**Decision:** The base configuration lives in `Secretfile.yml`; environment- or context-specific overrides go in `.szvar` files that are merged at load time.
**Reasoning:** Supports multi-environment setups where the same Secretfile is used across dev/staging/prod by supplying different `.szvar` files. Later files take precedence in deep merge.
**Alternatives considered:** Multiple Secretfiles per environment (rejected — duplicates provider and secret definitions); environment variables for all config (rejected — too verbose for complex configurations).
**Consequences:** `ConfigLoader.load_file()` accepts `var_files: list[Path]` in order. The lockfile tracks `var_files` basenames and a hash of the merged variables for variable context change detection.
