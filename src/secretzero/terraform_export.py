"""Terraform export utilities for SecretZero.

This module translates a :class:`secretzero.models.Secretfile` into a
Terraform configuration model that can be emitted as HCL2 (``.tf``) or
Terraform JSON (``.tf.json``).

The mapping is intentionally conservative and focuses on:

* Secret generators that correspond to Terraform's ``random`` provider.
* Provider/target pairs that map cleanly onto well-known Terraform
  resources (initially AWS, Azure Key Vault, and HashiCorp Vault).
* Provider bundle metadata declared via
  :class:`secretzero.bundles.registry.TerraformProviderConfig`.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from secretzero.bundles import get_bundle_registry
from secretzero.bundles.registry import BundleRegistry, TerraformProviderConfig
from secretzero.generators.traits import secret_prompts_like_static
from secretzero.hcl_values import format_hcl_string
from secretzero.models import Secret, Secretfile, TargetConfig


class TerraformOutputFormat(str, Enum):
    """Supported Terraform output formats."""

    HCL = "hcl"
    JSON = "json"


class TerraformRequiredProvider(BaseModel):
    """Entry in ``terraform.required_providers``."""

    name: str
    source: str | None = None
    version: str | None = None


class TerraformProviderBlock(BaseModel):
    """Single ``provider`` block."""

    name: str
    config: dict[str, Any] = Field(default_factory=dict)


class TerraformResource(BaseModel):
    """Terraform ``resource`` block."""

    type: str
    name: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class TerraformProject(BaseModel):
    """In-memory Terraform project representation."""

    required_providers: dict[str, TerraformRequiredProvider] = Field(default_factory=dict)
    providers: list[TerraformProviderBlock] = Field(default_factory=list)
    resources: list[TerraformResource] = Field(default_factory=list)
    variables: dict[str, dict[str, Any]] = Field(default_factory=dict)
    outputs: dict[str, dict[str, Any]] = Field(default_factory=dict)

    def to_json_dict(self) -> dict[str, Any]:
        """Convert project to a Terraform JSON-compatible dict."""

        terraform_block: dict[str, Any] = {}
        if self.required_providers:
            terraform_block["required_providers"] = {
                rp.name: {
                    **({"source": rp.source} if rp.source else {}),
                    **({"version": rp.version} if rp.version else {}),
                }
                for rp in self.required_providers.values()
            }

        provider_block: dict[str, Any] = {}
        for p in self.providers:
            provider_block.setdefault(p.name, []).append(p.config or {})

        resource_block: dict[str, Any] = {}
        for r in self.resources:
            by_name = resource_block.setdefault(r.type, {})
            by_name[r.name] = r.attributes or {}

        data: dict[str, Any] = {}
        if terraform_block:
            data["terraform"] = terraform_block
        if provider_block:
            data["provider"] = provider_block
        if resource_block:
            data["resource"] = resource_block
        if self.variables:
            data["variable"] = self.variables
        if self.outputs:
            data["output"] = self.outputs

        return data

    def _hcl_value(self, value: Any, indent: int = 2) -> str:
        """Render a Python value as HCL.

        Strings that use legacy interpolation syntax (``${ ... }``) are
        rendered as bare expressions without the wrapping interpolation
        markers so that modern HCL2-style expressions are used.
        """

        ind = " " * indent

        # Terraform expression expressed with legacy ${...} interpolation
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            # Strip the interpolation wrapper and emit the inner expression
            return value[2:-1].strip()

        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str):
            return format_hcl_string(value)
        if isinstance(value, list):
            inner = ", ".join(self._hcl_value(v, indent=0) for v in value)
            return f"[{inner}]"
        if isinstance(value, dict):
            parts: list[str] = []
            for k, v in value.items():
                parts.append(f"{ind}{k} = {self._hcl_value(v, indent + 2)}")
            return "{\n" + "\n".join(parts) + "\n" + (" " * (indent - 2)) + "}"

        return json.dumps(value)

    def to_hcl(self) -> str:
        """Render project as a single HCL string."""

        lines: list[str] = []

        # terraform.required_providers
        if self.required_providers:
            lines.append("terraform {")
            lines.append("  required_providers {")
            for rp in self.required_providers.values():
                lines.append(f"    {rp.name} = {{")
                if rp.source:
                    lines.append(f'      source  = "{rp.source}"')
                if rp.version:
                    lines.append(f'      version = "{rp.version}"')
                lines.append("    }")
            lines.append("  }")
            lines.append("}")
            lines.append("")

        # provider blocks
        for p in self.providers:
            lines.append(f'provider "{p.name}" {{')
            for key, value in p.config.items():
                lines.append(f"  {key} = {self._hcl_value(value, indent=4)}")
            lines.append("}")
            lines.append("")

        # variable blocks
        for name, body in self.variables.items():
            lines.append(f'variable "{name}" {{')
            for key, value in body.items():
                lines.append(f"  {key} = {self._hcl_value(value, indent=4)}")
            lines.append("}")
            lines.append("")

        # resource blocks
        for r in self.resources:
            lines.append(f'resource "{r.type}" "{r.name}" {{')
            for key, value in r.attributes.items():
                lines.append(f"  {key} = {self._hcl_value(value, indent=4)}")
            lines.append("}")
            lines.append("")

        # outputs
        for name, body in self.outputs.items():
            lines.append(f'output "{name}" {{')
            for key, value in body.items():
                lines.append(f"  {key} = {self._hcl_value(value, indent=4)}")
            lines.append("}")
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"

    def write_files(self, output_dir: Path, fmt: TerraformOutputFormat) -> list[Path]:
        """Write Terraform configuration files to *output_dir*."""

        output_dir.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []

        if fmt == TerraformOutputFormat.JSON:
            path = output_dir / "main.tf.json"
            path.write_text(json.dumps(self.to_json_dict(), indent=2))
            written.append(path)
        else:
            path = output_dir / "main.tf"
            path.write_text(self.to_hcl())
            written.append(path)

        return written


class TerraformGeneratorOptions(BaseModel):
    """Options controlling Terraform generation."""

    output_dir: Path
    format: TerraformOutputFormat = TerraformOutputFormat.HCL
    module_name: str = "secretzero_secrets"
    include_static_secrets: bool = False


def _sanitize_name(name: str) -> str:
    """Convert an arbitrary name into a valid Terraform identifier."""

    safe = []
    for ch in name:
        if ch.isalnum() or ch == "_":
            safe.append(ch)
        else:
            safe.append("_")
    result = "".join(safe)
    if not result:
        result = "secret"
    if result[0].isdigit():
        result = f"s_{result}"
    return result


def _ensure_random_required_provider(project: TerraformProject, in_use: bool) -> None:
    """Register the ``random`` provider if any random_* generators are used."""

    if not in_use:
        return
    if "random" in project.required_providers:
        return
    project.required_providers["random"] = TerraformRequiredProvider(
        name="random",
        source="hashicorp/random",
        version="~> 3.0",
    )


def _populate_required_providers_from_bundles(
    project: TerraformProject,
    provider_names: Iterable[str],
    registry: BundleRegistry,
    secretfile: Secretfile,
) -> None:
    """Populate required_providers and provider blocks from bundle manifests."""

    seen: set[str] = set()
    for provider_name in provider_names:
        if provider_name in seen:
            continue
        seen.add(provider_name)

        manifest = registry.get_bundle(provider_name)
        if manifest is None or manifest.terraform_provider is None:
            continue

        tp: TerraformProviderConfig = manifest.terraform_provider

        if tp.name not in project.required_providers:
            project.required_providers[tp.name] = TerraformRequiredProvider(
                name=tp.name,
                source=tp.source,
                version=tp.version,
            )

        provider_cfg: dict[str, Any] = dict(tp.default_config)
        provider_model = secretfile.providers.get(provider_name)
        if provider_model is not None:
            cfg = provider_model.config or {}
            if tp.name == "aws":
                region = cfg.get("region")
                if region:
                    provider_cfg.setdefault("region", region)

        project.providers.append(
            TerraformProviderBlock(
                name=tp.name,
                config=provider_cfg,
            )
        )


def _build_generator_expression(
    secret: Secret,
    project: TerraformProject,
    options: TerraformGeneratorOptions,
    random_in_use_flag: dict[str, bool],
) -> str | None:
    """Create generator resources and return the expression for secret value."""

    kind = secret.kind
    safe_name = _sanitize_name(secret.name)

    if kind in {"random_password", "random_string"}:
        random_in_use_flag["used"] = True
        res_type = kind
        attrs: dict[str, Any] = {}

        length = secret.config.get("length")
        if isinstance(length, int):
            attrs["length"] = length

        if kind == "random_password":
            for src_key, dst_key in [
                ("special", "special"),
                ("uppercase", "upper"),
                ("lowercase", "lower"),
                ("digits", "numeric"),
            ]:
                if src_key in secret.config:
                    attrs[dst_key] = bool(secret.config.get(src_key))

            exclude = secret.config.get("exclude_characters")
            if isinstance(exclude, str) and exclude:
                attrs["override_special"] = exclude

        resource = TerraformResource(type=res_type, name=safe_name, attributes=attrs)
        project.resources.append(resource)
        return f"${{{res_type}.{safe_name}.result}}"

    if secret_prompts_like_static(secret, registry=get_bundle_registry()):
        var_name = f"secret_{safe_name}"
        static_default = secret.config.get("default", secret.config.get("value"))
        variable_body: dict[str, Any] = {
            "description": f"Value for static secret '{secret.name}'.",
            "sensitive": True,
        }
        if isinstance(static_default, (dict, list)):
            variable_body["type"] = "any"
        else:
            variable_body["type"] = "string"
        if options.include_static_secrets and static_default is not None:
            variable_body["default"] = static_default
        project.variables.setdefault(var_name, variable_body)
        return f"${{var.{var_name}}}"

    return None


def _map_target_to_resources(
    secret: Secret,
    target: TargetConfig,
    value_expr: str | None,
    project: TerraformProject,
) -> None:
    """Map a SecretZero target to one or more Terraform resources."""

    provider = target.provider
    kind = str(target.kind)
    cfg = target.config or {}
    safe_secret_name = _sanitize_name(secret.name)

    if value_expr is None:
        return

    if provider == "aws" and kind == "ssm_parameter":
        res_type = "aws_ssm_parameter"
        res_name = safe_secret_name
        attrs: dict[str, Any] = {
            "name": cfg.get("name", f"/secretzero/{secret.name}"),
            "value": value_expr,
        }
        if "type" in cfg:
            attrs["type"] = cfg["type"]
        if "overwrite" in cfg:
            attrs["overwrite"] = bool(cfg["overwrite"])
        if "description" in cfg:
            attrs["description"] = cfg["description"]
        if "tier" in cfg:
            attrs["tier"] = cfg["tier"]
        project.resources.append(TerraformResource(type=res_type, name=res_name, attributes=attrs))
        return

    if provider == "aws" and kind == "secrets_manager":
        meta_type = "aws_secretsmanager_secret"
        meta_name = f"{safe_secret_name}_meta"
        secret_name = cfg.get("name", secret.name)
        meta_attrs: dict[str, Any] = {
            "name": secret_name,
        }
        if "description" in cfg:
            meta_attrs["description"] = cfg["description"]
        if "kms_key_id" in cfg:
            meta_attrs["kms_key_id"] = cfg["kms_key_id"]

        project.resources.append(
            TerraformResource(
                type=meta_type,
                name=meta_name,
                attributes=meta_attrs,
            )
        )

        ver_type = "aws_secretsmanager_secret_version"
        ver_name = safe_secret_name
        ver_attrs: dict[str, Any] = {
            "secret_id": f"${{{meta_type}.{meta_name}.id}}",
            "secret_string": value_expr,
        }
        project.resources.append(
            TerraformResource(
                type=ver_type,
                name=ver_name,
                attributes=ver_attrs,
            )
        )
        return

    if provider == "azure" and kind in {"azure_keyvault", "key_vault"}:
        res_type = "azurerm_key_vault_secret"
        res_name = safe_secret_name
        secret_name = cfg.get("secret_name", secret.name)

        var_name = "azure_key_vault_id"
        project.variables.setdefault(
            var_name,
            {
                "type": "string",
                "description": "ID of the target Azure Key Vault for SecretZero-generated secrets.",
            },
        )

        attrs: dict[str, Any] = {
            "name": secret_name,
            "value": value_expr,
            "key_vault_id": f"${{var.{var_name}}}",
        }
        if "tags" in cfg and isinstance(cfg["tags"], dict):
            attrs["tags"] = cfg["tags"]

        project.resources.append(TerraformResource(type=res_type, name=res_name, attributes=attrs))
        return

    if provider == "vault" and kind in {"vault_kv", "kv"}:
        res_type = "vault_kv_secret_v2"
        res_name = safe_secret_name

        path = cfg.get("path", f"secret/data/{secret.name}")
        mount_point = cfg.get("mount_point", "secret")

        data_expr = f'${{jsonencode({{"value" = {value_expr}}})}}'

        attrs: dict[str, Any] = {
            "mount": mount_point,
            "name": path,
            "data_json": data_expr,
        }

        project.resources.append(TerraformResource(type=res_type, name=res_name, attributes=attrs))
        return


def generate_terraform(
    secretfile: Secretfile,
    options: TerraformGeneratorOptions,
    registry: BundleRegistry | None = None,
) -> TerraformProject:
    """Generate a :class:`TerraformProject` from a Secretfile."""

    if registry is None:
        registry = get_bundle_registry()

    project = TerraformProject()

    random_in_use_flag: dict[str, bool] = {"used": False}
    secret_value_expr: dict[str, str] = {}

    for secret in secretfile.secrets:
        expr = _build_generator_expression(secret, project, options, random_in_use_flag)
        if expr is not None:
            secret_value_expr[secret.name] = expr

    used_providers: set[str] = set()
    for secret in secretfile.secrets:
        for target in secret.targets:
            used_providers.add(target.provider)
            value_expr = secret_value_expr.get(secret.name)
            _map_target_to_resources(secret, target, value_expr, project)

    _ensure_random_required_provider(project, random_in_use_flag["used"])
    _populate_required_providers_from_bundles(project, used_providers, registry, secretfile)

    return project


__all__ = [
    "TerraformOutputFormat",
    "TerraformRequiredProvider",
    "TerraformProviderBlock",
    "TerraformResource",
    "TerraformProject",
    "TerraformGeneratorOptions",
    "generate_terraform",
]
