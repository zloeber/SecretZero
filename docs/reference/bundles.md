# Bundle Reference

API-level reference for the SecretZero provider bundle framework. For a practical walkthrough, see [Extending SecretZero](../extending.md). For a generated registry snapshot, see [Provider Bundles (Auto-Reference)](provider-bundles-auto.md).

## BundleManifest

::: secretzero.bundles.registry.BundleManifest
    options:
      show_bases: true
      members_order: source

## BundleRegistry

::: secretzero.bundles.registry.BundleRegistry
    options:
      show_bases: false
      members_order: source

## Module-level functions

::: secretzero.bundles.registry.get_bundle_registry

::: secretzero.bundles.registry.discover_bundles

::: secretzero.bundles.registry.reset_bundle_registry

## Class Loader

::: secretzero.bundles.loader.load_class

::: secretzero.bundles.loader.load_class_safe

## Base Classes

These are the abstract base classes that bundle implementations must subclass.

### BaseProvider

::: secretzero.providers.base.BaseProvider
    options:
      show_bases: true
      members:
        - provider_kind
        - test_connection
        - authenticate
        - is_authenticated
        - get_supported_targets
        - get_capabilities
        - get_provider_detail
      members_order: source

### ProviderAuth

::: secretzero.providers.base.ProviderAuth
    options:
      show_bases: true
      members:
        - authenticate
        - is_authenticated
        - get_client
        - get_token_info
      members_order: source

### BaseGenerator

::: secretzero.generators.base.BaseGenerator
    options:
      show_bases: true
      members:
        - generate
        - generate_with_fallback
      members_order: source

### BaseTarget

::: secretzero.targets.base.BaseTarget
    options:
      show_bases: true
      members:
        - store
        - retrieve
        - validate
      members_order: source

## Dotted Path Format

All class references in a `BundleManifest` use the `module.path:ClassName` format:

```
secretzero_mycloud.provider:MyCloudProvider
│                  │        │
│                  │        └── Attribute name within the module
│                  └── Submodule
└── Top-level package
```

The colon (`:`) separates the importable module path from the class attribute. This is the same format used by Python `entry_points`.

## Entry Points Group

Bundles register under the `secretzero.providers` entry-point group:

```toml
# pyproject.toml
[project.entry-points."secretzero.providers"]
mycloud = "secretzero_mycloud:BUNDLE_MANIFEST"
```

The entry-point **name** (left side) is informational. The entry-point **value** (right side) must resolve to a `BundleManifest` instance.

## Built-in Bundle Manifests

Each built-in provider exposes a `_get_bundle_manifest()` factory function that returns its `BundleManifest`. These are registered by `_register_builtin_bundles()` during registry initialization rather than via `entry_points`.

| Provider | Manifest factory |
|----------|-----------------|
| AWS | `secretzero.providers.aws:_get_bundle_manifest` |
| Azure | `secretzero.providers.azure:_get_bundle_manifest` |
| Vault | `secretzero.providers.vault:_get_bundle_manifest` |
| GitHub | `secretzero.providers.github:_get_bundle_manifest` |
| GitLab | `secretzero.providers.gitlab:_get_bundle_manifest` |
| Jenkins | `secretzero.providers.jenkins:_get_bundle_manifest` |
| Kubernetes | `secretzero.providers.kubernetes:_get_bundle_manifest` |
| Ansible Vault | `secretzero.providers.ansible_vault:_get_bundle_manifest` |
| SOPS | `secretzero.providers.sops:_get_bundle_manifest` |
| git-crypt | `secretzero.providers.git_crypt:_get_bundle_manifest` |
| Infisical | `secretzero.providers.infisical:_get_bundle_manifest` |

Built-in manifests that set the optional ``terraform_provider`` field
also participate in the :mod:`secretzero.terraform_export` pipeline,
allowing :command:`secretzero terraform` to automatically declare
matching Terraform providers and resource blocks where supported.
