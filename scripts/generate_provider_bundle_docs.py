#!/usr/bin/env python3
"""Generate auto-reference docs for registered provider bundles."""

from __future__ import annotations

import argparse
from pathlib import Path

from secretzero.bundles.registry import BundleManifest, get_bundle_registry


def _fmt_required_package(manifest: BundleManifest, provider_cls: type | None) -> str:
    if provider_cls is None:
        return "n/a (provider class unavailable)"
    required = getattr(provider_cls, "required_package", None)
    if not required:
        return "None"
    import_name, install_hint = required
    return f"`{import_name}` (`{install_hint}`)"


def _fmt_auth_methods(provider_cls: type | None) -> str:
    if provider_cls is None:
        return "n/a"
    methods = getattr(provider_cls, "auth_methods", {}) or {}
    if not methods:
        return "None declared"
    return ", ".join(f"`{m}`" for m in sorted(methods.keys()))


def _fmt_target_kinds(manifest: BundleManifest) -> str:
    target_kinds = sorted(manifest.targets.keys())
    if not target_kinds:
        target_kinds = sorted(manifest.target_kinds)
    if not target_kinds:
        return "None"
    return ", ".join(f"`{k}`" for k in target_kinds)


def build_markdown() -> str:
    reg = get_bundle_registry()
    bundles = sorted(reg.list_bundles())

    lines: list[str] = []
    lines.append("# Provider Bundles (Auto-Generated)")
    lines.append("")
    lines.append(
        "This page is generated from the live `BundleRegistry` and provider class metadata."
    )
    lines.append("It complements the hand-written workflow pages under `user-guide/providers/*`.")
    lines.append("")
    lines.append("## Provider Bundle Matrix")
    lines.append("")
    lines.append(
        "| Bundle | Version | Provider kind | Provider class path | Target kinds | Auth methods | Required dependency |"
    )
    lines.append("|---|---|---|---|---|---|---|")

    for bundle_name in bundles:
        manifest = reg.get_bundle(bundle_name)
        if manifest is None:
            continue
        provider_kind = manifest.name if manifest.provider_class else "(none)"
        provider_cls = reg.get_provider_class(provider_kind) if manifest.provider_class else None
        provider_path = f"`{manifest.provider_class}`" if manifest.provider_class else "n/a"
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{manifest.name}`",
                    f"`{manifest.version}`",
                    f"`{provider_kind}`" if manifest.provider_class else "n/a",
                    provider_path,
                    _fmt_target_kinds(manifest),
                    _fmt_auth_methods(provider_cls),
                    _fmt_required_package(manifest, provider_cls),
                ]
            )
            + " |"
        )

    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append(
        "- Discovery includes built-in bundle manifests and any installed third-party entry points."
    )
    lines.append("- Missing optional dependencies can prevent provider classes from loading.")
    lines.append("- Regenerate via `task docs:generate:provider-bundles`.")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate provider bundle auto-reference docs")
    parser.add_argument(
        "--output",
        default="docs/reference/provider-bundles-auto.md",
        help="Output markdown file path",
    )
    args = parser.parse_args()
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_markdown())
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
