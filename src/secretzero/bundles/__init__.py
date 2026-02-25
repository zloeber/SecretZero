"""SecretZero provider bundle framework.

This package implements the bundle architecture for third-party providers,
generators, and targets.  A *bundle* is a pip-installable package that can
contribute any combination of:

* A :class:`~secretzero.providers.base.BaseProvider` subclass
* One or more :class:`~secretzero.generators.base.BaseGenerator` subclasses
  mapped to new generator *kind* strings
* One or more :class:`~secretzero.targets.base.BaseTarget` subclasses
  mapped to new target *kind* strings

Bundles are discovered automatically via Python ``entry_points`` under the
``"secretzero.providers"`` group.  The entry-point value must be a
:class:`BundleManifest` instance exported from the bundle package.

Quick start for bundle authors::

    # my_bundle/__init__.py
    from secretzero.bundles import BundleManifest

    BUNDLE_MANIFEST = BundleManifest(
        name="myprovider",
        version="1.0.0",
        provider_class="my_bundle.provider:MyProvider",
        generators={
            "my_token": "my_bundle.generators:MyTokenGenerator",
        },
        targets={
            "my_vault": "my_bundle.targets:MyVaultTarget",
        },
    )

    # pyproject.toml
    [project.entry-points."secretzero.providers"]
    myprovider = "my_bundle:BUNDLE_MANIFEST"
"""

from secretzero.bundles.loader import load_class, load_class_safe
from secretzero.bundles.registry import (
    BundleManifest,
    BundleRegistry,
    discover_bundles,
    get_bundle_registry,
    reset_bundle_registry,
)

__all__ = [
    "BundleManifest",
    "BundleRegistry",
    "discover_bundles",
    "get_bundle_registry",
    "load_class",
    "load_class_safe",
    "reset_bundle_registry",
]
