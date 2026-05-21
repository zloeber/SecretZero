"""Secret synchronization engine."""

import inspect
import json
import os
from pathlib import Path
from typing import Any

import yaml

from secretzero.bundles import get_bundle_registry
from secretzero.generators.base import BaseGenerator
from secretzero.lockfile import Lockfile, LockfileSyncIdentity
from secretzero.models import AgentInstructions, Secret, Secretfile, Template
from secretzero.policy import (
    collect_applicable_provider_identity_policies,
    evaluate_provider_identity_policy,
)
from secretzero.providers.capabilities import CapabilityType
from secretzero.sync_identity import collect_lockfile_sync_identity

# Import providers


def _drop_none_values(value: Any) -> Any:
    """Recursively remove ``None`` values from nested dict/list structures."""
    if isinstance(value, dict):
        return {k: _drop_none_values(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_drop_none_values(v) for v in value]
    return value


class SyncEngine:
    """Engine for synchronizing secrets from configuration to targets."""

    def __init__(
        self,
        secretfile: Secretfile,
        lockfile: Lockfile,
        secretfile_path: Path | None = None,
        secretfile_content: str | None = None,
        hide_input: bool = True,
        prompt_on_empty: bool = True,
        *,
        sync_client: str = "cli",
        sync_identity: LockfileSyncIdentity | None = None,
        sync_identity_cwd: Path | None = None,
    ) -> None:
        """Initialize sync engine.

        Args:
            secretfile: Loaded Secretfile configuration
            lockfile: Lockfile for tracking secrets
            secretfile_path: Path to the Secretfile (for tracking)
            secretfile_content: Raw content of the Secretfile (for change detection)
            hide_input: If True, mask user input when prompting for secrets (default: True)
            prompt_on_empty: If True, prompt for values when empty/unresolved (default: True)
            sync_client: Logical caller surface (cli, api, agent, network_web) for lockfile metadata
            sync_identity: When set, persisted as lockfile sync identity instead of auto-collection
            sync_identity_cwd: Optional directory for git identity probes (defaults to Secretfile parent)
        """
        self.secretfile = secretfile
        self.lockfile = lockfile
        self.secretfile_path = secretfile_path
        self.secretfile_content = secretfile_content
        self.hide_input = hide_input
        self.prompt_on_empty = prompt_on_empty
        self.sync_client = sync_client
        self.sync_identity_override = sync_identity
        self.sync_identity_cwd = sync_identity_cwd
        self._sync_identity_snapshot: LockfileSyncIdentity | None = None
        self._lockfile_source_recorded = False
        self._bundle_registry = get_bundle_registry()
        self._providers: dict[str, Any] = {}
        self._template_targets: dict[str, Any] = {}  # Track template targets and their secrets
        self._initialize_providers()

    def _git_identity_cwd(self) -> Path | None:
        if self.sync_identity_cwd is not None:
            return self.sync_identity_cwd
        if self.secretfile_path is not None:
            return self.secretfile_path.parent
        return None

    def _resolve_sync_identity(self) -> LockfileSyncIdentity:
        if self.sync_identity_override is not None:
            return self.sync_identity_override
        if self._sync_identity_snapshot is None:
            self._sync_identity_snapshot = collect_lockfile_sync_identity(
                client=self.sync_client,
                cwd=self._git_identity_cwd(),
            )
        return self._sync_identity_snapshot

    def _sync_actor_dict(self) -> dict[str, Any]:
        return self._resolve_sync_identity().model_dump(mode="json", exclude_none=True)

    def _target_provenance_actor(self, target_actor: dict[str, Any] | None) -> dict[str, Any]:
        """Merge sync identity with target/provider actor metadata for provenance."""
        actor = self._sync_actor_dict()
        if isinstance(target_actor, dict):
            # Provider/target actor metadata wins for overlapping keys and may include
            # auth/introspection details (account IDs, token mode, usernames, etc).
            actor.update(_drop_none_values(target_actor))
        return _drop_none_values(actor)

    def _record_lockfile_source_state(self, dry_run: bool) -> None:
        """Update secretfile tracking and sync identity once per engine run (non–dry-run only)."""
        if dry_run or not self.secretfile_path or not self.secretfile_content:
            return
        if self._lockfile_source_recorded:
            return
        self.lockfile.track_secretfile(
            self.secretfile_path,
            self.secretfile_content,
            sync_identity=self._resolve_sync_identity(),
        )
        self._lockfile_source_recorded = True

    @staticmethod
    def _build_target_id(target_config) -> str:
        """Build a consistent target identifier.

        Args:
            target_config: Target configuration

        Returns:
            Target identifier string
        """
        provider = target_config.provider
        kind = target_config.kind

        # For file targets, use path as the identifier
        if kind == "file":
            identifier = target_config.config.get("path", "")
        # For most other targets, use name
        else:
            identifier = target_config.config.get("name", "")

        return f"{provider}/{kind}/{identifier}"

    def _is_target_tracked(self, target_config: Any, tracked_targets: set[str]) -> bool:
        """Return True if *target_config* appears in the lockfile target map."""
        target_id = self._build_target_id(target_config)
        if target_id in tracked_targets:
            return True
        if target_config.kind == "file":
            old_target_id = f"{target_config.provider}/{target_config.kind}/"
            if old_target_id in tracked_targets:
                return True
        return False

    def _valid_target_ids_for_secret(self, secret: Secret) -> set[str]:
        """Return lockfile target IDs that are valid for *secret* now.

        Includes legacy file target IDs to avoid false mismatches for older lockfiles.
        """
        valid: set[str] = set()
        for target_config in secret.targets:
            valid.add(self._build_target_id(target_config))
            if target_config.kind == "file":
                valid.add(f"{target_config.provider}/{target_config.kind}/")
        return valid

    def refresh_lockfile_targets(
        self,
        *,
        secret_names: list[str] | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Detect and optionally prune stale lockfile target IDs.

        A stale target ID is present in ``lockfile.secrets[secret].targets`` but no longer
        matches any configured target in the current Secretfile.
        """
        scoped = self.secretfile.secrets
        if secret_names:
            scoped = [s for s in self.secretfile.secrets if s.name in secret_names]

        checked = 0
        stale_targets_total = 0
        stale_secrets = 0
        rows: list[dict[str, Any]] = []

        for secret in scoped:
            entry = self.lockfile.get_secret_info(secret.name)
            if not entry:
                continue
            checked += 1
            tracked = set(entry.targets.keys())
            if not tracked:
                continue

            valid = self._valid_target_ids_for_secret(secret)
            stale = sorted(tid for tid in tracked if tid not in valid)
            if not stale:
                continue

            stale_secrets += 1
            stale_targets_total += len(stale)
            rows.append(
                {
                    "secret": secret.name,
                    "stale_targets": stale,
                    "status": "would_prune" if dry_run else "pruned",
                }
            )

            if not dry_run:
                for target_id in stale:
                    entry.targets.pop(target_id, None)
                    entry.target_provenance.pop(target_id, None)

        return {
            "checked_secrets": checked,
            "mismatch_secrets": stale_secrets,
            "mismatch_targets": stale_targets_total,
            "rows": rows,
        }

    def _retrieve_candidates_for_partial_sync(
        self,
        all_target_configs: list[Any],
        targets_to_sync: list[Any],
        tracked_targets: set[str],
    ) -> list[Any]:
        """Order targets to try for read-back during partial sync.

        Tries ``targets_to_sync`` first (including targets not yet in the lockfile,
        e.g. a local file that already holds the value), then any remaining
        lockfile-tracked targets. This avoids failing when the only readable
        copy is an untracked destination or when non-retrievable tracked targets
        (e.g. some cloud secrets) are listed before a file target.
        """
        seen: set[str] = set()
        ordered: list[Any] = []
        for tc in targets_to_sync:
            tid = self._build_target_id(tc)
            if tid in seen:
                continue
            seen.add(tid)
            ordered.append(tc)
        for tc in all_target_configs:
            tid = self._build_target_id(tc)
            if tid in seen:
                continue
            if self._is_target_tracked(tc, tracked_targets):
                seen.add(tid)
                ordered.append(tc)
        return ordered

    def _initialize_providers(self) -> None:
        """Initialize providers from secretfile configuration."""
        if not self.secretfile.providers:
            return

        for provider_name, provider_config in self.secretfile.providers.items():
            try:
                # Convert Pydantic model to dict
                config_dict = provider_config.model_dump()
                provider = self._create_provider(provider_name, config_dict)
                if provider:
                    self._providers[provider_name] = provider
            except Exception:
                # Skip providers that can't be initialized
                pass

    def _create_provider(self, name: str, config: dict) -> Any | None:
        """Create a provider instance using the bundle registry.

        Args:
            name: Provider name
            config: Provider configuration

        Returns:
            Provider instance or None
        """
        # model_dump() may include ``kind: null`` when omitted in YAML; dict.get
        # would return None instead of falling back to the provider alias (e.g. aws).
        provider_kind = config.get("kind") or name
        provider_class = self._bundle_registry.get_provider_class(provider_kind)
        if provider_class is not None:
            try:
                return provider_class(name=name, config=config)
            except Exception:
                return None
        return None

    def _get_provider(self, provider_name: str) -> Any | None:
        """Get a provider by name.

        Args:
            provider_name: Name of the provider

        Returns:
            Provider instance or None
        """
        return self._providers.get(provider_name)

    def get_provider_secret(
        self,
        provider_name: str,
        secret_id: str,
        method_name: str | None = None,
        method_args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Retrieve a secret using provider bundle capability methods.

        Args:
            provider_name: Alias of the configured provider in ``secretfile.providers``.
            secret_id: Secret identifier consumed by the provider retrieve method.
            method_name: Optional explicit provider method to call.
            method_args: Optional keyword arguments for the provider method.

        Returns:
            Dictionary containing retrieval metadata and the retrieved value.

        Raises:
            ValueError: If provider is unavailable, authentication fails, or retrieval fails.
        """
        provider = self._get_provider(provider_name)
        if provider is None:
            raise ValueError(f"Provider '{provider_name}' is not initialized")

        if not provider.is_authenticated() and not provider.authenticate():
            raise ValueError(f"Provider '{provider_name}' authentication failed")

        args = dict(method_args or {})
        candidate_names = [method_name] if method_name else ["retrieve_secret", "get_secret"]
        selected_name = None
        selected_method = None
        for candidate in candidate_names:
            if not candidate:
                continue
            method = getattr(provider, candidate, None)
            if callable(method):
                selected_name = candidate
                selected_method = method
                break

        if selected_method is None or selected_name is None:
            capabilities = provider.get_capabilities()
            retrieve_methods = sorted(capabilities.list_methods_by_type(CapabilityType.RETRIEVE))
            raise ValueError(
                f"Provider '{provider_name}' does not expose retrieval method "
                f"'{method_name or 'retrieve_secret'}'. Available retrieve methods: "
                f"{', '.join(retrieve_methods) if retrieve_methods else 'none'}"
            )

        params = [
            p for p in inspect.signature(selected_method).parameters.values() if p.name != "self"
        ]
        if params:
            secret_param_name = params[0].name
            if secret_param_name not in args:
                args[secret_param_name] = secret_id

        try:
            value = selected_method(**args)
        except TypeError as exc:
            raise ValueError(
                f"Invalid arguments for '{selected_name}' on provider '{provider_name}': {exc}"
            ) from exc
        except Exception as exc:
            raise ValueError(
                f"Failed to retrieve secret from provider '{provider_name}': {exc}"
            ) from exc

        text_value = value if isinstance(value, str) else str(value)
        placeholder_values = {
            "[SECRET EXISTS]",
            "[CREDENTIAL EXISTS]",
        }
        is_placeholder = text_value in placeholder_values or text_value.startswith(
            "[SECRET EXISTS in "
        )

        return {
            "provider": provider_name,
            "method": selected_name,
            "retrieved": True,
            "revealable": not is_placeholder,
            "value": text_value,
            "raw_value": value,
            "notes": (
                "Provider API confirms existence but does not expose plaintext value."
                if is_placeholder
                else None
            ),
        }

    def _validate_target_access(self) -> dict[str, Any]:
        """Validate that at least one target can be accessed.

        Tests connection to all providers used by targets.

        Returns:
            Dictionary with validation results:
                - accessible_count: Number of accessible providers
                - total_count: Total number of unique providers
                - results: List of tuples (provider_name, success, error_msg)
        """
        # Collect unique providers from all targets
        provider_names = set()
        for secret in self.secretfile.secrets:
            for target in secret.targets:
                provider_names.add(target.provider)

        # Test connection to each provider
        results = []
        accessible_count = 0

        for provider_name in provider_names:
            # Local file targets don't require authentication
            if provider_name == "local":
                results.append((provider_name, True, None))
                accessible_count += 1
                continue

            provider = self._get_provider(provider_name)
            if provider is None:
                results.append((provider_name, False, "Provider not initialized"))
                continue

            # Test connection
            try:
                success, error_msg = provider.test_connection()
                results.append((provider_name, success, error_msg))
                if success:
                    accessible_count += 1
            except Exception as e:
                results.append((provider_name, False, str(e)))

        return {
            "accessible_count": accessible_count,
            "total_count": len(provider_names),
            "results": results,
        }

    def preflight_provider_identity_policies(
        self,
        secrets_in_scope: list[Secret] | None = None,
    ) -> dict[str, Any]:
        """Evaluate ``provider_identity`` policies without raising (for UI preflight).

        Uses the same rules as sync enforcement. When ``secrets_in_scope`` is omitted,
        all secrets in the manifest are considered (same scope as a full sync).

        Returns:
            Dict with ``has_policies``, ``all_ok``, ``blocking``, ``headline``, ``rows``
            (list of per policy/provider status rows).
        """
        secrets = secrets_in_scope if secrets_in_scope is not None else self.secretfile.secrets
        applicable = collect_applicable_provider_identity_policies(self.secretfile, secrets)
        rows: list[dict[str, Any]] = []
        if not applicable:
            return {
                "has_policies": False,
                "all_ok": True,
                "blocking": False,
                "headline": (
                    "No provider identity policies apply to these secrets. "
                    "Sync is not gated by `kind: provider_identity` rules."
                ),
                "rows": [],
            }

        all_ok = True
        blocking = False
        for policy_name, policy in applicable:
            if not policy.enabled:
                continue
            for provider_alias in policy.providers:
                entry: dict[str, Any] = {
                    "policy_name": policy_name,
                    "provider_alias": provider_alias,
                    "status": "ok",
                    "detail": None,
                }
                provider = self._get_provider(provider_alias)
                if provider is None:
                    entry["status"] = "provider_missing"
                    entry["detail"] = (
                        "Provider is not initialized. Check your `providers:` configuration."
                    )
                    all_ok = False
                    blocking = True
                    rows.append(entry)
                    continue
                if getattr(provider, "auth", None) is not None:
                    auth_exc: BaseException | None = None
                    try:
                        ok = provider.authenticate()
                    except Exception as exc:
                        ok = False
                        auth_exc = exc
                    if not ok:
                        msg = f"authenticate() returned false for provider {provider_alias!r}"
                        if auth_exc is not None:
                            msg = str(auth_exc)
                        entry["status"] = "auth_failed"
                        entry["detail"] = msg
                        all_ok = False
                        blocking = True
                        rows.append(entry)
                        continue
                try:
                    actor = provider.get_actor_info()
                except Exception as exc:
                    entry["status"] = "actor_failed"
                    entry["detail"] = str(exc)
                    all_ok = False
                    blocking = True
                    rows.append(entry)
                    continue
                if not isinstance(actor, dict):
                    entry["status"] = "actor_failed"
                    entry["detail"] = "Provider returned non-dict actor metadata"
                    all_ok = False
                    blocking = True
                    rows.append(entry)
                    continue
                eval_ok, msg = evaluate_provider_identity_policy(policy, actor)
                if not eval_ok:
                    entry["status"] = "policy_failed"
                    entry["detail"] = msg
                    all_ok = False
                    blocking = True
                rows.append(entry)

        if all_ok:
            headline = (
                "All applicable provider identity policies pass. "
                "Authenticated identities match your manifest rules."
            )
        else:
            headline = (
                "One or more provider identity policies fail. Sync will be blocked until you "
                "use credentials that satisfy the rules below or adjust the manifest."
            )
        return {
            "has_policies": True,
            "all_ok": all_ok,
            "blocking": blocking,
            "headline": headline,
            "rows": rows,
        }

    def preflight_sync_readiness(
        self,
        secrets_in_scope: list[Secret] | None = None,
    ) -> dict[str, Any]:
        """Summarize conditions that would block a full sync (same gates as :meth:`sync`).

        Combines:

        - ``provider_identity`` policy evaluation (see :meth:`preflight_provider_identity_policies`)
        - Provider connectivity for all targets (see :meth:`_validate_target_access`)

        Args:
            secrets_in_scope: Secrets to evaluate; default is all secrets in the manifest.

        Returns:
            Dict with ``sync_blocked``, ``headline``, ``blocking_reasons``,
            ``provider_identity`` (preflight dict), and ``target_access`` (serializable results).
        """
        secrets = secrets_in_scope if secrets_in_scope is not None else self.secretfile.secrets
        identity = self.preflight_provider_identity_policies(secrets)
        access = self._validate_target_access()
        access_serializable = {
            "accessible_count": access["accessible_count"],
            "total_count": access["total_count"],
            "results": [
                {"provider": name, "ok": ok, "error": err} for name, ok, err in access["results"]
            ],
        }

        identity_blocks = bool(identity.get("blocking"))
        no_accessible_targets = access["total_count"] > 0 and access["accessible_count"] == 0
        sync_blocked = identity_blocks or no_accessible_targets

        reasons: list[str] = []
        if identity_blocks:
            reasons.append("provider_identity_policy")
        if no_accessible_targets:
            reasons.append("no_accessible_targets")

        if sync_blocked:
            if identity_blocks and no_accessible_targets:
                headline = (
                    "Sync would be blocked: provider identity policies failed and no provider "
                    "targets are reachable (connection tests returned no successes)."
                )
            elif no_accessible_targets:
                headline = (
                    "Sync would be blocked: no accessible provider targets "
                    "(all non-local provider connection tests failed or providers are missing)."
                )
            else:
                headline = str(identity.get("headline") or "Provider identity policies block sync.")
        else:
            headline = "Full sync readiness: no blocking policy or target-access issues detected."

        return {
            "sync_blocked": sync_blocked,
            "headline": headline,
            "blocking_reasons": reasons,
            "provider_identity": identity,
            "target_access": access_serializable,
        }

    def _enforce_provider_identity_policies(self, secrets_to_sync: list[Secret]) -> None:
        """Raise when ``provider_identity`` policies are not satisfied for in-scope targets."""
        result = self.preflight_provider_identity_policies(secrets_to_sync)
        for it in result["rows"]:
            if it["status"] != "ok":
                raise RuntimeError(
                    f"Provider identity policy {it['policy_name']!r} failed for provider "
                    f"{it['provider_alias']!r}: {it['detail']}"
                )

    def sync(
        self,
        dry_run: bool = False,
        force_rotation: bool = False,
        secret_names: list[str] | None = None,
        ignore_foreign_context_targets: bool = False,
        force_targets: dict[str, frozenset[str]] | None = None,
        refresh: bool = True,
    ) -> dict[str, Any]:
        """Synchronize all secrets to their targets.

        Args:
            dry_run: If True, only simulate without making changes
            force_rotation: If True, regenerate secrets even if they exist
            secret_names: If provided, only sync secrets with these names
            force_targets: Optional map of secret name -> target IDs (from
                :meth:`_build_target_id`) to push to again even when already tracked.

        Returns:
            Dictionary with sync results and statistics

        Raises:
            RuntimeError: If no targets can be accessed
        """
        # Validate target access before generating secrets
        # Only validate if there are actual targets configured
        validation = self._validate_target_access()
        if validation["total_count"] > 0 and validation["accessible_count"] == 0:
            error_details = []
            for provider_name, success, error_msg in validation["results"]:
                if error_msg:
                    error_details.append(f"  • {provider_name}: {error_msg}")
                else:
                    error_details.append(f"  • {provider_name}: Connection failed")

            error_message = (
                f"Cannot sync secrets: No accessible targets found.\n"
                f"Tested {validation['total_count']} provider(s):\n" + "\n".join(error_details)
            )
            raise RuntimeError(error_message)

        results = {
            "secrets_processed": 0,
            "secrets_generated": 0,
            "secrets_skipped": 0,
            "secrets_stored": 0,
            "errors": [],
            "details": [],
            "secretfile_changed": False,
            "refresh": None,
        }

        self._sync_identity_snapshot = None
        self._lockfile_source_recorded = False

        # Track secretfile for change detection (if tracking info provided)
        if self.secretfile_path and self.secretfile_content:
            secretfile_changed = self.lockfile.secretfile_changed(
                self.secretfile_path, self.secretfile_content
            )
            results["secretfile_changed"] = secretfile_changed

            # Track the secretfile in the lockfile (identity captured once per sync)
            self._record_lockfile_source_state(dry_run)

        # Filter secrets by name if specified
        secrets_to_sync = self.secretfile.secrets
        if secret_names:
            secrets_to_sync = [s for s in self.secretfile.secrets if s.name in secret_names]
            # Warn about secrets that don't exist
            found_names = {s.name for s in secrets_to_sync}
            missing_names = set(secret_names) - found_names
            if missing_names:
                results["errors"].append(
                    f"Warning: Secrets not found in Secretfile: {', '.join(sorted(missing_names))}"
                )

        self._enforce_provider_identity_policies(secrets_to_sync)

        if refresh:
            refresh_report = self.refresh_lockfile_targets(
                secret_names=secret_names,
                dry_run=dry_run,
            )
            results["refresh"] = refresh_report
            if refresh_report["mismatch_targets"] > 0:
                results["errors"].append(
                    "Warning: lockfile target mismatches detected "
                    f"({refresh_report['mismatch_targets']} stale target entr"
                    f"{'y' if refresh_report['mismatch_targets'] == 1 else 'ies'})"
                )

        resolved_cache: dict[str, Any] = {}
        for secret in secrets_to_sync:
            try:
                fti: frozenset[str] | None = None
                if force_targets and secret.name in force_targets:
                    fti = force_targets[secret.name]
                result = self._sync_secret(
                    secret,
                    dry_run,
                    force_rotation,
                    ignore_foreign_context_targets=ignore_foreign_context_targets,
                    force_target_ids=fti,
                    resolved_cache=resolved_cache,
                )
                results["secrets_processed"] += 1
                results["details"].append(result)

                if result["generated"]:
                    results["secrets_generated"] += 1
                if result["skipped"]:
                    results["secrets_skipped"] += 1
                if result["stored"]:
                    results["secrets_stored"] += 1
                if result.get("errors"):
                    results["errors"].extend(result["errors"])

            except Exception as e:
                error_msg = f"Error syncing secret '{secret.name}': {e}"
                results["errors"].append(error_msg)

        # Render template targets after all secrets are synced
        if not dry_run:
            template_render_errors = self._render_template_targets()
            if template_render_errors:
                results["errors"].extend(template_render_errors)

        return results

    @staticmethod
    def _extract_object_field(value: Any, field_path: str | None) -> Any:
        """Extract nested object field by dot path when requested."""
        if not field_path:
            return value
        current = value
        for segment in field_path.split("."):
            key = segment.strip()
            if not key:
                raise ValueError("Field path contains an empty segment")
            if not isinstance(current, dict) or key not in current:
                raise ValueError(f"Field path '{field_path}' not found in source payload")
            current = current[key]
        return current

    @staticmethod
    def _normalize_secret_value(value: Any) -> str:
        """Normalize source/generator outputs to string payloads for targets."""
        if isinstance(value, str):
            return value
        if isinstance(value, (dict, list)):
            return json.dumps(value, separators=(",", ":"), sort_keys=True)
        return str(value)

    @staticmethod
    def _parse_dotenv_text(content: str) -> dict[str, str]:
        """Parse dotenv content into a plain key/value map."""
        data: dict[str, str] = {}
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip().strip('"').strip("'")
        return data

    def _resolve_file_source(self, source_cfg: dict[str, Any]) -> Any:
        path_raw = source_cfg.get("path")
        if not isinstance(path_raw, str) or not path_raw.strip():
            raise ValueError("file source requires non-empty config.path")
        source_path = Path(path_raw)
        if not source_path.is_absolute() and self.secretfile_path is not None:
            source_path = self.secretfile_path.parent / source_path
        if not source_path.exists():
            raise ValueError(f"file source path does not exist: {source_path}")

        encoding = str(source_cfg.get("encoding", "utf-8"))
        format_hint = str(source_cfg.get("format", "")).strip().lower()
        if not format_hint:
            name_lower = source_path.name.lower()
            if name_lower.endswith(".tfvars.json"):
                format_hint = "json"
            elif name_lower.endswith(".tfvars"):
                format_hint = "tfvars"
            else:
                suffix = source_path.suffix.lower()
                format_hint = {
                    ".json": "json",
                    ".yml": "yaml",
                    ".yaml": "yaml",
                    ".env": "dotenv",
                    ".txt": "text",
                }.get(suffix, "text")

        text = source_path.read_text(encoding=encoding)
        if format_hint == "json":
            parsed = json.loads(text) if text.strip() else {}
        elif format_hint == "yaml":
            parsed = yaml.safe_load(text) if text.strip() else {}
            if parsed is None:
                parsed = {}
        elif format_hint == "dotenv":
            parsed = self._parse_dotenv_text(text)
        elif format_hint == "tfvars":
            from secretzero.hcl_tfvars import parse_tfvars

            parsed = parse_tfvars(text)
        elif format_hint == "text":
            parsed = text
        else:
            raise ValueError(f"Unsupported file source format: {format_hint}")

        return self._extract_object_field(parsed, source_cfg.get("key"))

    def _resolve_provider_read_source(self, source_cfg: dict[str, Any]) -> Any:
        provider_name = source_cfg.get("provider")
        if not isinstance(provider_name, str) or not provider_name.strip():
            raise ValueError("provider_read source requires config.provider")
        kind = source_cfg.get("kind")
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError("provider_read source requires config.kind")

        read_cfg = source_cfg.get("read")
        if not isinstance(read_cfg, dict):
            raise ValueError("provider_read source requires object config.read")

        method_name = str(source_cfg.get("method") or "retrieve_secret")
        method_args = {**read_cfg}
        method_args.setdefault("kind", kind)
        profile = source_cfg.get("profile")
        if profile is not None:
            method_args.setdefault("profile", profile)

        secret_id = str(read_cfg.get("name") or read_cfg.get("path") or "")
        if not secret_id:
            raise ValueError(
                "provider_read source config.read requires at least one locator key (name or path)"
            )

        provider_result = self.get_provider_secret(
            provider_name=provider_name,
            secret_id=secret_id,
            method_name=method_name,
            method_args=method_args,
        )
        value = provider_result.get("raw_value")
        return self._extract_object_field(value, source_cfg.get("field"))

    def _resolve_secret_source(
        self, secret: Secret, resolved_cache: dict[str, Any]
    ) -> tuple[bool, Any | None, str | None]:
        """Resolve optional secret.source value for a secret."""
        source = secret.source
        if source is None:
            return False, None, None

        cfg = source.config or {}
        kind = source.kind.value
        try:
            if kind == "env":
                env_name = cfg.get("name")
                if not isinstance(env_name, str) or not env_name.strip():
                    raise ValueError("env source requires non-empty config.name")
                env_value = os.environ.get(env_name)
                if env_value is None:
                    raise ValueError(f"env source variable not set: {env_name}")
                if cfg.get("trim", True):
                    env_value = env_value.strip()
                value = env_value
            elif kind == "file":
                value = self._resolve_file_source(cfg)
            elif kind == "secret_ref":
                secret_name = cfg.get("secret")
                if not isinstance(secret_name, str) or not secret_name.strip():
                    raise ValueError("secret_ref source requires non-empty config.secret")
                if secret_name == secret.name:
                    raise ValueError("secret_ref source cannot reference itself")
                if secret_name not in resolved_cache:
                    raise ValueError(
                        f"secret_ref source '{secret_name}' is unavailable; "
                        "only previously resolved non-template secrets are supported"
                    )
                value = self._extract_object_field(resolved_cache[secret_name], cfg.get("field"))
            elif kind == "provider_read":
                value = self._resolve_provider_read_source(cfg)
            else:
                raise ValueError(f"Unsupported source kind: {kind}")
            return True, value, None
        except Exception as exc:
            if source.required:
                return False, None, str(exc)
            return False, None, None

    def _sync_secret(
        self,
        secret: Secret,
        dry_run: bool,
        force_rotation: bool = False,
        ignore_foreign_context_targets: bool = False,
        force_target_ids: frozenset[str] | None = None,
        resolved_cache: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Sync a single secret.

        Args:
            secret: Secret definition
            dry_run: If True, only simulate
            force_rotation: If True, regenerate even if exists
            force_target_ids: If set, these target IDs are synced even when already
                in the lockfile (re-push current value).

        Returns:
            Dictionary with sync details for this secret
        """
        result = {
            "name": secret.name,
            "kind": secret.kind,
            "generated": False,
            "skipped": False,
            "stored": False,
            "targets": [],
            "errors": [],
        }

        self._record_lockfile_source_state(dry_run)

        # Check if this is a template-based secret
        if secret.kind.startswith("templates."):
            template_name = secret.kind.replace("templates.", "")
            template = self.secretfile.templates.get(template_name)
            if template:
                return self._sync_template_secret(
                    secret,
                    template,
                    dry_run,
                    force_rotation,
                    ignore_foreign_context_targets=ignore_foreign_context_targets,
                    force_target_ids=force_target_ids,
                )

        # Check if secret needs generation (one_time check)
        if secret.one_time and self.lockfile.has_secret(secret.name) and not force_rotation:
            result["skipped"] = True
            result["reason"] = "One-time secret already exists"
            return result

        # Check if secret exists in lockfile and has all targets tracked
        secret_exists = self.lockfile.has_secret(secret.name)
        lockfile_entry = self.lockfile.get_secret_info(secret.name) if secret_exists else None

        # Determine which targets need syncing
        if lockfile_entry and lockfile_entry.targets and not ignore_foreign_context_targets:
            tracked_targets = set(lockfile_entry.targets.keys())
        else:
            # When ignoring foreign contexts, treat as if no targets have been synced yet
            tracked_targets = set()
        targets_to_sync = []

        for target_config in secret.targets:
            target_id = self._build_target_id(target_config)
            force_this = bool(force_target_ids and target_id in force_target_ids)
            needs_sync = force_rotation or target_id not in tracked_targets or force_this

            # For file targets, also check if the file actually exists
            if (
                not needs_sync
                and target_config.provider == "local"
                and target_config.kind == "file"
            ):
                file_path = Path(target_config.config.get("path", ""))
                if not file_path.exists():
                    needs_sync = True  # File missing, needs to be recreated

            if needs_sync:
                targets_to_sync.append(target_config)

        # If no targets need syncing and secret exists, skip
        # Special case: if secret has no targets at all and doesn't exist, generate it
        if not targets_to_sync and (secret_exists or len(secret.targets) > 0):
            result["skipped"] = True
            result["reason"] = "All targets already synced"
            return result

        # Get or generate secret value
        secret_value = None
        cache = resolved_cache if resolved_cache is not None else {}

        # For partial sync (secret exists, not forcing), try to retrieve from existing target
        if secret_exists and not force_rotation and tracked_targets:
            candidates = self._retrieve_candidates_for_partial_sync(
                secret.targets, targets_to_sync, tracked_targets
            )
            for target_config in candidates:
                secret_value = self._retrieve_from_target(secret.name, target_config)
                if secret_value is not None:
                    result["retrieved_from_existing"] = True
                    break

            if secret_value is None and force_target_ids:
                env_val = os.environ.get(secret.name.upper())
                if env_val:
                    secret_value = env_val

            if secret_value is None:
                # For source-enabled secrets, fall through and attempt source/generator
                # resolution before declaring partial-sync failure.
                if secret.source is None:
                    result["skipped"] = True
                    if force_target_ids:
                        result["reason"] = (
                            "Cannot obtain plaintext for force-target sync (read-back failed for all "
                            "candidates). Set "
                            f"{secret.name.upper()} in the environment, use a retrievable target "
                            "(e.g. local file), or use --force-rotation to regenerate."
                        )
                    else:
                        result["reason"] = (
                            "Cannot retrieve existing value for partial sync. Use --force-rotation to regenerate."
                        )
                    result["errors"].append(
                        f"{secret.name}: Unable to retrieve from existing targets for partial sync"
                    )
                    return result

        if secret_value is None:
            source_used, source_value, source_error = self._resolve_secret_source(secret, cache)
            if source_error:
                result["errors"].append(f"{secret.name}: source resolution failed: {source_error}")
                result["skipped"] = True
                return result
            if source_used:
                secret_value = self._normalize_secret_value(source_value)
                result["source"] = "resolved"

        # Generate new value if needed (full sync or force rotation)
        if secret_value is None:
            env_var_name = secret.name.upper()
            secret_value = self._generate_secret_value(
                secret.kind,
                secret.config,
                env_var_name,
                field_description=f"Secret: {secret.name}",
                agent_instructions=secret.agent_instructions,
            )
            result["generated"] = True
        else:
            secret_value = self._normalize_secret_value(secret_value)

        cache[secret.name] = secret_value

        # Store in targets (only targets that need syncing)
        if not dry_run:
            # all_targets_ok = True
            any_target_stored = False
            for target_config in targets_to_sync:
                target_result = self._store_in_target(secret.name, secret_value, target_config)
                result["targets"].append(target_result)

                if target_result.get("status") in {"failed", "error", "unsupported"}:
                    # all_targets_ok = False
                    message = target_result.get("message", "Target store failed")
                    result["errors"].append(
                        f"{secret.name} -> {target_result['provider']}/{target_result['kind']}: {message}"
                    )
                else:
                    # Track successful target stores
                    any_target_stored = True
                    target_id = self._build_target_id(target_config)
                    self.lockfile.add_secret(
                        secret.name, secret_value, target_id=target_id, is_rotation=force_rotation
                    )
                    self.lockfile.record_target_update(
                        secret.name,
                        target_id,
                        actor=self._target_provenance_actor(target_result.get("actor")),
                    )

            # If secret has no targets, still persist its hash in lockfile.
            if len(targets_to_sync) == 0 and secret_value is not None:
                self.lockfile.add_secret(
                    secret.name, secret_value, target_id=None, is_rotation=force_rotation
                )
                result["stored"] = True
            elif any_target_stored:
                # Mark as stored if at least one target succeeded
                result["stored"] = True
        else:
            result["dry_run"] = True
            for target_config in targets_to_sync:
                result["targets"].append(
                    {
                        "provider": target_config.provider,
                        "kind": target_config.kind,
                        "status": "would_store",
                    }
                )

        return result

    def _sync_template_secret(
        self,
        secret: Secret,
        template: Template,
        dry_run: bool,
        force_rotation: bool = False,
        ignore_foreign_context_targets: bool = False,
        force_target_ids: frozenset[str] | None = None,
    ) -> dict[str, Any]:
        """Sync a template-based secret with multiple fields.

        Args:
            secret: Secret definition
            template: Template definition
            dry_run: If True, only simulate
            force_rotation: If True, regenerate even if exists
            force_target_ids: Re-push field values to these target IDs when set.

        Returns:
            Dictionary with sync details
        """
        result = {
            "name": secret.name,
            "kind": secret.kind,
            "template": True,
            "fields": [],
            "generated": False,
            "stored": False,
            "skipped": False,
            "errors": [],
        }

        self._record_lockfile_source_state(dry_run)

        # Process each field in the template
        for field_name, field_def in template.fields.items():
            field_result = {
                "name": field_name,
                "generated": False,
                "stored": False,
                "targets": [],
                "errors": [],
            }

            # Combine secret and field targets
            all_targets = field_def.targets + template.targets
            field_secret_name = f"{secret.name}.{field_name}"

            # Check if field exists in lockfile
            field_exists = self.lockfile.has_secret(field_secret_name)
            lockfile_entry = (
                self.lockfile.get_secret_info(field_secret_name) if field_exists else None
            )

            # Determine which targets need syncing
            if lockfile_entry and lockfile_entry.targets and not ignore_foreign_context_targets:
                tracked_targets = set(lockfile_entry.targets.keys())
            else:
                tracked_targets = set()
            targets_to_sync = []

            for target_config in all_targets:
                target_id = self._build_target_id(target_config)
                force_this = bool(force_target_ids and target_id in force_target_ids)
                if force_rotation or target_id not in tracked_targets or force_this:
                    targets_to_sync.append(target_config)

            # If no targets need syncing, skip
            if not targets_to_sync:
                field_result["skipped"] = True
                result["fields"].append(field_result)
                continue

            # Get or generate field value
            field_value = None

            # For partial sync, try to retrieve from existing target
            if field_exists and not force_rotation and tracked_targets:
                candidates = self._retrieve_candidates_for_partial_sync(
                    all_targets, targets_to_sync, tracked_targets
                )
                for target_config in candidates:
                    field_value = self._retrieve_from_target(field_name, target_config)
                    if field_value is not None:
                        field_result["retrieved_from_existing"] = True
                        break

                if field_value is None and force_target_ids:
                    env_key = f"{secret.name.upper()}_{field_name.upper()}"
                    env_val = os.environ.get(env_key)
                    if env_val:
                        field_value = env_val

                if field_value is None:
                    field_result["skipped"] = True
                    field_result["errors"].append(
                        f"{field_secret_name}: Unable to retrieve from existing targets for partial sync"
                    )
                    result["fields"].append(field_result)
                    continue

            # Generate new value if needed
            if field_value is None:
                env_var_name = f"{secret.name.upper()}_{field_name.upper()}"
                field_value = self._generate_secret_value(
                    field_def.generator.kind.value,
                    field_def.generator.config,
                    env_var_name,
                    field_description=field_def.description,
                )
                field_result["generated"] = True
                result["generated"] = True

            # Store in targets (only targets that need syncing)
            if not dry_run:
                all_targets_ok = True
                for target_config in targets_to_sync:
                    target_result = self._store_in_target(field_name, field_value, target_config)
                    field_result["targets"].append(target_result)

                    if target_result.get("status") in {"failed", "error", "unsupported"}:
                        all_targets_ok = False
                        message = target_result.get("message", "Target store failed")
                        field_result["errors"].append(
                            f"{field_secret_name} -> {target_result['provider']}/{target_result['kind']}: {message}"
                        )
                    else:
                        # Track successful target stores
                        target_id = self._build_target_id(target_config)
                        self.lockfile.add_secret(
                            field_secret_name, field_value, target_id=target_id
                        )
                        self.lockfile.record_target_update(
                            field_secret_name,
                            target_id,
                            actor=self._target_provenance_actor(target_result.get("actor")),
                        )

                if all_targets_ok:
                    field_result["stored"] = True
                    result["stored"] = True
                else:
                    result["errors"].extend(field_result["errors"])
            else:
                field_result["dry_run"] = True
                for target_config in targets_to_sync:
                    field_result["targets"].append(
                        {
                            "provider": target_config.provider,
                            "kind": target_config.kind,
                            "status": "would_store",
                        }
                    )

            result["fields"].append(field_result)

        return result

    def _resolve_provider_in_config(
        self, generator_class: type, config: dict[str, Any]
    ) -> dict[str, Any]:
        """Inject a live provider instance into *config* if the generator needs one.

        Generator classes that require a provider instance declare two class
        attributes:

        * ``PROVIDER_CONFIG_KEY`` – the ``config`` key that holds the provider
          *name* string (defaults to ``"provider"``).
        * ``PROVIDER_INJECTION_KEY`` – the ``config`` key under which the
          resolved provider *instance* should be injected.

        When the resolved provider is not found the config is returned
        unchanged; the generator's own ``generate()`` method will raise an
        appropriate error at generation time.

        Args:
            generator_class: The generator class about to be instantiated.
            config: Current generator config dict.

        Returns:
            Possibly-augmented config dict.
        """
        provider_config_key: str | None = getattr(generator_class, "PROVIDER_CONFIG_KEY", None)
        provider_injection_key: str | None = getattr(
            generator_class, "PROVIDER_INJECTION_KEY", None
        )

        if not provider_config_key or not provider_injection_key:
            return config

        provider_name = config.get(provider_config_key)
        if not provider_name or not isinstance(provider_name, str):
            return config

        provider = self._get_provider(provider_name)
        if provider is None:
            return config

        return {**config, provider_injection_key: provider}

    def _generate_secret_value(
        self,
        kind: str,
        config: dict[str, Any],
        env_var_name: str,
        field_description: str | None = None,
        agent_instructions: AgentInstructions | None = None,
    ) -> str:
        """Generate a secret value using the bundle registry.

        Looks up the generator class for *kind* in the bundle registry,
        optionally injects a live provider instance (for generators that
        declare ``PROVIDER_CONFIG_KEY`` / ``PROVIDER_INJECTION_KEY``), and
        delegates to :meth:`~secretzero.generators.base.BaseGenerator.generate_with_fallback`.

        When *agent_instructions* are provided (from the Secretfile
        ``agent_instructions`` block) they are attached to the generator so
        they take precedence over any built-in instructions.  If generation
        fails, the effective instructions (user-defined or built-in) are
        printed to the console before the exception is re-raised.

        Args:
            kind: Generator kind string (e.g. ``"random_password"``).
            config: Generator configuration dict from the Secretfile.
            env_var_name: Environment variable name checked before generation.
            field_description: Optional human-readable label for user prompts.
            agent_instructions: Optional Secretfile-defined retrieval instructions
                that override the generator's built-in manual instructions.

        Returns:
            Generated secret value string.

        Raises:
            ValueError: If *kind* is not registered in the bundle registry.
        """
        generator_class = self._bundle_registry.get_generator_class(kind)
        if generator_class is None:
            raise ValueError(
                f"Unknown generator kind: '{kind}'. "
                f"Available kinds: {', '.join(self._bundle_registry.list_generator_kinds())}"
            )

        # Inject provider instance for generators that require one
        resolved_config = self._resolve_provider_in_config(generator_class, config)

        # Validate that provider-backed generators received their provider.
        # When the provider is missing, try to show manual instructions before
        # raising so the user knows how to obtain the secret value by hand.
        injection_key: str | None = getattr(generator_class, "PROVIDER_INJECTION_KEY", None)
        if injection_key and resolved_config.get(injection_key) is None:
            config_key: str = getattr(generator_class, "PROVIDER_CONFIG_KEY", "provider")
            provider_name = config.get(config_key, kind)
            if self._get_provider(provider_name) is None:
                # Attempt to instantiate the generator without its provider so we
                # can call get_manual_instructions().  Some generators (e.g.
                # github_pat) can be created without a resolved provider instance;
                # others (e.g. provider_backed) cannot, in which case we simply
                # skip the instructions display.
                effective_instructions: AgentInstructions | None = agent_instructions
                if effective_instructions is None:
                    try:
                        _tmp_gen = generator_class(resolved_config)
                        effective_instructions = _tmp_gen.get_manual_instructions()
                    except Exception:
                        pass  # Generator cannot be instantiated without its provider
                if effective_instructions is not None:
                    BaseGenerator._display_manual_instructions(effective_instructions)
                raise ValueError(
                    f"'{kind}' generator requires provider '{provider_name}' "
                    f"to be configured in the Secretfile providers section."
                )

        generator = generator_class(resolved_config)
        if self.hide_input:
            generator.hide_input = True

        # Allow generators to opt in to prompt_on_empty control
        if hasattr(generator, "prompt_on_empty"):
            generator.prompt_on_empty = self.prompt_on_empty

        # Attach Secretfile-defined instructions so they take precedence over
        # the generator's built-in defaults when prompting or on failure.
        if agent_instructions is not None:
            generator.manual_instructions = agent_instructions

        try:
            return generator.generate_with_fallback(
                env_var_name, field_description=field_description
            )
        except Exception:
            # Display manual retrieval instructions before propagating the error
            # so the user understands how to obtain the value by hand.
            instructions = generator.get_manual_instructions()
            if instructions is not None:
                BaseGenerator._display_manual_instructions(instructions)
            raise

    def _retrieve_from_target(self, secret_name: str, target_config: Any) -> str | None:
        """Retrieve a secret value from a target using the bundle registry.

        Args:
            secret_name: Name of the secret
            target_config: Target configuration

        Returns:
            Secret value if found, None otherwise
        """
        try:
            kind_str = str(target_config.kind)

            # Resolve provider for non-local targets
            provider = None
            if target_config.provider != "local":
                provider = self._get_provider(target_config.provider)
                if provider is None:
                    return None
                if not provider.is_authenticated():
                    if not provider.authenticate():
                        return None

            # Look up target class in bundle registry
            target_class = self._bundle_registry.get_target_class(kind_str)
            if target_class is None:
                return None

            # Local targets receive only config; provider-based targets receive (provider, config)
            if target_config.provider == "local":
                target = target_class(target_config.config)
            else:
                target = target_class(provider, target_config.config)

            return target.retrieve(secret_name)

        except Exception:
            return None

    def _get_local_actor_info(self) -> dict[str, Any]:
        """Return actor information for local (non-provider) operations."""
        import getpass
        import os

        username = None
        full_name = None
        uid: int | None = None

        try:
            username = getpass.getuser()
        except Exception:
            try:
                username = os.getenv("USER") or os.getenv("USERNAME")
            except Exception:
                username = None

        try:
            uid = os.getuid()
            try:
                import pwd  # type: ignore[import]

                pw = pwd.getpwuid(uid)
                gecos = pw.pw_gecos or ""
                full_name = (gecos.split(",")[0] or None) if gecos else None
            except Exception:
                full_name = None
        except Exception:
            uid = None

        return {
            "provider": "local",
            "username": username,
            "uid": uid,
            "full_name": full_name,
        }

    def _store_in_target(
        self, secret_name: str, secret_value: str, target_config: Any
    ) -> dict[str, Any]:
        """Store a secret in a target using the bundle registry.

        Args:
            secret_name: Name of the secret
            secret_value: Value to store
            target_config: Target configuration

        Returns:
            Dictionary with storage result
        """
        result: dict[str, Any] = {
            "provider": target_config.provider,
            "kind": target_config.kind,
            "status": "unknown",
        }

        try:
            kind_str = str(target_config.kind)

            # Look up the target class from the bundle registry
            target_class = self._bundle_registry.get_target_class(kind_str)
            if target_class is None:
                result["status"] = "unsupported"
                result["message"] = (
                    f"Target kind '{kind_str}' is not registered. "
                    f"Available kinds: {', '.join(self._bundle_registry.list_target_kinds())}"
                )
                return result

            # Resolve provider for non-local targets
            provider = None
            actor_info: dict[str, Any] | None = None
            if target_config.provider != "local":
                provider = self._get_provider(target_config.provider)
                if provider is None:
                    result["status"] = "error"
                    result["message"] = f"{target_config.provider} provider not initialized"
                    return result

                # Authenticate if not already authenticated
                if not provider.is_authenticated():
                    if not provider.authenticate():
                        result["status"] = "error"
                        result["message"] = f"{target_config.provider} authentication failed"
                        return result

                try:
                    actor_info = provider.get_actor_info()
                except Exception:
                    actor_info = None
            else:
                # Local targets: use OS user information
                actor_info = self._get_local_actor_info()

            # Instantiate the target
            if target_config.provider == "local":
                target = target_class(target_config.config)
            else:
                target = target_class(provider, target_config.config)

            # File targets: validate before storing
            if kind_str == "file":
                is_valid, error_msg = target.validate()
                if not is_valid:
                    result["status"] = "error"
                    result["message"] = f"File target validation failed: {error_msg}"
                    return result

            # Template targets: collect secrets for deferred rendering
            if kind_str == "template":
                success = target.store(secret_name, secret_value)
                template_id = target_config.config.get("output_path", "unknown")
                if template_id not in self._template_targets:
                    self._template_targets[template_id] = {
                        "target": target,
                        "secrets": {},
                    }
                self._template_targets[template_id]["secrets"][secret_name] = secret_value
                result["status"] = "stored" if success else "failed"
                return result

            # Generic store
            success = target.store(secret_name, secret_value)
            result["status"] = "stored" if success else "failed"

            if actor_info is not None:
                result["actor"] = actor_info

        except ImportError as exc:
            result["status"] = "error"
            result["message"] = f"Missing dependency: {exc}"
        except Exception as exc:
            result["status"] = "error"
            result["message"] = str(exc)

        return result

    def _render_template_targets(self) -> list[str]:
        """Render all collected template targets with their secrets.

        Returns:
            List of error messages from failed renderings
        """
        errors = []

        for template_id, template_info in self._template_targets.items():
            try:
                target = template_info["target"]
                secrets = template_info["secrets"]

                # Render the template with collected secrets
                success = target.render(secrets)

                if not success:
                    errors.append(
                        f"Failed to render template to {target.output_path}: Unknown error"
                    )
            except Exception as e:
                errors.append(f"Failed to render template to {template_id}: {e}")

        # Clear the template targets after rendering
        self._template_targets.clear()

        return errors

    def get_secret_info(self, secret_name: str) -> dict[str, Any] | None:
        """Get information about a specific secret.

        Args:
            secret_name: Name of the secret

        Returns:
            Dictionary with secret information or None if not found
        """
        # Find secret in configuration
        secret = None
        for s in self.secretfile.secrets:
            if s.name == secret_name:
                secret = s
                break

        if not secret:
            return None

        # Get lockfile entry
        lock_entry = self.lockfile.secrets.get(secret_name)

        info = {
            "name": secret.name,
            "kind": secret.kind,
            "one_time": secret.one_time,
            "rotation_period": secret.rotation_period,
            "targets": [{"provider": t.provider, "kind": t.kind} for t in secret.targets],
            "exists_in_lockfile": lock_entry is not None,
        }

        if lock_entry:
            info["created_at"] = lock_entry.created_at
            info["updated_at"] = lock_entry.updated_at
            info["hash"] = lock_entry.hash

        return info
