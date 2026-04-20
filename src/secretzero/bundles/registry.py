"""Bundle registry for SecretZero provider bundles.

This module implements the bundle discovery, registration, and lookup
machinery that enables third-party packages to ship their own providers,
generators, and targets as self-contained pip-installable bundles.

Bundles are discovered via Python ``entry_points`` (PEP 621):

.. code-block:: toml

    [project.entry-points."secretzero.providers"]
    myprovider = "myprovider_package:BUNDLE_MANIFEST"

Example bundle manifest:

.. code-block:: python

    from secretzero.bundles import BundleManifest

    BUNDLE_MANIFEST = BundleManifest(
        name="github",
        version="1.0.0",
        provider_class="secretzero.providers.github:GitHubProvider",
        generators={
            "github_pat": "secretzero.generators.github_pat:GitHubPATGenerator",
        },
        targets={
            "github_secret": "secretzero.targets.github:GitHubSecretTarget",
        },
    )
"""

import importlib.metadata
from typing import Any

from pydantic import BaseModel, Field

from secretzero.bundles.loader import load_class_safe


class TerraformProviderConfig(BaseModel):
    """Terraform provider configuration metadata for a bundle.

    This describes how a SecretZero provider maps to a Terraform provider
    block and required_providers entry.

    Attributes:
        name: Terraform provider name used in configuration blocks
            (e.g. ``"aws"``, ``"azurerm"``, ``"vault"``, ``"kubernetes"``).
        source: Optional Terraform Registry source string
            (e.g. ``"hashicorp/aws"``).
        version: Optional version constraint string
            (e.g. ``"~> 5.0"``).
        default_config: Optional default configuration arguments that
            should be emitted in the provider block. These can be
            overridden or extended by the Terraform generator based on
            the Secretfile configuration.
    """

    name: str = Field(description="Terraform provider name (e.g. 'aws', 'azurerm', 'vault')")
    source: str | None = Field(
        default=None,
        description="Terraform Registry source (e.g. 'hashicorp/aws')",
    )
    version: str | None = Field(
        default=None,
        description="Terraform provider version constraint (e.g. '~> 5.0')",
    )
    default_config: dict[str, Any] = Field(
        default_factory=dict,
        description="Default configuration arguments for the provider block",
    )


class BundleManifest(BaseModel):
    """Manifest describing a SecretZero provider bundle.

    A bundle is a pip-installable package that contributes one or more of:
    a provider class, generator kinds, and target kinds to SecretZero.

    Bundles register themselves via Python ``entry_points`` under the
    ``secretzero.providers`` group, and the bundle registry discovers
    them automatically at startup.

    Attributes:
        name: Unique bundle identifier (e.g. ``"github"``, ``"aws"``).
        version: Semantic version string for the bundle.
        provider_class: Dotted path to the provider class
            (``"module.path:ClassName"``), or ``None`` if the bundle
            only contributes generators/targets.
        generators: Mapping of generator kind string to dotted class path.
        targets: Mapping of target kind string to dotted class path.
        generator_kinds: Optional list of new ``GeneratorKind`` enum values
            this bundle declares (informational; enums are open by default).
        target_kinds: Optional list of new ``TargetKind`` enum values this
            bundle declares (informational; enums are open by default).
        terraform_provider: Optional Terraform provider configuration
            metadata used by the Terraform export feature to generate
            ``terraform.required_providers`` and ``provider`` blocks.
    """

    name: str = Field(description="Unique bundle identifier (e.g. 'github', 'aws')")
    version: str = Field(default="1.0.0", description="Bundle version")
    provider_class: str | None = Field(
        default=None,
        description="Dotted path to provider class ('module.path:ClassName')",
    )
    generators: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of generator kind string to dotted class path",
    )
    targets: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of target kind string to dotted class path",
    )
    generator_kinds: list[str] = Field(
        default_factory=list,
        description="New GeneratorKind enum values declared by this bundle",
    )
    target_kinds: list[str] = Field(
        default_factory=list,
        description="New TargetKind enum values declared by this bundle",
    )
    terraform_provider: TerraformProviderConfig | None = Field(
        default=None,
        description=(
            "Optional Terraform provider metadata for this bundle. When set, "
            "the Terraform exporter can automatically declare required_providers "
            "and provider blocks for this bundle."
        ),
    )


