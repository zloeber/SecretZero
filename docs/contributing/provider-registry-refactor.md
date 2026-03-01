# Provider Registry Refactor — Progress Tracker

> **Goal:** Eliminate hardcoded provider-specific if/elif chains and metadata
> dicts throughout the CLI and orchestration layer, replacing them with
> registry-driven dispatch using class-level metadata on `BaseProvider` and
> `ProviderAuth`.
>
> **Status:** Complete — all 5 phases done, 763 tests passing, lint clean.

## Summary of Changes

### Phase 1 — Provider Metadata on Base Classes ✅

| File | Change |
|------|--------|
| `providers/base.py` | Added `display_name`, `description`, `required_package`, `auth_class` class attrs to `BaseProvider`; added `ENV_TOKEN` to `ProviderAuth` |
| `providers/aws.py` | Set `display_name`, `description`, `required_package`, `auth_class` |
| `providers/azure.py` | Set `display_name`, `description`, `required_package`, `auth_class` |
| `providers/vault.py` | Set `display_name`, `description`, `required_package`, `auth_class` |
| `providers/github.py` | Set `display_name`, `description`, `required_package`, `auth_class` |
| `providers/gitlab.py` | Set `display_name`, `description`, `required_package`, `auth_class` |
| `providers/jenkins.py` | Set `display_name`, `description`, `required_package`, `auth_class` |
| `providers/kubernetes.py` | Set `display_name`, `description`, `required_package`, `auth_class` |
| `providers/ansible_vault.py` | Set `display_name`, `description`, `required_package`, `auth_class` |

### Phase 2 — Refactor CLI Provider Instantiation ✅

| File | Change |
|------|--------|
| `cli.py` `test` command (~L1324–1460) | Replaced ~140-line if/elif chain with 5-line registry lookup |
| `cli.py` `_test_provider_profiles` (~L1204–1248) | Replaced ~60-line if/elif chain with registry lookup |

### Phase 3 — Refactor CLI Dependency Check ✅

| File | Change |
|------|--------|
| `cli.py` `check-deps` command (~L180) | Replaced hardcoded `provider_packages` dict with `required_package` class attr |

### Phase 4 — Refactor CLI Provider List Metadata ✅

| File | Change |
|------|--------|
| `cli_providers.py` `list` command | Replaced hardcoded `provider_info` dict with `display_name`/`description` class attrs |

### Phase 5 — Refactor Environment Variable Map ✅

| File | Change |
|------|--------|
| `cli_providers.py` `token-info` | Replaced hardcoded `env_var_map` dict with `ProviderAuth.ENV_TOKEN` class attr |

## Design Decisions

1. **Class-level metadata** — `display_name`, `description`, and `required_package`
   are class attributes on `BaseProvider` with sensible defaults derived from the
   class name. Subclasses override with specific values.

2. **`required_package` tuple** — `(import_name, install_name)` e.g.
   `("boto3", "secretzero[aws]")`. Base returns `None` (no extra deps).

3. **`ENV_TOKEN` on `ProviderAuth`** — Already existed on GitHub/GitLab/Jenkins/Vault
   auth classes. Added default `""` on base class so the CLI can read it generically.

4. **`auth_class` on `BaseProvider`** — Points to the concrete `ProviderAuth` subclass
   (e.g. `GitHubAuth`, `VaultAuth`). Lets the CLI inspect auth-level metadata like
   `ENV_TOKEN` without instantiating the provider.

5. **Registry-based instantiation** — `GLOBAL_PROVIDER_REGISTRY.get_provider_class(kind)`
   returns the class, which we instantiate directly. `ImportError` is caught generically
   since the registry import already succeeded.

## Lines Removed (approximate)

| Area | Before | After | Reduction |
|------|--------|-------|-----------|
| `test` command if/elif | ~140 lines | ~15 lines | ~125 lines |
| `_test_provider_profiles` if/elif | ~50 lines | ~10 lines | ~40 lines |
| `check-deps` dict | ~10 lines | ~5 lines | ~5 lines |
| `providers list` dict | ~10 lines | ~5 lines | ~5 lines |
| `token-info` env_var_map | ~8 lines | ~3 lines | ~5 lines |
| **Total** | **~218 lines** | **~38 lines** | **~180 lines** |
