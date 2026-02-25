# Provider Bundle Architecture Plan

## Problem Statement

Today every provider, generator, and target in SecretZero lives inside the core
`src/secretzero/` tree.  Provider-specific code is scattered across three
separate directories (`providers/`, `generators/`, `targets/`), and the sync
engine hard-codes resolution of both generators and targets.  This makes it
difficult for outside contributors or vendors to ship self-contained provider
packages without modifying the core codebase.

The GitHub PAT feature we just added illustrates the friction: the generator
(`generators/github_pat.py`) is a thin shell that delegates to the provider
(`providers/github.py`), but the sync engine still needs an explicit `elif`
branch to wire the two together, and any new provider-scoped generator will
require a similar change.

---

## Goals

| #  | Goal | Measure |
|----|------|---------|
| G1 | A single pip-installable package can deliver a provider + its generators + its targets | `pip install secretzero-provider-github` adds all three |
| G2 | Zero changes to the core `secretzero` package when adding a third-party provider | No edits to `sync.py`, `models.py`, `registry.py` |
| G3 | Providers can declare scoped generator kinds and target kinds in their own package | `github_pat` generator kind ships inside the GitHub provider bundle |
| G4 | Existing built-in providers continue to work unmodified during migration | Backward-compatible; built-ins are simply re-packaged as bundles |
| G5 | Clear, documented interface for vendor-authored bundles | A `cookiecutter` template or spec document |

---

## Proposed Architecture

### 1. Bundle Package Layout

```
secretzero-provider-github/
├── pyproject.toml           # declares entry_points
├── src/
│   └── secretzero_provider_github/
│       ├── __init__.py      # exports BUNDLE_MANIFEST
│       ├── provider.py      # GitHubProvider + GitHubAuth
│       ├── generators/
│       │   ├── __init__.py
│       │   ├── pat.py       # GitHubPATGenerator
│       │   └── password.py  # the existing generate_password (if scoped)
│       ├── targets/
│       │   ├── __init__.py
│       │   └── secret.py    # GitHubSecretTarget
│       ├── permissions.py   # PAT permission schema + validation
│       └── tests/
│           ├── test_provider.py
│           ├── test_generators.py
│           └── test_targets.py
└── README.md
```

### 2. Bundle Manifest

Each bundle exports a typed manifest at its package root:

```python
# secretzero_provider_github/__init__.py
from secretzero.bundles import BundleManifest

BUNDLE_MANIFEST = BundleManifest(
    name="github",
    version="1.0.0",
    provider_class="secretzero_provider_github.provider:GitHubProvider",
    generators={
        "github_pat": "secretzero_provider_github.generators.pat:GitHubPATGenerator",
    },
    targets={
        "github_secret": "secretzero_provider_github.targets.secret:GitHubSecretTarget",
        "github_environment_secret": "secretzero_provider_github.targets.secret:GitHubEnvSecretTarget",
    },
    # Optional: declare new GeneratorKind / TargetKind enum values
    generator_kinds=["github_pat"],
    target_kinds=["github_secret", "github_environment_secret"],
)
```

### 3. Entry Point Discovery

Bundles register via Python `entry_points` (PEP 621):

```toml
# pyproject.toml of the bundle
[project.entry-points."secretzero.providers"]
github = "secretzero_provider_github:BUNDLE_MANIFEST"
```

The core registry discovers bundles at startup:

```python
# secretzero/bundles/registry.py
import importlib.metadata

def discover_bundles() -> list[BundleManifest]:
    """Discover all installed provider bundles via entry points."""
    bundles = []
    for ep in importlib.metadata.entry_points(group="secretzero.providers"):
        manifest = ep.load()
        bundles.append(manifest)
    return bundles
```

### 4. Core Changes Required

#### Phase 1 – Bundle Framework (foundation)

