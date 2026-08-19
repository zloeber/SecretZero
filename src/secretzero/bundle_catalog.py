"""Machine-complete catalog of SecretZero generators, targets, and provider bundles."""

from __future__ import annotations

from typing import Any

from secretzero import __version__
from secretzero.bundles.registry import BundleManifest, BundleRegistry, get_bundle_registry

_CORE_BUNDLE = "core"
_LOCAL_BUNDLE = "local"

# Heuristic defaults for authoring: which generators commonly pair with a target.
_TYPICAL_GENERATORS_BY_TARGET: dict[str, list[str]] = {
    "file": ["random_password", "random_string", "static", "script"],
    "template": ["random_password", "random_string", "static", "script"],
    "github_secret": ["random_password", "random_string", "static", "github_pat"],
    "gitlab_variable": [
        "random_password",
        "random_string",
        "static",
        "gitlab_project_token",
        "gitlab_group_token",
    ],
    "gitlab_group_variable": [
        "random_password",
        "random_string",
        "static",
        "gitlab_group_token",
        "gitlab_group_service_account",
    ],
    "jenkins_credential": ["random_password", "random_string", "static"],
    "kubernetes_secret": ["random_password", "random_string", "static"],
    "external_secret": ["random_password", "random_string", "static"],
    "vercel_env": ["random_password", "random_string", "static"],
    "keeper_record": ["random_password", "random_string", "static"],
    "sops_file": ["random_password", "random_string", "static"],
    "git_crypt_file": ["random_password", "random_string", "static"],
    "ansible_vault_file": ["random_password", "random_string", "static"],
}


def _class_description(cls: type | None) -> str | None:
    if cls is None:
        return None
    doc = (cls.__doc__ or "").strip()
    return doc.split("\n")[0] if doc else None


def _class_path(cls: type | None) -> str | None:
    if cls is None:
        return None
    return f"{cls.__module__}:{cls.__qualname__}"