class BundleRegistry:
    """Central registry for provider bundles, generators, targets, and providers.

    The registry maps string kind identifiers to their corresponding classes,
    enabling the sync engine to look up implementations without hard-coded
    ``if/elif`` chains.

    Built-in generators, targets, and providers are pre-registered at
    startup.  Third-party bundles are discovered via Python ``entry_points``
    (group ``"secretzero.providers"``).

    Usage::

        registry = get_bundle_registry()
        generator_class = registry.get_generator_class("random_password")
        target_class = registry.get_target_class("github_secret")
        provider_class = registry.get_provider_class("aws")
    """

    def __init__(self) -> None:
        """Initialize an empty bundle registry."""
        self._bundles: dict[str, BundleManifest] = {}
        self._generator_classes: dict[str, type] = {}
        self._target_classes: dict[str, type] = {}
        self._provider_classes: dict[str, type] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_bundle(self, manifest: BundleManifest) -> None:
        """Register all classes declared in a bundle manifest.

        Classes that cannot be imported (e.g. missing optional dependency)
        are silently skipped for graceful degradation.

        Args:
            manifest: The bundle manifest to register.
        """
        self._bundles[manifest.name] = manifest

        if manifest.provider_class:
            cls = load_class_safe(manifest.provider_class)
            if cls is not None:
                self._provider_classes[manifest.name] = cls

        for kind, path in manifest.generators.items():
            cls = load_class_safe(path)
            if cls is not None:
                self._generator_classes[kind] = cls

        for kind, path in manifest.targets.items():
            cls = load_class_safe(path)
            if cls is not None:
                self._target_classes[kind] = cls

    def register_generator(self, kind: str, cls: type) -> None:
        """Directly register a generator class by kind.

        Args:
            kind: Generator kind identifier (e.g. ``"random_password"``).
            cls: Generator class to register.
        """
        self._generator_classes[kind] = cls

    def register_target(self, kind: str, cls: type) -> None:
        """Directly register a target class by kind.

        Args:
            kind: Target kind identifier (e.g. ``"file"``).
            cls: Target class to register.
        """
        self._target_classes[kind] = cls

    def register_provider(self, kind: str, cls: type) -> None:
        """Directly register a provider class by kind.

        Args:
            kind: Provider kind identifier (e.g. ``"aws"``).
            cls: Provider class to register.
        """
        self._provider_classes[kind] = cls

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover_and_register(self) -> None:
        """Auto-discover installed bundles via Python ``entry_points``.

        Iterates over all packages that have registered an entry point
        under the ``"secretzero.providers"`` group.  Each entry point
        value must be a :class:`BundleManifest` instance; others are
        silently skipped.
        """
        for ep in importlib.metadata.entry_points(group="secretzero.providers"):
            try:
                manifest = ep.load()
                if isinstance(manifest, BundleManifest):
                    self.register_bundle(manifest)
            except Exception:
                pass  # graceful degradation: never crash on bad bundles

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    def get_generator_class(self, kind: str) -> type | None:
        """Return the generator class for *kind*, or ``None`` if unknown.

        Args:
            kind: Generator kind string (e.g. ``"random_password"``).

        Returns:
            Generator class or ``None``.
        """
        return self._generator_classes.get(kind)

    def get_target_class(self, kind: str) -> type | None:
        """Return the target class for *kind*, or ``None`` if unknown.

        Args:
            kind: Target kind string (e.g. ``"github_secret"``).

        Returns:
            Target class or ``None``.
        """
        return self._target_classes.get(kind)

    def get_provider_class(self, kind: str) -> type | None:
        """Return the provider class for *kind*, or ``None`` if unknown.

        Args:
            kind: Provider kind string (e.g. ``"aws"``).

        Returns:
            Provider class or ``None``.
        """
        return self._provider_classes.get(kind)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_bundles(self) -> list[str]:
        """Return a sorted list of all registered bundle names.

        Returns:
            Sorted list of bundle name strings.
        """
        return sorted(self._bundles.keys())

    def list_generator_kinds(self) -> list[str]:
        """Return a sorted list of all registered generator kind strings.

        Returns:
            Sorted list of generator kind strings.
        """
        return sorted(self._generator_classes.keys())

    def list_target_kinds(self) -> list[str]:
        """Return a sorted list of all registered target kind strings.

        Returns:
            Sorted list of target kind strings.
        """
        return sorted(self._target_classes.keys())

    def list_provider_kinds(self) -> list[str]:
        """Return a sorted list of all registered provider kind strings.

        Returns:
            Sorted list of provider kind strings.
        """
        return sorted(self._provider_classes.keys())

    def get_bundle(self, name: str) -> BundleManifest | None:
        """Return the manifest for a registered bundle, or ``None``.

        Args:
            name: Bundle name.

        Returns:
            BundleManifest or ``None``.
        """
        return self._bundles.get(name)

    def validate_bundle_manifest(self, manifest: BundleManifest) -> list[str]:
        """Validate that all dotted paths in a manifest can be resolved.

        Checks that each declared class path is importable, inherits from
        the appropriate base class, and is callable.

        Args:
            manifest: The manifest to validate.

        Returns:
            List of error strings.  An empty list means the manifest is valid.
        """
        from secretzero.bundles.loader import load_class
        from secretzero.generators.base import BaseGenerator
        from secretzero.providers.base import BaseProvider
        from secretzero.targets.base import BaseTarget

        errors: list[str] = []

        if manifest.provider_class:
            try:
                cls = load_class(manifest.provider_class)
                if not (isinstance(cls, type) and issubclass(cls, BaseProvider)):
                    errors.append(
                        f"provider_class '{manifest.provider_class}' must subclass BaseProvider"
                    )
            except (ImportError, AttributeError, ValueError) as exc:
                errors.append(f"provider_class '{manifest.provider_class}': {exc}")

        for kind, path in manifest.generators.items():
            try:
                cls = load_class(path)
                if not (isinstance(cls, type) and issubclass(cls, BaseGenerator)):
                    errors.append(f"generator '{kind}' path '{path}' must subclass BaseGenerator")
            except (ImportError, AttributeError, ValueError) as exc:
                errors.append(f"generator '{kind}' path '{path}': {exc}")

        for kind, path in manifest.targets.items():
            try:
                cls = load_class(path)
                if not (isinstance(cls, type) and issubclass(cls, BaseTarget)):
                    errors.append(f"target '{kind}' path '{path}' must subclass BaseTarget")
            except (ImportError, AttributeError, ValueError) as exc:
                errors.append(f"target '{kind}' path '{path}': {exc}")

        return errors


