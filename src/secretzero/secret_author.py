"""Add or edit one secret's generator, optional value source, and targets.

The writer updates ``Secretfile.yml`` in place (comments preserved via ruamel.yaml)
and never accepts plaintext static secret values. Humans enter those later through
``secretzero sync`` or ``secretzero web``.
"""

from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from secretzero.bundle_catalog import build_bundle_catalog
from secretzero.bundles.registry import get_bundle_registry
from secretzero.config import ConfigLoader
from secretzero.models import Secret, SecretSourceKind

AuthorMode = Literal["create", "edit", "upsert"]

_SCHEMA_HEADER = "# yaml-language-server: $schema=https://github.com/zloeber/SecretZero/raw/refs/heads/main/Secretfile.schema.json"

_PLACEHOLDER_RE = re.compile(r"^\$\{[^}]+\}$")

_LOCAL_TARGET_KINDS = frozenset({"file", "template"})
_ENCRYPTED_TARGET_KINDS = frozenset({"sops_file", "git_crypt_file", "ansible_vault_file"})

# Fields the wizard asks for when the catalog entry does not mark them required.
_TARGET_PROMPT_FIELDS: dict[str, list[tuple[str, str]]] = {
    "file": [("path", ".env.local"), ("format", "dotenv")],
    "template": [("template_path", "templates/secret.j2"), ("output_path", "out/secret.txt")],
    "ssm_parameter": [("name", "/app/secret")],
    "secrets_manager": [("name", "app/secret")],
    "vault_kv": [("path", "secret/data/app")],
    "azure_keyvault": [("name", "app-secret")],
    "kubernetes_secret": [("name", "app-secret"), ("namespace", "default")],
    "github_secret": [("name", "APP_SECRET")],
    "gitlab_variable": [("key", "APP_SECRET")],
    "gitlab_group_variable": [("key", "APP_SECRET")],
    "sops_file": [("path", "secrets.enc.yaml")],
    "git_crypt_file": [("path", "secrets.yaml")],
    "ansible_vault_file": [("path", "secrets.vault.yml")],
}

_PREFERRED_GENERATORS = (
    "random_password",
    "random_string",
    "static",
    "script",
    "azure_app_reg",
    "provider_backed",
)


class SecretAuthorError(ValueError):
    """User-facing authoring error (invalid kind, plaintext static value, missing secret)."""


@dataclass
class TargetDraft:
    """One target to attach to a secret."""

    provider: str
    kind: str
    config: dict[str, Any] = field(default_factory=dict)
    identity_policies: list[str] = field(default_factory=list)

    def identity(self) -> tuple[str, str, str]:
        """Stable key used to avoid appending a duplicate target."""
        marker = (
            self.config.get("path")
            or self.config.get("name")
            or self.config.get("key")
            or self.config.get("output_path")
            or ""
        )
        return (self.provider, self.kind, str(marker))


@dataclass
class SourceDraft:
    """Optional non-human ``source:`` block."""

    kind: str
    required: bool = True
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class SecretDraft:
    """Manifest fragment for one secret. Generator config must not hold plaintext."""

    name: str
    kind: str
    config: dict[str, Any] = field(default_factory=dict)
    targets: list[TargetDraft] = field(default_factory=list)
    source: SourceDraft | None = None


@dataclass
class ApplyResult:
    """Metadata-only result of applying a draft. Generator config is omitted."""

    action: Literal["created", "updated"]
    path: str
    name: str
    generator_kind: str
    source_kind: str | None
    targets: list[dict[str, Any]]
    providers_added: list[str]
    dry_run: bool
    yaml_preview: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "action": self.action,
            "path": self.path,
            "name": self.name,
            "generator_kind": self.generator_kind,
            "source_kind": self.source_kind,
            "targets": self.targets,
            "providers_added": self.providers_added,
            "dry_run": self.dry_run,
        }
        if self.yaml_preview is not None:
            payload["yaml_preview"] = self.yaml_preview
        return payload


def parse_scalar(raw: str) -> Any:
    """Parse a CLI value: JSON scalars/objects, otherwise a string."""
    text = raw.strip()
    if text == "":
        return ""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def parse_kv_pairs(items: tuple[str, ...] | list[str]) -> dict[str, Any]:
    """Parse ``KEY=VALUE`` items. ``VALUE`` uses :func:`parse_scalar`."""
    parsed: dict[str, Any] = {}
    for item in items:
        if "=" not in item:
            raise SecretAuthorError(f"Expected KEY=VALUE, got '{item}'.")
        key, raw_value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise SecretAuthorError(f"Expected KEY=VALUE, got '{item}'.")
        parsed[key] = parse_scalar(raw_value)
    return parsed