def _generator_entry(
    registry: BundleRegistry,
    kind: str,
    *,
    bundle: str | None,
    generator_details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cls = registry.get_generator_class(kind)
    details = (generator_details or {}).get(kind, {})
    entry: dict[str, Any] = {
        "kind": kind,
        "bundle": bundle,
        "class_path": _class_path(cls),
        "description": _class_description(cls),
        "loaded": cls is not None,
    }
    if details.get("description"):
        entry["description"] = details["description"]
    if details.get("config"):
        entry["config"] = details["config"]
    if details.get("example"):
        entry["example"] = details["example"]
    if cls is not None:
        provider_key = getattr(cls, "PROVIDER_CONFIG_KEY", None)
        if provider_key:
            entry["provider_config_key"] = provider_key
        if getattr(cls, "PROMPTS_LIKE_STATIC", False):
            entry["prompts_like_static"] = True
    return entry


def _target_entry(
    registry: BundleRegistry,
    kind: str,
    *,
    bundle: str | None,
    provider_kind: str | None = None,
    target_details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cls = registry.get_target_class(kind)
    details = (target_details or {}).get(kind, {})
    entry: dict[str, Any] = {
        "kind": kind,
        "bundle": bundle,
        "provider_kind": provider_kind,
        "class_path": _class_path(cls),
        "description": details.get("description") or _class_description(cls),
        "loaded": cls is not None,
        "typical_generators": _TYPICAL_GENERATORS_BY_TARGET.get(
            kind, ["random_password", "random_string", "static"]
        ),
    }
    config = details.get("config")
    if config:
        entry["config"] = config
    example = details.get("example")
    if example:
        entry["example"] = example
    return entry


def _provider_entry(provider_class: type | None) -> dict[str, Any]:
    if provider_class is None:
        return {"loaded": False}
    required = getattr(provider_class, "required_package", None)
    required_package: str | None
    if isinstance(required, tuple):
        required_package = (
            f"{required[0]} ({required[1]})" if len(required) > 1 else str(required[0])
        )
    elif isinstance(required, str):
        required_package = required
    else:
        required_package = None
    return {
        "display_name": getattr(provider_class, "display_name", None),
        "description": getattr(provider_class, "description", None),
        "auth_methods": getattr(provider_class, "auth_methods", None) or {},
        "config_options": getattr(provider_class, "config_options", None) or {},
        "required_package": required_package,
        "class_path": _class_path(provider_class),
        "loaded": True,
    }


def _kind_bundle_maps(
    registry: BundleRegistry,
) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """Map generator/target kinds and provider kinds to bundle names."""
    generator_bundles: dict[str, str] = {}
    target_bundles: dict[str, str] = {}
    provider_bundles: dict[str, str] = {}
    for bundle_name in registry.list_bundles():
        manifest = registry.get_bundle(bundle_name)
        if manifest is None:
            continue
        for kind in manifest.generators:
            generator_bundles[kind] = bundle_name
        for kind in manifest.targets:
            target_bundles[kind] = bundle_name
        if manifest.provider_class:
            provider_bundles[bundle_name] = bundle_name
    return generator_bundles, target_bundles, provider_bundles


def _local_bundle_manifest() -> dict[str, Any]:
    return {
        "name": _LOCAL_BUNDLE,
        "version": "builtin",
        "provider_kind": _LOCAL_BUNDLE,
        "provider": {
            "display_name": "Local Filesystem",
            "description": "Local file and template targets",
            "auth_methods": {"none": "No authentication required"},
            "config_options": {"base_path": "Base directory for files (default: .)"},
            "loaded": True,
        },
        "generator_kinds": [],
        "target_kinds": ["file", "template"],
    }


def build_bundle_catalog(
    registry: BundleRegistry | None = None,
    *,
    bundle: str | None = None,
    provider_kind: str | None = None,
    kind: str | None = None,
    kind_type: str | None = None,
) -> dict[str, Any]:
    """Build a machine-readable catalog from the live bundle registry.

    Args:
        registry: Bundle registry instance (defaults to global singleton).
        bundle: Optional bundle name filter.
        provider_kind: Optional provider kind filter (bundle name for provider bundles).
        kind: Optional generator or target kind filter.
        kind_type: When ``kind`` is set, restrict to ``generator`` or ``target``.

    Returns:
        Catalog dictionary suitable for JSON/YAML serialization.
    """
    registry = registry or get_bundle_registry()
    generator_bundles, target_bundles, _provider_bundles = _kind_bundle_maps(registry)

    generators: list[dict[str, Any]] = []
    for gen_kind in registry.list_generator_kinds():
        bundle_name = generator_bundles.get(gen_kind, _CORE_BUNDLE)
        provider_cls = (
            registry.get_provider_class(bundle_name)
            if bundle_name not in (_CORE_BUNDLE, _LOCAL_BUNDLE)
            else None
        )
        generator_details = (
            getattr(provider_cls, "generator_details", None) if provider_cls else None
        )
        generators.append(
            _generator_entry(
                registry,
                gen_kind,
                bundle=bundle_name,
                generator_details=generator_details,
            )
        )

    targets: list[dict[str, Any]] = []
    for target_kind in registry.list_target_kinds():
        bundle_name = target_bundles.get(target_kind, _LOCAL_BUNDLE)
        provider_cls = (
            registry.get_provider_class(bundle_name)
            if bundle_name not in (_CORE_BUNDLE, _LOCAL_BUNDLE)
            else None
        )
        target_details = getattr(provider_cls, "target_details", None) if provider_cls else None
        targets.append(
            _target_entry(
                registry,
                target_kind,
                bundle=bundle_name,
                provider_kind=(
                    bundle_name
                    if bundle_name not in (_CORE_BUNDLE, _LOCAL_BUNDLE)
                    else _LOCAL_BUNDLE
                ),
                target_details=target_details,
            )
        )

    bundles: list[dict[str, Any]] = []
    for bundle_name in registry.list_bundles():
        manifest = registry.get_bundle(bundle_name)
        if manifest is None:
            continue
        provider_cls = registry.get_provider_class(bundle_name)
        bundles.append(_bundle_catalog_entry(registry, manifest, provider_cls))

    bundles.append(
        {
            **_local_bundle_manifest(),
            "targets": [
                _target_entry(registry, "file", bundle=_LOCAL_BUNDLE, provider_kind=_LOCAL_BUNDLE),
                _target_entry(
                    registry, "template", bundle=_LOCAL_BUNDLE, provider_kind=_LOCAL_BUNDLE
                ),
            ],
            "generators": [],
        }
    )

    core_generators = [
        _generator_entry(registry, gen_kind, bundle=_CORE_BUNDLE)
        for gen_kind in registry.list_generator_kinds()
        if gen_kind not in generator_bundles
    ]
    if core_generators:
        bundles.insert(
            0,
            {
                "name": _CORE_BUNDLE,
                "version": "builtin",
                "provider_kind": None,
                "provider": None,
                "generator_kinds": [g["kind"] for g in core_generators],
                "target_kinds": [],
                "generators": core_generators,
                "targets": [],
            },
        )

    catalog: dict[str, Any] = {
        "secretzero_version": __version__,
        "generator_kinds": [g["kind"] for g in generators],
        "target_kinds": [t["kind"] for t in targets],
        "generators": generators,
        "targets": targets,
        "bundles": bundles,
    }

    if bundle:
        catalog["bundles"] = [b for b in catalog["bundles"] if b.get("name") == bundle]
        allowed_generators = {
            g["kind"] for b in catalog["bundles"] for g in b.get("generators", [])
        }
        allowed_targets = {t["kind"] for b in catalog["bundles"] for t in b.get("targets", [])}
        catalog["generators"] = [g for g in generators if g["kind"] in allowed_generators]
        catalog["targets"] = [t for t in targets if t["kind"] in allowed_targets]
        catalog["generator_kinds"] = [g["kind"] for g in catalog["generators"]]
        catalog["target_kinds"] = [t["kind"] for t in catalog["targets"]]

    if provider_kind:
        catalog["bundles"] = [
            b
            for b in catalog["bundles"]
            if b.get("provider_kind") == provider_kind or b.get("name") == provider_kind
        ]
        allowed_generators = {
            g["kind"] for b in catalog["bundles"] for g in b.get("generators", [])
        }
        allowed_targets = {t["kind"] for b in catalog["bundles"] for t in b.get("targets", [])}
        catalog["generators"] = [
            g for g in catalog["generators"] if g["kind"] in allowed_generators
        ]
        catalog["targets"] = [t for t in catalog["targets"] if t["kind"] in allowed_targets]
        catalog["generator_kinds"] = [g["kind"] for g in catalog["generators"]]
        catalog["target_kinds"] = [t["kind"] for t in catalog["targets"]]

    if kind:
        if kind_type == "generator":
            catalog["generators"] = [g for g in catalog["generators"] if g["kind"] == kind]
            catalog["targets"] = []
        elif kind_type == "target":
            catalog["targets"] = [t for t in catalog["targets"] if t["kind"] == kind]
            catalog["generators"] = []
        else:
            catalog["generators"] = [g for g in catalog["generators"] if g["kind"] == kind]
            catalog["targets"] = [t for t in catalog["targets"] if t["kind"] == kind]
        catalog["generator_kinds"] = [g["kind"] for g in catalog["generators"]]
        catalog["target_kinds"] = [t["kind"] for t in catalog["targets"]]

    return catalog


def _bundle_catalog_entry(
    registry: BundleRegistry,
    manifest: BundleManifest,
    provider_cls: type | None,
) -> dict[str, Any]:
    target_details = getattr(provider_cls, "target_details", None) if provider_cls else None
    generator_details = getattr(provider_cls, "generator_details", None) if provider_cls else None
    generators = [
        _generator_entry(
            registry,
            kind,
            bundle=manifest.name,
            generator_details=generator_details,
        )
        for kind in sorted(manifest.generators)
    ]
    targets = [
        _target_entry(
            registry,
            kind,
            bundle=manifest.name,
            provider_kind=manifest.name,
            target_details=target_details,
        )
        for kind in sorted(manifest.targets)
    ]
    return {
        "name": manifest.name,
        "version": manifest.version,
        "provider_kind": manifest.name,
        "provider": _provider_entry(provider_cls),
        "generator_kinds": sorted(manifest.generators.keys()),
        "target_kinds": sorted(manifest.targets.keys()),
        "generators": generators,
        "targets": targets,
    }


def find_catalog_entry(
    catalog: dict[str, Any],
    kind: str,
) -> dict[str, Any] | None:
    """Return a generator or target catalog entry by kind."""
    for entry in catalog.get("generators", []):
        if entry.get("kind") == kind:
            return {"type": "generator", **entry}
    for entry in catalog.get("targets", []):
        if entry.get("kind") == kind:
            return {"type": "target", **entry}
    return None