# ---------------------------------------------------------------------------
# Singleton + bootstrap
# ---------------------------------------------------------------------------

_bundle_registry: BundleRegistry | None = None


def get_bundle_registry() -> BundleRegistry:
    """Return the global :class:`BundleRegistry` singleton.

    On first call the registry is populated with all built-in generators,
    targets, and providers, then third-party bundles discovered via
    ``entry_points`` are registered.

    Returns:
        Global BundleRegistry instance.
    """
    global _bundle_registry
    if _bundle_registry is None:
        _bundle_registry = BundleRegistry()
        _register_builtin_generators(_bundle_registry)
        _register_builtin_targets(_bundle_registry)
        _register_builtin_providers(_bundle_registry)
        _register_builtin_bundles(_bundle_registry)
        _bundle_registry.discover_and_register()
    return _bundle_registry


def discover_bundles() -> list[BundleManifest]:
    """Discover all installed provider bundles via ``entry_points``.

    Returns:
        List of :class:`BundleManifest` instances found on the system.
    """
    bundles: list[BundleManifest] = []
    for ep in importlib.metadata.entry_points(group="secretzero.providers"):
        try:
            manifest = ep.load()
            if isinstance(manifest, BundleManifest):
                bundles.append(manifest)
        except Exception:
            pass
    return bundles