def parse_target_spec(spec: str) -> TargetDraft:
    """Parse ``provider=local,kind=file,path=.env.local,format=dotenv``."""
    parts = [part.strip() for part in spec.split(",") if part.strip()]
    if not parts:
        raise SecretAuthorError("Target spec is empty.")
    fields = parse_kv_pairs(parts)
    provider = fields.pop("provider", None)
    kind = fields.pop("kind", None)
    if not isinstance(provider, str) or not provider.strip():
        raise SecretAuthorError("Target spec requires provider=<alias>.")
    if not isinstance(kind, str) or not kind.strip():
        raise SecretAuthorError("Target spec requires kind=<target kind>.")
    policies = fields.pop("identity_policies", None)
    identity_policies: list[str] = []
    if isinstance(policies, str) and policies.strip():
        identity_policies = [item.strip() for item in policies.split("|") if item.strip()]
    elif isinstance(policies, list):
        identity_policies = [str(item) for item in policies]
    return TargetDraft(
        provider=provider.strip(),
        kind=kind.strip(),
        config=fields,
        identity_policies=identity_policies,
    )


def prompts_like_static_kind(kind: str) -> bool:
    """True when the registered generator prompts like ``static``."""
    cls = get_bundle_registry().get_generator_class(kind)
    if cls is None:
        return kind in {"static", "azure_app_reg"}
    return bool(getattr(cls, "PROMPTS_LIKE_STATIC", False))


def _is_placeholder(value: Any, *, nested: bool) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        if _PLACEHOLDER_RE.match(value):
            return True
        if value == "" and not nested:
            return True
        return False
    if isinstance(value, dict):
        return all(_is_placeholder(item, nested=True) for item in value.values())
    if isinstance(value, list):
        return all(_is_placeholder(item, nested=True) for item in value)
    return False


def reject_plaintext_static(kind: str, config: dict[str, Any]) -> None:
    """Refuse literal secret material on static-like generators."""
    if not prompts_like_static_kind(kind):
        return
    for key in ("value", "default"):
        if key not in config:
            continue
        if not _is_placeholder(config[key], nested=False):
            raise SecretAuthorError(
                f"{kind} config.{key} must be null or a ${{VAR}} placeholder. "
                "Enter the secret later with `secretzero web` or `secretzero sync`."
            )


def default_generator_config(kind: str) -> dict[str, Any]:
    """Sensible config when the caller does not supply generator options."""
    if kind == "random_password":
        return {"length": 32, "special": True}
    if kind == "random_string":
        return {"length": 32}
    if prompts_like_static_kind(kind):
        return {"value": None}
    return {}


def known_generator_kinds() -> list[str]:
    """Catalog generator kinds, common kinds first."""
    catalog = build_bundle_catalog()
    kinds = list(catalog.get("generator_kinds") or [])
    preferred = [kind for kind in _PREFERRED_GENERATORS if kind in kinds]
    rest = sorted(kind for kind in kinds if kind not in preferred)
    return preferred + rest


def known_target_kinds() -> list[str]:
    catalog = build_bundle_catalog()
    return list(catalog.get("target_kinds") or [])


def target_category(kind: str) -> str:
    if kind in _LOCAL_TARGET_KINDS:
        return "local"
    if kind in _ENCRYPTED_TARGET_KINDS:
        return "encrypted"
    return "cloud"


def targets_in_category(category: str) -> list[dict[str, Any]]:
    catalog = build_bundle_catalog()
    rows = []
    for entry in catalog.get("targets") or []:
        if target_category(str(entry.get("kind"))) == category:
            rows.append(entry)
    return rows


def provider_kind_for_target(target_kind: str) -> str:
    catalog = build_bundle_catalog()
    for entry in catalog.get("targets") or []:
        if entry.get("kind") == target_kind:
            return str(entry.get("provider_kind") or "local")
    if target_kind in _LOCAL_TARGET_KINDS:
        return "local"
    return target_kind