| File | Change |
|------|--------|
| **NEW** `src/secretzero/bundles/__init__.py` | `BundleManifest` Pydantic model |
| **NEW** `src/secretzero/bundles/registry.py` | `discover_bundles()`, `load_bundle()` |
| **NEW** `src/secretzero/bundles/loader.py` | Dynamic class import from dotted-path strings |
| `src/secretzero/providers/registry.py` | Call `discover_bundles()` during `_global_registry` init |
| `src/secretzero/models.py` | Make `GeneratorKind` and `TargetKind` open enums (accept unknown string values from bundles) |
| `src/secretzero/sync.py` | Replace hard-coded `elif` chain in `_generate_secret_value` and `_create_provider` with registry lookups |

#### Phase 2 – Refactor Built-in Providers

Move each existing provider into its own bundle package while keeping them
installed by default in the `secretzero[all]` extra:

```
secretzero-provider-aws/
secretzero-provider-azure/
secretzero-provider-github/
secretzero-provider-gitlab/
secretzero-provider-vault/
secretzero-provider-kubernetes/
secretzero-provider-jenkins/
secretzero-provider-ansible-vault/
secretzero-provider-infisical/
```

The core `secretzero` package keeps only the base classes and bundle framework.

#### Phase 3 – Vendor SDK & Cookiecutter Template

- Publish a `secretzero-provider-template` cookiecutter.
- Publish `secretzero-sdk` (or just document the base classes clearly).
- Add a `secretzero validate-bundle <path>` CLI command.

---

## Detailed Implementation Steps (for an agent)

### Step 1: Create `BundleManifest` Model

```python
# src/secretzero/bundles/__init__.py
from pydantic import BaseModel, Field

class BundleManifest(BaseModel):
    """Manifest describing a provider bundle's contents."""

    name: str = Field(description="Provider bundle name (e.g. 'github')")
    version: str = Field(default="1.0.0")
    provider_class: str = Field(
        description="Dotted path to provider class 'pkg.module:ClassName'"
    )
    generators: dict[str, str] = Field(
        default_factory=dict,
        description="Map of generator_kind -> dotted class path",
    )
    targets: dict[str, str] = Field(
        default_factory=dict,
        description="Map of target_kind -> dotted class path",
    )
    generator_kinds: list[str] = Field(default_factory=list)
    target_kinds: list[str] = Field(default_factory=list)
    requires: list[str] = Field(
        default_factory=list,
        description="pip dependencies (informational)",
    )
```

### Step 2: Create Bundle Loader

```python
# src/secretzero/bundles/loader.py
import importlib

def load_class(dotted_path: str) -> type:
    """Import a class from 'package.module:ClassName' format."""
    module_path, _, class_name = dotted_path.rpartition(":")
    module = importlib.import_module(module_path)
    return getattr(module, class_name)
```

### Step 3: Create Bundle Registry

```python
# src/secretzero/bundles/registry.py
import importlib.metadata
from secretzero.bundles import BundleManifest
from secretzero.bundles.loader import load_class

class BundleRegistry:
    """Central registry for provider bundles."""

    def __init__(self) -> None:
        self._bundles: dict[str, BundleManifest] = {}
        self._generator_classes: dict[str, type] = {}
        self._target_classes: dict[str, type] = {}
        self._provider_classes: dict[str, type] = {}

    def register_bundle(self, manifest: BundleManifest) -> None:
        """Register a bundle and all its components."""
        self._bundles[manifest.name] = manifest
        self._provider_classes[manifest.name] = load_class(manifest.provider_class)
        for kind, path in manifest.generators.items():
            self._generator_classes[kind] = load_class(path)
        for kind, path in manifest.targets.items():
            self._target_classes[kind] = load_class(path)

    def discover_and_register(self) -> None:
        """Auto-discover installed bundles via entry points."""
        for ep in importlib.metadata.entry_points(group="secretzero.providers"):
            try:
                manifest = ep.load()
                if isinstance(manifest, BundleManifest):
                    self.register_bundle(manifest)
            except Exception:
                pass  # graceful degradation

    def get_generator_class(self, kind: str) -> type | None:
        return self._generator_classes.get(kind)

    def get_target_class(self, kind: str) -> type | None:
        return self._target_classes.get(kind)

    def get_provider_class(self, kind: str) -> type | None:
        return self._provider_classes.get(kind)
```