# ---------------------------------------------------------------------------
# Built-in registration helpers
# ---------------------------------------------------------------------------


def _register_builtin_generators(registry: BundleRegistry) -> None:
    """Populate *registry* with all built-in generator classes."""
    _builtin_generators: list[tuple[str, str, str]] = [
        ("random_password", "secretzero.generators.random_password", "RandomPasswordGenerator"),
        ("random_string", "secretzero.generators.random_string", "RandomStringGenerator"),
        ("static", "secretzero.generators.static", "StaticGenerator"),
        ("script", "secretzero.generators.script", "ScriptGenerator"),
        ("provider_backed", "secretzero.generators.provider_backed", "ProviderBackedGenerator"),
        # github_pat is registered via the GitHub BundleManifest
    ]
    for kind, module_path, class_name in _builtin_generators:
        try:
            import importlib as _importlib

            mod = _importlib.import_module(module_path)
            cls: type = getattr(mod, class_name)
            registry.register_generator(kind, cls)
        except (ImportError, AttributeError):
            pass


def _register_builtin_targets(registry: BundleRegistry) -> None:
    """Populate *registry* with all built-in target classes."""
    _builtin_targets: list[tuple[str, str, str]] = [
        # Core targets (not tied to a specific provider)
        ("file", "secretzero.targets.file", "FileTarget"),
        ("template", "secretzero.targets.template", "TemplateTarget"),
        # All provider-specific targets are registered via BundleManifests
    ]
    for kind, module_path, class_name in _builtin_targets:
        try:
            import importlib as _importlib

            mod = _importlib.import_module(module_path)
            cls = getattr(mod, class_name)
            registry.register_target(kind, cls)
        except (ImportError, AttributeError):
            pass


def _register_builtin_providers(registry: BundleRegistry) -> None:
    """Populate *registry* with all built-in provider classes."""
    _builtin_providers: list[tuple[str, str, str]] = [
        # All providers are now registered via BundleManifests
    ]
    for kind, module_path, class_name in _builtin_providers:
        try:
            import importlib as _importlib

            mod = _importlib.import_module(module_path)
            cls = getattr(mod, class_name)
            registry.register_provider(kind, cls)
        except (ImportError, AttributeError):
            pass


def _register_builtin_bundles(registry: BundleRegistry) -> None:
    """Register built-in providers that ship as self-contained bundle manifests.

    These providers can be extracted into standalone pip-installable packages
    by simply moving the code and registering via ``entry_points`` instead.
    """
    _manifest_factories: list[tuple[str, str]] = [
        # (module_path, factory_function_name)
        ("secretzero.providers.aws", "_get_bundle_manifest"),
        ("secretzero.providers.azure", "_get_bundle_manifest"),
        ("secretzero.providers.vault", "_get_bundle_manifest"),
        ("secretzero.providers.github", "_get_bundle_manifest"),
        ("secretzero.providers.gitlab", "_get_bundle_manifest"),
        ("secretzero.providers.jenkins", "_get_bundle_manifest"),
        ("secretzero.providers.kubernetes", "_get_bundle_manifest"),
        ("secretzero.providers.ansible_vault", "_get_bundle_manifest"),
        ("secretzero.providers.infisical", "_get_bundle_manifest"),
        ("secretzero.providers.entra_agent_id", "_get_bundle_manifest"),
    ]
    for module_path, factory_name in _manifest_factories:
        try:
            import importlib as _importlib

            mod = _importlib.import_module(module_path)
            factory = getattr(mod, factory_name)
            manifest: BundleManifest = factory()
            registry.register_bundle(manifest)
        except (ImportError, AttributeError):
            pass


def reset_bundle_registry() -> None:
    """Reset the global bundle registry singleton (for testing only).

    After calling this, the next call to :func:`get_bundle_registry` will
    create a fresh registry and re-run discovery.
    """
    global _bundle_registry
    _bundle_registry = None


# Re-export public API
__all__ = [
    "TerraformProviderConfig",
    "BundleManifest",
    "BundleRegistry",
    "get_bundle_registry",
    "discover_bundles",
    "reset_bundle_registry",
]