def prompt_fields_for_target(target_kind: str) -> list[tuple[str, str | None]]:
    """Return ``(field, default)`` pairs to ask for. ``default`` may be None."""
    curated = _TARGET_PROMPT_FIELDS.get(target_kind)
    if curated:
        return [(name, default) for name, default in curated]
    catalog = build_bundle_catalog(kind=target_kind, kind_type="target")
    fields: list[tuple[str, str | None]] = []
    for entry in catalog.get("targets") or []:
        config = entry.get("config") or {}
        if isinstance(config, dict):
            for key, desc in config.items():
                text = str(desc).lower()
                if "required" in text:
                    fields.append((str(key), None))
    return fields


def _yaml() -> YAML:
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.width = 120
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def _load_document(path: Path) -> CommentedMap:
    if not path.exists():
        doc: CommentedMap = CommentedMap()
        doc.yaml_set_start_comment(_SCHEMA_HEADER)
        return doc
    yaml = _yaml()
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.load(handle)
    if loaded is None:
        loaded = CommentedMap()
    if not isinstance(loaded, dict):
        raise SecretAuthorError(f"{path} is not a YAML mapping.")
    if not isinstance(loaded, CommentedMap):
        loaded = CommentedMap(loaded)
    return loaded


def _dump_text(data: CommentedMap) -> str:
    import io

    buf = io.StringIO()
    _yaml().dump(data, buf)
    text = buf.getvalue()
    if not text.startswith("# yaml-language-server") and _SCHEMA_HEADER not in text:
        text = _SCHEMA_HEADER + "\n" + text
    return text


def _validate_text(text: str) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False, encoding="utf-8") as handle:
        handle.write(text)
        temp_path = Path(handle.name)
    try:
        ok, message = ConfigLoader().validate_file(temp_path)
        if not ok:
            raise SecretAuthorError(message)
    finally:
        temp_path.unlink(missing_ok=True)


def _ensure_provider(doc: CommentedMap, alias: str, provider_kind: str) -> bool:
    providers = doc.get("providers")
    if not isinstance(providers, dict):
        providers = CommentedMap()
        doc["providers"] = providers
    if alias in providers:
        return False
    stub: CommentedMap = CommentedMap()
    stub["kind"] = provider_kind
    if provider_kind == "local":
        stub["config"] = CommentedMap()
    else:
        auth = CommentedMap()
        auth["kind"] = "ambient"
        stub["auth"] = auth
    providers[alias] = stub
    return True


def _target_map(target: TargetDraft) -> CommentedMap:
    node: CommentedMap = CommentedMap()
    node["provider"] = target.provider
    node["kind"] = target.kind
    if target.config:
        node["config"] = CommentedMap(target.config)
    if target.identity_policies:
        node["identity_policies"] = CommentedSeq(target.identity_policies)
    return node


def _source_map(source: SourceDraft) -> CommentedMap:
    try:
        SecretSourceKind(source.kind)
    except ValueError as exc:
        raise SecretAuthorError(
            "source kind must be file, env, secret_ref, or provider_read."
        ) from exc
    node: CommentedMap = CommentedMap()
    node["kind"] = source.kind
    node["required"] = source.required
    node["config"] = CommentedMap(source.config)
    return node


def _secret_map(
    draft: SecretDraft,
    existing: dict[str, Any] | None,
    *,
    update_source: bool,
) -> CommentedMap:
    node = CommentedMap(existing) if existing else CommentedMap()
    node["name"] = draft.name
    node["kind"] = draft.kind
    node["config"] = CommentedMap(draft.config)
    if update_source:
        if draft.source is None:
            node.pop("source", None)
        else:
            node["source"] = _source_map(draft.source)
    node["targets"] = CommentedSeq([_target_map(target) for target in draft.targets])
    return node


def _existing_targets(secret: dict[str, Any]) -> list[TargetDraft]:
    drafts: list[TargetDraft] = []
    for raw in secret.get("targets") or []:
        if not isinstance(raw, dict):
            continue
        config = raw.get("config") or {}
        if not isinstance(config, dict):
            config = {}
        policies = raw.get("identity_policies") or []
        drafts.append(
            TargetDraft(
                provider=str(raw.get("provider") or ""),
                kind=str(raw.get("kind") or ""),
                config=dict(config),
                identity_policies=[str(item) for item in policies]
                if isinstance(policies, list)
                else [],
            )
        )
    return drafts


def _merge_targets(existing: list[TargetDraft], incoming: list[TargetDraft]) -> list[TargetDraft]:
    merged = list(existing)
    seen = {item.identity() for item in merged}
    for target in incoming:
        if target.identity() in seen:
            continue
        merged.append(target)
        seen.add(target.identity())
    return merged