### Step 4: Make Enums Extensible

Change `GeneratorKind` and `TargetKind` to accept unknown string values from
bundles.  Two approaches:

**Option A – Open Enum (recommended):**
Override `_missing_` so unknown strings are accepted at runtime:

```python
class GeneratorKind(str, Enum):
    # ... existing members ...

    @classmethod
    def _missing_(cls, value: object) -> "GeneratorKind | None":
        """Accept unknown generator kinds registered by bundles."""
        if isinstance(value, str):
            obj = str.__new__(cls, value)
            obj._name_ = value
            obj._value_ = value
            return obj
        return None
```

**Option B – Plain string with validation:**
Replace the enum with a `Literal` union or just `str` validated against the
registry at config-load time.

### Step 5: Refactor Sync Engine

Replace both hard-coded chains:

```python
# _generate_secret_value – current:
if kind == "random_password": ...
elif kind == "github_pat": ...

# _generate_secret_value – new:
generator_class = self._bundle_registry.get_generator_class(kind)
if generator_class is None:
    raise ValueError(f"Unknown generator kind: {kind}")
generator = generator_class(config)
```

Same pattern for `_create_provider` and `_store_in_target`.

### Step 6: Migrate Built-in Providers

For each existing provider (e.g. `github`):

1. Create a new package `secretzero-provider-github` with the layout above.
2. Move `providers/github.py` → `secretzero_provider_github/provider.py`.
3. Move `generators/github_pat.py` → `secretzero_provider_github/generators/pat.py`.
4. Move `targets/github.py` → `secretzero_provider_github/targets/secret.py`.
5. Add `BUNDLE_MANIFEST` and entry point in `pyproject.toml`.
6. In core `secretzero`, register built-in bundles as fallback if the external
   package isn't installed (backward compat).

### Step 7: Vendor Cookiecutter

Create `secretzero-provider-template`:

```
cookiecutter-secretzero-provider/
├── cookiecutter.json
├── {{cookiecutter.package_name}}/
│   ├── pyproject.toml.j2
│   ├── src/
│   │   └── {{cookiecutter.module_name}}/
│   │       ├── __init__.py.j2
│   │       ├── provider.py.j2
│   │       ├── generators/
│   │       └── targets/
│   └── tests/
└── README.md
```

### Step 8: CLI Validation Command

```bash
secretzero validate-bundle ./path/to/bundle
# Checks:
# - BUNDLE_MANIFEST is valid
# - All dotted paths resolve
# - Provider class inherits BaseProvider
# - Generator classes inherit BaseGenerator
# - Target classes inherit BaseTarget
# - Tests discovered and runnable
```

---

## Migration Strategy

| Phase | Scope | Breaking? | Timeline |
|-------|-------|-----------|----------|
| 1 | Bundle framework + registry | No | 1-2 weeks |
| 2 | Move built-in providers to bundles | No (backwards compatible) | 2-3 weeks |
| 3 | Cookiecutter + SDK docs + CLI command | No | 1 week |
| 4 | Deprecate in-tree providers (optional) | Minor | Future release |

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Entry point discovery is slow | Cache discovered bundles; lazy-load classes |
| Circular imports between bundle and core | Bundle depends on `secretzero` base classes only; no reverse dependency |
| Version skew between core and bundle | Declare `secretzero >= X.Y` in bundle deps; validate at load time |
| Vendor bundles with security issues | Document trust model; optional bundle signing |

---

## Summary

The bundle architecture lets vendor/community providers ship as independent pip
packages containing their own provider + generators + targets, discovered
automatically via Python entry points.  The implementation requires ~6 focused
PRs, is fully backward-compatible, and the framework itself is small (~200 LOC
for the core bundle module).
