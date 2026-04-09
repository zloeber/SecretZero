---
name: add-bundle
description: Adding a new provider, generator, or target to SecretZero — either as a built-in or as a third-party bundle.
triggers:
  - "add provider"
  - "new provider"
  - "add generator"
  - "new generator"
  - "add target"
  - "new target"
  - "bundle"
  - "extend"
  - "plugin"
edges:
  - target: context/architecture.md
    condition: when understanding how BundleRegistry and SyncEngine connect
  - target: context/conventions.md
    condition: when unsure about naming, structure, or capability method prefixes
  - target: context/decisions.md
    condition: when understanding why the bundle system works the way it does
  - target: patterns/debug-sync.md
    condition: when the new bundle fails to register or dispatch
last_updated: 2026-04-09
---

# Add Bundle (Provider / Generator / Target)

## Context

Load `context/architecture.md` — all providers, generators, and targets are registered in
`BundleRegistry` at startup. `SyncEngine` only uses `BundleRegistry` for lookups; it never
references provider kinds by name in conditional logic.

Three components can be added independently:
- **Provider** — authenticates to an external service; optional for local/file targets
- **Generator** — produces a secret value (random, static, API-derived, etc.)
- **Target** — stores the secret in a destination (file, cloud store, CI/CD system)

## Task: Add a New Provider

### Steps

1. Create `src/secretzero/providers/myprovider.py` — subclass `BaseProvider`:
```python
from secretzero.providers.base import BaseProvider, ProviderAuth
from secretzero.bundles import BundleManifest

class MyProviderAuth(ProviderAuth):
    ENV_TOKEN = "MYPROVIDER_TOKEN"    # class-level for CLI introspection

    def authenticate(self) -> bool:
        token = self.config.get("token") or os.environ.get(self.ENV_TOKEN)
        if not token:
            return False
        self._client = MyProviderSDK(token=token)
        return True

    def is_authenticated(self) -> bool:
        return self._client is not None

class MyProvider(BaseProvider):
    display_name = "My Provider"
    description = "Stores secrets in MyProvider service"
    required_package = ("myprovider_sdk", "secretzero[myprovider]")
    auth_class = MyProviderAuth
    auth_methods = {"token": "Use a personal access token"}

    @property
    def provider_kind(self) -> str:
        return "myprovider"

    def test_connection(self) -> tuple[bool, str | None]:
        try:
            self.auth._client.ping()
            return True, None
        except Exception as e:
            return False, str(e)

    def get_supported_targets(self) -> list[str]:
        return ["myprovider_secret"]

    # Capability methods — MUST use prefixes: generate_, retrieve_, store_, rotate_, delete_
    def store_secret(self, path: str, value: str) -> bool:
        return self.auth._client.set(path, value)

def _get_bundle_manifest() -> BundleManifest:
    return BundleManifest(
        name="myprovider",
        version="1.0.0",
        provider_class="secretzero.providers.myprovider:MyProvider",
        targets={"myprovider_secret": "secretzero.targets.myprovider:MyProviderTarget"},
    )
```
2. Create the target `src/secretzero/targets/myprovider.py` (see "Add a New Target" task below).
3. Register in `bundles/registry.py` `_register_builtin_bundles()`:
```python
("secretzero.providers.myprovider", "_get_bundle_manifest"),
```
4. Add optional extra in `pyproject.toml`:
```toml
myprovider = ["myprovider-sdk>=1.0.0"]
```

### Gotchas

- **`required_package` tuple must be `(import_name, pip_install_name)`** — `import_name` is what Python imports (e.g., `"boto3"`); `pip_install_name` is what the user installs (e.g., `"secretzero[aws]"`). Used by `secretzero init` to show helpful error messages.
- **`test_connection()` is called before any secrets are generated** — it must be fast and not raise; return `(False, error_message)` on failure.
- **Capability method names drive auto-discovery** — `BaseProvider.get_capabilities()` introspects the class looking for methods prefixed `generate_`, `retrieve_`, `store_`, `rotate_`, `delete_`. A method named `save_secret` will NOT be discovered.
- **Auth initialisation happens in `authenticate()`**, not `__init__()` — the provider is instantiated before it is known whether auth is needed.