def _check_kinds(draft: SecretDraft) -> None:
    generators = set(known_generator_kinds())
    if draft.kind not in generators:
        raise SecretAuthorError(
            f"Unknown generator kind '{draft.kind}'. Run `secretzero catalog` for the list."
        )
    targets = set(known_target_kinds())
    for target in draft.targets:
        if target.kind not in targets:
            raise SecretAuthorError(
                f"Unknown target kind '{target.kind}'. Run `secretzero catalog` for the list."
            )
    if draft.kind == "script" and not str(draft.config.get("command") or "").strip():
        raise SecretAuthorError("script generator requires config.command.")
    if not draft.targets:
        raise SecretAuthorError("At least one target is required.")


def apply_secret_draft(
    path: Path,
    draft: SecretDraft,
    *,
    mode: AuthorMode = "upsert",
    replace_targets: bool = False,
    update_source: bool = False,
    dry_run: bool = False,
) -> ApplyResult:
    """Insert or update one secret and any missing provider stubs.

    Args:
        path: Secretfile path. Created when it does not exist.
        draft: Secret fragment. Static-like plaintext values are rejected.
        mode: ``create`` fails if the name exists; ``edit`` fails if it does not;
            ``upsert`` does either.
        replace_targets: When editing, replace targets instead of appending new ones.
        update_source: When true, write ``draft.source`` (including clearing it when None).
            When false, an existing ``source:`` block is left unchanged.
        dry_run: Validate and return a preview without writing ``path``.
    """
    name = draft.name.strip()
    if not name or not re.match(r"^[A-Za-z_][A-Za-z0-9_.-]*$", name):
        raise SecretAuthorError(
            "Secret name must start with a letter or underscore and contain only "
            "letters, numbers, '_', '.', or '-'."
        )
    draft.name = name
    if not draft.config:
        draft.config = default_generator_config(draft.kind)
    reject_plaintext_static(draft.kind, draft.config)
    _check_kinds(draft)

    # Model-check the fragment before touching the file.
    fragment: dict[str, Any] = {
        "name": draft.name,
        "kind": draft.kind,
        "config": draft.config,
        "targets": [
            {
                "provider": target.provider,
                "kind": target.kind,
                "config": target.config,
                "identity_policies": target.identity_policies,
            }
            for target in draft.targets
        ],
    }
    if draft.source is not None:
        fragment["source"] = {
            "kind": draft.source.kind,
            "required": draft.source.required,
            "config": draft.source.config,
        }
    try:
        Secret.model_validate(fragment)
    except Exception as exc:
        raise SecretAuthorError(str(exc)) from exc

    doc = _load_document(path)
    secrets = doc.get("secrets")
    if not isinstance(secrets, list):
        secrets = CommentedSeq()
        doc["secrets"] = secrets

    index = None
    for i, item in enumerate(secrets):
        if isinstance(item, dict) and item.get("name") == draft.name:
            index = i
            break

    if index is None and mode == "edit":
        raise SecretAuthorError(f"Secret '{draft.name}' was not found in {path}.")
    if index is not None and mode == "create":
        raise SecretAuthorError(
            f"Secret '{draft.name}' already exists. Re-run with --edit to update it."
        )

    providers_added: list[str] = []
    for target in draft.targets:
        added = _ensure_provider(doc, target.provider, provider_kind_for_target(target.kind))
        if added:
            providers_added.append(target.provider)

    if index is None:
        action: Literal["created", "updated"] = "created"
        secrets.append(
            _secret_map(draft, None, update_source=update_source or draft.source is not None)
        )
    else:
        action = "updated"
        existing = secrets[index]
        if not isinstance(existing, dict):
            existing = {}
        targets = draft.targets
        if not replace_targets:
            targets = _merge_targets(_existing_targets(existing), draft.targets)
        updated = SecretDraft(
            name=draft.name,
            kind=draft.kind,
            config=draft.config,
            targets=targets,
            source=draft.source,
        )
        secrets[index] = _secret_map(updated, existing, update_source=update_source)
        draft = updated

    text = _dump_text(doc)
    _validate_text(text)

    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    return ApplyResult(
        action=action,
        path=str(path),
        name=draft.name,
        generator_kind=draft.kind,
        source_kind=draft.source.kind if draft.source else None,
        targets=[
            {"provider": target.provider, "kind": target.kind, "config": dict(target.config)}
            for target in draft.targets
        ],
        providers_added=providers_added,
        dry_run=dry_run,
        yaml_preview=text if dry_run else None,
    )
