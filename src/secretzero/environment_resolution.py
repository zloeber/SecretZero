"""Environment and target-profile resolution helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from secretzero.models import Secretfile, TargetConfig


@dataclass(frozen=True)
class ResolvedEnvironmentContext:
    """Resolved runtime context for environment-aware execution."""

    selected_environment: str | None
    resolved_var_files: list[Path]
    resolved_lockfile: Path
    resolved_target_profile: str | None
    lockfile_source: str
    var_file_sources: list[str]


def _default_lockfile_for_manifest(secretfile_path: Path) -> Path:
    if secretfile_path.name == "Secretfile.yml":
        return secretfile_path.parent / ".gitsecrets.lock"
    return secretfile_path.parent / f"{secretfile_path.stem}.lock"


def resolve_environment_context(
    *,
    secretfile: Secretfile,
    secretfile_path: Path,
    environment: str | None,
    runtime_var_files: list[Path] | None,
    runtime_lockfile: str | None,
) -> ResolvedEnvironmentContext:
    """Resolve effective lane inputs with runtime-overrides precedence."""
    selected_environment = environment
    env_cfg = secretfile.environments
    if selected_environment is None and env_cfg and env_cfg.default:
        selected_environment = env_cfg.default

    profile = None
    if selected_environment and env_cfg:
        profile = env_cfg.profiles.get(selected_environment)
        if profile is None:
            known = ", ".join(sorted(env_cfg.profiles.keys()))
            raise ValueError(
                f"Unknown environment '{selected_environment}'. Known environments: {known or '[none]'}"
            )
    elif selected_environment and not env_cfg:
        raise ValueError(
            "Environment was provided but this Secretfile has no top-level environments map"
        )

    resolved_var_files: list[Path] = []
    var_file_sources: list[str] = []
    if profile:
        for vf in profile.var_files:
            p = Path(vf)
            if not p.is_absolute():
                p = (secretfile_path.parent / p).resolve()
            resolved_var_files.append(p)
            var_file_sources.append("environment_profile")

    for vf in runtime_var_files or []:
        resolved_var_files.append(vf)
        var_file_sources.append("runtime_flag")

    if runtime_lockfile:
        lockfile_path = Path(runtime_lockfile)
        if not lockfile_path.is_absolute():
            lockfile_path = (secretfile_path.parent / lockfile_path).resolve()
        lockfile_source = "runtime_flag"
    elif profile and profile.lockfile:
        lockfile_path = Path(profile.lockfile)
        if not lockfile_path.is_absolute():
            lockfile_path = (secretfile_path.parent / lockfile_path).resolve()
        lockfile_source = "environment_profile"
    else:
        lockfile_path = _default_lockfile_for_manifest(secretfile_path)
        lockfile_source = "default_derived"

    return ResolvedEnvironmentContext(
        selected_environment=selected_environment,
        resolved_var_files=resolved_var_files,
        resolved_lockfile=lockfile_path,
        resolved_target_profile=(profile.target_profile if profile else None),
        lockfile_source=lockfile_source,
        var_file_sources=var_file_sources,
    )


def _merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        if isinstance(out.get(key), dict) and isinstance(value, dict):
            out[key] = _merge_dict(out[key], value)
        else:
            out[key] = value
    return out


def apply_target_profile(secretfile: Secretfile, profile_name: str | None) -> Secretfile:
    """Return a manifest copy with target profile defaults merged into targets."""
    if not profile_name:
        return secretfile
    profile = secretfile.target_profiles.get(profile_name)
    if profile is None:
        raise ValueError(f"Unknown target profile '{profile_name}'")

    secretfile_copy = secretfile.model_copy(deep=True)
    for secret in secretfile_copy.secrets:
        merged_targets: list[TargetConfig] = []
        for target in secret.targets:
            next_cfg = dict(target.config)
            provider_override = profile.provider_overrides.get(target.provider, {})
            target_override = profile.target_overrides.get(str(target.kind), {})
            if provider_override:
                next_cfg = _merge_dict(next_cfg, provider_override)
            if target_override:
                next_cfg = _merge_dict(next_cfg, target_override)

            identity_policies = list(target.identity_policies)
            for policy in profile.identity_policies:
                if policy not in identity_policies:
                    identity_policies.append(policy)

            merged_targets.append(
                target.model_copy(
                    update={
                        "config": next_cfg,
                        "identity_policies": identity_policies,
                    }
                )
            )
        secret.targets = merged_targets
    return secretfile_copy