## Task: Add a New Generator

### Steps

1. Create `src/secretzero/generators/my_gen.py` — subclass `BaseGenerator`:
```python
from secretzero.generators.base import BaseGenerator

class MyGenerator(BaseGenerator):
    def generate(self) -> str:
        # Read config keys from self.config
        length = self.config.get("length", 32)
        prefix = self.config.get("prefix", "")
        return prefix + generate_my_value(length)

    def get_manual_instructions(self):
        # Override if manual fallback instructions should be shown when generation fails
        return self.manual_instructions  # uses Secretfile agent_instructions if set
```
2. Register in the provider's `_get_bundle_manifest()` under `generators`:
```python
generators={"my_generator": "secretzero.generators.my_gen:MyGenerator"},
```
   Or for a standalone built-in, add to `_register_builtin_generators()` in `bundles/registry.py`.
3. Add `MY_GENERATOR` to `GeneratorKind` enum in `models.py` (informational — the enum accepts unknown strings, but adding it improves type hints and IDE support).

### Gotchas

- **Never call `generate()` directly from outside the generator** — `SyncEngine` calls `generate_with_fallback(env_var_name)` which checks the environment variable first. If you bypass this, env var seeding stops working.
- **Generator is instantiated fresh per secret** — do not cache expensive state on `self` across multiple secrets; use class-level or module-level caching if needed.
- **`provider_backed` generator pattern** — if your generator needs a live provider instance, declare `PROVIDER_CONFIG_KEY = "provider"` and `PROVIDER_INJECTION_KEY = "_provider_instance"` as class attributes. `SyncEngine._resolve_provider_in_config()` will inject the provider before instantiation.

## Task: Add a New Target

### Steps

1. Create `src/secretzero/targets/mytarget.py` — subclass `BaseTarget`:
```python
from secretzero.targets.base import BaseTarget

class MyTarget(BaseTarget):
    def store(self, secret_name: str, secret_value: str) -> bool:
        # self.provider = authenticated provider instance (or None for local)
        # self.config = target config dict from Secretfile
        path = self.config.get("path", secret_name)
        try:
            self.provider.store_secret(path, secret_value)
            return True
        except Exception:
            return False

    def retrieve(self, secret_name: str) -> str | None:
        path = self.config.get("path", secret_name)
        try:
            return self.provider.get_secret(path)
        except Exception:
            return None

    def validate(self) -> tuple[bool, str | None]:
        # Optional: called before store() for "file" kind targets
        # Return (True, None) or (False, "error description")
        return True, None
```
2. Register in the bundle manifest under `targets`:
```python
targets={"my_target": "secretzero.targets.mytarget:MyTarget"},
```
3. Add `MY_TARGET` to `TargetKind` enum in `models.py` (informational).

### Gotchas

- **`store()` and `retrieve()` must never raise** — return `False`/`None` on failure; `SyncEngine` catches exceptions but clean error returns are preferred. Log errors via `result["errors"]` accumulation in the caller.
- **Local targets (provider == "local") receive only `config`** — `SyncEngine._store_in_target()` calls `target_class(target_config.config)` not `target_class(provider, config)` when provider is `"local"`. Your `__init__` must handle the backward-compat path in `BaseTarget.__init__` already handles this.
- **Template targets have deferred rendering** — `SyncEngine` accumulates secrets for template targets during sync, then calls `target.render(secrets_dict)` once all secrets are processed. If you implement a target that acts like a template, implement `render()` in addition to `store()`.

## Update Scaffold

- [ ] Update `.mex/ROUTER.md` "Current Project State" if a new provider/generator/target changes what's working
- [ ] Update `context/architecture.md` External Dependencies if a new external service is added
- [ ] Update `context/stack.md` Provider Optional Extras if a new pip extra is added
- [ ] Add to `INDEX.md` if you create a new pattern from this work
